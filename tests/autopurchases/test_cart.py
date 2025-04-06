import pytest
from django.db.models import QuerySet
from rest_framework.response import Response

from autopurchases.models import Cart, Order, Stock, User
from autopurchases.serializers import (
    CartSerializer,
    OrderSerializer,
)
from tests.utils import CustomAPIClient

pytestmark = pytest.mark.django_db


class TestGetList:
    def test_success(self, user_client: CustomAPIClient, cart_factory, url_factory):
        cart_quantity = 2
        cart_factory(cart_quantity)
        cart: list[Cart] = cart_factory(cart_quantity, customer=user_client.orm_user_obj)
        url: str = url_factory("cart-list")

        response: Response = user_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = sorted(response.json()["results"], key=lambda x: x["id"])
        db_data: list[dict] = sorted(CartSerializer(cart, many=True).data, key=lambda x: x["id"])
        assert api_data == db_data

    def test_fail_unauthorized(self, anon_client: CustomAPIClient, url_factory):
        url: str = url_factory("cart-list")

        response: Response = anon_client.get(url)

        assert response.status_code == 401


class TestGetDetail:
    def test_success(self, user_client: CustomAPIClient, cart_factory, url_factory):
        cart_quantity = 2
        cart: list[Cart] = cart_factory(cart_quantity, customer=user_client.orm_user_obj)
        target_product: Cart = cart[0]
        url: str = url_factory("cart-detail", pk=target_product.id)

        response: Response = user_client.get(url)

        assert response.status_code == 200
        api_data: dict = response.json()
        db_data: dict = CartSerializer(target_product).data
        assert api_data == db_data

    def test_fail_not_owner(self, user_client: CustomAPIClient, cart_factory, url_factory):
        cart_quantity = 2
        cart: list[Cart] = cart_factory(cart_quantity)
        target_product: Cart = cart[0]
        url: str = url_factory("cart-detail", pk=target_product.id)

        response: Response = user_client.get(url)

        assert response.status_code == 404


class TestPost:
    def test_success(self, user_client: CustomAPIClient, stock_factory, url_factory):
        stock: Stock = stock_factory()
        product_quantity = stock.quantity // 2
        cart_info = {"product": stock.id, "quantity": product_quantity}
        url: str = url_factory("cart-list")

        response: Response = user_client.post(url, data=cart_info)

        assert response.status_code == 201
        api_data: dict = response.json()
        assert api_data["total_price"] == product_quantity * stock.price
        assert api_data["quantity"] == product_quantity
        assert api_data["customer"] == user_client.orm_user_obj.email

    def test_fail_product_unavailable_for_order(
        self, user_client: CustomAPIClient, stock_factory, url_factory
    ):
        stock: Stock = stock_factory(can_buy=False)
        product_quantity = stock.quantity // 2
        cart_info = {"product": stock.id, "quantity": product_quantity}
        url: str = url_factory("cart-list")

        response: Response = user_client.post(url, data=cart_info)

        assert response.status_code == 400

    def test_fail_not_enough_product_in_stock(
        self, user_client: CustomAPIClient, stock_factory, url_factory
    ):
        stock: Stock = stock_factory()
        product_quantity = stock.quantity + 1
        cart_info = {"product": stock.id, "quantity": product_quantity}
        url: str = url_factory("cart-list")

        response: Response = user_client.post(url, data=cart_info)

        assert response.status_code == 400

    def test_fail_unauthorized(self, anon_client: CustomAPIClient, stock_factory, url_factory):
        stock: Stock = stock_factory()
        product_quantity = stock.quantity // 2
        cart_info = {"product": stock.id, "quantity": product_quantity}
        url: str = url_factory("cart-list")

        response: Response = anon_client.post(url, data=cart_info)

        assert response.status_code == 401


class TestPatch:
    def test_success(self, user_client: CustomAPIClient, cart_factory, url_factory):
        cart: Cart = cart_factory(customer=user_client.orm_user_obj)
        product_quantity = cart.product.quantity // 2
        cart_info = {"quantity": product_quantity}
        url: str = url_factory("cart-detail", pk=cart.id)

        response: Response = user_client.patch(url, data=cart_info)

        assert response.status_code == 200
        api_data: dict = response.json()
        assert api_data["total_price"] == product_quantity * cart.product.price
        assert api_data["quantity"] == product_quantity
        assert api_data["customer"] == user_client.orm_user_obj.email

    def test_fail_not_enough_product_in_stock(
        self, user_client: CustomAPIClient, cart_factory, url_factory
    ):
        cart: Cart = cart_factory(customer=user_client.orm_user_obj)
        product_quantity = cart.product.quantity + 1
        cart_info = {"quantity": product_quantity}
        url: str = url_factory("cart-detail", pk=cart.id)

        response: Response = user_client.patch(url, data=cart_info)

        assert response.status_code == 400

    def test_fail_not_users_cart(self, user_client: CustomAPIClient, cart_factory, url_factory):
        cart: Cart = cart_factory()
        product_quantity = cart.product.quantity // 2
        cart_info = {"quantity": product_quantity}
        url: str = url_factory("cart-detail", pk=cart.id)

        response: Response = user_client.patch(url, data=cart_info)

        assert response.status_code == 404


class TestDelete:
    def test_success(self, user_client: CustomAPIClient, cart_factory, url_factory):
        cart: Cart = cart_factory(customer=user_client.orm_user_obj)
        url: str = url_factory("cart-detail", pk=cart.id)

        response: Response = user_client.delete(url)

        assert response.status_code == 204

    def test_fail_not_users_cart(self, user_client: CustomAPIClient, cart_factory, url_factory):
        cart: Cart = cart_factory()
        url: str = url_factory("cart-detail", pk=cart.id)

        response: Response = user_client.delete(url)

        assert response.status_code == 404


class TestConfirmOrder:
    def test_success(
        self, user_client: CustomAPIClient, cart_factory, contact_factory, url_factory
    ):
        cart_quantity = 2
        user: User = user_client.orm_user_obj
        cart_factory(cart_quantity, customer=user)
        order_info = {"delivery_address": contact_factory(as_dict=True)}
        url: str = url_factory("cart-confirm-order")

        response: Response = user_client.post(url, data=order_info)

        assert response.status_code == 201
        api_data: list[dict] = sorted(response.json(), key=lambda x: x["id"])
        assert len(api_data) == cart_quantity
        for order in api_data:
            assert order["delivery_address"] == order_info["delivery_address"]
            assert order["customer"] == user.email
        orders: QuerySet[Order] = Order.objects.filter(customer=user)
        db_data: list[dict] = sorted(OrderSerializer(orders, many=True).data, key=lambda x: x["id"])
        assert api_data == db_data

    def test_fail_empty_cart(
        self, user_client: CustomAPIClient, cart_factory, contact_factory, url_factory
    ):
        order_info = {"delivery_address": contact_factory(as_dict=True)}
        url: str = url_factory("cart-confirm-order")

        response: Response = user_client.post(url, data=order_info)

        assert response.status_code == 404

    def test_fail_few_products_unavailable_for_order(
        self, user_client: CustomAPIClient, cart_factory, contact_factory, url_factory
    ):
        cart_quantity = 2
        user: User = user_client.orm_user_obj
        unavailable_products: list[Cart] = cart_factory(
            cart_quantity, customer=user, product__can_buy=False
        )
        cart_factory(cart_quantity, customer=user)
        order_info = {"delivery_address": contact_factory(as_dict=True)}
        url: str = url_factory("cart-confirm-order")

        response: Response = user_client.post(url, data=order_info)

        assert response.status_code == 201
        api_data: list[dict] = sorted(response.json(), key=lambda x: x["id"])
        assert len(api_data) == cart_quantity
        for order in api_data:
            assert order["delivery_address"] == order_info["delivery_address"]
            assert order["customer"] == user.email
        orders: QuerySet[Order] = Order.objects.filter(customer=user)
        db_data: list[dict] = sorted(OrderSerializer(orders, many=True).data, key=lambda x: x["id"])
        assert api_data == db_data
        cart: QuerySet[Cart] = Cart.objects.filter(customer=user)
        assert list(cart) == unavailable_products

    def test_fail_all_products_unavailable_for_order(
        self, user_client: CustomAPIClient, cart_factory, contact_factory, url_factory
    ):
        cart_quantity = 2
        user: User = user_client.orm_user_obj
        cart_factory(cart_quantity, customer=user, product__can_buy=False)
        order_info = {"delivery_address": contact_factory(as_dict=True)}
        url: str = url_factory("cart-confirm-order")

        response: Response = user_client.post(url, data=order_info)

        assert response.status_code == 409

    def test_fail_no_delivery_address(
        self, user_client: CustomAPIClient, cart_factory, url_factory
    ):
        cart_quantity = 2
        user: User = user_client.orm_user_obj
        cart_factory(cart_quantity, customer=user)
        url: str = url_factory("cart-confirm-order")

        response: Response = user_client.post(url)

        assert response.status_code == 400
