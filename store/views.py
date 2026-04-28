import logging

from django.conf import settings
from django.core.cache import cache
from django.db.models import F
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Category, Product
from .serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)

# Configurar el logger
logger = logging.getLogger(__name__)


CACHE_TTL = getattr(settings, "CACHE_TTL", 60 * 5)  # 5 minutos por defecto


# --- Mixin para Lógica de Caching Reutilizable ---
class CachingMixin:
    """
    Mixin para ViewSets que añade lógica de caching para list y retrieve,
    e invalidación automática en operaciones CUD.

    - Cachea respuestas si no hay búsqueda/ordenamiento.
    - Invalida la caché tras operaciones CUD.
    - Permite definir clave base de caché.
    """

    cache_base_key: str | None = (
        None  # Debe ser definido por la subclase (ej. 'products', 'categories')
    )

    def get_cache_key_list(self, request):
        """
        Genera la clave de caché para operaciones de listado (list).
        Si hay parámetros de búsqueda, ordenamiento o filtrado, no usa caché.
        """
        # Get query parameters that affect the result
        search = request.query_params.get("search", "")
        ordering = request.query_params.get("ordering", "")
        category = request.query_params.get("category__slug", "")

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
        """Lista objetos usando caché si no hay parámetros de búsqueda."""
        cache_key = self.get_cache_key_list(request)

        if cache_key is None:
            logger.debug(f"Bypassing cache for {self.cache_base_key} list")
            return super().list(request, *args, **kwargs)

        cached_data = cache.get(cache_key)

        if cached_data:
            logger.debug(f"Cache HIT: {self.cache_base_key} list")
            return Response(cached_data)

        response = super().list(request, *args, **kwargs)

        if response.data is not None:
            try:
                cache.set(cache_key, response.data, timeout=CACHE_TTL)
                cache_keys = cache.get(f"{self.cache_base_key}_list_keys", set())
                if cache_key not in cache_keys:
                    cache_keys.add(cache_key)
                    cache.set(
                        f"{self.cache_base_key}_list_keys", cache_keys, timeout=None
                    )
                logger.debug(f"Cache MISS: {self.cache_base_key} list")
            except Exception as e:
                logger.error(f"Error saving {self.cache_base_key} list to cache: {e}")
        else:
            logger.warning(f"Response data is None for {self.cache_base_key} list")

        return Response(response.data)

    def retrieve(self, request, *args, **kwargs):
        """
        Devuelve el detalle de un objeto, usando caché si está disponible.
        """
        instance_id = self.kwargs[self.lookup_field]
        if self.cache_base_key == "categories":
            cache_key = f"category_detail:{instance_id}"
        else:
            cache_key = f"product_detail:{instance_id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.debug(f"Cache HIT: {self.cache_base_key} {instance_id}")
            return Response(cached_data)

        response = super().retrieve(request, *args, **kwargs)
        try:
            cache.set(cache_key, response.data, timeout=CACHE_TTL)
            logger.debug(f"Cache MISS: {self.cache_base_key} {instance_id}")
        except Exception as e:
            logger.error(
                f"Error saving {self.cache_base_key} {instance_id} to cache: {e}"
            )
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
        if self.cache_base_key == "products":
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
        """Elimina objeto e invalida caché. Previene si hay OrderItems."""
        instance_id = instance.id
        try:
            if hasattr(instance, "orderitem_set") and instance.orderitem_set.exists():
                msg = f"Cannot delete {instance} because it has related OrderItems"
                raise Exception(msg)
            super().perform_destroy(instance)
        except Exception as e:
            logger.error(f"Error deleting {self.cache_base_key} {instance_id}: {e}")
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
        if self.action in ["create", "update", "destroy", "partial_update"]:
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
    cache_base_key = "categories"


class ProductViewSet(CachingMixin, AdminOrReadOnlyViewSet):
    """ViewSet for products with caching, filtering, and custom actions."""

    queryset = Product.objects.filter(is_active=True).select_related("category")
    lookup_field = "id"
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["category__slug"]
    search_fields = ["name", "description", "sku"]
    ordering_fields = ["price", "stock"]
    ordering = ["-id"]
    cache_base_key = "products"

    def get_serializer_class(self):
        """Return serializer based on action."""
        if self.action == "list":
            return ProductListSerializer
        return ProductDetailSerializer

    def _invalidate_related_caches(self, instance_id=None):
        """Invalidate product caches including featured and discounted."""
        super()._invalidate_related_caches(instance_id)
        logger.debug("Invalidating product caches (featured, discounted).")
        cache.delete("product_featured")
        cache.delete("product_discounted")

    @action(detail=False, methods=["get"])
    def featured(self, request):
        """Get featured products with caching."""
        cache_key = "product_featured"
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.debug("Cache HIT: featured products")
            return Response(cached_data)

        products = self.get_queryset().filter(is_featured=True)
        serializer = self.get_serializer(products, many=True)
        try:
            cache.set(cache_key, serializer.data, timeout=CACHE_TTL)
            logger.debug("Cache MISS: featured products")
        except Exception as e:
            logger.error(f"Error caching featured products: {e}")
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def discounted(self, request):
        """Get discounted products with caching."""
        cache_key = "product_discounted"
        cached_data = cache.get(cache_key)

        if cached_data:
            logger.debug("Cache HIT: discounted products")
            return Response(cached_data)

        products = self.get_queryset().filter(
            discount_price__isnull=False, discount_price__lt=F("price")
        )
        serializer = self.get_serializer(products, many=True)
        try:
            cache.set(cache_key, serializer.data, timeout=CACHE_TTL)
            logger.debug("Cache MISS: discounted products")
        except Exception as e:
            logger.error(f"Error caching discounted products: {e}")
        return Response(serializer.data)

    @action(detail=False, methods=["get"], permission_classes=[IsAdminUser])
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
        from store.services import ReportsService

        report_type = request.query_params.get("type", "sales_by_category")
        limit = int(request.query_params.get("limit", 10))

        service = ReportsService()

        if report_type == "sales_by_category":
            results = service.get_sales_by_category(limit)
            return Response(results)

        elif report_type == "profit_margin":
            products = service.get_profit_margin(limit)
            serializer = self.get_serializer(products, many=True)
            return Response(serializer.data)

        elif report_type == "combined":
            categories = service.get_combined(limit)
            serializer = CategorySerializer(categories, many=True)
            return Response(serializer.data)

        return Response(
            {"error": "Invalid report type"}, status=status.HTTP_400_BAD_REQUEST
        )
