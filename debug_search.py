#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce_api.settings')
django.setup()

from store.models import Product, Category
from django.contrib.auth.models import User

# Create test data
User.objects.all().delete()
Product.objects.all().delete()
Category.objects.all().delete()

category1 = Category.objects.create(name='Electronics', slug='electronics', is_active=True, featured=True)
product1 = Product.objects.create(
    name='Laptop Pro', slug='laptop-pro', price=1200.00, stock=10,
    category=category1, is_active=True, is_featured=True, sku='LAP001',
    description='A high-performance laptop.'
)
product2 = Product.objects.create(
    name='Mechanical Keyboard', slug='mech-keyboard', price=150.00, stock=5,
    category=category1, is_active=True, is_featured=False, sku='KEY001',
    description='Durable mechanical keyboard with RGB.'
)

print("Products created:")
for p in Product.objects.all():
    print(f"ID: {p.id}, Name: {p.name}, Description: {p.description}")

print("\nSearch for 'mechanical':")
from django.db.models import Q
results = Product.objects.filter(
    Q(name__icontains='mechanical') | 
    Q(description__icontains='mechanical') | 
    Q(sku__icontains='mechanical')
).order_by('-id')
for p in results:
    print(f"ID: {p.id}, Name: {p.name}")

print("\nSearch for 'keyboard':")
results = Product.objects.filter(
    Q(name__icontains='keyboard') | 
    Q(description__icontains='keyboard') | 
    Q(sku__icontains='keyboard')
).order_by('-id')
for p in results:
    print(f"ID: {p.id}, Name: {p.name}")