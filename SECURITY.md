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

**Rate limiting.** `/analyze/extract`, `/analyze/compare`, and
`POST /contracts/{id}/reports` share a best-effort in-memory limiter keyed
by client IP (`app/main.py::_rate_limited`). It resets on process restart
and depends on `request.client.host`, which a reverse proxy can obscure —
this is a deterrent against casual abuse, not a hard guarantee. Real abuse
resistance at scale would need a shared store (Redis) and proper
`X-Forwarded-For` handling.

**Citizen reports** (`POST /contracts/{id}/reports`) are public and
unauthenticated by design — that's the point of the feature. Two mitigations
against spam: a honeypot field real browsers never fill (a bot that fills it
gets a fake success response, so it doesn't learn to skip the field) and the
same rate limiter described above. Comments are rendered as plain text on
the frontend (React's default escaping, no `dangerouslySetInnerHTML`
anywhere near user content), so this isn't a stored-XSS vector.

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
