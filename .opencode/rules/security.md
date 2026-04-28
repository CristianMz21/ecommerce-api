# Security Rules — ecommerce-api

## OWASP Top 10 Compliance

### A01 — Broken Access Control

- **Always check object-level permissions** in DRF views, not just view-level
- Use `get_object()` with appropriate permission classes before any read/write
- Admin endpoints must verify `request.user.is_staff` or `request.user.is_superuser`
- Never rely solely on URL guessing prevention

### A02 — Cryptographic Failures

- **Never hardcode secrets** — use environment variables or `.env` with `python-dotenv`
- All secrets in code → immediate refactor required
- Use `django.core.cache` for Redis connections; never expose connection strings in logs

### A03 — Injection

- **Use Django ORM** — never concatenate raw SQL
- If raw SQL is needed, use parameterized queries exclusively
- Serializer validation must sanitize all user input before it reaches the model

### A04 — Security Misconfiguration

- `DEBUG=False` in production settings
- `ALLOWED_HOSTS` properly configured
- CORS settings: never use `*` for credentials-enabled requests

### A05 — Vulnerable Components

- Pin all dependencies with exact versions in `requirements.txt`
- Run `pip-audit` or `safety` in CI to detect vulnerabilities

## Django/DRF Specific

- Use `@csrf_exempt` only on API endpoints that use token auth (not session)
- Implement rate limiting via DRF throttling classes
- Never expose stack traces or Django DEBUG pages in production

## Secrets Detection

This project uses a **zero-tolerance policy** for hardcoded secrets:
- API keys, tokens, passwords in code → immediate fix
- Use `.env` template: create `.env.example` with all vars, never commit `.env`
- Redis URL, database credentials, JWT secrets → environment only
