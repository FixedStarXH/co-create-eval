"""Participant authentication, consent and assigned task summaries."""
import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlmodel import Session, select

from app.models import AuthSession, Participant, StudySession, TaskVersion
from app.security import hash_credential, token_digest, verify_credential

router = APIRouter(prefix="/api/v1")
CONSENT_VERSION = "demo-1"
DUMMY_HASH = hash_credential("invalid-credential-placeholder")
attempts: dict[str, deque[float]] = defaultdict(deque)

def now():
    return datetime.now(timezone.utc)

def session_db(request: Request):
    with Session(request.app.state.engine) as db:
        yield db

def check_origin(request: Request):
    origin = request.headers.get("origin")
    allowed = set(os.getenv("FRONTEND_ORIGINS", "http://127.0.0.1:4173,http://localhost:4173").split(","))
    allowed.add(str(request.base_url).rstrip("/"))
    if origin and origin not in allowed:
        raise HTTPException(403, "来源不允许")

def current(request: Request, db: Session = Depends(session_db)):
    token = request.cookies.get("session", "")
    if not token or len(token) > 256:
        raise HTTPException(401, "请先登录")
    auth = db.exec(select(AuthSession).where(AuthSession.token_hash == token_digest(token))).first()
    if not auth or auth.expires_at <= now():
        raise HTTPException(401, "登录已过期，请重新登录")
    participant = db.get(Participant, auth.participant_id)
    if not participant:
        raise HTTPException(401, "请先登录")
    return participant, auth

def csrf(request: Request, identity = Depends(current)):
    check_origin(request)
    header, cookie = request.headers.get("x-csrf-token", ""), request.cookies.get("csrf", "")
    if not header or len(header) > 256 or not hmac.compare_digest(header, cookie) or not hmac.compare_digest(token_digest(header), identity[1].csrf_hash):
        raise HTTPException(403, "请求验证失败")
    return identity

class Login(BaseModel):
    study_code: str = Field(min_length=1, max_length=32)
    credential: str = Field(min_length=1, max_length=128)

class Consent(BaseModel):
    consent_version: str = Field(max_length=32)
    agreed: bool

@router.post("/auth/participant-login")
def login(payload: Login, request: Request, response: Response, db: Session = Depends(session_db)):
    check_origin(request)
    ip = request.client.host if request.client else "unknown"
    timestamp = time.monotonic()
    bucket = attempts[ip]
    while bucket and timestamp - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= 10:
        raise HTTPException(429, "尝试次数过多，请稍后再试")
    bucket.append(timestamp)
    participant = db.exec(select(Participant).where(Participant.study_code == payload.study_code.strip().upper())).first()
    valid = verify_credential(payload.credential, participant.credential_hash if participant else DUMMY_HASH)
    if not participant or not valid:
        raise HTTPException(401, "编号或访问凭证不正确")
    bucket.clear()
    token, csrf_token = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(AuthSession(participant_id=participant.id, token_hash=token_digest(token), csrf_hash=token_digest(csrf_token), expires_at=now() + timedelta(hours=12)))
    db.commit()
    secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie("session", token, httponly=True, secure=secure, samesite="lax", max_age=43200, path="/")
    response.set_cookie("csrf", csrf_token, httponly=False, secure=secure, samesite="lax", max_age=43200, path="/")
    return {"data": {"study_code": participant.study_code, "consented": participant.consented_at is not None, "csrf_token": csrf_token}}

@router.get("/auth/me")
def me(request: Request, identity = Depends(current)):
    participant, auth = identity
    token = request.cookies.get("csrf", "")
    if not token or not hmac.compare_digest(token_digest(token), auth.csrf_hash):
        raise HTTPException(401, "登录状态不完整，请重新登录")
    return {"data": {"study_code": participant.study_code, "consented": participant.consented_at is not None, "csrf_token": token}}

@router.post("/participant/consent")
def consent(payload: Consent, identity = Depends(csrf), db: Session = Depends(session_db)):
    participant, _ = identity
    if not payload.agreed or payload.consent_version != CONSENT_VERSION:
        raise HTTPException(400, "请确认当前版本的参与说明")
    db.execute(update(Participant).where(Participant.id == participant.id, Participant.consented_at.is_(None)).values(consented_at=now(), consent_version=CONSENT_VERSION))
    db.commit()
    participant = db.get(Participant, participant.id)
    db.refresh(participant)
    return {"data": {"consent_version": participant.consent_version, "consented_at": participant.consented_at.isoformat().replace("+00:00", "Z")}}

@router.get("/participant/sessions")
def sessions(identity = Depends(current), db: Session = Depends(session_db)):
    participant, _ = identity
    if not participant.consented_at:
        raise HTTPException(403, "请先确认参与说明")
    rows = db.exec(select(StudySession).where(StudySession.participant_id == participant.id).order_by(StudySession.round_no)).all()
    first_complete = any(row.round_no == 1 and row.state in ("SUBMITTED", "RATED") for row in rows)
    result = []
    for row in rows:
        item = {"id": row.id, "round_no": row.round_no, "state": row.state}
        if row.round_no == 1 or first_complete:
            task = db.get(TaskVersion, row.task_version_id)
            item.update({"task_code": task.task_code, "task_title": task.title, "condition": row.condition})
        result.append(item)
    return {"data": result}

@router.post("/auth/logout")
def logout(response: Response, identity = Depends(csrf), db: Session = Depends(session_db)):
    auth = db.get(AuthSession, identity[1].id)
    if auth:
        db.delete(auth)
        db.commit()
    response.delete_cookie("session", path="/")
    response.delete_cookie("csrf", path="/")
    return {"data": {"logged_out": True}}
