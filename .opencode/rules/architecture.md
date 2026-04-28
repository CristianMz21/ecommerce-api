# Architecture Rules — ecommerce-api

## Domain-Driven Design Principles

- **Fat Services**: Keep business logic in service layers, not in views or serializers.
- **Models**: Django models should only define data structure, validation (`clean()`), and relationships. No business logic.
- **Separation**: Views handle HTTP, serializers handle representation, services handle business logic.

## Project Structure

```
ecommerce_api/          # Django project config (settings, urls, wsgi, asgi)
store/                  # Main domain app
    models.py           # Data structure ONLY
    serializers.py      # Representation + read validation
    services.py         # Business logic (CREATE THIS)
    views.py            # HTTP handling + routing to services
    urls.py             # URL routing
    admin.py            # Django admin
    tests.py            # Integration tests
```

## Key Rules

### Do

- Create a `services.py` module for complex business logic (analytics, caching invalidation, etc.)
- Use custom model `clean()` methods for field validation
- Keep ViewSets focused on routing; delegate to services
- Use dataclasses or Pydantic for internal data transfer objects (DTOs)

### Don't

- Don't put business logic in `views.py` beyond routing
- Don't use models for read-only representations (use serializers for that)
- Don't mix HTTP concerns with business rules