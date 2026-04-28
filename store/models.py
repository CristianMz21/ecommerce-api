from typing import Any

from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    slug = models.SlugField(unique=True, blank=True, db_index=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    featured = models.BooleanField(default=False, db_index=True)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        products_with_orderitems = self.products.filter(
            orderitem__isnull=False
        ).distinct()
        if products_with_orderitems.exists():
            raise Exception(
                f"Cannot delete category '{self.name}' — has products with OrderItems"
            )
        self.products.all().delete()
        return super().delete(*args, **kwargs)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name_plural = "Categories"
        indexes = [
            models.Index(fields=["name", "is_active"]),
        ]


class Product(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(unique=True, blank=True, db_index=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, db_index=True)
    discount_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    stock = models.PositiveIntegerField(default=0, db_index=True)
    category = models.ForeignKey(
        Category, related_name="products", on_delete=models.PROTECT, db_index=True
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    sku = models.CharField(
        max_length=50, unique=True, blank=True, null=True, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        self.orderitem_set.all().delete()
        return super().delete(*args, **kwargs)

    def clean(self) -> None:
        from django.core.exceptions import ValidationError

        if self.price < 0:
            raise ValidationError("Price cannot be negative")
        if self.discount_price and self.discount_price >= self.price:
            raise ValidationError("Discount price must be lower than regular price")

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["name", "category"]),
            models.Index(fields=["price", "is_active"]),
        ]


class Order(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    customer_name = models.CharField(max_length=100, db_index=True)
    customer_email = models.EmailField(db_index=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        db_index=True,
    )

    def clean(self) -> None:
        from django.core.exceptions import ValidationError
        from django.db.models.fields import CharField

        status_field = self._meta.get_field("status")
        assert isinstance(status_field, CharField)
        assert status_field.choices is not None
        valid_statuses = {item[0] for item in status_field.choices}
        if self.status not in valid_statuses:
            raise ValidationError("Invalid order status")

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Order #{self.id} - {self.customer_name}"

    class Meta:
        indexes = [
            models.Index(fields=["created_at", "status"]),
        ]


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, related_name="items", on_delete=models.CASCADE, db_index=True
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, db_index=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def clean(self) -> None:
        from django.core.exceptions import ValidationError

        if self.quantity <= 0:
            raise ValidationError("Quantity must be greater than 0")

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.quantity}x {self.product.name} (Order #{self.order.id})"

    class Meta:
        indexes = [
            models.Index(fields=["order", "product"]),
            models.Index(fields=["product", "order"]),
        ]
