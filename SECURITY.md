# Security

Contractor AI is a fully public, read-mostly civic-tech tool: no user
accounts, no authentication, no private data. The threat model is narrower
than a typical SaaS product as a result, but the two write paths (contract
analysis and citizen reports) still take arbitrary input from anyone on the
internet, so they get the most scrutiny below.

## Reporting a vulnerability

Open a GitHub issue, or email the maintainers directly if the finding is
sensitive enough that you'd rather not post it publicly first. There's no
bug bounty — this is a volunteer civic-tech project — but real reports are
taken seriously and credited.

## What's protected, and how

**SSRF guard on link extraction** (`POST /analyze/extract` with
`method=link`). A visitor can submit any URL; the server fetches it
server-side to pull contract text. `app/analysis.py::_is_safe_public_url`
blocks non-http(s) schemes and anything resolving to a private, loopback,
link-local, reserved, or multicast address. Redirects are re-validated at
every hop (`_fetch_validated`) rather than followed blindly — a URL that
passes the initial check can't 302 its way to an internal address or a
cloud metadata endpoint (`169.254.169.254`) and still get fetched.

*Known residual gap, disclosed rather than silently ignored*: the safety
check and the actual outbound connection each resolve DNS separately,
milliseconds apart. A DNS server that answers differently between those two
lookups (DNS rebinding) could still slip a private IP past the check.
Closing that fully means bypassing urllib's own connection handling to bind
directly to the address already validated — a meaningfully bigger rewrite
than this best-effort text-extraction feature currently warrants. Flagged
here, and in the code, so it isn't forgotten.

**Rate limiting.** `/analyze/*`, `POST /contracts/{id}/reports`,
`POST /inquiries`, the inquiry lookup and the admin endpoints share an
in-memory limiter keyed by the real client IP (`app/security.py`): Cloudflare's
`CF-Connecting-IP` when it fronts the site, otherwise the last hop of
`X-Forwarded-For` that Render appends -- never the client-supplied leftmost
entries, and never `request.client.host`, which behind Render is the proxy
itself (every visitor used to share one bucket). It resets on restart and
isn't shared between instances; a Cloudflare WAF rate-limiting rule is the
layer that stops a real flood (docs/security/cloudflare.md).

**Bot checks on forms.** Citizen reports and inquiries carry a honeypot field
real browsers never fill (a bot that fills it gets a fake success, so it
doesn't learn to skip it) and, when `TURNSTILE_SECRET_KEY` is set, a
Cloudflare Turnstile token verified server-side; verification fails closed if
Cloudflare can't be reached. User text is rendered as plain text (React's
escaping, no `dangerouslySetInnerHTML` near user content), so it isn't a
stored-XSS vector.

**Inquiries are private.** `POST /inquiries` stores no IP address or
fingerprint, the e-mail is optional, and the text is never returned by any
public endpoint: the tracking lookup shows only kind, status and the team's
answer. Codes are 8 characters from a 31-symbol alphabet and the lookup is
rate-limited, so walking the code space isn't practical. The admin endpoints
answer 404 unless `ADMIN_TOKEN` is set and matched (constant-time compare).

**Headers and crawlers.** The API sends `nosniff`, `X-Frame-Options: DENY`,
HSTS and a `default-src 'none'` policy. The frontend sends HSTS, a content
security policy that only allows scripts from itself, Cloudflare Turnstile and
Spline, `frame-ancestors 'none'`, and a restrictive Permissions-Policy.
Self-identified AI crawlers and scraping libraries get a 403
(`frontend/middleware.ts`) and are disallowed in robots.txt; bots that lie
about their user agent need Cloudflare's Bot Fight Mode.

**Upload limits.** PDF uploads are capped at 15 MB
(`main.py::MAX_UPLOAD_BYTES`); link fetches are capped at 3 MB
(`analysis.py::MAX_FETCH_BYTES`) with a 10-second timeout, so a slow or
oversized response can't tie up a worker indefinitely.

**No secrets in the repo.** `backend/.env` (which holds the production
database URL) is gitignored and has never been committed — verified via
`git log --all --full-history` before writing this document, not assumed.
`backend/.dockerignore` excludes `.env` and `*.db` from the built image.

**Dependencies are pinned.** `backend/requirements.txt` lists exact versions
rather than bare package names, so a build today and a build in six months
install the same code instead of silently picking up whatever shipped in
between.

**SQL injection.** Every database query goes through SQLAlchemy's
query-builder (Core `select()` / ORM), which parameterizes values —
there's no raw string interpolation into SQL anywhere in the codebase.

**CORS.** Restricted to the deployed frontend's Vercel project (by regex,
covering preview deployments) plus `localhost`/`127.0.0.1` on any port for
local development. No credentials are used, so there's no cookie/session
exposure risk even with a permissive `allow_headers`.

## Explicitly out of scope for this document

- Anything about the OCDS/CSV data ingestion pipelines (`backend/scripts/`)
  — those run offline, by a maintainer, against trusted government sources.
- Frontend build tooling and its transitive npm dependencies — not audited
  here; run `npm audit` in `frontend/` for that.
