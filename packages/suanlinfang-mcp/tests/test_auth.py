import pytest
from fastmcp.exceptions import ToolError

import suanlinfang_mcp.auth as auth


def test_key_from_header(monkeypatch):
    monkeypatch.delenv("SUANLINFANG_API_KEY", raising=False)
    monkeypatch.setattr(auth, "get_http_headers", lambda: {"X-SLF-Api-Key": "nk-from-header"})
    assert auth.resolve_api_key() == "nk-from-header"


def test_key_from_bearer_header(monkeypatch):
    monkeypatch.delenv("SUANLINFANG_API_KEY", raising=False)
    monkeypatch.setattr(
        auth, "get_http_headers", lambda: {"Authorization": "Bearer nk-from-bearer"}
    )
    assert auth.resolve_api_key() == "nk-from-bearer"


def test_header_takes_precedence_over_env(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-from-env")
    monkeypatch.setattr(auth, "get_http_headers", lambda: {"X-SLF-Api-Key": "nk-from-header"})
    assert auth.resolve_api_key() == "nk-from-header"


def test_key_from_env_when_no_headers(monkeypatch):
    monkeypatch.setenv("SUANLINFANG_API_KEY", "nk-from-env")
    monkeypatch.setattr(auth, "get_http_headers", lambda: {})
    assert auth.resolve_api_key() == "nk-from-env"


def test_no_key_raises_guidance(monkeypatch):
    monkeypatch.delenv("SUANLINFANG_API_KEY", raising=False)
    monkeypatch.setattr(auth, "get_http_headers", lambda: {})
    with pytest.raises(ToolError) as exc_info:
        auth.resolve_api_key()
    assert "api-keys.html" in str(exc_info.value)
    assert "SUANLINFANG_API_KEY" in str(exc_info.value)
