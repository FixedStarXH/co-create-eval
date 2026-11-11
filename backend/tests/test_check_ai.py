from app import check_ai
from app.model_provider import ModelConfig, ModelError, ModelResult


def test_live_check_requires_explicit_flag(monkeypatch, capsys):
    def forbidden():
        raise AssertionError("must not load configuration or send a request")
    monkeypatch.setattr(check_ai.ModelConfig, "from_environment", forbidden)
    assert check_ai.main([]) == 0
    assert "未发送请求" in capsys.readouterr().out


def test_live_check_caps_output_and_hides_reply(monkeypatch, capsys):
    monkeypatch.setattr(check_ai.ModelConfig, "from_environment", lambda: ModelConfig("https://example.com", "model", "secret", max_output_tokens=1024))
    def fake(self, messages):
        assert self._config.max_output_tokens == 128
        assert messages == [{"role": "user", "content": "请简短回复：连接正常。"}]
        return ModelResult("private reply", "model", None)
    monkeypatch.setattr(check_ai.CompatibleChatProvider, "generate_chat", fake)
    assert check_ai.main(["--run"]) == 0
    output = capsys.readouterr().out
    assert "成功" in output and "secret" not in output and "private reply" not in output


def test_live_check_reports_safe_error(monkeypatch, capsys):
    def fail():
        raise ModelError("invalid_configuration")
    monkeypatch.setattr(check_ai.ModelConfig, "from_environment", fail)
    assert check_ai.main(["--run"]) == 1
    assert "invalid_configuration" in capsys.readouterr().out
