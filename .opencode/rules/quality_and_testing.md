# Quality and Testing Rules — ecommerce-api

## ZERO TOLERANCE: NO SUPPRESSIONS

**NEVER use any of these — fix errors instead of silencing them:**
```
# noqa, # noqa: F401, # noqa: E501 | # type: ignore, # type: ignore[anything]
# pylint: disable=..., # nosec | @pytest.mark.skip, @pytest.mark.skipif
# coverage: ignore, # coverage: no-cover | @unittest.skip, @unittest.skipIf
```

> "Si hay un error: CORRÍGELO. Nunca lo silencies."

## PROTECTED FILES

The following files are **NEVER to be modified** by OpenCode or any agent:

| File | Reason |
|------|--------|
| `scripts/check_suppressions.py` | Enforces ZERO SUPPRESSIONS rule. Must remain unchanged. |

## Testing

### Framework

- Use **Django `APITestCase`** (current) — do not migrate to pytest unless explicitly requested
- Test location: `store/tests.py`
- Run with: `python manage.py test store`

### Test Coverage Goals

- All API endpoints must have integration tests
- Test both success AND error paths
- Test permissions: anonymous, authenticated, admin
- Test caching behavior (hit, miss, invalidation)

### Test Structure Convention

```
class BaseAPITestCase(APITestCase):
    """Base class with common fixtures and helper methods"""

class CategoryViewSetTest(BaseAPITestCase):
    ...

class ProductViewSetTest(BaseAPITestCase):
    ...
```

## Code Quality

### Ruff (Linting)

- Line length: 88 (Black-compatible)
- Target: Python 3.13
- Plugins: `ruff` itself, plus `ruff-format` for formatting

### Type Checking

- Use `mypy` with Django stubs (`django-stubs`)
- **STRICT typing — no `Any` allowed** unless absolutely indispensable
- `Any` is ONLY permitted when:
  - Django/Python runtime lacks type annotations (legacy libraries)
  - Dynamic attribute access (`__getattr__`, dynamic models)
  - Callback/hook interfaces where type cannot be constrained
  - When ALL alternatives have been exhausted and documented why
- **NEVER use `Any` for convenience** — if you use it, document WHY it was necessary
- Type annotations required on:
  - All function signatures (parameters + return type)
  - Class attributes in services
  - Serializer field types
  - ViewSet methods (queryset, get_object, etc.)
- Use `Unknown` or `object` instead of `Any` when possible
- For Django ORM: use `django-stubs` TypedDict or explicit model types
- For DRF serializers: define explicit field types, don't use `Any`

### Pre-commit Hooks

- **Before every commit**: ruff format + ruff check + mypy
- **NO exceptions** — hooks must pass before commit succeeds

## Import Conventions

- Standard library → third-party → local (empty line between groups)
- Use explicit relative imports in Django apps
- Never use `import *`

## Documentation

- Every service function must have a docstring with:
  - What it does
  - Parameters (with types)
  - Return value (with type)
  - Any exceptions it raises
