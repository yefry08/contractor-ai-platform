# Cloudflare: putting Contractor AI behind the shield

The code already does what it can by itself: security headers and a content
policy on every page, AI crawlers turned away (`frontend/middleware.ts`,
`app/robots.ts`), a honeypot and per-IP rate limits on every form, and the
real client IP read correctly behind proxies (`backend/app/security.py`).

What only Cloudflare can do -- stop bots that lie about who they are, absorb
floods, and challenge suspicious traffic before it reaches Vercel or Render --
needs a Cloudflare account and a domain of your own. These steps need the
account owner; nothing here can be done from the repo.

## 1. Turnstile on the forms (free, works today on vercel.app)

Turnstile is Cloudflare's privacy-friendly CAPTCHA replacement: most people
never see a puzzle. It protects *Consultas y reclamos* and the citizen
reports on each contract.

1. Cloudflare dashboard -> **Turnstile** -> **Add widget**.
2. Hostnames: `contractor-ai-one.vercel.app` (and your own domain later).
   Mode: **Managed**.
3. Copy the two keys and set them:
   - **Vercel** (project `contractor-ai` -> Settings -> Environment Variables,
     Production): `NEXT_PUBLIC_TURNSTILE_SITE_KEY` = the *site key*. Redeploy.
   - **Render** (`contractor-ai-api` -> Environment):
     `TURNSTILE_SECRET_KEY` = the *secret key*.
4. Check: the form shows the Turnstile box, and a POST to `/inquiries`
   without a token answers 403.

Until both are set, forms keep working with the honeypot and rate limits
only. Set the Vercel key and the Render secret together: with only the
secret, the API rejects every submission.

For local testing Cloudflare publishes test keys that always pass: site key
`1x00000000000000000000AA`, secret `1x0000000000000000000000000000000AA`.

## 2. Your own domain behind Cloudflare (WAF, bot protection, DDoS)

A `*.vercel.app` address can't be proxied by your Cloudflare account. With a
domain (e.g. `contractor-ai.org`):

1. Add the domain to Cloudflare (Free plan is enough) and switch its
   nameservers at the registrar.
2. DNS: `CNAME @ -> cname.vercel-dns.com` and `CNAME api -> contractor-ai-api.onrender.com`,
   both **Proxied** (orange cloud).
3. Add the domain in Vercel (Settings -> Domains) and in Render (Settings ->
   Custom Domains) for `api.`.
4. **SSL/TLS** -> mode **Full (strict)**; **Always Use HTTPS** on.
5. **Security -> Bots**: turn on **Bot Fight Mode** and **Block AI Bots**.
6. **Security -> WAF -> Rate limiting rules** (free plan allows one):
   `http.request.method eq "POST" and starts_with(http.request.uri.path, "/inquiries")`
   -> 10 requests per minute per IP -> Block.
7. **Security -> WAF -> Custom rules**: Managed Challenge for
   `cf.threat_score gt 14`.
8. Point the frontend at the new API host: `NEXT_PUBLIC_API_URL=https://api.<domain>`
   in Vercel, and add `https://<domain>` to `CORS_ALLOW_ORIGINS` in Render.

The API already reads `CF-Connecting-IP`, so rate limits keep counting real
visitors once Cloudflare sits in front.

## 3. Reading inquiries

Inquiries are private. Set `ADMIN_TOKEN` in Render to a long random string,
then:

```
curl -H "Authorization: Bearer $ADMIN_TOKEN" https://contractor-ai-api.onrender.com/admin/inquiries
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"status": "derivado", "response": "Lo derivamos a la Contraloría."}' \
  https://contractor-ai-api.onrender.com/admin/inquiries/CAI-XXXXXXXX
```

Without `ADMIN_TOKEN` those endpoints answer 404.
