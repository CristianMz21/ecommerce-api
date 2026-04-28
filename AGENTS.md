# AGENTS.md — ecommerce-api

Django 6.0 + DRF 3.17 e-commerce API. Python 3.14, SQLite (dev) / PostgreSQL (prod-ready).

**Full rules auto-loaded from `.opencode/rules/`:**
- `architecture.md` — DDD, fat services, no business logic in views
- `security.md` — OWASP Top 10, zero hardcoded secrets
- `quality_and_testing.md` — Zero suppressions, Django APITestCase
- `backend-django.md` — DRF conventions, permissions, admin registration

## Run commands

```bash
# Activate venv
source .venv/bin/activate

# Tests
python manage.py test store

# Pre-commit (runs ALL quality gates — required before commit)
pre-commit run --all-files

# Individual gates
ruff format store/ ecommerce_api/
ruff check store/ ecommerce_api/
mypy store/ ecommerce_api/
python scripts/check_suppressions.py --strict
```

## What agents get wrong

### Business logic lives in views — move to services
`store/views.py` line ~271 has inline raw SQL in the `reports` action. DDD rules say all business logic must be in `store/services.py`. **Before adding any new business logic, create services.py.**

### No `services.py` yet
Models have `clean()` validation, views handle HTTP + caching, serializers handle representation. Create `store/services.py` for any new business logic (analytics, inventory, etc.).

### `AdminOrReadOnlyViewSet` permissions
GET → `AllowAny` (browsable catalog), POST/PATCH/DELETE → `IsAdminUser`. Do not add business logic here.

### Test structure: 881-line `store/tests.py`
Uses `BaseAPITestCase` → concrete test classes. `admin_user` and `regular_user` fixtures available. Cache is cleared between tests via Django's test framework.

### Pre-commit has a custom local hook
`check-suppressions` (scripts/check_suppressions.py) is a local hook, not from a remote repo. It runs before ruff/mypy. It is **protected** — never modify `scripts/check_suppressions.py`.

### Model `delete()` has side effects
`Category.delete()` cascades to products (only those without OrderItems), `Product.delete()` cascades to OrderItems. Do not rely on ON DELETE CASCADE alone.

### Slugs auto-generated on save
`Category.save()` and `Product.save()` auto-generate slugs via `slugify()` if blank. Do not manually set slugs in fixtures.

### Settings uses LocMemCache (not Redis)
`ecommerce_api/settings.py`: LocMemCache for dev. Redis is optional and only needed for production. Cache failures are silent (try/except).

## Quick reference

| Path | Purpose |
|------|---------|
| `ecommerce_api/` | Django project config (settings, URLs, WSGI) |
| `store/` | Domain app: models, views, serializers, tests |
| `store/models.py` | Category, Product, Order, OrderItem |
| `store/views.py` | ViewSets with CachingMixin, custom actions |
| `store/services.py` | Business logic (to be created for new features) |
| `scripts/check_suppressions.py` | **Protected** — zero suppressions enforcement |
