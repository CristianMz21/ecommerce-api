from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.cache import cache
from django.contrib.auth import get_user_model
from unittest.mock import patch # Importar patch para mocking
import time # Importar para generar slugs/skus únicos
import uuid # Importar para generar slugs/skus únicos

from store.models import Category, Product # Ajusta 'store' si tu app se llama diferente

User = get_user_model() # Obtiene el modelo de usuario activo (Django's default User)

# --- Base de Pruebas con Configuración de Datos ---
class BaseAPITestCase(APITestCase):
    """
    Clase base para pruebas de API que configura datos comunes y usuarios.
    """
    @classmethod
    def setUpTestData(cls):
        """
        Configura los datos de prueba que se usarán en todas las pruebas de la clase.
        Se ejecuta solo una vez por clase.
        """
        # Crear usuarios de prueba
        cls.admin_user = User.objects.create_superuser(
            username='adminuser',
            email='admin@example.com',
            password='adminpassword'
        )
        cls.regular_user = User.objects.create_user(
            username='regularuser',
            email='user@example.com',
            password='userpassword'
        )

        # Crear categorías de prueba
        cls.category1 = Category.objects.create(name='Electronics', slug='electronics', is_active=True, featured=True)
        cls.category2 = Category.objects.create(name='Books', slug='books', is_active=True, featured=False)

        # Crear productos de prueba, incluyendo un campo 'description'
        cls.product1 = Product.objects.create(
            name='Laptop Pro', slug='laptop-pro', price=1200.00, stock=10,
            category=cls.category1, is_active=True, is_featured=True, sku='LAP001',
            description='A high-performance laptop.'
        )
        cls.product2 = Product.objects.create(
            name='Mechanical Keyboard', slug='mech-keyboard', price=150.00, stock=5,
            category=cls.category1, is_active=True, is_featured=False, sku='KEY001',
            description='Durable mechanical keyboard with RGB.'
        )
        cls.product3 = Product.objects.create(
            name='The Great Novel', slug='great-novel', price=25.00, discount_price=20.00, stock=20,
            category=cls.category2, is_active=True, is_featured=False, sku='NOV001',
            description='A captivating story for all ages.'
        )
        cls.product4 = Product.objects.create( # Inactive product
            name='Old Monitor', slug='old-monitor', price=100.00, stock=0,
            category=cls.category1, is_active=False, is_featured=False, sku='MON001',
            description='An old monitor, not for sale.'
        )

    def setUp(self):
        """
        Se ejecuta antes de cada método de prueba.
        Asegura que la caché esté limpia antes de cada prueba que la use.
        """
        cache.clear() # Limpia la caché para asegurar un estado inicial predecible

# --- Pruebas para CategoryViewSet ---
class CategoryViewSetTests(BaseAPITestCase):
    def test_list_categories_caching(self):
        url = reverse('category-list')

        # Primera solicitud - debería ir a la DB y cachear
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Simular que el cache.get() ahora devolverá datos para la segunda llamada
        with patch('django.core.cache.cache.get', return_value=response1.data) as mock_cache_get:
            response2 = self.client.get(url)
            self.assertEqual(response2.status_code, status.HTTP_200_OK)
            self.assertEqual(response1.data, response2.data)
            mock_cache_get.assert_called_with('categories_list:')
        # Ahora probamos la invalidación de caché al crear una categoría
        self.client.force_login(self.admin_user)
        unique_slug = f'gadgets-{int(time.time())}' # Generar slug único
        new_category_data = {'name': 'Gadgets', 'slug': unique_slug, 'is_active': True}
        create_url = reverse('category-list')
        self.client.post(create_url, new_category_data)
        
        with self.subTest("List cache invalidated after create"):
            with patch('django.core.cache.cache.get', return_value=None) as mock_cache_get:
                response3 = self.client.get(url)
                self.assertEqual(response3.status_code, status.HTTP_200_OK)
                # Verifica que 'Gadgets' esté en la nueva respuesta de la lista
                self.assertTrue(any(item['name'] == 'Gadgets' for item in response3.data))
                mock_cache_get.assert_called_with('categories_list:')

    def test_retrieve_category_caching(self):
        url = reverse('category-detail', args=[self.category1.id])

        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        with patch('django.core.cache.cache.get', return_value=response1.data) as mock_cache_get:
            response2 = self.client.get(url)
            self.assertEqual(response2.status_code, status.HTTP_200_OK)
            self.assertEqual(response1.data, response2.data)
            mock_cache_get.assert_called_with(f'category_detail:{self.category1.id}')
        # Probar invalidación al actualizar
        self.client.force_login(self.admin_user)
        unique_slug = f'electronics-updated-{int(time.time())}'
        update_url = reverse('category-detail', args=[self.category1.id])
        updated_data = {'name': 'Electronics Updated', 'slug': unique_slug, 'is_active': True}
        self.client.patch(update_url, updated_data, format='json')

        with self.subTest("Detail cache invalidated after update"):
            with patch('django.core.cache.cache.get', return_value=None) as mock_cache_get:
                response3 = self.client.get(url)
                self.assertEqual(response3.status_code, status.HTTP_200_OK)
                self.assertEqual(response3.data['name'], 'Electronics Updated')
                mock_cache_get.assert_called_with(f'category_detail:{self.category1.id}')

    # --- Pruebas de Permisos para CategoryViewSet ---
    def test_category_permissions_anonymous_read_only(self):
        list_url = reverse('category-list')
        create_url = reverse('category-list')
        detail_url = reverse('category-detail', args=[self.category1.id])
        
        # GET (allowed)
        response_list = self.client.get(list_url)
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        response_detail = self.client.get(detail_url)
        self.assertEqual(response_detail.status_code, status.HTTP_200_OK)

        # POST (denied)
        unique_slug = f'test-cat-{int(time.time())}'
        response_post = self.client.post(create_url, {'name': 'Test Cat', 'slug': unique_slug, 'is_active': True}, format='json')
        self.assertEqual(response_post.status_code, status.HTTP_403_FORBIDDEN) # Anonymous cannot create

        # PUT/PATCH/DELETE (denied)
        unique_slug_update = f'test-cat-update-{int(time.time())}'
        response_put = self.client.put(detail_url, {'name': 'Test Cat Update', 'slug': unique_slug_update, 'is_active': True}, format='json')
        self.assertEqual(response_put.status_code, status.HTTP_403_FORBIDDEN)
        response_patch = self.client.patch(detail_url, {'name': 'Test Cat Patch'}, format='json')
        self.assertEqual(response_patch.status_code, status.HTTP_403_FORBIDDEN)
        response_delete = self.client.delete(detail_url)
        self.assertEqual(response_delete.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_category_permissions_regular_user_read_only(self):
        self.client.force_login(self.regular_user)
        list_url = reverse('category-list')
        create_url = reverse('category-list')
        detail_url = reverse('category-detail', args=[self.category1.id])

        # GET (allowed)
        response_list = self.client.get(list_url)
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        response_detail = self.client.get(detail_url)
        self.assertEqual(response_detail.status_code, status.HTTP_200_OK)

        # POST (denied)
        unique_slug = f'test-cat-regular-{int(time.time())}'
        response_post = self.client.post(create_url, {'name': 'Test Cat', 'slug': unique_slug, 'is_active': True}, format='json')
        self.assertEqual(response_post.status_code, status.HTTP_403_FORBIDDEN) # Regular user cannot create

        # PUT/PATCH/DELETE (denied)
        unique_slug_update = f'test-cat-regular-update-{int(time.time())}'
        response_put = self.client.put(detail_url, {'name': 'Test Cat Update', 'slug': unique_slug_update, 'is_active': True}, format='json')
        self.assertEqual(response_put.status_code, status.HTTP_403_FORBIDDEN)
        response_patch = self.client.patch(detail_url, {'name': 'Test Cat Patch'}, format='json')
        self.assertEqual(response_patch.status_code, status.HTTP_403_FORBIDDEN)
        response_delete = self.client.delete(detail_url)
        self.assertEqual(response_delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_category_permissions_admin_full_access(self):
        self.client.force_login(self.admin_user)
        list_url = reverse('category-list')
        create_url = reverse('category-list')
        detail_url = reverse('category-detail', args=[self.category1.id])

        # GET (allowed)
        response_list = self.client.get(list_url)
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        response_detail = self.client.get(detail_url)
        self.assertEqual(response_detail.status_code, status.HTTP_200_OK)

        # POST (allowed)
        unique_slug = f'test-cat-admin-{int(time.time())}'
        response_post = self.client.post(create_url, {'name': 'Test Cat Admin', 'slug': unique_slug, 'is_active': True}, format='json')
        self.assertEqual(response_post.status_code, status.HTTP_201_CREATED) # Admin can create

        # PUT/PATCH/DELETE (allowed)
        unique_slug_update = f'electronics-admin-update-{int(time.time())}'
        response_put = self.client.put(detail_url, {'name': 'Electronics Admin Update', 'slug': unique_slug_update, 'is_active': True}, format='json')
        self.assertEqual(response_put.status_code, status.HTTP_200_OK)
        response_patch = self.client.patch(detail_url, {'name': 'Electronics Admin Patch'}, format='json')
        self.assertEqual(response_patch.status_code, status.HTTP_200_OK)
        response_delete = self.client.delete(detail_url)
        self.assertEqual(response_delete.status_code, status.HTTP_204_NO_CONTENT)

# --- Pruebas para ProductViewSet ---
class ProductViewSetTests(BaseAPITestCase):
    def test_list_products_caching(self):
        url = reverse('product-list')

        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        with patch('django.core.cache.cache.get', return_value=response1.data) as mock_cache_get:
            response2 = self.client.get(url)
            self.assertEqual(response2.status_code, status.HTTP_200_OK)
            self.assertEqual(response1.data, response2.data)
            mock_cache_get.assert_called_with('products_list:')
        # Invalida cache al crear
        self.client.force_login(self.admin_user)
        unique_slug = f'new-tablet-{int(time.time())}'
        unique_sku = f'TAB-{uuid.uuid4().hex[:8]}'
        new_product_data = {
            'name': 'New Tablet', 'slug': unique_slug, 'price': 300.00, 'stock': 15,
            'category': self.category1.slug, 'is_active': True, 'sku': unique_sku,
            'description': 'A shiny new tablet for all your needs.'
        }
        create_url = reverse('product-list')
        self.client.post(create_url, new_product_data, format='json')

        with self.subTest("List cache invalidated after create"):
            with patch('django.core.cache.cache.get', return_value=None) as mock_cache_get:
                response3 = self.client.get(url)
                self.assertEqual(response3.status_code, status.HTTP_200_OK)
                self.assertTrue(any(item['name'] == 'New Tablet' for item in response3.data))
                mock_cache_get.assert_called_with('products_list:')


    def test_retrieve_product_caching(self):
        url = reverse('product-detail', args=[self.product1.id])

        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        with patch('django.core.cache.cache.get', return_value=response1.data) as mock_cache_get:
            response2 = self.client.get(url)
            self.assertEqual(response2.status_code, status.HTTP_200_OK)
            self.assertEqual(response1.data, response2.data)
            mock_cache_get.assert_called_with(f'product_detail:{self.product1.id}')
        # Probar invalidación al actualizar
        self.client.force_login(self.admin_user)
        update_url = reverse('product-detail', args=[self.product1.id])
        updated_data = {'name': 'Laptop Pro Max', 'description': 'Updated description for laptop.'}
        self.client.patch(update_url, updated_data, format='json')

        with self.subTest("Detail cache invalidated after update"):
            with patch('django.core.cache.cache.get', return_value=None) as mock_cache_get:
                response3 = self.client.get(url)
                self.assertEqual(response3.status_code, status.HTTP_200_OK)
                self.assertEqual(response3.data['name'], 'Laptop Pro Max')
                mock_cache_get.assert_called_with(f'product_detail:{self.product1.id}')
    
    def test_featured_products_caching(self):
        url = reverse('product-featured')

        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response1.data), 1) # Only product1 is featured
        self.assertEqual(response1.data[0]['name'], 'Laptop Pro')

        with patch('django.core.cache.cache.get', return_value=response1.data) as mock_cache_get:
            response2 = self.client.get(url)
            self.assertEqual(response2.status_code, status.HTTP_200_OK)
            self.assertEqual(response1.data, response2.data)
            mock_cache_get.assert_called_with('product_featured')
        # Invalida cache al crear/actualizar un producto
        self.client.force_login(self.admin_user)
        # Make product2 featured to invalidate cache
        update_url = reverse('product-detail', args=[self.product2.id])
        self.client.patch(update_url, {'is_featured': True}, format='json')

        with self.subTest("Featured cache invalidated after product update"):
            with patch('django.core.cache.cache.get', return_value=None) as mock_cache_get:
                response3 = self.client.get(url)
                self.assertEqual(response3.status_code, status.HTTP_200_OK)
                self.assertEqual(len(response3.data), 2) # Now product1 and product2 should be featured
                mock_cache_get.assert_called_with('product_featured')

    def test_discounted_products_caching(self):
        url = reverse('product-discounted')

        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response1.data), 1) # Only product3 has a discount
        self.assertEqual(response1.data[0]['name'], 'The Great Novel')

        with patch('django.core.cache.cache.get', return_value=response1.data) as mock_cache_get:
            response2 = self.client.get(url)
            self.assertEqual(response2.status_code, status.HTTP_200_OK)
            self.assertEqual(response1.data, response2.data)
            mock_cache_get.assert_called_with('product_discounted')
        # Invalida cache al crear/actualizar un producto
        self.client.force_login(self.admin_user)
        # Add a discount to product2
        update_url = reverse('product-detail', args=[self.product2.id])
        self.client.patch(update_url, {'discount_price': 100.00}, format='json')

        with self.subTest("Discounted cache invalidated after product update"):
            with patch('django.core.cache.cache.get', return_value=None) as mock_cache_get:
                response3 = self.client.get(url)
                self.assertEqual(response3.status_code, status.HTTP_200_OK)
                self.assertEqual(len(response3.data), 2) # Now product2 and product3 should be discounted
                mock_cache_get.assert_called_with('product_discounted')

    # --- Pruebas de Permisos para ProductViewSet ---
    def test_product_permissions_anonymous_read_only(self):
        list_url = reverse('product-list')
        create_url = reverse('product-list')
        detail_url = reverse('product-detail', args=[self.product1.id])
        
        # GET (allowed)
        response_list = self.client.get(list_url)
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        response_detail = self.client.get(detail_url)
        self.assertEqual(response_detail.status_code, status.HTTP_200_OK)

        # POST (denied)
        unique_slug = f'anon-product-{uuid.uuid4().hex[:8]}'
        unique_sku = f'ANON-{uuid.uuid4().hex[:8]}'
        new_product_data = {
            'name': 'Anon Product', 'slug': unique_slug, 'price': 10.00,
            'stock': 1, 'category': self.category1.id, 'is_active': True, 'sku': unique_sku,
            'description': 'A product from anonymous user.'
        }
        response_post = self.client.post(create_url, new_product_data, format='json')
        self.assertEqual(response_post.status_code, status.HTTP_403_FORBIDDEN)

        # PUT/PATCH/DELETE (denied)
        response_put = self.client.put(detail_url, {'name': 'Update Anon'}, format='json')
        self.assertEqual(response_put.status_code, status.HTTP_403_FORBIDDEN)
        response_patch = self.client.patch(detail_url, {'name': 'Patch Anon'})
        self.assertEqual(response_patch.status_code, status.HTTP_403_FORBIDDEN)
        response_delete = self.client.delete(detail_url)
        self.assertEqual(response_delete.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_product_permissions_regular_user_read_only(self):
        self.client.force_login(self.regular_user)
        list_url = reverse('product-list')
        create_url = reverse('product-list')
        detail_url = reverse('product-detail', args=[self.product1.id])

        # GET (allowed)
        response_list = self.client.get(list_url)
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        response_detail = self.client.get(detail_url)
        self.assertEqual(response_detail.status_code, status.HTTP_200_OK)

        # POST (denied)
        unique_slug = f'regular-product-{uuid.uuid4().hex[:8]}'
        unique_sku = f'REG-{uuid.uuid4().hex[:8]}'
        new_product_data = {
            'name': 'Regular Product', 'slug': unique_slug, 'price': 10.00,
            'stock': 1, 'category': self.category1.id, 'is_active': True, 'sku': unique_sku,
            'description': 'A product from regular user.'
        }
        response_post = self.client.post(create_url, new_product_data, format='json')
        self.assertEqual(response_post.status_code, status.HTTP_403_FORBIDDEN)

        # PUT/PATCH/DELETE (denied)
        response_put = self.client.put(detail_url, {'name': 'Update Regular'}, format='json')
        self.assertEqual(response_put.status_code, status.HTTP_403_FORBIDDEN)
        response_patch = self.client.patch(detail_url, {'name': 'Patch Regular'})
        self.assertEqual(response_patch.status_code, status.HTTP_403_FORBIDDEN)
        response_delete = self.client.delete(detail_url)
        self.assertEqual(response_delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_product_permissions_admin_full_access(self):
        self.client.force_login(self.admin_user)
        list_url = reverse('product-list')
        create_url = reverse('product-list')
        detail_url = reverse('product-detail', args=[self.product1.id])

        # GET (allowed)
        response_list = self.client.get(list_url)
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        response_detail = self.client.get(detail_url)
        self.assertEqual(response_detail.status_code, status.HTTP_200_OK)

        # POST (allowed)
        unique_slug = f'admin-product-{uuid.uuid4().hex[:8]}'
        unique_sku = f'ADM-{uuid.uuid4().hex[:8]}'
        new_product_data = {
            'name': 'Admin Product', 'slug': unique_slug, 'price': 50.00, 'stock': 5,
            'category': self.category1.slug, 'is_active': True, 'sku': unique_sku,
            'description': 'Description for admin product.'
        }
        response_post = self.client.post(create_url, new_product_data, format='json')
        self.assertEqual(response_post.status_code, status.HTTP_201_CREATED)

        # PUT/PATCH/DELETE (allowed)
        unique_slug_update = f'laptop-pro-admin-update-{uuid.uuid4().hex[:8]}'
        unique_sku_update = f'LAPUPD-{uuid.uuid4().hex[:8]}'
        response_put = self.client.put(detail_url, {
            'name': 'Laptop Pro Admin Update', 'slug': unique_slug_update, 'price': 1300.00,
            'stock': 8, 'category': self.category1.slug, 'is_active': True, 'sku': unique_sku_update,
            'description': 'Updated description by admin.'
        }, format='json')
        self.assertEqual(response_put.status_code, status.HTTP_200_OK)
        response_patch = self.client.patch(detail_url, {'name': 'Laptop Pro Admin Patch', 'description': 'Patched by admin.'}, format='json')
        self.assertEqual(response_patch.status_code, status.HTTP_200_OK)
        response_delete = self.client.delete(detail_url)
        self.assertEqual(response_delete.status_code, status.HTTP_204_NO_CONTENT)
    # --- Pruebas de Filtrado, Búsqueda y Ordenamiento ---
    def test_product_filter_by_category_slug(self):
        url = reverse('product-list') + f'?category__slug={self.category1.slug}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Only active products should be returned. product4 is inactive.
        self.assertEqual(len(response.data), 2) # product1, product2
        for product in response.data:
            self.assertEqual(product['category'], self.category1.slug) # Check category slug
            self.assertIn(product['name'], ['Laptop Pro', 'Mechanical Keyboard'])
    def test_product_search(self):
        url = reverse('product-list') + '?search=Laptop'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Laptop Pro')

        url = reverse('product-list') + '?search=keyboard' # search by description
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Mechanical Keyboard')

        url = reverse('product-list') + '?search=KEY001' # search by SKU
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Mechanical Keyboard')

    def test_product_ordering(self):
        # Order by price ascending (default is descending id)
        url = reverse('product-list') + '?ordering=price'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3) # product1, product2, product3 (all active)
        # Expected order: The Great Novel (25.00), Mechanical Keyboard (150.00), Laptop Pro (1200.00)
        self.assertEqual(response.data[0]['name'], 'The Great Novel')
        self.assertEqual(response.data[1]['name'], 'Mechanical Keyboard')
        self.assertEqual(response.data[2]['name'], 'Laptop Pro')

        # Order by stock descending
        url = reverse('product-list') + '?ordering=-stock'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        # Expected order: The Great Novel (20), Laptop Pro (10), Mechanical Keyboard (5)
        self.assertEqual(response.data[0]['name'], 'The Great Novel')
        self.assertEqual(response.data[1]['name'], 'Laptop Pro')
        self.assertEqual(response.data[2]['name'], 'Mechanical Keyboard')

    def test_product_inactive_not_listed(self):
        url = reverse('product-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3) # Only product1, product2, product3 (active)
        self.assertFalse(any(item['name'] == 'Old Monitor' for item in response.data))

    def test_product_search_inactive_not_included(self):
        # Search for an inactive product by name
        url = reverse('product-list') + '?search=Old Monitor'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0) # No inactive products should be returned

        # Search for an inactive product by SKU
        url = reverse('product-list') + '?search=MON001'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0) # No inactive products should be returned

        # Search for an inactive product by description
        url = reverse('product-list') + '?search=old monitor'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0) # No inactive products should be returned
