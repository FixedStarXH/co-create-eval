"""Server-side text model adapter; not yet exposed as a participant endpoint."""

from dataclasses import dataclass, field
import json
import os
import socket
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ModelError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ModelConfig:
    endpoint: str
    model: str
    api_key: str = field(repr=False)
    timeout_seconds: float = 30

    @classmethod
    def from_environment(cls) -> "ModelConfig":
        endpoint = os.getenv("AI_CHAT_ENDPOINT", "").strip()
        model = os.getenv("AI_CHAT_MODEL", "").strip()
        key = os.getenv("AI_API_KEY", "").strip()
        try:
            timeout = float(os.getenv("AI_TIMEOUT_SECONDS", "30"))
        except ValueError:
            raise ModelError("invalid_configuration") from None
        try:
            url = urlsplit(endpoint)
        except ValueError:
            raise ModelError("invalid_configuration") from None
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.fragment or not model or not key or not 1 <= timeout <= 120):
            raise ModelError("invalid_configuration")
        return cls(endpoint, model, key, timeout)


@dataclass(frozen=True)
class ModelResult:
    text: str
    model: str
    provider_request_id: str | None


class ModelProvider(Protocol):
    def generate_chat(self, messages: list[dict[str, str]]) -> ModelResult: ...


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _send(request: Request, timeout: float) -> tuple[bytes, str | None]:
    with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
        body = response.read(1_000_001)
        if len(body) > 1_000_000:
            raise ModelError("invalid_response")
        return body, response.headers.get("x-request-id")


class CompatibleChatProvider:
    """Adapter for providers supporting the chat-completions message format."""

    def __init__(self, config: ModelConfig, send: Callable = _send):
        self._config = config
        self._send = send

    def generate_chat(self, messages: list[dict[str, str]]) -> ModelResult:
        if not messages or any(set(m) != {"role", "content"} or m["role"] not in {"system", "user", "assistant"}
                               or not isinstance(m["content"], str) or not m["content"].strip() for m in messages):
            raise ValueError("invalid messages")
        payload = json.dumps({"model": self._config.model, "messages": messages, "stream": False}, ensure_ascii=False).encode("utf-8")
        request = Request(self._config.endpoint, data=payload, method="POST", headers={
            "Authorization": f"Bearer {self._config.api_key}", "Content-Type": "application/json",
        })
        try:
            body, request_id = self._send(request, self._config.timeout_seconds)
        except HTTPError as exc:
            code = "rate_limited" if exc.code == 429 else "authentication_failed" if exc.code in (401, 403) else "provider_unavailable"
            raise ModelError(code) from None
        except (TimeoutError, socket.timeout):
            raise ModelError("timeout") from None
        except URLError as exc:
            raise ModelError("timeout" if isinstance(exc.reason, (TimeoutError, socket.timeout)) else "provider_unavailable") from None
        except OSError:
            raise ModelError("provider_unavailable") from None
        try:
            data = json.loads(body)
            message = data["choices"][0]["message"]
            if message.get("refusal"):
                raise ModelError("refused")
            text = message["content"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError("empty response")
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            raise ModelError("invalid_response") from None
        return ModelResult(text=text, model=self._config.model, provider_request_id=request_id)
