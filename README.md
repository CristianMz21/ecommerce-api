# E-commerce REST API

Production-grade e-commerce backend built with **Django 6.0.4** and **Django REST Framework 3.17.1**. Implements role-based access control, Redis-backed caching, optimized database indexes, and custom analytics endpoints.

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.0-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.17-A30000?logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![Redis](https://img.shields.io/badge/Redis-cache-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Mypy](https://img.shields.io/badge/mypy-strict-0%20errors-2E7D32?logo=mypy&logoColor=white)](https://mypy.readthedocs.io/)
[![Tests](https://img.shields.io/badge/tests-28%20%2F%2028%20%F0%9F%9F%A8-success)](store/tests.py)
[![Portfolio](https://img.shields.io/badge/Portfolio-cristianarellano.com-f97316)](https://cristianarellano.com)

---

## Highlights

- **Type-safe** — Full mypy strict mode coverage with zero suppressions
- **Caching strategy** — Per-resource Redis cache with smart invalidation on writes (`CachingMixin`)
- **RBAC** — Anonymous + regular users get read-only; admins get full CRUD
- **Performance** — Composite database indexes on hot query paths (name+category, price+is_active, etc.)
- **Filtering** — `django-filter` integrated for query-param filtering across all endpoints
- **Analytics** — Custom admin-only `/reports/` endpoint aggregating sales, top products, and inventory metrics

## Tech stack

| Layer | Tools |
|---|---|
| **Runtime** | Python 3.14 |
| **Framework** | Django 6.0.4, Django REST Framework 3.17.1 |
| **Cache** | Redis via `django-redis` 6.0.0 |
| **Filtering** | `django-filter` 25.2 |
| **Database** | SQLite (dev) — drop-in PostgreSQL ready |
| **Tests** | Django `APITestCase` |
| **Type checking** | mypy 1.20.2 strict mode |

## Architecture

```
ecommerce_api/          # Project config (settings, root URLs, WSGI/ASGI)
├── settings.py         # Environment-based settings
└── store/              # Domain app
    ├── models.py       # Category, Product, Order, OrderItem
    ├── serializers.py  # DRF serializers (per-action variants)
    ├── services.py    # Business logic layer (ReportsService)
    ├── views.py        # ViewSets + CachingMixin + custom actions
    ├── urls.py         # DRF DefaultRouter
    ├── admin.py        # Django admin registration
    └── tests.py        # API integration tests (28 tests)
```

### Caching pattern

The `CachingMixin` (in `store/views.py`) wraps all read operations with Redis-backed caching:

```python
def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
    cache_key = self.get_cache_key_list(request)
    if cache_key is None:
        return super().list(request, *args, **kwargs)
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)
    response = super().list(request, *args, **kwargs)
    cache.set(cache_key, response.data, timeout=CACHE_TTL)
    return Response(response.data)
```

Writes (`POST/PATCH/DELETE`) invalidate related caches via `_invalidate_related_caches()`, ensuring consistency without stale reads.

### Permissions

```python
class AdminOrReadOnlyViewSet(viewsets.ModelViewSet[Any]):
    def get_permissions(self) -> list[BasePermission]:
        if self.action in ("create", "update", "destroy", "partial_update"):
            return [IsAdminUser()]
        return super().get_permissions()
```

This means anyone can browse the catalog, but only authenticated admins can mutate it or access analytics.

## Quickstart

```bash
git clone https://github.com/CristianMz21/ecommerce-api.git
cd ecommerce-api

uv venv .venv
source .venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

API is now live at `http://localhost:8000/api/`.

> **Note:** Redis is required for caching. If you don't have it locally, run `docker run -d -p 6379:6379 redis:alpine` or comment out `CACHES` in `settings.py`.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/categories/` | public | List all categories |
| `GET` | `/api/categories/{id}/` | public | Retrieve category |
| `POST` | `/api/categories/` | admin | Create category |
| `PATCH` | `/api/categories/{id}/` | admin | Update category |
| `DELETE` | `/api/categories/{id}/` | admin | Delete category (if no products with OrderItems) |
| `GET` | `/api/products/` | public | List products (filters: `category__slug`, `is_active`, `price__gte`, `price__lte`, `search`, `ordering`) |
| `GET` | `/api/products/{id}/` | public | Retrieve product |
| `GET` | `/api/products/featured/` | public | List featured products |
| `GET` | `/api/products/discounted/` | public | List discounted products |
| `GET` | `/api/products/reports/` | admin | Sales + inventory analytics |
| `POST` | `/api/products/` | admin | Create product |

### Example query

```bash
# All active products in electronics category, priced 100-500
curl 'http://localhost:8000/api/products/?category__slug=electronics&is_active=true&price__gte=100&price__lte=500'
```

## Quality gates

All changes pass these checks before commit:

```bash
pre-commit run --all-files        # ruff format, ruff check, mypy, check yaml
python manage.py test store       # 28 tests
python scripts/check_suppressions.py --strict  # zero suppressions
```

## Testing

```bash
python manage.py test store
```

Coverage spans:
- **Caching:** verifies cached responses, invalidation on writes, TTL behavior
- **Permissions:** anonymous read-only, regular user read-only, admin full access
- **CRUD:** all standard operations on all resources
- **Filtering & search:** valid params, invalid params, edge cases
- **Reports:** sales by category, profit margin, combined metrics

## Roadmap

- [ ] Migrate from SQLite to PostgreSQL with proper migrations
- [ ] Add JWT authentication (`djangorestframework-simplejwt`)
- [ ] Add Celery + RabbitMQ for async order processing
- [ ] OpenAPI schema via `drf-spectacular`
- [ ] Containerize with Docker + docker-compose

## License

MIT — see [LICENSE](LICENSE).

---

<sub>Built by **[Cristian Arellano Muñoz](https://cristianarellano.com)** — Backend Engineer · Software Architect.<br>
Looking for a backend engineer? Let's talk: [hi@cristianarellano.com](mailto:hi@cristianarellano.com) or [book a call](https://cal.com/cristianarellano).</sub>