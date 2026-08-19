import json

from app import ai


def test_unavailable_without_a_key(monkeypatch):
    monkeypatch.setattr(ai.settings, "bazaarlink_api_key", None)
    assert ai.is_available() is False
    assert ai.generate_narrative("some contract text", "verdict: normal") is None


def test_available_with_a_key(monkeypatch):
    monkeypatch.setattr(ai.settings, "bazaarlink_api_key", "sk-bl-fake-test-key")
    assert ai.is_available() is True


def _fake_response(body: dict):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(body).encode()

    return FakeResponse()


def test_generate_narrative_sets_a_browser_user_agent(monkeypatch):
    # Regression test: api.bazaarlink.ai sits behind Cloudflare, which
    # returns a 403 "error code: 1010" for urllib's default User-Agent --
    # found by testing against the real API, not assumed. Without this
    # header every real request 403s and silently degrades to None.
    monkeypatch.setattr(ai.settings, "bazaarlink_api_key", "sk-bl-fake-test-key")
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["user_agent"] = req.get_header("User-agent")
        return _fake_response({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(ai.urllib.request, "urlopen", fake_urlopen)
    ai.generate_narrative("texto", "verdict: normal")
    assert captured["user_agent"]
    assert "python-urllib" not in captured["user_agent"].lower()


def test_generate_narrative_parses_a_real_shaped_response(monkeypatch):
    monkeypatch.setattr(ai.settings, "bazaarlink_api_key", "sk-bl-fake-test-key")
    monkeypatch.setattr(
        ai.urllib.request,
        "urlopen",
        lambda *a, **k: _fake_response(
            {"choices": [{"message": {"content": " Contrato de servicios de limpieza. "}}]}
        ),
    )
    result = ai.generate_narrative("texto de prueba", "verdict: normal")
    assert result == "Contrato de servicios de limpieza."


def test_generate_narrative_degrades_to_none_on_network_error(monkeypatch):
    import urllib.error

    monkeypatch.setattr(ai.settings, "bazaarlink_api_key", "sk-bl-fake-test-key")

    def raise_error(*a, **k):
        raise urllib.error.URLError("boom")

    monkeypatch.setattr(ai.urllib.request, "urlopen", raise_error)
    assert ai.generate_narrative("texto", "verdict: normal") is None


def test_generate_narrative_degrades_to_none_on_malformed_response(monkeypatch):
    monkeypatch.setattr(ai.settings, "bazaarlink_api_key", "sk-bl-fake-test-key")
    monkeypatch.setattr(ai.urllib.request, "urlopen", lambda *a, **k: _fake_response({"unexpected": "shape"}))
    assert ai.generate_narrative("texto", "verdict: normal") is None


def test_generate_narrative_degrades_to_none_on_empty_content(monkeypatch):
    monkeypatch.setattr(ai.settings, "bazaarlink_api_key", "sk-bl-fake-test-key")
    monkeypatch.setattr(
        ai.urllib.request,
        "urlopen",
        lambda *a, **k: _fake_response({"choices": [{"message": {"content": "   "}}]}),
    )
    assert ai.generate_narrative("texto", "verdict: normal") is None
