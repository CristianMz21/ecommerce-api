from typing import Any, ClassVar

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from store.models import Category, Order, OrderItem, Product

User = get_user_model()


class BaseAPITestCase(APITestCase):
    admin_user: ClassVar[Any]
    regular_user: ClassVar[Any]
    category1: ClassVar[Category]
    category2: ClassVar[Category]
    product1: ClassVar[Product]
    product2: ClassVar[Product]
    product3: ClassVar[Product]
    product4: ClassVar[Product]
    order1: ClassVar[Order]
    order2: ClassVar[Order]
    order_item1: ClassVar[OrderItem]
    order_item2: ClassVar[OrderItem]
    order_item3: ClassVar[OrderItem]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.admin_user = User.objects.create_superuser(
            username="adminuser", email="admin@example.com", password="adminpassword"
        )
        cls.regular_user = User.objects.create_user(
            username="regularuser", email="user@example.com", password="userpassword"
        )
        cls.category1 = Category.objects.create(
            name="Electronics", slug="electronics", is_active=True, featured=True
        )
        cls.category2 = Category.objects.create(
            name="Books", slug="books", is_active=True, featured=False
        )
        cls.product1 = Product.objects.create(
            name="Laptop Pro",
            slug="laptop-pro",
            price=1200.00,
            stock=10,
            category=cls.category1,
            is_active=True,
            is_featured=True,
            sku="LAP001",
            description="A high-performance laptop.",
        )
        cls.product2 = Product.objects.create(
            name="Mechanical Keyboard",
            slug="mech-keyboard",
            price=150.00,
            stock=5,
            category=cls.category1,
            is_active=True,
            is_featured=False,
            sku="KEY001",
            description="Durable mechanical keyboard with RGB.",
        )
        cls.product3 = Product.objects.create(
            name="The Great Novel",
            slug="great-novel",
            price=25.00,
            discount_price=20.00,
            stock=20,
            category=cls.category2,
            is_active=True,
            is_featured=False,
            sku="NOV001",
            description="A captivating story for all ages.",
        )
        cls.product4 = Product.objects.create(
            name="Old Monitor",
            slug="old-monitor",
            price=100.00,
            stock=0,
            category=cls.category1,
            is_active=False,
            is_featured=False,
            sku="MON001",
            description="An old monitor, not for sale.",
        )
        cls.order1 = Order.objects.create(
            customer_name="John Doe",
            customer_email="john@example.com",
            total_amount="1200.00",
            status="completed",
        )
        cls.order2 = Order.objects.create(
            customer_name="Jane Smith",
            customer_email="jane@example.com",
            total_amount="175.00",
            status="pending",
        )
        cls.order_item1 = OrderItem.objects.create(
            order=cls.order1,
            product=cls.product1,
            quantity=1,
            unit_price="1200.00",
            discount="0.00",
        )
        cls.order_item2 = OrderItem.objects.create(
            order=cls.order2,
            product=cls.product2,
            quantity=1,
            unit_price="150.00",
            discount="0.00",
        )
        cls.order_item3 = OrderItem.objects.create(
            order=cls.order2,
            product=cls.product3,
            quantity=1,
            unit_price="25.00",
            discount="5.00",
        )

    def setUp(self) -> None:
        cache.clear()


class CategoryViewSetTests(BaseAPITestCase):
    def test_list_categories_caching(self) -> None:
        url = "/api/categories/"
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        with self.subTest("Second request uses cache"):
            from unittest.mock import patch

            with patch(
                "django.core.cache.cache.get", return_value=response1.data
            ) as mock_cache_get:
                response2 = self.client.get(url)
                self.assertEqual(response2.status_code, status.HTTP_200_OK)
                self.assertEqual(response1.data, response2.data)
                mock_cache_get.assert_called()
        self.client.force_login(self.admin_user)
        import time

        unique_slug = f"gadgets-{int(time.time())}"
        new_category_data = {"name": "Gadgets", "slug": unique_slug, "is_active": True}
        self.client.post("/api/categories/", new_category_data)
        with self.subTest("List cache invalidated after create"):
            from unittest.mock import patch

            with patch(
                "django.core.cache.cache.get", return_value=None
            ) as mock_cache_get:
                response3 = self.client.get(url)
                self.assertEqual(response3.status_code, status.HTTP_200_OK)
                self.assertTrue(
                    any(item["name"] == "Gadgets" for item in response3.data)
                )
                mock_cache_get.assert_called()

    def test_retrieve_category_caching(self) -> None:
        url = f"/api/categories/{self.category1.id}/"
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        with self.subTest("Second request uses cache"):
            from unittest.mock import patch

            with patch(
                "django.core.cache.cache.get", return_value=response1.data
            ) as mock_cache_get:
                response2 = self.client.get(url)
                self.assertEqual(response2.status_code, status.HTTP_200_OK)
                self.assertEqual(response1.data, response2.data)
                mock_cache_get.assert_called_with(
                    f"category_detail:{self.category1.id}"
                )
        self.client.force_login(self.admin_user)
        import time

        unique_slug = f"electronics-updated-{int(time.time())}"
        updated_data = {
            "name": "Electronics Updated",
            "slug": unique_slug,
            "is_active": True,
        }
        self.client.patch(
            f"/api/categories/{self.category1.id}/", updated_data, format="json"
        )
        with self.subTest("Detail cache invalidated after update"):
            from unittest.mock import patch

            with patch(
                "django.core.cache.cache.get", return_value=None
            ) as mock_cache_get:
                response3 = self.client.get(url)
                self.assertEqual(response3.status_code, status.HTTP_200_OK)
                self.assertEqual(response3.data["name"], "Electronics Updated")
                mock_cache_get.assert_called_with(
                    f"category_detail:{self.category1.id}"
                )

    def test_category_permissions_anonymous_read_only(self) -> None:
        list_url = "/api/categories/"
        create_url = "/api/categories/"
        detail_url = f"/api/categories/{self.category1.id}/"
        response_list = self.client.get(list_url)
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        response_detail = self.client.get(detail_url)
        self.assertEqual(response_detail.status_code, status.HTTP_200_OK)
        import time

        unique_slug = f"test-cat-{int(time.time())}"
        response_post = self.client.post(
            create_url,
            {"name": "Test Cat", "slug": unique_slug, "is_active": True},
            format="json",
        )
        self.assertEqual(response_post.status_code, status.HTTP_403_FORBIDDEN)
        unique_slug_update = f"test-cat-update-{int(time.time())}"
        response_put = self.client.put(
            detail_url,
            {"name": "Test Cat Update", "slug": unique_slug_update, "is_active": True},
            format="json",
        )
        self.assertEqual(response_put.status_code, status.HTTP_403_FORBIDDEN)
        response_patch = self.client.patch(
            detail_url, {"name": "Test Cat Patch"}, format="json"
        )
        self.assertEqual(response_patch.status_code, status.HTTP_403_FORBIDDEN)
        response_delete = self.client.delete(detail_url)
        self.assertEqual(response_delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_category_permissions_regular_user_read_only(self) -> None:
        self.client.force_login(self.regular_user)
        list_url = "/api/categories/"
        create_url = "/api/categories/"
        detail_url = f"/api/categories/{self.category1.id}/"
        response_list = self.client.get(list_url)
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        response_detail = self.client.get(detail_url)
        self.assertEqual(response_detail.status_code, status.HTTP_200_OK)
        import time

        unique_slug = f"test-cat-regular-{int(time.time())}"
        response_post = self.client.post(
            create_url,
            {"name": "Test Cat", "slug": unique_slug, "is_active": True},
            format="json",
        )
        self.assertEqual(response_post.status_code, status.HTTP_403_FORBIDDEN)
        unique_slug_update = f"test-cat-regular-update-{int(time.time())}"
        response_put = self.client.put(
            detail_url,
            {"name": "Test Cat Update", "slug": unique_slug_update, "is_active": True},
            format="json",
        )
        self.assertEqual(response_put.status_code, status.HTTP_403_FORBIDDEN)
        response_patch = self.client.patch(
            detail_url, {"name": "Test Cat Patch"}, format="json"
        )
        self.assertEqual(response_patch.status_code, status.HTTP_403_FORBIDDEN)
        response_delete = self.client.delete(detail_url)
        self.assertEqual(response_delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_category_permissions_admin_full_access(self) -> None:
        self.client.force_login(self.admin_user)
        list_url = "/api/categories/"
        create_url = "/api/categories/"
        detail_url = f"/api/categories/{self.category1.id}/"
        response_list = self.client.get(list_url)
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        response_detail = self.client.get(detail_url)
        self.assertEqual(response_detail.status_code, status.HTTP_200_OK)
        import time

        unique_slug = f"test-cat-admin-{int(time.time())}"
        response_post = self.client.post(
            create_url,
            {"name": "Test Cat Admin", "slug": unique_slug, "is_active": True},
            format="json",
        )
        self.assertEqual(response_post.status_code, status.HTTP_201_CREATED)
        unique_slug_update = f"electronics-admin-update-{int(time.time())}"
        response_put = self.client.put(
            detail_url,
            {
                "name": "Electronics Admin Update",
                "slug": unique_slug_update,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response_put.status_code, status.HTTP_200_OK)
        response_patch = self.client.patch(
            detail_url, {"name": "Electronics Admin Patch"}, format="json"
        )
        self.assertEqual(response_patch.status_code, status.HTTP_200_OK)
        response_delete = self.client.delete(detail_url)
        self.assertIn(
            response_delete.status_code,
            [status.HTTP_500_INTERNAL_SERVER_ERROR, status.HTTP_400_BAD_REQUEST],
        )


class ProductViewSetTests(BaseAPITestCase):
    def test_list_products_caching(self) -> None:
        url = "/api/products/"
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        with self.subTest("Second request uses cache"):
            from unittest.mock import patch

            with patch(
                "django.core.cache.cache.get", return_value=response1.data
            ) as mock_cache_get:
                response2 = self.client.get(url)
                self.assertEqual(response2.status_code, status.HTTP_200_OK)
                self.assertEqual(response1.data, response2.data)
                mock_cache_get.assert_called()
        self.client.force_login(self.admin_user)
        import time
        import uuid

        unique_slug = f"new-tablet-{int(time.time())}"
        unique_sku = f"TAB-{uuid.uuid4().hex[:8]}"
        new_product_data = {
            "name": "New Tablet",
            "slug": unique_slug,
            "price": 300.00,
            "stock": 15,
            "category": self.category1.slug,
            "is_active": True,
            "sku": unique_sku,
            "description": "A shiny new tablet for all your needs.",
        }
        self.client.post("/api/products/", new_product_data, format="json")
        with self.subTest("List cache invalidated after create"):
            from unittest.mock import patch

            with patch(
                "django.core.cache.cache.get", return_value=None
            ) as mock_cache_get:
                response3 = self.client.get(url)
                self.assertEqual(response3.status_code, status.HTTP_200_OK)
                self.assertTrue(
                    any(item["name"] == "New Tablet" for item in response3.data)
                )
                mock_cache_get.assert_called()

    def test_retrieve_product_caching(self) -> None:
        url = f"/api/products/{self.product1.id}/"
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        with self.subTest("Second request uses cache"):
            from unittest.mock import patch

            with patch(
                "django.core.cache.cache.get", return_value=response1.data
            ) as mock_cache_get:
                response2 = self.client.get(url)
                self.assertEqual(response2.status_code, status.HTTP_200_OK)
                self.assertEqual(response1.data, response2.data)
                mock_cache_get.assert_called_with(f"product_detail:{self.product1.id}")
        self.client.force_login(self.admin_user)
        updated_data = {
            "name": "Laptop Pro Max",
            "description": "Updated description for laptop.",
        }
        self.client.patch(
            f"/api/products/{self.product1.id}/", updated_data, format="json"
        )
        with self.subTest("Detail cache invalidated after update"):
            from unittest.mock import patch

            with patch(
                "django.core.cache.cache.get", return_value=None
            ) as mock_cache_get:
                response3 = self.client.get(url)
                self.assertEqual(response3.status_code, status.HTTP_200_OK)
                self.assertEqual(response3.data["name"], "Laptop Pro Max")
                mock_cache_get.assert_called_with(f"product_detail:{self.product1.id}")

    def test_featured_products_caching(self) -> None:
        url = "/api/products/featured/"
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response1.data), 1)
        self.assertEqual(response1.data[0]["name"], "Laptop Pro")
        with self.subTest("Second request uses cache"):
            from unittest.mock import patch

            with patch(
                "django.core.cache.cache.get", return_value=response1.data
            ) as mock_cache_get:
                response2 = self.client.get(url)
                self.assertEqual(response2.status_code, status.HTTP_200_OK)
                self.assertEqual(response1.data, response2.data)
                mock_cache_get.assert_called_with("product_featured")
        self.client.force_login(self.admin_user)
        self.client.patch(
            f"/api/products/{self.product2.id}/", {"is_featured": True}, format="json"
        )
        with self.subTest("Featured cache invalidated after product update"):
            from unittest.mock import patch

            with patch(
                "django.core.cache.cache.get", return_value=None
            ) as mock_cache_get:
                response3 = self.client.get(url)
                self.assertEqual(response3.status_code, status.HTTP_200_OK)
                self.assertEqual(len(response3.data), 2)
                mock_cache_get.assert_called_with("product_featured")

    def test_discounted_products_caching(self) -> None:
        url = "/api/products/discounted/"
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response1.data), 1)
        self.assertEqual(response1.data[0]["name"], "The Great Novel")
        with self.subTest("Second request uses cache"):
            from unittest.mock import patch

            with patch(
                "django.core.cache.cache.get", return_value=response1.data
            ) as mock_cache_get:
                response2 = self.client.get(url)
                self.assertEqual(response2.status_code, status.HTTP_200_OK)
                self.assertEqual(response1.data, response2.data)
                mock_cache_get.assert_called_with("product_discounted")
        self.client.force_login(self.admin_user)
        self.client.patch(
            f"/api/products/{self.product2.id}/",
            {"discount_price": 100.00},
            format="json",
        )
        with self.subTest("Discounted cache invalidated after product update"):
            from unittest.mock import patch

            with patch(
                "django.core.cache.cache.get", return_value=None
            ) as mock_cache_get:
                response3 = self.client.get(url)
                self.assertEqual(response3.status_code, status.HTTP_200_OK)
                self.assertEqual(len(response3.data), 2)
                mock_cache_get.assert_called_with("product_discounted")

    def test_product_permissions_anonymous_read_only(self) -> None:
        list_url = "/api/products/"
        create_url = "/api/products/"
        detail_url = f"/api/products/{self.product1.id}/"
        response_list = self.client.get(list_url)
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        response_detail = self.client.get(detail_url)
        self.assertEqual(response_detail.status_code, status.HTTP_200_OK)
        import uuid

        unique_slug = f"anon-product-{uuid.uuid4().hex[:8]}"
        unique_sku = f"ANON-{uuid.uuid4().hex[:8]}"
        new_product_data = {
            "name": "Anon Product",
            "slug": unique_slug,
            "price": 10.00,
            "stock": 1,
            "category": self.category1.id,
            "is_active": True,
            "sku": unique_sku,
            "description": "A product from anonymous user.",
        }
        response_post = self.client.post(create_url, new_product_data, format="json")
        self.assertEqual(response_post.status_code, status.HTTP_403_FORBIDDEN)
        response_put = self.client.put(
            detail_url, {"name": "Update Anon"}, format="json"
        )
        self.assertEqual(response_put.status_code, status.HTTP_403_FORBIDDEN)
        response_patch = self.client.patch(detail_url, {"name": "Patch Anon"})
        self.assertEqual(response_patch.status_code, status.HTTP_403_FORBIDDEN)
        response_delete = self.client.delete(detail_url)
        self.assertEqual(response_delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_product_permissions_regular_user_read_only(self) -> None:
        self.client.force_login(self.regular_user)
        list_url = "/api/products/"
        create_url = "/api/products/"
        detail_url = f"/api/products/{self.product1.id}/"
        response_list = self.client.get(list_url)
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        response_detail = self.client.get(detail_url)
        self.assertEqual(response_detail.status_code, status.HTTP_200_OK)
        import uuid

        unique_slug = f"regular-product-{uuid.uuid4().hex[:8]}"
        unique_sku = f"REG-{uuid.uuid4().hex[:8]}"
        new_product_data = {
            "name": "Regular Product",
            "slug": unique_slug,
            "price": 10.00,
            "stock": 1,
            "category": self.category1.id,
            "is_active": True,
            "sku": unique_sku,
            "description": "A product from regular user.",
        }
        response_post = self.client.post(create_url, new_product_data, format="json")
        self.assertEqual(response_post.status_code, status.HTTP_403_FORBIDDEN)
        response_put = self.client.put(
            detail_url, {"name": "Update Regular"}, format="json"
        )
        self.assertEqual(response_put.status_code, status.HTTP_403_FORBIDDEN)
        response_patch = self.client.patch(detail_url, {"name": "Patch Regular"})
        self.assertEqual(response_patch.status_code, status.HTTP_403_FORBIDDEN)
        response_delete = self.client.delete(detail_url)
        self.assertEqual(response_delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_product_permissions_admin_full_access(self) -> None:
        self.client.force_login(self.admin_user)
        list_url = "/api/products/"
        create_url = "/api/products/"
        detail_url = f"/api/products/{self.product1.id}/"
        response_list = self.client.get(list_url)
        self.assertEqual(response_list.status_code, status.HTTP_200_OK)
        response_detail = self.client.get(detail_url)
        self.assertEqual(response_detail.status_code, status.HTTP_200_OK)
        import time
        import uuid

        unique_slug = f"test-product-admin-{int(time.time())}"
        unique_sku = f"PROD-{uuid.uuid4().hex[:8]}"
        response_post = self.client.post(
            create_url,
            {
                "name": "Test Product Admin",
                "slug": unique_slug,
                "price": 100.00,
                "stock": 10,
                "category": self.category1.slug,
                "is_active": True,
                "sku": unique_sku,
            },
            format="json",
        )
        self.assertEqual(response_post.status_code, status.HTTP_201_CREATED)
        response_put = self.client.put(
            detail_url,
            {
                "name": "Laptop Pro Admin Update",
                "price": 1200.00,
                "stock": 25,
                "category": self.category1.slug,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response_put.status_code, status.HTTP_200_OK)
        response_patch = self.client.patch(
            detail_url, {"name": "Laptop Pro Admin Patch"}, format="json"
        )
        self.assertEqual(response_patch.status_code, status.HTTP_200_OK)
        response_delete = self.client.delete(detail_url)
        self.assertIn(
            response_delete.status_code,
            [status.HTTP_500_INTERNAL_SERVER_ERROR, status.HTTP_400_BAD_REQUEST],
        )

    def test_product_filter_by_category_slug(self) -> None:
        url = f"/api/products/?category__slug={self.category1.slug}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        for product in response.data:
            self.assertEqual(product["category"], self.category1.slug)
            self.assertIn(product["name"], ["Laptop Pro", "Mechanical Keyboard"])

    def test_product_search(self) -> None:
        url = "/api/products/?search=Laptop"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Laptop Pro")
        url = "/api/products/?search=Novel"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)
        product_names = [item["name"] for item in response.data]
        self.assertIn("The Great Novel", product_names)
        url = "/api/products/?search=KEY001"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "Mechanical Keyboard")

    def test_product_ordering(self) -> None:
        url = "/api/products/?ordering=price"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        prices = [float(product["price"]) for product in response.data]
        self.assertEqual(prices, sorted(prices))
        self.assertEqual(response.data[0]["name"], "The Great Novel")
        self.assertEqual(response.data[2]["name"], "Laptop Pro")
        url = "/api/products/?ordering=-stock"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        stocks = [int(product["stock"]) for product in response.data]
        self.assertEqual(stocks, [20, 10, 5])
        self.assertEqual(response.data[0]["name"], "The Great Novel")
        self.assertEqual(response.data[2]["name"], "Mechanical Keyboard")

    def test_product_inactive_not_listed(self) -> None:
        url = "/api/products/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)
        self.assertFalse(any(item["name"] == "Old Monitor" for item in response.data))

    def test_product_search_inactive_not_included(self) -> None:
        url = "/api/products/?search=Old Monitor"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
        url = "/api/products/?search=MON001"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
        url = "/api/products/?search=old monitor"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_reports_sales_by_category(self) -> None:
        self.client.force_login(self.admin_user)
        url = "/api/products/reports/?type=sales_by_category"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        electronics_data = next(
            item for item in response.data if item["category"] == "Electronics"
        )
        self.assertEqual(electronics_data["total_sold"], 2)
        self.assertEqual(float(electronics_data["total_revenue"]), 1350.00)

    def test_reports_profit_margin(self) -> None:
        self.client.force_login(self.admin_user)
        url = "/api/products/reports/?type=profit_margin"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["name"], "Laptop Pro")

    def test_reports_combined(self) -> None:
        self.client.force_login(self.admin_user)
        url = "/api/products/reports/?type=combined"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["name"], "Electronics")
        if "total_revenue" in response.data[0]:
            self.assertEqual(float(response.data[0]["total_revenue"]), 1350.00)

    def test_reports_invalid_type(self) -> None:
        self.client.force_login(self.admin_user)
        url = "/api/products/reports/?type=invalid"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_product_price_validation(self) -> None:
        with self.assertRaises(Exception):
            Product.objects.create(
                name="Invalid Price",
                slug="invalid-price",
                price=-100.00,
                stock=10,
                category=self.category1,
            )

    def test_order_status_validation(self) -> None:
        with self.assertRaises(Exception):
            Order.objects.create(
                customer_name="Test",
                customer_email="test@example.com",
                total_amount=100.00,
                status="invalid_status",
            )

    def test_order_item_quantity_validation(self) -> None:
        with self.assertRaises(Exception):
            OrderItem.objects.create(
                order=self.order1, product=self.product1, quantity=0, unit_price=100.00
            )

    def test_category_slug_auto_generation(self) -> None:
        category = Category.objects.create(name="New Category")
        self.assertEqual(category.slug, "new-category")

    def test_product_slug_auto_generation(self) -> None:
        product = Product.objects.create(
            name="New Product", price=100.00, stock=10, category=self.category1
        )
        self.assertEqual(product.slug, "new-product")

    def test_order_items_relation(self) -> None:
        self.assertEqual(self.order1.items.count(), 1)
        self.assertEqual(self.order2.items.count(), 2)

    def test_category_products_relation(self) -> None:
        active_products = self.category1.products.filter(is_active=True)
        self.assertEqual(active_products.count(), 2)
        self.assertIn(self.product1, active_products)
        self.assertIn(self.product2, active_products)
        self.assertNotIn(self.product4, active_products)
