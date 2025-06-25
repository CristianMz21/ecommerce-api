import logging
from django.core.cache import cache
from django.conf import settings
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser
from django.db.models import F, Count, Avg
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import ValidationError

from .models import Product, Category
from .serializers import (
    ProductListSerializer,
    ProductDetailSerializer,
    CategorySerializer
)

# Configurar el logger
logger = logging.getLogger(__name__)


CACHE_TTL = getattr(settings, 'CACHE_TTL', 60 * 5)  # 5 minutos por defecto


# --- Mixin para Lógica de Caching Reutilizable ---
class CachingMixin:
    """
    Mixin reutilizable para ViewSets que añade lógica de caching para los métodos list y retrieve,
    e invalidación automática de caché en operaciones de creación, actualización y borrado (CUD).

    - Cachea respuestas de list y retrieve si no hay parámetros de búsqueda/ordenamiento.
    - Invalida la caché relevante tras operaciones CUD.
    - Permite a subclases definir la clave base de caché (cache_base_key).
    - Gestiona claves de caché para invalidación eficiente.
    - Incluye manejo especial para productos destacados y con descuento.
    """
    cache_base_key = None  # Debe ser definido por la subclase (ej. 'products', 'categories')

    def get_cache_key_list(self, request):
        """
        Genera la clave de caché para operaciones de listado (list).
        Si hay parámetros de búsqueda, ordenamiento o filtrado, no usa caché.
        """
        # Get query parameters that affect the result
        search = request.query_params.get('search', '')
        ordering = request.query_params.get('ordering', '')
        category = request.query_params.get('category__slug', '')
        
        # If there are search parameters, don't use cache
        if search or ordering or category:
            return None
            
        return f"{self.cache_base_key}_list:"

    def get_cache_key_detail(self, instance_id):
        """
        Genera la clave de caché para operaciones de detalle (retrieve).
        """
        return f"{self.cache_base_key}_detail:{instance_id}"

    def list(self, request, *args, **kwargs):
        """
        Devuelve la lista de objetos, usando caché si no hay parámetros de búsqueda/ordenamiento.
        """
        cache_key = self.get_cache_key_list(request)
        
        # If cache_key is None, it means we have search/filter parameters
        # so we should bypass cache and go directly to the database
        if cache_key is None:
            logger.debug(f"Bypassing cache for {self.cache_base_key} list due to search/filter parameters")
            return super().list(request, *args, **kwargs)
            
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.debug(
                f"Cache HIT: Obteniendo lista de {self.cache_base_key} desde caché con clave: {cache_key}")
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        
        # Only cache if response.data is not None
        if response.data is not None:
            try:
                cache.set(cache_key, response.data, timeout=CACHE_TTL)
                # Track this cache key for future invalidation
                cache_keys = cache.get(f"{self.cache_base_key}_list_keys", [])
                if cache_key not in cache_keys:
                    cache_keys.append(cache_key)
                    cache.set(f"{self.cache_base_key}_list_keys", cache_keys, timeout=None)
                logger.debug(
                    f"Cache MISS: Obteniendo lista de {self.cache_base_key} desde DB y guardando en caché con clave: {cache_key}")
            except Exception as e:
                logger.error(
                    f"Error al guardar lista de {self.cache_base_key} en caché ({cache_key}): {e}")
        else:
            logger.warning(f"Response data is None for {self.cache_base_key} list, skipping cache")
            
        return Response(response.data)

    def retrieve(self, request, *args, **kwargs):
        """
        Devuelve el detalle de un objeto, usando caché si está disponible.
        """
        instance_id = self.kwargs[self.lookup_field]
        if self.cache_base_key == 'categories':
            cache_key = f"category_detail:{instance_id}"
        else:
            cache_key = f"product_detail:{instance_id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.debug(f"Cache HIT: Obteniendo detalle de {self.cache_base_key} {instance_id} desde caché.")
            return Response(cached_data)

        response = super().retrieve(request, *args, **kwargs)
        try:
            cache.set(cache_key, response.data, timeout=CACHE_TTL)
            logger.debug(
                f"Cache MISS: Obteniendo detalle de {self.cache_base_key} {instance_id} desde DB y guardando en caché.")
        except Exception as e:
            logger.error(
                f"Error al guardar detalle de {self.cache_base_key} {instance_id} en caché ({cache_key}): {e}")
        return Response(response.data)

    def _invalidate_related_caches(self, instance_id=None):
        """
        Invalida la caché relacionada (detalle y listas) y claves especiales si aplica.
        """
        # Invalidate detail cache if instance_id provided
        if instance_id:
            cache.delete(f"{self.cache_base_key}_detail:{instance_id}")
            cache.delete(self.get_cache_key_detail(instance_id))
        
        # Invalidate all list caches using tracked keys
        list_cache_keys = cache.get(f"{self.cache_base_key}_list_keys", set())
        for key in list_cache_keys:
            cache.delete(key)
        cache.delete(f"{self.cache_base_key}_list_keys")
        
        # Invalidate special caches if this is the product viewset
        if self.cache_base_key == 'products':
            cache.delete("product_featured")
            cache.delete("product_discounted")

    def perform_create(self, serializer):
        """
        Crea un objeto e invalida la caché de listas.
        """
        super().perform_create(serializer)
        self._invalidate_related_caches()

    def perform_update(self, serializer):
        """
        Actualiza un objeto e invalida la caché de detalle y listas.
        """
        super().perform_update(serializer)
        self._invalidate_related_caches(serializer.instance.id)

    def perform_destroy(self, instance):
        """
        Elimina un objeto e invalida la caché de detalle y listas. Previene borrado si hay relaciones dependientes.
        """
        instance_id = instance.id
        try:
            # Verificar si hay relaciones dependientes
            if hasattr(instance, 'orderitem_set') and instance.orderitem_set.exists():
                raise Exception(f"Cannot delete {instance} because it has related OrderItems")
            super().perform_destroy(instance)
        except Exception as e:
            logger.error(f"Error deleting {self.cache_base_key} {instance_id}: {e}")
            # Return a proper HTTP response instead of raising an exception
            raise ValidationError(str(e))
        self._invalidate_related_caches(instance_id)


# --- Base ViewSet para manejar permisos ---
class AdminOrReadOnlyViewSet(viewsets.ModelViewSet):
    """
    ViewSet base que aplica permisos IsAuthenticatedOrReadOnly para operaciones GET
    y IsAdminUser para operaciones de creación, actualización y borrado (CUD).
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        """
        Asigna permisos según la acción (action) del ViewSet.
        """
        if self.action in ['create', 'update', 'destroy', 'partial_update']:
            return [IsAdminUser()]
        return super().get_permissions()


# --- Category ViewSet con Caching ---
class CategoryViewSet(CachingMixin, AdminOrReadOnlyViewSet):
    """
    Endpoint de API para ver o editar categorías.
    - Solo lista categorías activas.
    - Implementa caching para list y retrieve.
    - Solo administradores pueden crear, actualizar o borrar.
    """
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    cache_base_key = 'categories'  # Define la clave base para este ViewSet


# --- Product ViewSet con Caching ---
class ProductViewSet(CachingMixin, AdminOrReadOnlyViewSet):
    """
    Endpoint de API para productos:
    - Permite ver, buscar, ordenar y editar productos.
    - Proporciona acciones especiales para productos destacados y con descuento.
    - Implementa caching para list y retrieve.
    - Solo administradores pueden crear, actualizar o borrar.
    """
    queryset = Product.objects.filter(is_active=True).select_related('category')
    lookup_field = 'id'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category__slug']
    search_fields = ['name', 'description', 'sku']
    ordering_fields = ['price', 'stock']
    ordering = ['-id']
    cache_base_key = 'products'  # Define la clave base para este ViewSet

    def get_serializer_class(self):
        """
        Devuelve el serializer adecuado según la acción (list o detail).
        """
        if self.action == 'list':
            return ProductListSerializer
        return ProductDetailSerializer

    # Sobreescribe el método de invalidación del mixin si necesitas invalidaciones específicas
    def _invalidate_related_caches(self, instance_id=None):
        """
        Invalida la caché relacionada a productos, incluyendo destacados y con descuento.
        """
        super()._invalidate_related_caches(instance_id)  # Llama al método del mixin primero
        logger.debug("Invalidando cachés específicas de productos (featured, discounted).")
        cache.delete("product_featured")  # Usar delete para claves exactas
        cache.delete("product_discounted")

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """
        Endpoint para obtener productos destacados (is_featured=True).
        Respuesta cacheada bajo la clave 'product_featured'.
        """
        cache_key = "product_featured"  # Clave fija para todos los destacados
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.debug("Cache HIT: Obteniendo productos destacados desde caché.")
            return Response(cached_data)

        products = self.get_queryset().filter(is_featured=True)
        serializer = self.get_serializer(products, many=True)
        try:
            cache.set(cache_key, serializer.data, timeout=CACHE_TTL)
            logger.debug("Cache MISS: Obteniendo productos destacados desde DB y guardando en caché.")
        except Exception as e:
            logger.error(f"Error al guardar productos destacados en caché ({cache_key}): {e}")
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def discounted(self, request):
        """
        Endpoint para obtener productos con descuento (discount_price < price).
        Respuesta cacheada bajo la clave 'product_discounted'.
        """
        cache_key = "product_discounted"  # Clave fija para todos los descontados
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.debug("Cache HIT: Obteniendo productos con descuento desde caché.")
            return Response(cached_data)

        products = self.get_queryset().filter(
            discount_price__isnull=False,
            discount_price__lt=F('price')
        )
        serializer = self.get_serializer(products, many=True)
        try:
            cache.set(cache_key, serializer.data, timeout=CACHE_TTL)
            logger.debug("Cache MISS: Obteniendo productos con descuento desde DB y guardando en caché.")
        except Exception as e:
            logger.error(
                f"Error al guardar productos con descuento en caché ({cache_key}): {e}")
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def reports(self, request):
        """
        Genera reportes de ventas y productos.
        Parámetros de query:
        - type: tipo de reporte ('sales_by_category', 'profit_margin', 'combined')
        - limit: máximo de resultados a devolver (por defecto 10)
        Respuestas:
        - sales_by_category: ventas totales y revenue por categoría.
        - profit_margin: productos ordenados por margen de ganancia.
        - combined: resumen combinado por categoría.
        """
        from django.db import connection
        from django.db.models import Sum, F, ExpressionWrapper, FloatField, Count, Avg
        from django.db.models.functions import Coalesce

        report_type = request.query_params.get('type', 'sales_by_category')
        limit = int(request.query_params.get('limit', 10))

        if report_type == 'sales_by_category':
            # Optimized query using JOINs and GROUP BY with proper indexes
            query = """
            SELECT 
                c.name AS category,
                SUM(oi.quantity) AS total_sold,
                SUM(oi.quantity * oi.unit_price) AS total_revenue
            FROM store_orderitem oi
            JOIN store_product p ON oi.product_id = p.id
            JOIN store_category c ON p.category_id = c.id
            GROUP BY c.name
            ORDER BY total_sold DESC
            LIMIT %s
            """
            with connection.cursor() as cursor:
                cursor.execute(query, [limit])
                results = [
                    {'category': row[0], 'total_sold': row[1], 'total_revenue': row[2]}
                    for row in cursor.fetchall()
                ]
            return Response(results)

        elif report_type == 'profit_margin':
            # Using Django ORM with annotations for profit calculation
            from .models import Product
            products = Product.objects.annotate(
                total_sold=Coalesce(Sum('orderitem__quantity', output_field=FloatField()), 0.0),
                total_revenue=Coalesce(Sum(
                    ExpressionWrapper(
                        F('orderitem__quantity') * F('orderitem__unit_price'),
                        output_field=FloatField()
                    )
                ), 0.0),
                cost_price=ExpressionWrapper(
                    F('price') * 0.7,  # Assuming 30% margin
                    output_field=FloatField()
                ),
                profit_margin=ExpressionWrapper(
                    (F('price') - F('cost_price')) / F('price') * 100.0,
                    output_field=FloatField()
                )
            ).order_by('-profit_margin')[:limit]
            
            serializer = self.get_serializer(products, many=True)
            return Response(serializer.data)

        elif report_type == 'combined':
            # Combined report showing category performance
            from .models import Category
            categories = Category.objects.annotate(
                product_count=Count('products'),
                total_sold=Coalesce(Sum('products__orderitem__quantity', output_field=FloatField()), 0.0),
                avg_price=Avg('products__price', output_field=FloatField()),
                total_revenue=Coalesce(Sum(
                    ExpressionWrapper(
                        F('products__orderitem__quantity') * F('products__orderitem__unit_price'),
                        output_field=FloatField()
                    )
                ), 0.0)
            ).order_by('-total_revenue')[:limit]
            
            serializer = CategorySerializer(categories, many=True)
            return Response(serializer.data)

        return Response(
            {'error': 'Invalid report type'},
            status=status.HTTP_400_BAD_REQUEST
        )
