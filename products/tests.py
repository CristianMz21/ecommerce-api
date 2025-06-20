from rest_framework.test import APITestCase
from rest_framework import status
from .models import Category, Product

class ProductAPITests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Pruebas", description="Test")
        self.product_data = {
            "name": "Producto Test",
            "description": "Descripción prueba",
            "price": 100.00,
            "stock": 5,
            "category": self.category.id
        }

    def test_create_product(self):
        response = self.client.post("/api/products/products/", self.product_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Product.objects.count(), 1)

    def test_get_products(self):
        Product.objects.create(**self.product_data)
        response = self.client.get("/api/products/products/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_update_product(self):
        product = Product.objects.create(**self.product_data)
        update_data = self.product_data.copy()
        update_data["name"] = "Producto Editado"
        response = self.client.put(f"/api/products/products/{product.id}/", update_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Producto Editado")

    def test_delete_product(self):
        product = Product.objects.create(**self.product_data)
        response = self.client.delete(f"/api/products/products/{product.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
