from django.db import models
from django.utils.text import slugify

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    slug = models.SlugField(unique=True, blank=True, db_index=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    featured = models.BooleanField(default=False, db_index=True)

    def delete(self, *args, **kwargs):
        # Check if any products have related OrderItems before attempting deletion
        products_with_orderitems = self.products.filter(orderitem__isnull=False).distinct()
        if products_with_orderitems.exists():
            raise Exception(f"Cannot delete category '{self.name}' because it has products with related OrderItems")
        # Delete related products first (only those without OrderItems)
        self.products.all().delete()
        super().delete(*args, **kwargs)

    class Meta:
        verbose_name_plural = 'Categories'
        indexes = [
            models.Index(fields=['name', 'is_active']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(unique=True, blank=True, db_index=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, db_index=True)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    stock = models.PositiveIntegerField(default=0, db_index=True)
    category = models.ForeignKey(Category, related_name="products", on_delete=models.PROTECT, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    is_featured = models.BooleanField(default=False, db_index=True)
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def delete(self, *args, **kwargs):
        # Delete related order items first
        self.orderitem_set.all().delete()
        super().delete(*args, **kwargs)
 
    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['name', 'category']),
            models.Index(fields=['price', 'is_active']),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.price < 0:
            raise ValidationError('Price cannot be negative')
        if self.discount_price and self.discount_price >= self.price:
            raise ValidationError('Discount price must be lower than regular price')

    def save(self, *args, **kwargs):
        self.clean()
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Order(models.Model):
    """Model representing customer orders and sales"""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    customer_name = models.CharField(max_length=100, db_index=True)
    customer_email = models.EmailField(db_index=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='pending', db_index=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.status not in dict(self._meta.get_field('status').choices):
            raise ValidationError('Invalid order status')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=['created_at', 'status']),
        ]

    def __str__(self):
        return f"Order #{self.id} - {self.customer_name}"

class OrderItem(models.Model):
    """Model representing individual items within an order"""
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE, db_index=True)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, db_index=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        indexes = [
            models.Index(fields=['order', 'product']),
            models.Index(fields=['product', 'order']),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.quantity <= 0:
            raise ValidationError('Quantity must be greater than 0')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity}x {self.product.name} (Order #{self.order.id})"
