import json
from urllib.error import HTTPError, URLError

import pytest

from app.model_provider import CompatibleChatProvider, ModelConfig, ModelError


def test_provider_sends_chat_and_extracts_response():
    config = ModelConfig("https://models.example/v1/chat/completions", "test-model", "secret-key")
    messages = [{"role": "system", "content": "Offer helpful ideas"}, {"role": "user", "content": "你好"}]

    def send(request, timeout):
        assert request.get_header("Authorization") == "Bearer secret-key"
        assert json.loads(request.data) == {"model": "test-model", "messages": messages, "stream": False}
        assert timeout == 30
        return json.dumps({"choices": [{"message": {"content": "建议"}}]}).encode(), "req-1"

    result = CompatibleChatProvider(config, send).generate_chat(messages)
    assert (result.text, result.model, result.provider_request_id) == ("建议", "test-model", "req-1")
    assert "secret-key" not in repr(config)


@pytest.mark.parametrize(("failure", "code"), [
    (HTTPError("https://example.com", 429, "limited", {}, None), "rate_limited"),
    (HTTPError("https://example.com", 401, "secret", {}, None), "authentication_failed"),
    (HTTPError("https://example.com", 500, "failed", {}, None), "provider_unavailable"),
    (URLError(TimeoutError()), "timeout"),
    (URLError("unreachable"), "provider_unavailable"),
])
def test_provider_errors_are_classified_without_leaking_details(failure, code):
    def fail(_request, _timeout):
        raise failure
    provider = CompatibleChatProvider(ModelConfig("https://example.com", "model", "secret"), fail)
    with pytest.raises(ModelError) as error:
        provider.generate_chat([{"role": "user", "content": "test"}])
    assert str(error.value) == code


@pytest.mark.parametrize("body,code", [
    (b"not-json", "invalid_response"),
    (b'{"choices": []}', "invalid_response"),
    (b'{"choices": [{"message": {"content": ""}}]}', "invalid_response"),
    (b'{"choices": [{"message": {"refusal": "no"}}]}', "refused"),
])
def test_provider_rejects_invalid_response(body, code):
    provider = CompatibleChatProvider(ModelConfig("https://example.com", "model", "secret"), lambda *_: (body, None))
    with pytest.raises(ModelError, match=code):
        provider.generate_chat([{"role": "user", "content": "test"}])


def test_environment_requires_secure_complete_configuration(monkeypatch):
    monkeypatch.setenv("AI_CHAT_ENDPOINT", "http://example.com/v1/chat/completions")
    monkeypatch.setenv("AI_CHAT_MODEL", "model")
    monkeypatch.setenv("AI_API_KEY", "secret")
    with pytest.raises(ModelError, match="invalid_configuration"):
        ModelConfig.from_environment()
    monkeypatch.setenv("AI_CHAT_ENDPOINT", "https://example.com/v1/chat/completions")
    assert ModelConfig.from_environment().model == "model"
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "nan")
    with pytest.raises(ModelError, match="invalid_configuration"):
        ModelConfig.from_environment()
