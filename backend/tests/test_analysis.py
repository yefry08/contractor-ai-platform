import http.server
import socket
import threading

import pytest

from app import analysis


# ---------- _is_safe_public_url (SSRF guard) ----------

@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "file:///etc/passwd",
        "javascript:alert(1)",
    ],
)
def test_rejects_non_http_schemes(url):
    assert analysis._is_safe_public_url(url) is not None


def test_rejects_url_with_no_hostname():
    assert analysis._is_safe_public_url("http:///path") is not None


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://0.0.0.0/",
    ],
)
def test_rejects_private_loopback_and_link_local_addresses(url):
    assert analysis._is_safe_public_url(url) is not None


def test_allows_a_public_looking_address():
    # A literal public IP resolves without a real DNS lookup, so this stays
    # a fast, offline-safe unit test.
    assert analysis._is_safe_public_url("http://8.8.8.8/") is None


def test_unresolvable_domain_is_rejected(monkeypatch):
    def fake_getaddrinfo(*_args, **_kwargs):
        raise socket.gaierror("nope")

    monkeypatch.setattr(analysis.socket, "getaddrinfo", fake_getaddrinfo)
    assert analysis._is_safe_public_url("http://does-not-exist.invalid/") is not None


# ---------- _fetch_validated redirect handling ----------
# _is_safe_public_url is unit-tested above; here it's monkeypatched to treat
# the local test server's loopback URL as "public" so these tests can
# isolate the redirect-loop behavior itself: does it re-run the safety
# check on the *target* of a redirect instead of trusting urllib to follow
# it blindly (the SSRF bypass this function exists to close).

@pytest.fixture
def local_redirect_server():
    class Handler(http.server.BaseHTTPRequestHandler):
        location = None

        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", self.location)
            self.end_headers()

        def log_message(self, *_a):
            pass

    def _start(location: str):
        Handler.location = location
        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return f"http://127.0.0.1:{port}/", server

    servers = []

    def factory(location: str):
        url, server = _start(location)
        servers.append(server)
        return url

    yield factory

    for s in servers:
        s.shutdown()


@pytest.fixture
def allow_loopback_as_public(monkeypatch):
    real_check = analysis._is_safe_public_url

    def patched(url):
        if "127.0.0.1" in url:
            return None
        return real_check(url)

    monkeypatch.setattr(analysis, "_is_safe_public_url", patched)


def test_redirect_to_a_blocked_address_is_not_followed(local_redirect_server, allow_loopback_as_public):
    entry_url = local_redirect_server("http://169.254.169.254/latest/meta-data/")
    result = analysis._fetch_validated(entry_url)
    assert isinstance(result, analysis.ExtractionResult)
    assert "no p" in result.warning.lower()  # "...red no pública"


def test_redirect_to_a_safe_address_is_followed(local_redirect_server, allow_loopback_as_public):
    entry_url = local_redirect_server("https://example.com/")
    result = analysis._fetch_validated(entry_url)
    assert not isinstance(result, analysis.ExtractionResult)
    raw, content_type = result
    assert len(raw) > 0
    assert "html" in content_type.lower()


# ---------- _amount_candidates ----------

def test_amount_candidates_parses_dot_thousands_separator():
    assert 1500000.0 in analysis._amount_candidates("El monto es 1.500.000 PYG")


def test_amount_candidates_parses_comma_decimal():
    candidates = analysis._amount_candidates("Total: 12.345,67 EUR")
    assert 12345.67 in candidates


def test_amount_candidates_ignores_small_numbers():
    # Dates, IDs, and small counts shouldn't be mistaken for a contract amount.
    candidates = analysis._amount_candidates("Expediente 123, año 2024, folio 45")
    assert all(c >= 1000 for c in candidates)


def test_amount_candidates_sorted_largest_first_and_capped():
    text = " ".join(str(n) for n in range(1000, 2000, 50))
    candidates = analysis._amount_candidates(text)
    assert candidates == sorted(candidates, reverse=True)
    assert len(candidates) <= 8
