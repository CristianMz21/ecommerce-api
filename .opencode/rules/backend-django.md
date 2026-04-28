# Backend Django/DRF Rules — ecommerce-api

## Django Conventions

### Models

- Use `django.db.models` — avoid `django.db.models.sql` directly
- All models inherit from `models.Model`
- Use `get_absolute_url()` for SEO-friendly URLs
- Indexes defined via `Meta.indexes` or `db_index=True`
- Validation in `clean()` method, not in views

### Migrations

- One migration per logical change
- Migration files: NEVER edit manually after creation
- Use `--dry-run` to review before generating

### Settings

- Environment-based settings (dev/staging/prod)
- Secrets via environment variables, never in code
- `ALLOWED_HOSTS` = `environ.getlist('ALLOWED_HOSTS', [])`

## Django REST Framework Conventions

### Serializers

- Use `Serializer` for read-only representations
- Use `ModelSerializer` for create/update operations
- Separate serializers per action when representation differs significantly
- Validate related objects exist in `validate_<field>` methods

### Views

- **Always** use ViewSets for CRUD resources
- Use `@action` for custom endpoints on resources
- Permission classes: `AllowAny` for public, `IsAuthenticated` for private, `IsAdminUser` for admin
- Pagination: use DRF default or custom cursor pagination

### URL Patterns

- DRF DefaultRouter for automatic URL generation
- Namespace routers when multiple apps share URL space
- Include router URLs in project `urls.py`

### Caching (current implementation)

- `CachingMixin` in `views.py` handles Redis caching
- Cache invalidation on POST/PATCH/DELETE via `_invalidate_related_caches()`
- TTL defined in settings as `CACHE_TTL`

## Performance Patterns

- Use `select_related()` and `prefetch_related()` to avoid N+1 queries
- Use `only()` or `defer()` when full object isn't needed
- Database indexes on hot query paths (see `models.py` `Meta.indexes`)

## Error Handling

- Return appropriate HTTP status codes:
  - `200` OK
  - `201` Created
  - `400` Bad Request (validation errors)
  - `401` Unauthorized
  - `403` Forbidden
  - `404` Not Found
  - `405` Method Not Allowed
  - `500` Internal Server Error (never expose stack traces)

## Admin Configuration

- Register all models in `admin.py`
- Use `list_display`, `list_filter`, `search_fields` for usability
- Use `readonly_fields` for computed or sensitive fields