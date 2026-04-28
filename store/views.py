from datetime import datetime
from typing import Any, cast

from django.core.cache import cache
from django.db.models import F
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import (
    BasePermission,
    IsAdminUser,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer, Serializer

from store.models import Category, Product
from store.serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)
from store.services import ReportFilters, ReportsService

logger = __import__("logging").getLogger(__name__)

CACHE_TTL = getattr(
    __import__("django.conf", fromlist=["settings"]).settings, "CACHE_TTL", 60 * 5
)


class CachingMixin:
    cache_base_key: str | None = None

    def get_cache_key_list(self, request: Request) -> str | None:
        search = request.query_params.get("search", "")
        ordering = request.query_params.get("ordering", "")
        category = request.query_params.get("category__slug", "")
        if search or ordering or category:
            return None
        return f"{self.cache_base_key}_list:"

    def get_cache_key_detail(self, instance_id: int | str) -> str:
        return f"{self.cache_base_key}_detail:{instance_id}"

    def _invalidate_list_caches(self) -> None:
        list_cache_keys = cache.get(f"{self.cache_base_key}_list_keys", set())
        for key in list_cache_keys:
            cache.delete(key)
        cache.delete(f"{self.cache_base_key}_list_keys")

    def _invalidate_detail_cache(self, instance_id: int | str) -> None:
        cache.delete(f"{self.cache_base_key}_detail:{instance_id}")


class AdminOrReadOnlyViewSet(viewsets.ModelViewSet[Any]):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_permissions(self) -> list[BasePermission]:
        if self.action in ["create", "update", "destroy", "partial_update"]:
            return [IsAdminUser()]
        raw = super().get_permissions()
        return cast(list[BasePermission], list(raw))


class CategoryViewSet(CachingMixin, AdminOrReadOnlyViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    cache_base_key = "categories"

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
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

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance_id = self.kwargs[self.lookup_field]
        cache_key = f"category_detail:{instance_id}"
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

    def perform_create(self, serializer: BaseSerializer[Category]) -> None:
        super().perform_create(serializer)
        self._invalidate_list_caches()

    def perform_update(self, serializer: BaseSerializer[Category]) -> None:
        super().perform_update(serializer)
        self._invalidate_list_caches()

    def perform_destroy(self, instance: Category) -> None:
        instance_id = instance.id
        try:
            if hasattr(instance, "orderitem_set") and instance.orderitem_set.exists():
                msg = f"Cannot delete {instance} because it has related OrderItems"
                raise Exception(msg)
            super().perform_destroy(instance)
        except Exception as e:
            logger.error(f"Error deleting {self.cache_base_key} {instance_id}: {e}")
            raise ValidationError(str(e))
        self._invalidate_detail_cache(instance_id)
        self._invalidate_list_caches()


class ProductViewSet(CachingMixin, AdminOrReadOnlyViewSet):
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

    def get_serializer_class(self) -> type[Serializer[Any]]:
        if self.action == "list":
            return ProductListSerializer
        return ProductDetailSerializer

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
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

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance_id = self.kwargs[self.lookup_field]
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

    def perform_create(self, serializer: BaseSerializer[Product]) -> None:
        super().perform_create(serializer)
        self._invalidate_list_caches()
        cache.delete("product_featured")
        cache.delete("product_discounted")

    def perform_update(self, serializer: BaseSerializer[Product]) -> None:
        super().perform_update(serializer)
        self._invalidate_list_caches()
        cache.delete("product_featured")
        cache.delete("product_discounted")

    def perform_destroy(self, instance: Product) -> None:
        instance_id = instance.id
        try:
            if hasattr(instance, "orderitem_set") and instance.orderitem_set.exists():
                msg = f"Cannot delete {instance} because it has related OrderItems"
                raise Exception(msg)
            super().perform_destroy(instance)
        except Exception as e:
            logger.error(f"Error deleting {self.cache_base_key} {instance_id}: {e}")
            raise ValidationError(str(e))
        self._invalidate_detail_cache(instance_id)
        self._invalidate_list_caches()
        cache.delete("product_featured")
        cache.delete("product_discounted")

    @action(detail=False, methods=["get"])
    def featured(self, request: Request) -> Response:
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
    def discounted(self, request: Request) -> Response:
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
    def reports(self, request: Request) -> Response:
        report_type = request.query_params.get("type", "sales_by_category")
        filters = self._parse_report_filters(request)
        service = ReportsService()
        if report_type == "sales_by_category":
            return Response(service.get_sales_by_category(filters))
        elif report_type == "profit_margin":
            return Response(service.get_profit_margin(filters))
        elif report_type == "combined":
            return Response(service.get_combined(filters))
        return Response(
            {"error": "Invalid report type"}, status=status.HTTP_400_BAD_REQUEST
        )

    def _parse_report_filters(self, request: Request) -> ReportFilters:
        """Parse query params into ReportFilters dataclass."""
        limit_str = request.query_params.get("limit", "10")
        try:
            limit = int(limit_str)
        except ValueError:
            raise ValidationError("limit must be a valid integer")
        start_date: datetime | None = None
        end_date: datetime | None = None
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        if start_date_str:
            try:
                start_date = datetime.fromisoformat(start_date_str)
            except ValueError:
                raise ValidationError(
                    "start_date must be valid ISO format (YYYY-MM-DD)"
                )
        if end_date_str:
            try:
                end_date = datetime.fromisoformat(end_date_str)
            except ValueError:
                raise ValidationError("end_date must be valid ISO format (YYYY-MM-DD)")
        category_id_str = request.query_params.get("category_id")
        category_id: int | None = None
        if category_id_str:
            try:
                category_id = int(category_id_str)
            except ValueError:
                raise ValidationError("category_id must be a valid integer")
        return ReportFilters(
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
        )
