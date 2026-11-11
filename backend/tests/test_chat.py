from datetime import datetime, timedelta, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import app.chat_api as chat_api
import app.creation_api as creation_api
from app.main import create_app
from app.model_provider import ModelError, ModelResult
from app.models import ChatRequest
from app.provision import provision

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'chat.sqlite3').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("AI_CHAT_ENDPOINT", "https://models.example/v1/chat/completions")
    monkeypatch.setenv("AI_CHAT_MODEL", "test-model")
    monkeypatch.setenv("AI_API_KEY", "test-secret")
    command.upgrade(Config(str(ROOT / 'alembic.ini')), 'head')
    app = create_app(url)
    with Session(app.state.engine) as db:
        provision(db, 'P001', 'password-one', 'S1')
        provision(db, 'P002', 'password-two', 'S2')
    clock = [datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)]
    monkeypatch.setattr(creation_api, 'now', lambda: clock[0])
    monkeypatch.setattr(chat_api, 'now', lambda: clock[0])
    with TestClient(app) as client:
        def login(code, password):
            auth = client.post('/api/v1/auth/participant-login', json={'study_code':code,'credential':password}).json()['data']
            headers = {'x-csrf-token': auth['csrf_token']}
            client.post('/api/v1/participant/consent', headers=headers, json={'consent_version':'demo-1','agreed':True})
            session_id = client.get('/api/v1/participant/sessions').json()['data'][0]['id']
            return headers, session_id
        headers, session_id = login('P001', 'password-one')
        yield app, client, headers, session_id, clock, login


def payload(message='如何安排活动？'):
    return {'client_request_id': str(uuid4()), 'message': message}


def test_chat_permissions_idempotency_and_saved_history(setup, monkeypatch):
    app, client, headers, session_id, clock, login = setup
    url = f'/api/v1/sessions/{session_id}/chat'
    body = payload()
    assert client.post(url, headers=headers, json=body).status_code == 409
    client.post(f'/api/v1/sessions/{session_id}/start', headers=headers)
    assert client.post(url, headers=headers, json=body).status_code == 409
    clock[0] += timedelta(seconds=301)
    calls = []
    def respond(self, messages):
        calls.append(messages)
        return ModelResult('先明确目标。', 'test-model', 'provider-id')
    monkeypatch.setattr(chat_api.CompatibleChatProvider, 'generate_chat', respond)
    assert client.post(url, json=body).status_code == 403
    first = client.post(url, headers=headers, json=body)
    assert first.status_code == 200 and first.json()['data']['status'] == 'SUCCEEDED'
    assert first.json()['data']['reply'] == '先明确目标。'
    assert client.post(url, headers=headers, json=body).json() == first.json()
    assert len(calls) == 1 and calls[0][-1]['content'] == body['message']
    assert client.post(url, headers=headers, json={**body, 'message':'不同内容'}).status_code == 409
    assert client.get(url).json()['data'][0]['reply'] == '先明确目标。'
    with Session(app.state.engine) as db:
        row = db.exec(select(ChatRequest)).one()
        assert row.model == 'test-model' and row.prompt_version == 'chat-1' and row.provider_request_id == 'provider-id'
    other_headers, other_id = login('P002', 'password-two')
    assert client.get(url).status_code == 404
    assert client.post(f'/api/v1/sessions/{other_id}/chat', headers=other_headers, json=payload()).status_code == 403


def test_chat_failure_and_deadline_preserve_records(setup, monkeypatch):
    _app, client, headers, session_id, clock, _login = setup
    client.post(f'/api/v1/sessions/{session_id}/start', headers=headers)
    clock[0] += timedelta(seconds=301)
    def fail(*_):
        raise ModelError('timeout')
    monkeypatch.setattr(chat_api.CompatibleChatProvider, 'generate_chat', fail)
    url = f'/api/v1/sessions/{session_id}/chat'
    body = payload()
    result = client.post(url, headers=headers, json=body).json()['data']
    assert result['status'] == 'FAILED' and result['error_code'] == 'timeout'
    clock[0] += timedelta(seconds=1200)
    assert client.post(url, headers=headers, json=payload()).status_code == 409
    assert client.post(url, headers=headers, json=body).json()['data']['id'] == result['id']
    assert client.get(f'/api/v1/sessions/{session_id}/progress').json()['data']['draft']['revision'] == 0


def test_only_one_model_call_can_be_pending(setup, monkeypatch):
    _app, client, headers, session_id, clock, _login = setup
    client.post(f'/api/v1/sessions/{session_id}/start', headers=headers)
    clock[0] += timedelta(seconds=301)
    entered, release = Event(), Event()
    def slow(_self, _messages):
        entered.set()
        assert release.wait(10)
        return ModelResult('建议', 'test-model', None)
    monkeypatch.setattr(chat_api.CompatibleChatProvider, 'generate_chat', slow)
    url = f'/api/v1/sessions/{session_id}/chat'
    body = payload()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(client.post, url, headers=headers, json=body)
        try:
            assert entered.wait(10)
            assert client.post(url, headers=headers, json=body).json()['data']['status'] == 'PENDING'
            assert client.post(url, headers=headers, json=payload()).status_code == 409
        finally:
            release.set()
        assert future.result(timeout=10).json()['data']['status'] == 'SUCCEEDED'
