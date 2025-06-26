# 📋 Documentación Completa - E-commerce API

## 🚀 Descripción General

API REST para un sistema de e-commerce construida con Django REST Framework. Incluye gestión de productos, categorías, órdenes y reportes con sistema de caché optimizado para mejorar el rendimiento.

## 🛠️ Stack Tecnológico

- **Framework**: Django 5.2.3
- **API**: Django REST Framework 3.16.0
- **Base de Datos**: SQLite3 (desarrollo)
- **Caché**: Django LocMem Cache
- **Filtros**: django-filter 25.1
- **Python**: 3.13.5

## 📁 Estructura del Proyecto

```
ecommerce-api/
├── ecommerce_api/          # Configuración principal de Django
│   ├── settings.py         # Configuraciones del proyecto
│   ├── urls.py             # URLs principales
│   ├── wsgi.py             # WSGI para deployment
│   └── asgi.py             # ASGI para async
├── store/                  # App principal del ecommerce
│   ├── models.py           # Modelos de datos
│   ├── views.py            # ViewSets y lógica de negocio
│   ├── serializers.py      # Serializers para API
│   ├── urls.py             # URLs de la app
│   ├── admin.py            # Configuración del admin
│   └── tests.py            # Tests unitarios
├── manage.py               # Comando principal de Django
├── requirements.txt        # Dependencias Python
└── README.md               # Documentación básica
```

## 🗄️ Modelos de Datos

### Category (Categorías)
```python
class Category(models.Model):
    """
    Modelo para categorías de productos.
    
    Atributos:
        name: Nombre único de la categoría (max 100 chars)
        slug: URL-friendly identifier único
        description: Descripción opcional de la categoría
        is_active: Estado activo/inactivo (default: True)
        featured: Categoría destacada (default: False)
    
    Índices:
        - name, is_active (compuesto)
        - Campos individuales con db_index=True
    
    Comportamiento:
        - Auto-genera slug desde name si no se proporciona
        - Previene eliminación si tiene productos con OrderItems
        - Elimina productos relacionados al borrarse
    """
```

### Product (Productos)
```python
class Product(models.Model):
    """
    Modelo para productos del ecommerce.
    
    Atributos:
        name: Nombre del producto (max 255 chars)
        slug: URL-friendly identifier único
        description: Descripción del producto
        price: Precio regular (10 dígitos, 2 decimales)
        discount_price: Precio con descuento (opcional)
        stock: Cantidad disponible (entero positivo)
        category: Relación con Category (PROTECT)
        is_active: Estado activo/inactivo
        is_featured: Producto destacado
        sku: Código único del producto (opcional)
        created_at: Fecha de creación (auto)
        updated_at: Fecha de última actualización (auto)
    
    Validaciones:
        - price no puede ser negativo
        - discount_price debe ser menor que price
    
    Índices:
        - name, category (compuesto)
        - price, is_active (compuesto)
        - Campos individuales con db_index=True
    
    Comportamiento:
        - Auto-genera slug desde name
        - Elimina OrderItems relacionados al borrarse
        - Ordenamiento por -created_at
    """
```

### Order (Órdenes)
```python
class Order(models.Model):
    """
    Modelo para órdenes de compra.
    
    Atributos:
        created_at: Fecha de creación
        updated_at: Fecha de actualización
        customer_name: Nombre del cliente (max 100 chars)
        customer_email: Email del cliente
        total_amount: Monto total de la orden
        status: Estado de la orden (pending/completed/cancelled)
    
    Estados:
        - pending: Orden pendiente (default)
        - completed: Orden completada
        - cancelled: Orden cancelada
    
    Índices:
        - created_at, status (compuesto)
    """
```

### OrderItem (Items de Orden)
```python
class OrderItem(models.Model):
    """
    Modelo para items individuales dentro de una orden.
    
    Atributos:
        order: Relación con Order (CASCADE)
        product: Relación con Product (PROTECT)
        quantity: Cantidad del producto (entero positivo)
        unit_price: Precio unitario al momento de la compra
        discount: Descuento aplicado (default: 0)
    
    Validaciones:
        - quantity debe ser mayor a 0
    
    Índices:
        - order, product (compuesto)
        - product, order (compuesto inverso)
    """
```

## 🔧 ViewSets y Endpoints

### CategoryViewSet
```python
class CategoryViewSet(CachingMixin, AdminOrReadOnlyViewSet):
    """
    API endpoint para gestión de categorías.
    
    Funcionalidades:
        - Lista solo categorías activas (is_active=True)
        - Caché automático para list y retrieve
        - Solo admins pueden crear/actualizar/eliminar
        - Lectura pública permitida
    
    Endpoints:
        GET    /api/categories/          # Lista categorías
        POST   /api/categories/          # Crear (solo admin)
        GET    /api/categories/{id}/     # Detalle
        PUT    /api/categories/{id}/     # Actualizar (solo admin)
        DELETE /api/categories/{id}/     # Eliminar (solo admin)
    """
```

### ProductViewSet
```python
class ProductViewSet(CachingMixin, AdminOrReadOnlyViewSet):
    """
    API endpoint para gestión de productos.
    
    Funcionalidades:
        - Lista productos activos con paginación
        - Búsqueda por name, description, sku
        - Filtro por category__slug
        - Ordenamiento por price, stock
        - Caché inteligente (se invalida con parámetros)
        - Endpoints especiales para featured/discounted
        - Sistema de reportes avanzado
    
    Endpoints:
        GET    /api/products/                    # Lista productos
        POST   /api/products/                    # Crear (solo admin)
        GET    /api/products/{id}/               # Detalle
        PUT    /api/products/{id}/               # Actualizar (solo admin)
        DELETE /api/products/{id}/               # Eliminar (solo admin)
        GET    /api/products/featured/           # Productos destacados
        GET    /api/products/discounted/         # Productos con descuento
        GET    /api/products/reports/            # Reportes de ventas
    
    Parámetros de búsqueda:
        - search: Busca en name, description, sku
        - category__slug: Filtra por categoría
        - ordering: Ordena por price, stock
    
    Acciones especiales:
        - featured(): Productos con is_featured=True
        - discounted(): Productos con discount_price < price
        - reports(): Genera reportes de ventas
    """
```

## 🚀 Sistema de Caché

### CachingMixin
```python
class CachingMixin:
    """
    Mixin reutilizable para ViewSets con caché automático.
    
    Funcionalidades:
        - Caché automático para operaciones list y retrieve
        - Invalidación inteligente en operaciones CUD
        - Bypass de caché con parámetros de búsqueda
        - Gestión de claves de caché para invalidación
        - Manejo de errores en operaciones de caché
    
    Configuración:
        - cache_base_key: Clave base definida por subclase
        - CACHE_TTL: Tiempo de vida del caché (5 min default)
    
    Claves de caché:
        - Lista: {base_key}_list:
        - Detalle: {base_key}_detail:{id}
        - Especiales: product_featured, product_discounted
    
    Invalidación:
        - Automática en create/update/delete
        - Rastrea claves para invalidación eficiente
        - Manejo especial para productos destacados
    """
```

### Estrategia de Caché

**Caché Activo:**
- ✅ Listas sin parámetros de búsqueda
- ✅ Detalles de productos/categorías individuales
- ✅ Productos destacados (`/products/featured/`)
- ✅ Productos con descuento (`/products/discounted/`)

**Bypass de Caché:**
- ❌ Búsquedas con parámetros (`?search=...`)
- ❌ Filtros (`?category__slug=...`)
- ❌ Ordenamiento (`?ordering=...`)
- ❌ Reportes (datos dinámicos)

## 📊 Sistema de Reportes

### Endpoint: `/api/products/reports/`

#### Parámetros:
- `type`: Tipo de reporte (`sales_by_category`, `profit_margin`, `combined`)
- `limit`: Máximo resultados (default: 10)

#### Tipos de Reportes:

**1. Sales by Category (`sales_by_category`)**
```sql
-- Query optimizada con JOINs e índices
SELECT 
    c.name AS category,
    SUM(oi.quantity) AS total_sold,
    SUM(oi.quantity * oi.unit_price) AS total_revenue
FROM store_orderitem oi
JOIN store_product p ON oi.product_id = p.id
JOIN store_category c ON p.category_id = c.id
GROUP BY c.name
ORDER BY total_sold DESC
```

**2. Profit Margin (`profit_margin`)**
```python
# Django ORM con anotaciones
products = Product.objects.annotate(
    total_sold=Sum('orderitem__quantity'),
    total_revenue=Sum(F('orderitem__quantity') * F('orderitem__unit_price')),
    cost_price=F('price') * 0.7,  # 30% margen asumido
    profit_margin=(F('price') - F('cost_price')) / F('price') * 100
).order_by('-profit_margin')
```

**3. Combined Report (`combined`)**
```python
# Reporte combinado por categoría
categories = Category.objects.annotate(
    product_count=Count('products'),
    total_sold=Sum('products__orderitem__quantity'),
    avg_price=Avg('products__price'),
    total_revenue=Sum(F('products__orderitem__quantity') * F('products__orderitem__unit_price'))
).order_by('-total_revenue')
```

## 🔒 Sistema de Permisos

### AdminOrReadOnlyViewSet
```python
class AdminOrReadOnlyViewSet(viewsets.ModelViewSet):
    """
    ViewSet base con permisos diferenciados:
    
    Operaciones de Lectura (GET):
        - IsAuthenticatedOrReadOnly
        - Permite acceso público para lectura
        - Usuarios autenticados tienen acceso completo de lectura
    
    Operaciones de Escritura (POST/PUT/DELETE):
        - IsAdminUser
        - Solo usuarios administradores
        - Requiere is_staff=True
    
    Acciones:
        - list, retrieve: Público/Autenticado
        - create, update, destroy: Solo Admin
    """
```

## 🗂️ Serializers

### CategorySerializer
```python
class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer para el modelo Category.
    
    Campos:
        - id, name, slug, description
        - is_active, featured
    
    Funcionalidades:
        - Validación automática de campos
        - Representación JSON completa
        - Compatible con operaciones CRUD
    """
```

### ProductListSerializer vs ProductDetailSerializer
```python
class ProductListSerializer(serializers.ModelSerializer):
    """
    Serializer optimizado para listas de productos.
    
    Campos esenciales:
        - id, name, slug, price, discount_price
        - stock, is_featured, category info
        - created_at para ordenamiento
    
    Optimizaciones:
        - Campos mínimos para rendimiento
        - Información de categoría anidada
        - Ideal para páginas de listado
    """

class ProductDetailSerializer(serializers.ModelSerializer):
    """
    Serializer completo para detalles de producto.
    
    Campos completos:
        - Todos los campos del producto
        - Información detallada de categoría
        - Metadatos completos
    
    Uso:
        - Páginas de detalle de producto
        - Operaciones de edición
        - APIs que requieren info completa
    """
```

## 🔧 Configuración (settings.py)

### Aplicaciones Instaladas
```python
INSTALLED_APPS = [
    'django.contrib.admin',           # Panel administrativo
    'django.contrib.auth',            # Autenticación
    'django.contrib.contenttypes',    # Tipos de contenido
    'django.contrib.sessions',        # Sesiones
    'django.contrib.messages',        # Mensajes
    'django.contrib.staticfiles',     # Archivos estáticos
    'django_filters',                 # Filtros para APIs
    'rest_framework',                 # Django REST Framework
    'store',                          # App principal del ecommerce
]
```

### Configuración de Caché
```python
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}
CACHE_TTL = 60 * 5  # 5 minutos
```

### Django REST Framework
```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly'
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend'
    ]
}
```

### Sistema de Logging
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
    'loggers': {
        'store': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    }
}
```

## 🚀 Instalación y Uso

### 1. Clonar e Instalar
```bash
git clone <repository-url>
cd ecommerce-api
pip install -r requirements.txt
```

### 2. Configurar Base de Datos
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 3. Ejecutar Servidor
```bash
python manage.py runserver
```

### 4. Acceder a la API
- **API Root**: http://localhost:8000/api/
- **Admin Panel**: http://localhost:8000/admin/
- **DRF Browser**: http://localhost:8000/api-auth/

## 📝 Ejemplos de Uso de la API

### Listar Productos
```bash
GET /api/products/
# Respuesta: Lista paginada de productos activos

# Con búsqueda
GET /api/products/?search=smartphone

# Con filtro por categoría
GET /api/products/?category__slug=electronics

# Con ordenamiento
GET /api/products/?ordering=price
```

### Productos Destacados
```bash
GET /api/products/featured/
# Respuesta: Productos con is_featured=True
```

### Productos con Descuento
```bash
GET /api/products/discounted/
# Respuesta: Productos con discount_price < price
```

### Reportes de Ventas
```bash
# Ventas por categoría
GET /api/products/reports/?type=sales_by_category&limit=5

# Margen de ganancia
GET /api/products/reports/?type=profit_margin&limit=10

# Reporte combinado
GET /api/products/reports/?type=combined&limit=8
```

### Crear Producto (Solo Admin)
```bash
POST /api/products/
Content-Type: application/json
Authorization: Basic <credentials>

{
    "name": "iPhone 15 Pro",
    "description": "Latest iPhone model",
    "price": "999.99",
    "discount_price": "899.99",
    "stock": 50,
    "category": 1,
    "is_featured": true,
    "sku": "IPH15PRO001"
}
```

## 🎯 Características Destacadas

### ✅ Optimizaciones de Rendimiento
- **Caché inteligente** con invalidación automática
- **Índices de base de datos** optimizados
- **Select related** para evitar N+1 queries
- **Queries raw SQL** para reportes complejos

### ✅ Seguridad
- **Permisos granulares** por operación
- **Validación de datos** en modelos y serializers
- **Protección CSRF** habilitada
- **Autenticación requerida** para operaciones sensibles

### ✅ Escalabilidad
- **Arquitectura modular** con mixins reutilizables
- **Separación de responsabilidades** clara
- **Sistema de logging** detallado
- **Configuración de caché** flexible

### ✅ Mantenibilidad
- **Código autodocumentado** con docstrings
- **Patrones consistentes** en todo el proyecto
- **Manejo de errores** robusto
- **Tests incluidos** para validación

## 🔄 Flujo de Datos

```
Cliente → Django URL Router → ViewSet → Serializer → Modelo → Base de Datos
                                  ↓
                               Caché (si aplica)
                                  ↓
                            Respuesta JSON
```

## 📈 Métricas y Monitoreo

### Logs Disponibles
- **Cache HIT/MISS**: Rendimiento del caché
- **Database queries**: Operaciones de BD
- **API requests**: Peticiones entrantes
- **Error tracking**: Errores y excepciones

### Puntos de Monitoreo
- **Tiempo de respuesta** de endpoints
- **Eficiencia del caché** (hit ratio)
- **Uso de base de datos** (query count)
- **Errores 4xx/5xx** en respuestas

---

*Esta documentación cubre la implementación actual del proyecto. Para contribuir o reportar issues, consulta el repositorio del proyecto.*