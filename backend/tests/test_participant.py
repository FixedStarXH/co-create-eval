from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import create_app
from app.models import AuthSession, Participant, StudySession, TaskVersion
from app.provision import SEQUENCES, provision

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def service(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'participants.sqlite3').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    app = create_app(url)
    with Session(app.state.engine) as db:
        for i, sequence in enumerate(SEQUENCES, 1):
            provision(db, f"P{i:03}", "test-credential", sequence)
    with TestClient(app) as client:
        yield app, client

def login(client, code="P001", credential="test-credential"):
    return client.post("/api/v1/auth/participant-login", json={"study_code": code, "credential": credential})

def test_all_sequences_are_persisted_and_balanced(service):
    app, _ = service
    with Session(app.state.engine) as db:
        people = db.exec(select(Participant).order_by(Participant.study_code)).all()
        for participant in people:
            assert "test-credential" not in participant.credential_hash
            sessions = db.exec(select(StudySession).where(StudySession.participant_id == participant.id).order_by(StudySession.round_no)).all()
            actual = [(db.get(TaskVersion, s.task_version_id).task_code, s.condition) for s in sessions]
            assert actual == list(SEQUENCES[participant.sequence])

def test_login_consent_csrf_restore_and_isolation(service):
    app, client = service
    assert client.get('/api/v1/participant/sessions').status_code == 401
    assert login(client, credential='wrong').status_code == 401
    response = login(client)
    assert response.status_code == 200 and not response.json()['data']['consented']
    assert 'HttpOnly' in response.headers.get_list('set-cookie')[0]
    token = response.json()['data']['csrf_token']
    assert client.get('/api/v1/participant/sessions').status_code == 403
    assert client.post('/api/v1/participant/consent', json={'consent_version':'demo-1','agreed':True}).status_code == 403
    headers = {'x-csrf-token': token}
    assert client.post('/api/v1/participant/consent', headers=headers, json={'consent_version':'demo-1','agreed':False}).status_code == 400
    first = client.post('/api/v1/participant/consent', headers=headers, json={'consent_version':'demo-1','agreed':True})
    second = client.post('/api/v1/participant/consent', headers=headers, json={'consent_version':'demo-1','agreed':True})
    assert first.json() == second.json()
    assert client.get('/api/v1/auth/me').json()['data']['consented']
    result = client.get('/api/v1/participant/sessions').json()['data']
    assert len(result) == 2 and result[0]['task_code'] == 'A' and 'task_code' not in result[1]
    first_ids = {item['id'] for item in result}
    assert client.post('/api/v1/auth/logout', headers=headers).status_code == 200
    assert client.get('/api/v1/auth/me').status_code == 401
    assert login(client).json()['data']['consented']
    assert {item['id'] for item in client.get('/api/v1/participant/sessions').json()['data']} == first_ids
    assert login(client, code='P002').status_code == 200
    token2 = client.get('/api/v1/auth/me').json()['data']['csrf_token']
    client.post('/api/v1/participant/consent', headers={'x-csrf-token':token2}, json={'consent_version':'demo-1','agreed':True})
    assert not first_ids.intersection(item['id'] for item in client.get('/api/v1/participant/sessions').json()['data'])
    with Session(app.state.engine) as db:
        assert db.exec(select(AuthSession)).first().token_hash != token

def test_cross_origin_and_duplicate_code_are_rejected(service):
    app, client = service
    assert client.post('/api/v1/auth/participant-login', headers={'origin':'https://untrusted.example'}, json={'study_code':'P001','credential':'test-credential'}).status_code == 403
    with Session(app.state.engine) as db:
        with pytest.raises(ValueError):
            provision(db, 'P001', 'test-credential', 'S1')
