from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TypedDict

from django.db.models import Avg, Count, Exists, F, FloatField, OuterRef, Sum
from django.db.models.functions import Coalesce

from store.models import Category, OrderItem, Product


class SalesByCategory(TypedDict):
    category: str
    total_sold: float
    total_revenue: float


class ProfitMargin(TypedDict):
    id: int
    name: str
    price: Decimal
    total_sold: float
    total_revenue: float
    cost_price: float
    profit_margin: float


class CategoryPerformance(TypedDict):
    name: str
    product_count: int
    total_sold: float
    avg_price: float
    total_revenue: float


@dataclass
class ReportFilters:
    limit: int = 10
    start_date: datetime | None = None
    end_date: datetime | None = None
    category_id: int | None = None


class ReportsService:
    """Business logic for analytics reports."""

    def get_sales_by_category(self, filters: ReportFilters) -> list[SalesByCategory]:
        """Sales totals and revenue per category using Django ORM."""
        validated = self._validate_filters(filters)
        queryset = OrderItem.objects.values("product__category__name").annotate(
            total_sold=Sum("quantity"),
            total_revenue=Sum(F("quantity") * F("unit_price")),
        )
        if validated.start_date:
            queryset = queryset.filter(order__created_at__gte=validated.start_date)
        if validated.end_date:
            queryset = queryset.filter(order__created_at__lte=validated.end_date)
        if validated.category_id:
            queryset = queryset.filter(product__category_id=validated.category_id)
        results = list(
            queryset.order_by("-total_sold")[: validated.limit].values(
                "product__category__name", "total_sold", "total_revenue"
            )
        )
        return [
            {
                "category": row["product__category__name"],
                "total_sold": float(row["total_sold"] or 0),
                "total_revenue": float(row["total_revenue"] or 0),
            }
            for row in results
        ]

    def get_profit_margin(self, filters: ReportFilters) -> list[ProfitMargin]:
        """Products ordered by profit margin using Django ORM."""
        validated = self._validate_filters(filters)
        queryset = Product.objects.annotate(
            total_sold=Coalesce(
                Sum(
                    "orderitem__quantity",
                    filter=Exists(
                        OrderItem.objects.filter(
                            order__created_at__gte=validated.start_date,
                            order__created_at__lte=validated.end_date,
                        )
                        if validated.start_date or validated.end_date
                        else OrderItem.objects.all()
                    ),
                    output_field=FloatField(),
                ),
                0.0,
            ),
            total_revenue=Coalesce(
                Sum(
                    F("orderitem__quantity") * F("orderitem__unit_price"),
                    filter=Exists(
                        OrderItem.objects.filter(
                            order__created_at__gte=validated.start_date,
                            order__created_at__lte=validated.end_date,
                        )
                        if validated.start_date or validated.end_date
                        else OrderItem.objects.all()
                    ),
                    output_field=FloatField(),
                ),
                0.0,
            ),
        ).order_by("-price")
        if validated.category_id:
            queryset = queryset.filter(category_id=validated.category_id)
        products = list(queryset[: validated.limit])
        results: list[ProfitMargin] = []
        for product in products:
            total_rev = float(product.total_revenue or 0)
            total_sold = float(product.total_sold or 0)
            price_val = float(product.price)
            if total_rev == 0 or price_val == 0:
                profit_margin = 0.0
                cost_price = 0.0
            else:
                cost_price = price_val * 0.7
                profit_margin = ((price_val - cost_price) / price_val) * 100.0
            results.append(
                {
                    "id": product.id,
                    "name": product.name,
                    "price": product.price,
                    "total_sold": total_sold,
                    "total_revenue": total_rev,
                    "cost_price": cost_price,
                    "profit_margin": profit_margin,
                }
            )
        results.sort(key=lambda x: x["profit_margin"], reverse=True)
        return results[: validated.limit]

    def get_combined(self, filters: ReportFilters) -> list[CategoryPerformance]:
        """Combined category performance using Django ORM."""
        validated = self._validate_filters(filters)
        date_filter = {}
        if validated.start_date:
            date_filter["products__orderitem__order__created_at__gte"] = (
                validated.start_date
            )
        if validated.end_date:
            date_filter["products__orderitem__order__created_at__lte"] = (
                validated.end_date
            )
        queryset = Category.objects.annotate(
            product_count=Count(
                "products",
                filter=Exists(Product.objects.filter(category=OuterRef("pk")))
                if date_filter
                else None,
            ),
            total_sold=Coalesce(
                Sum(
                    "products__orderitem__quantity",
                    filter=Exists(
                        OrderItem.objects.filter(
                            order__created_at__gte=validated.start_date,
                            order__created_at__lte=validated.end_date,
                        )
                        if validated.start_date and validated.end_date
                        else OrderItem.objects.all()
                    ),
                    output_field=FloatField(),
                ),
                0.0,
            ),
            avg_price=Avg(
                "products__price",
                filter=Exists(Product.objects.filter(category=OuterRef("pk"))),
            ),
            total_revenue=Coalesce(
                Sum(
                    F("products__orderitem__quantity")
                    * F("products__orderitem__unit_price"),
                    output_field=FloatField(),
                ),
                0.0,
            ),
        )
        if validated.category_id:
            queryset = queryset.filter(id=validated.category_id)
        categories = list(queryset[: validated.limit])
        results: list[CategoryPerformance] = []
        for cat in categories:
            avg_p = float(cat.avg_price or 0)
            results.append(
                {
                    "name": cat.name,
                    "product_count": cat.product_count or 0,
                    "total_sold": float(cat.total_sold or 0),
                    "avg_price": avg_p,
                    "total_revenue": float(cat.total_revenue or 0),
                }
            )
        results.sort(key=lambda x: x["total_revenue"], reverse=True)
        return results[: validated.limit]

    def _validate_filters(self, filters: ReportFilters) -> ReportFilters:
        """Validate and normalize report filters."""
        from django.core.exceptions import ValidationError

        if filters.limit < 1 or filters.limit > 100:
            raise ValidationError("limit must be between 1 and 100")
        if (
            filters.start_date
            and filters.end_date
            and filters.end_date < filters.start_date
        ):
            raise ValidationError("end_date must be after start_date")
        if filters.category_id:
            if not Category.objects.filter(id=filters.category_id).exists():
                raise ValidationError(
                    f"category_id {filters.category_id} does not exist"
                )
        return filters
