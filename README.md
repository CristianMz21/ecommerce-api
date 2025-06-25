# Ecommerce API

A Django REST Framework API for an e-commerce platform with product and category management.

## Features

- **Product Management**
  - Create, read, update and delete products
  - Filter products by category
  - Search products by name, description or SKU
  - Sort products by price or stock
  - Special endpoints for featured and discounted products

- **Category Management**
  - Create, read, update and delete categories
  - Automatic slug generation

- **Performance**
  - Built-in caching for list and detail views
  - Cache invalidation on data changes

## API Endpoints

### Categories
- `GET /store/categories/` - List all active categories
- `POST /store/categories/` - Create new category (admin only)
- `GET /store/categories/{id}/` - Get category details
- `PUT/PATCH /store/categories/{id}/` - Update category (admin only)
- `DELETE /store/categories/{id}/` - Delete category (admin only)

### Products
- `GET /store/products/` - List all active products
- `POST /store/products/` - Create new product (admin only)
- `GET /store/products/{id}/` - Get product details
- `PUT/PATCH /store/products/{id}/` - Update product (admin only)
- `DELETE /store/products/{id}/` - Delete product (admin only)
- `GET /store/products/featured/` - List featured products
- `GET /store/products/discounted/` - List discounted products

## Models

### Category
```python
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)
```

### Product
```python
class Product(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    stock = models.PositiveIntegerField(default=0)
    category = models.ForeignKey(Category, related_name="products", on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True)
```

## Setup

1. Clone the repository
2. Install requirements: `pip install -r requirements.txt`
3. Run migrations: `python manage.py migrate`
4. Start development server: `python manage.py runserver`

## Caching Configuration

The API uses Redis for caching with the following configuration:
- Default cache TTL: 5 minutes
- Cache keys:
  - Product lists: `products_list:[query_params]`
  - Product details: `product_detail:[id]` 
  - Category lists: `categories_list:[query_params]`
  - Category details: `category_detail:[id]`
  - Featured products: `product_featured`
  - Discounted products: `product_discounted`

To setup Redis:
1. Install Redis server
2. Add to Django settings:
```python
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}
```

## Production Deployment

### Requirements
- Python 3.8+
- Redis server
- PostgreSQL (recommended) or MySQL
- Gunicorn or uWSGI
- Nginx (recommended)

### Configuration
1. Set production settings in `ecommerce_api/settings/production.py`:
```python
from .base import *

DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com']
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'ecommerce_db',
        'USER': 'ecommerce_user',
        'PASSWORD': 'secure_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# HTTPS settings
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
```

2. Create `.env` file with:
```
SECRET_KEY=your_production_secret_key
DJANGO_SETTINGS_MODULE=ecommerce_api.settings.production
DB_NAME=ecommerce_db
DB_USER=ecommerce_user
DB_PASSWORD=secure_password
DB_HOST=localhost
REDIS_URL=redis://localhost:6379/0
```

### Deployment Commands
```bash
# Install requirements
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate

# Start Gunicorn
gunicorn --bind 0.0.0.0:8000 ecommerce_api.wsgi:application

# Nginx sample config
"""
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias /path/to/your/staticfiles/;
    }
}
"""
```

### Recommendations
- Use a process manager like Supervisor or systemd
- Set up monitoring (Sentry, New Relic)
- Implement regular backups
- Configure log rotation
- Use a CDN for static files

## Authentication

- Read operations: No authentication required
- Create/Update/Delete operations: Admin user required
