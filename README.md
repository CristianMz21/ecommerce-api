# E-commerce REST API

Production-grade e-commerce backend built with **Django 5.2** and **Django REST Framework 3.16**. Implements role-based access control, Redis-backed caching, optimized database indexes, and custom analytics endpoints.

[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-3.16-A30000?logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![Redis](https://img.shields.io/badge/Redis-cache-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![Tests](https://img.shields.io/badge/tests-672_lines-success)](store/tests.py)
[![Portfolio](https://img.shields.io/badge/Portfolio-cristianarellano.com-f97316)](https://cristianarellano.com)

---

## Highlights

- **Caching strategy** — Per-resource Redis cache with smart invalidation on writes (`CachingMixin`)
- **RBAC** — Anonymous + regular users get read-only; admins get full CRUD
- **Performance** — Composite database indexes on hot query paths (name+category, price+is_active, etc.)
- **Filtering** — `django-filter` integrated for query-param filtering across all endpoints
- **Analytics** — Custom admin-only `/reports/` endpoint aggregating sales, top products, and inventory metrics
- **Test coverage** — 672 lines across caching, permissions, CRUD, filtering edge cases

## Tech stack

| Layer | Tools |
|---|---|
| **Runtime** | Python 3.13 |
| **Framework** | Django 5.2 LTS, Django REST Framework 3.16 |
| **Cache** | Redis via `django-redis` |
| **Filtering** | `django-filter` 25.1 |
| **Database** | SQLite (dev) — drop-in PostgreSQL ready |
| **Tests** | Django `APITestCase` |

## Architecture

```
ecommerce_api/          # Project config (settings, root URLs, WSGI/ASGI)
└── store/              # Domain app
    ├── models.py       # Category, Product, Order, OrderItem
    ├── serializers.py  # DRF serializers (per-action variants)
    ├── views.py        # ViewSets + CachingMixin + custom actions
    ├── urls.py         # DRF DefaultRouter
    ├── admin.py        # Django admin registration
    └── tests.py        # API integration tests
```

### Caching pattern

The `CachingMixin` (in `store/views.py`) wraps all read operations with Redis-backed caching:

```python
def list(self, request):
    cache_key = self.get_cache_key_list(request)
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)
    response = super().list(request)
    cache.set(cache_key, response.data, timeout=CACHE_TTL)
    return response
```

Writes (`POST/PATCH/DELETE`) invalidate related caches via `_invalidate_related_caches()`, ensuring consistency without stale reads.

### Permissions

```python
class AdminOrReadOnlyViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'featured', 'discounted'):
            return [AllowAny()]
        return [IsAdminUser()]
```

This means anyone can browse the catalog, but only authenticated admins can mutate it or access analytics.

## Quickstart

```bash
git clone https://github.com/CristianMz21/ecommerce-api.git
cd ecommerce-api

python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

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
| `GET` | `/api/products/` | public | List products (filters: `category`, `is_active`, `price__gte`, `price__lte`) |
| `GET` | `/api/products/{id}/` | public | Retrieve product |
| `GET` | `/api/products/featured/` | public | List featured products |
| `GET` | `/api/products/discounted/` | public | List discounted products |
| `GET` | `/api/products/reports/` | admin | Sales + inventory analytics |
| `POST` | `/api/products/` | admin | Create product |

### Example query

```bash
# All active products in category 3, priced 100k-500k COP
curl 'http://localhost:8000/api/products/?category=3&is_active=true&price__gte=100000&price__lte=500000'
```

## Testing

```bash
python manage.py test store
```

Coverage spans:
- **Caching:** verifies cached responses, invalidation on writes, TTL behavior
- **Permissions:** anonymous read-only, regular user read-only, admin full access
- **CRUD:** all standard operations on all resources
- **Filtering:** valid params, invalid params, edge cases

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
