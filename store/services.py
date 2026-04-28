from django.db import connection
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Sum
from django.db.models.functions import Coalesce

from store.models import Category, Product


class ReportsService:
    """Business logic for analytics reports."""

    def get_sales_by_category(self, limit: int) -> list[dict[str, float]]:
        """
        Sales totals and revenue per category.
        Returns list of dicts with keys: category, total_sold, total_revenue.
        """
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
            return [
                {"category": row[0], "total_sold": row[1], "total_revenue": row[2]}
                for row in cursor.fetchall()
            ]

    def get_profit_margin(self, limit: int) -> list[Product]:
        """
        Products ordered by profit margin (descending).
        Assumes 30% cost margin (cost_price = price * 0.7).
        """
        return list(
            Product.objects.annotate(
                total_sold=Coalesce(
                    Sum("orderitem__quantity", output_field=FloatField()),
                    0.0,
                ),
                total_revenue=Coalesce(
                    Sum(
                        ExpressionWrapper(
                            F("orderitem__quantity") * F("orderitem__unit_price"),
                            output_field=FloatField(),
                        )
                    ),
                    0.0,
                ),
                cost_price=ExpressionWrapper(
                    F("price") * 0.7,
                    output_field=FloatField(),
                ),
                profit_margin=ExpressionWrapper(
                    (F("price") - F("cost_price")) / F("price") * 100.0,
                    output_field=FloatField(),
                ),
            ).order_by("-profit_margin")[:limit]
        )

    def get_combined(self, limit: int) -> list[Category]:
        """
        Combined category performance: product count, total sold,
        average price, and total revenue.
        """
        return list(
            Category.objects.annotate(
                product_count=Count("products"),
                total_sold=Coalesce(
                    Sum("products__orderitem__quantity", output_field=FloatField()),
                    0.0,
                ),
                avg_price=Avg("products__price", output_field=FloatField()),
                total_revenue=Coalesce(
                    Sum(
                        ExpressionWrapper(
                            F("products__orderitem__quantity")
                            * F("products__orderitem__unit_price"),
                            output_field=FloatField(),
                        )
                    ),
                    0.0,
                ),
            ).order_by("-total_revenue")[:limit]
        )
