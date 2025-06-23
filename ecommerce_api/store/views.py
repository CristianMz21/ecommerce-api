import logging
from django.core.cache import cache
from django.conf import settings
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAdminUser
from django.db.models import F
from django_filters.rest_framework import DjangoFilterBackend

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
    Un mixin para ViewSets que añade lógica de caching para métodos list y retrieve,
    y manejo de invalidación en operaciones CUD.
    """
    cache_base_key = None  # Debe ser definido por la subclase (ej. 'products', 'categories')

    def get_cache_key_list(self, request):
        """Genera la clave para la lista de recursos."""
        return f"{self.cache_base_key}_list:{request.GET.urlencode()}"

    def get_cache_key_detail(self, instance_id):
        """Genera la clave para un recurso individual."""
        return f"{self.cache_base_key}_detail:{instance_id}"

    def list(self, request, *args, **kwargs):
        cache_key = self.get_cache_key_list(request)
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.debug(
                f"Cache HIT: Obteniendo lista de {self.cache_base_key} desde caché con clave: {cache_key}")
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)
        try:
            cache.set(cache_key, response.data, timeout=CACHE_TTL)
            logger.debug(
                f"Cache MISS: Obteniendo lista de {self.cache_base_key} desde DB y guardando en caché con clave: {cache_key}")
        except Exception as e:
            logger.error(
                f"Error al guardar lista de {self.cache_base_key} en caché ({cache_key}): {e}")
        return Response(response.data)

    def retrieve(self, request, *args, **kwargs):
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
        """Método auxiliar para invalidar cachés relacionadas."""
        logger.debug(
            f"Invalidando cachés relacionadas para {self.cache_base_key} (ID: {instance_id if instance_id else 'N/A'}).")
        cache.delete_pattern(f"{self.cache_base_key}_list:*")
        if instance_id:
            cache.delete(self.get_cache_key_detail(instance_id))
        # Puedes añadir más invalidaciones aquí si hay acciones personalizadas generales
        # Ejemplo: if self.cache_base_key == 'products':
        #               cache.delete("product_featured")
        #               cache.delete("product_discounted")

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._invalidate_related_caches()

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._invalidate_related_caches(serializer.instance.id)

    def perform_destroy(self, instance):
        instance_id = instance.id
        super().perform_destroy(instance)
        self._invalidate_related_caches(instance_id)


# --- Base ViewSet para manejar permisos ---
class AdminOrReadOnlyViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet that applies IsAuthenticatedOrReadOnly for GET operations
    and IsAdminUser for CUD operations.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_permissions(self):
        """
        Set permissions based on the action.
        """
        if self.action in ['create', 'update', 'destroy', 'partial_update']:
            return [IsAdminUser()]
        return super().get_permissions()


# --- Category ViewSet con Caching ---
class CategoryViewSet(CachingMixin, AdminOrReadOnlyViewSet):
    """
    API endpoint that allows categories to be viewed or edited.
    Only active categories are listed. Implements caching.
    """
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    cache_base_key = 'categories'  # Define la clave base para este ViewSet


# --- Product ViewSet con Caching ---
class ProductViewSet(CachingMixin, AdminOrReadOnlyViewSet):
    """
    API endpoint that allows products to be viewed, searched, ordered, or edited.
    Provides special actions for featured and discounted products. Implements caching.
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
        Returns the appropriate serializer class based on the action.
        """
        if self.action == 'list':
            return ProductListSerializer
        return ProductDetailSerializer

    # Sobreescribe el método de invalidación del mixin si necesitas invalidaciones específicas
    def _invalidate_related_caches(self, instance_id=None):
        super()._invalidate_related_caches(instance_id)  # Llama al método del mixin primero
        logger.debug("Invalidando cachés específicas de productos (featured, discounted).")
        cache.delete("product_featured")  # Usar delete para claves exactas
        cache.delete("product_discounted")

    @action(detail=False, methods=['get'])
    def featured(self, request):
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
