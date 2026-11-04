"""Server-timed creation stages, optimistic drafts and immutable snapshots."""
import html
import json
from datetime import timedelta

import nh3
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import exists, select as sa_select, update
from sqlmodel import Session, select

from app.models import ArtifactDraft, ArtifactVersion, IdeaDraft, StudySession, TaskVersion
from app.participant_api import csrf, current, now, session_db

router = APIRouter(prefix="/api/v1/sessions")
KEYS = {"goal", "student", "flow", "resource", "assessment"}
GRACE_SECONDS = 30

def owned(db, identity, session_id):
    participant, _ = identity
    if not participant.consented_at:
        raise HTTPException(403, "请先确认参与说明")
    item = db.get(StudySession, session_id)
    if not item or item.participant_id != participant.id:
        raise HTTPException(404, "未找到任务")
    return item

def iso(value):
    return value.isoformat().replace("+00:00", "Z") if value else None

def has_content(raw):
    data = json.loads(raw)
    return any(html.unescape(nh3.clean(value, tags=set())).strip() for value in data.values())

def advance(db, item):
    current_time = now()
    if item.state == "IDEATION" and item.ideation_deadline_at and current_time >= item.ideation_deadline_at:
        task = db.get(TaskVersion, item.task_version_id)
        start = item.ideation_deadline_at
        claim = db.execute(update(StudySession).where(StudySession.id == item.id, StudySession.state == "IDEATION").values(state="DEVELOPMENT", development_started_at=start, development_deadline_at=start + timedelta(seconds=task.development_seconds)))
        if claim.rowcount:
            idea = db.get(IdeaDraft, item.id)
            if not db.exec(select(ArtifactVersion).where(ArtifactVersion.session_id == item.id, ArtifactVersion.stage == "INITIAL")).first():
                db.add(ArtifactVersion(session_id=item.id, stage="INITIAL", revision_no=idea.revision_no, content_json=idea.content_json, created_at=current_time))
            db.add(ArtifactDraft(session_id=item.id))
            db.commit()
        else:
            db.rollback()
        db.refresh(item)
    if item.state == "DEVELOPMENT" and item.development_deadline_at and current_time >= item.development_deadline_at + timedelta(seconds=GRACE_SECONDS):
        claim = db.execute(update(StudySession).where(StudySession.id == item.id, StudySession.state == "DEVELOPMENT").values(state="FINALIZING"))
        if claim.rowcount:
            draft = db.get(ArtifactDraft, item.id)
            if draft:
                db.refresh(draft)
            state = "SUBMITTED" if draft and has_content(draft.content_json) else "EXPIRED"
            db.execute(update(StudySession).where(StudySession.id == item.id).values(state=state, submitted_at=current_time if state == "SUBMITTED" else None))
            if state == "SUBMITTED":
                db.add(ArtifactVersion(session_id=item.id, stage="FINAL", revision_no=draft.revision_no, content_json=draft.content_json, created_at=current_time))
            db.commit()
        else:
            db.rollback()
        db.refresh(item)
    return item

def describe(db, item):
    item = advance(db, item)
    idea, draft = db.get(IdeaDraft, item.id), db.get(ArtifactDraft, item.id)
    return {"id": item.id, "state": item.state, "server_time": iso(now()), "ideation_deadline_at": iso(item.ideation_deadline_at), "idea_submitted_at": iso(item.idea_submitted_at), "development_deadline_at": iso(item.development_deadline_at), "idea": {"values": json.loads(idea.content_json), "revision": idea.revision_no, "saved_at": iso(idea.saved_at)} if idea else None, "draft": {"sections": json.loads(draft.content_json), "revision": draft.revision_no, "saved_at": iso(draft.saved_at)} if draft else None}

class IdeaPayload(BaseModel):
    expected_revision: int = Field(ge=0)
    values: list[str] = Field(min_length=3, max_length=3)
    @field_validator("values")
    @classmethod
    def limit_values(cls, values):
        if any(len(value) > 5000 for value in values):
            raise ValueError("每项构思不能超过 5000 字")
        return values

class DraftPayload(BaseModel):
    expected_revision: int = Field(ge=0)
    sections: dict[str, str]
    @field_validator("sections")
    @classmethod
    def validate_sections(cls, value):
        if set(value) != KEYS or any(len(text) > 20000 for text in value.values()):
            raise ValueError("作品必须包含五个有效章节")
        return {key: nh3.clean(text, tags={"p", "br", "strong", "b", "em", "i", "u", "h3", "ul", "ol", "li", "a"}, attributes={"a": {"href"}}, url_schemes={"https"}, clean_content_tags={"script", "style"}, link_rel="noopener noreferrer") for key, text in value.items()}

class Revision(BaseModel):
    expected_revision: int = Field(ge=0)

@router.get("/{session_id}/progress")
def progress(session_id: str, identity=Depends(current), db: Session = Depends(session_db)):
    return {"data": describe(db, owned(db, identity, session_id))}

@router.post("/{session_id}/start")
def start(session_id: str, identity=Depends(csrf), db: Session = Depends(session_db)):
    item = owned(db, identity, session_id)
    if item.state == "CREATED":
        if item.round_no == 2:
            previous = db.exec(select(StudySession).where(StudySession.participant_id == item.participant_id, StudySession.round_no == 1)).first()
            if not previous or previous.state not in ("SUBMITTED", "RATED"):
                raise HTTPException(409, "请先完成第一场任务")
        task = db.get(TaskVersion, item.task_version_id)
        timestamp = now()
        claim = db.execute(update(StudySession).where(StudySession.id == item.id, StudySession.state == "CREATED").values(state="IDEATION", ideation_started_at=timestamp, ideation_deadline_at=timestamp + timedelta(seconds=task.ideation_seconds)))
        if claim.rowcount:
            db.add(IdeaDraft(session_id=item.id))
            db.commit()
        else:
            db.rollback()
        db.refresh(item)
    return {"data": describe(db, item)}

@router.put("/{session_id}/idea-draft")
def save_idea(session_id: str, payload: IdeaPayload, identity=Depends(csrf), db: Session = Depends(session_db)):
    item = advance(db, owned(db, identity, session_id))
    timestamp = now()
    allowed = sa_select(StudySession.id).where(StudySession.id == item.id, StudySession.state == "IDEATION", StudySession.idea_submitted_at.is_(None), StudySession.ideation_deadline_at > timestamp).exists()
    result = db.execute(update(IdeaDraft).where(IdeaDraft.session_id == item.id, IdeaDraft.revision_no == payload.expected_revision, allowed).values(content_json=json.dumps(payload.values, ensure_ascii=False), revision_no=payload.expected_revision + 1, saved_at=timestamp))
    if not result.rowcount:
        db.rollback()
        raise HTTPException(409, "保存冲突或构思阶段已结束，请刷新后核对本地内容")
    db.commit()
    return {"data": {"revision": payload.expected_revision + 1, "saved_at": iso(timestamp)}}

@router.post("/{session_id}/initial")
def submit_initial(session_id: str, payload: Revision, identity=Depends(csrf), db: Session = Depends(session_db)):
    item = advance(db, owned(db, identity, session_id))
    if item.idea_submitted_at:
        return {"data": describe(db, item)}
    draft = db.get(IdeaDraft, item.id)
    if not draft or draft.revision_no != payload.expected_revision or not any(x.strip() for x in json.loads(draft.content_json)):
        raise HTTPException(409, "请保存至少一项构思，并确认修订版本")
    valid_revision = sa_select(IdeaDraft.session_id).where(IdeaDraft.session_id == item.id, IdeaDraft.revision_no == payload.expected_revision).exists()
    timestamp = now()
    claim = db.execute(update(StudySession).where(StudySession.id == item.id, StudySession.state == "IDEATION", StudySession.idea_submitted_at.is_(None), StudySession.ideation_deadline_at > timestamp, valid_revision).values(idea_submitted_at=timestamp))
    if not claim.rowcount:
        db.rollback()
        db.refresh(item)
        if item.idea_submitted_at:
            return {"data": describe(db, item)}
        raise HTTPException(409, "构思阶段已结束或版本已变化")
    db.add(ArtifactVersion(session_id=item.id, stage="INITIAL", revision_no=draft.revision_no, content_json=draft.content_json, created_at=timestamp))
    db.commit()
    db.refresh(item)
    return {"data": describe(db, item)}

@router.put("/{session_id}/draft")
def save_draft(session_id: str, payload: DraftPayload, identity=Depends(csrf), db: Session = Depends(session_db)):
    item = advance(db, owned(db, identity, session_id))
    timestamp = now()
    allowed = sa_select(StudySession.id).where(StudySession.id == item.id, StudySession.state == "DEVELOPMENT", StudySession.development_deadline_at > timestamp - timedelta(seconds=GRACE_SECONDS)).exists()
    result = db.execute(update(ArtifactDraft).where(ArtifactDraft.session_id == item.id, ArtifactDraft.revision_no == payload.expected_revision, allowed).values(content_json=json.dumps(payload.sections, ensure_ascii=False), revision_no=payload.expected_revision + 1, saved_at=timestamp))
    if not result.rowcount:
        db.rollback()
        raise HTTPException(409, "保存冲突或创作阶段已结束，请保留本地内容并核对")
    db.commit()
    return {"data": {"revision": payload.expected_revision + 1, "saved_at": iso(timestamp)}}

@router.post("/{session_id}/submit")
def submit(session_id: str, payload: Revision, identity=Depends(csrf), db: Session = Depends(session_db)):
    item = advance(db, owned(db, identity, session_id))
    if item.state == "SUBMITTED":
        final = db.exec(select(ArtifactVersion).where(ArtifactVersion.session_id == item.id, ArtifactVersion.stage == "FINAL")).one()
        return {"data": {"id": final.id, "submitted_at": iso(item.submitted_at)}}
    draft = db.get(ArtifactDraft, item.id)
    if item.state != "DEVELOPMENT" or not draft or draft.revision_no != payload.expected_revision or not has_content(draft.content_json):
        raise HTTPException(409, "请先保存有效作品，并确认阶段与修订版本")
    timestamp = now()
    valid_revision = sa_select(ArtifactDraft.session_id).where(ArtifactDraft.session_id == item.id, ArtifactDraft.revision_no == payload.expected_revision).exists()
    claim = db.execute(update(StudySession).where(StudySession.id == item.id, StudySession.state == "DEVELOPMENT", valid_revision).values(state="SUBMITTED", submitted_at=timestamp))
    if not claim.rowcount:
        db.rollback()
        raise HTTPException(409, "作品版本已变化，请核对后重试")
    final = ArtifactVersion(session_id=item.id, stage="FINAL", revision_no=draft.revision_no, content_json=draft.content_json, created_at=timestamp)
    db.add(final)
    db.commit()
    return {"data": {"id": final.id, "submitted_at": iso(timestamp)}}
