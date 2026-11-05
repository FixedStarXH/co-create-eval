from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import create_app
from app.models import ArtifactVersion, StudySession
from app.provision import provision
import app.creation_api as creation

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def setup(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'creation.sqlite3').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config(str(ROOT / 'alembic.ini')), 'head')
    app = create_app(url)
    with Session(app.state.engine) as db:
        provision(db, 'P001', 'password-one', 'S1')
        provision(db, 'P002', 'password-two', 'S2')
    clock = [datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr(creation, 'now', lambda: clock[0])
    with TestClient(app) as client:
        auth = client.post('/api/v1/auth/participant-login', json={'study_code':'P001','credential':'password-one'}).json()['data']
        headers = {'x-csrf-token': auth['csrf_token']}
        client.post('/api/v1/participant/consent', headers=headers, json={'consent_version':'demo-1','agreed':True})
        ids = [x['id'] for x in client.get('/api/v1/participant/sessions').json()['data']]
        yield app, client, headers, ids, clock

def test_timed_creation_and_revision_conflict(setup):
    app, client, headers, ids, clock = setup
    first, second = ids
    assert client.post(f'/api/v1/sessions/{second}/start', headers=headers).status_code == 409
    p = client.post(f'/api/v1/sessions/{first}/start', headers=headers).json()['data']
    assert p['state'] == 'IDEATION' and p['idea']['revision'] == 0
    assert client.post(f'/api/v1/sessions/{first}/start', headers=headers).json()['data']['ideation_deadline_at'] == p['ideation_deadline_at']
    data = {'expected_revision': 0, 'values': ['问题', '活动', '评价']}
    assert client.put(f'/api/v1/sessions/{first}/idea-draft', headers=headers, json=data).json()['data']['revision'] == 1
    assert client.put(f'/api/v1/sessions/{first}/idea-draft', headers=headers, json=data).status_code == 409
    assert client.post(f'/api/v1/sessions/{first}/initial', headers=headers, json={'expected_revision':1}).json()['data']['idea_submitted_at']
    assert client.put(f'/api/v1/sessions/{first}/idea-draft', headers=headers, json={**data, 'expected_revision':1}).status_code == 409
    assert client.get(f'/api/v1/sessions/{first}/progress').json()['data']['state'] == 'IDEATION'
    clock[0] += timedelta(seconds=301)
    p = client.get(f'/api/v1/sessions/{first}/progress').json()['data']
    assert p['state'] == 'DEVELOPMENT' and p['draft']['revision'] == 0
    sections = {'goal':'<p>目标<script>alert(1)</script></p>', 'student':'', 'flow':'', 'resource':'', 'assessment':''}
    saved = client.put(f'/api/v1/sessions/{first}/draft', headers=headers, json={'expected_revision':0,'sections':sections})
    assert saved.status_code == 200 and saved.json()['data']['revision'] == 1
    assert client.put(f'/api/v1/sessions/{first}/draft', headers=headers, json={'expected_revision':0,'sections':sections}).status_code == 409
    p = client.get(f'/api/v1/sessions/{first}/progress').json()['data']
    assert 'script' not in p['draft']['sections']['goal'] and 'alert' not in p['draft']['sections']['goal']
    final = client.post(f'/api/v1/sessions/{first}/submit', headers=headers, json={'expected_revision':1})
    assert final.status_code == 200
    assert client.post(f'/api/v1/sessions/{first}/submit', headers=headers, json={'expected_revision':1}).json() == final.json()
    assert client.put(f'/api/v1/sessions/{first}/draft', headers=headers, json={'expected_revision':1,'sections':sections}).status_code == 409
    assert client.get('/api/v1/participant/sessions').json()['data'][1]['task_code'] == 'B'
    with Session(app.state.engine) as db:
        snapshots = db.exec(select(ArtifactVersion).where(ArtifactVersion.session_id == first)).all()
        assert {x.stage for x in snapshots} == {'INITIAL', 'FINAL'} and len(snapshots) == 2
    assert client.post(f'/api/v1/sessions/{second}/start', headers=headers).status_code == 200

def test_expiration_and_cross_participant_access(setup):
    app, client, headers, ids, clock = setup
    first = ids[0]
    client.post(f'/api/v1/sessions/{first}/start', headers=headers)
    clock[0] += timedelta(seconds=301)
    assert client.get(f'/api/v1/sessions/{first}/progress').json()['data']['state'] == 'DEVELOPMENT'
    clock[0] += timedelta(seconds=1231)
    assert client.get(f'/api/v1/sessions/{first}/progress').json()['data']['state'] == 'EXPIRED'
    other = client.post('/api/v1/auth/participant-login', json={'study_code':'P002','credential':'password-two'}).json()['data']
    client.post('/api/v1/participant/consent', headers={'x-csrf-token':other['csrf_token']}, json={'consent_version':'demo-1','agreed':True})
    assert client.get(f'/api/v1/sessions/{first}/progress').status_code == 404
    with Session(app.state.engine) as db:
        assert db.get(StudySession, first).state == 'EXPIRED'

def test_deadline_grace_preserves_last_saved_draft(setup):
    app, client, headers, ids, clock = setup
    first = ids[0]
    client.post(f'/api/v1/sessions/{first}/start', headers=headers)
    clock[0] += timedelta(seconds=301)
    client.get(f'/api/v1/sessions/{first}/progress')
    clock[0] += timedelta(seconds=1200)
    sections = {'goal':'<p>保留的目标</p>', 'student':'', 'flow':'', 'resource':'', 'assessment':''}
    assert client.put(f'/api/v1/sessions/{first}/draft', headers=headers, json={'expected_revision':0,'sections':sections}).status_code == 200
    clock[0] += timedelta(seconds=31)
    assert client.get(f'/api/v1/sessions/{first}/progress').json()['data']['state'] == 'SUBMITTED'
    assert client.put(f'/api/v1/sessions/{first}/draft', headers=headers, json={'expected_revision':1,'sections':sections}).status_code == 409
    with Session(app.state.engine) as db:
        final = db.exec(select(ArtifactVersion).where(ArtifactVersion.session_id == first, ArtifactVersion.stage == 'FINAL')).one()
        assert '保留的目标' in final.content_json
