from __future__ import annotations

import pytest
from curl_cffi.requests.exceptions import RequestException, Timeout

from src.http import HttpClient, HttpError


class FakeResponse:
    def __init__(self, status: int, data=None, invalid_json: bool = False):
        self.status_code = status
        self._data = data
        self._invalid_json = invalid_json

    def json(self):
        if self._invalid_json:
            raise ValueError("json inválido")
        return self._data


class FakeSession:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []
        self.closed = False

    def get(self, url, **kwargs):
        self.calls.append({"method": "GET", "url": url, **kwargs})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def post(self, url, **kwargs):
        self.calls.append({"method": "POST", "url": url, **kwargs})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def close(self):
        self.closed = True


def _client(session: FakeSession, **kwargs) -> HttpClient:
    return HttpClient(
        "teste",
        session_factory=lambda _impersonate: session,
        min_interval=0,
        **kwargs,
    )


def test_post_json_sends_body():
    session = FakeSession([FakeResponse(200, {"ok": True})])
    client = _client(session)

    result = client.post_json("https://example.test/search", {"query": "leite"})

    assert result == {"ok": True}
    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["json"] == {"query": "leite"}


def test_retries_429_then_succeeds(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("src.http.time.sleep", sleeps.append)
    session = FakeSession([FakeResponse(429), FakeResponse(206, [{"ok": True}])])
    client = _client(session)

    assert client.get_json("https://example.test/search") == [{"ok": True}]
    assert len(session.calls) == 2
    assert sleeps == [0.5]


def test_retries_5xx_with_backoff(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("src.http.time.sleep", sleeps.append)
    session = FakeSession(
        [FakeResponse(503), FakeResponse(502), FakeResponse(200, {"ok": True})]
    )
    client = _client(session)

    assert client.get_json("https://example.test/search") == {"ok": True}
    assert sleeps == [0.5, 1.5]


def test_exhausted_retries_raise_instability(monkeypatch):
    monkeypatch.setattr("src.http.time.sleep", lambda _s: None)
    session = FakeSession([FakeResponse(503), FakeResponse(503), FakeResponse(503)])
    client = _client(session)
    with pytest.raises(HttpError, match="instabilidade"):
        client.get_json("https://example.test/search")


def test_timeout_is_friendly():
    session = FakeSession([Timeout("estourou")])
    client = _client(session)
    with pytest.raises(HttpError, match="tempo esgotado"):
        client.get_json("https://example.test/search")


def test_400_is_unexpected_response():
    session = FakeSession([FakeResponse(400)])
    client = _client(session)
    with pytest.raises(HttpError, match="resposta inesperada"):
        client.get_json("https://example.test/search")


def test_invalid_json_is_unexpected_response():
    session = FakeSession([FakeResponse(200, invalid_json=True)])
    client = _client(session)
    with pytest.raises(HttpError, match="resposta inesperada"):
        client.get_json("https://example.test/search")


def test_spaces_are_percent_encoded_not_plus():
    session = FakeSession([FakeResponse(200, [])])
    client = _client(session)
    client.get_json(
        "https://example.test/api/catalog_system/pub/products/search",
        {"ft": "leite integral", "_from": 0, "_to": 49},
    )
    url = session.calls[0]["url"]
    assert "leite%20integral" in url
    assert "+" not in url


def test_impersonation_falls_back_on_request_error():
    first = FakeSession([RequestException("tls rejeitado")])
    second = FakeSession([FakeResponse(200, [{"ok": True}])])
    sessions = iter([first, second])
    impersonates: list[str] = []

    def factory(profile: str):
        impersonates.append(profile)
        return next(sessions)

    client = HttpClient(
        "teste",
        impersonate="chrome",
        fallbacks=("chrome110",),
        session_factory=factory,
        min_interval=0,
    )

    assert client.get_json("https://example.test/search") == [{"ok": True}]
    assert impersonates == ["chrome", "chrome110"]
    assert first.closed is True


def test_connection_error_is_friendly():
    sessions = iter(
        [
            FakeSession([RequestException("falhou")]),
            FakeSession([RequestException("x")]),
        ]
    )
    client = HttpClient(
        "teste",
        impersonate="chrome",
        fallbacks=("chrome110",),
        session_factory=lambda _profile: next(sessions),
        min_interval=0,
    )
    with pytest.raises(HttpError, match="falha de conexão"):
        client.get_json("https://example.test/search")


def test_close_is_idempotent():
    session = FakeSession([FakeResponse(200, {})])
    client = _client(session)
    client.get_json("https://example.test/search")
    client.close()
    client.close()
    assert session.closed is True
