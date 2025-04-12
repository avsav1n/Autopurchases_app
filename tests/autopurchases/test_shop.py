import json

import pytest
import yaml
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.mail import EmailMessage
from django_celery_results.models import TaskResult
from faker import Faker
from rest_framework.response import Response

from autopurchases.models import STATUS_CHOICES, Order, Product, Shop, Stock, User
from autopurchases.serializers import OrderSerializer, ShopSerializer, StockSerializer
from tests.utils import CustomAPIClient, sorted_list_of_dicts_by_id

pytestmark = pytest.mark.django_db


class TestGetList:
    def test_success(self, user_client: CustomAPIClient, shop_factory, url_factory):
        shops_quantity = 5
        shops: list[Shop] = shop_factory(shops_quantity)
        url: str = url_factory("shop-list")

        response: Response = user_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = response.json()
        assert api_data["count"] == shops_quantity
        db_data: list[dict] = ShopSerializer(shops, many=True).data
        for shop_info in api_data["results"]:
            assert shop_info in db_data

    def test_unauthorized_success(self, anon_client: CustomAPIClient, shop_factory, url_factory):
        shops_quantity = 5
        shops: list[Shop] = shop_factory(shops_quantity)
        url: str = url_factory("shop-list")

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = response.json()
        assert api_data["count"] == shops_quantity
        db_data: list[dict] = ShopSerializer(shops, many=True).data
        for shop_info in api_data["results"]:
            assert shop_info in db_data


class TestGetDetail:
    def test_success(self, user_client: CustomAPIClient, shop_factory, url_factory):
        shop: Shop = shop_factory()
        url: str = url_factory("shop-detail", slug=shop.slug)

        response: Response = user_client.get(url)

        assert response.status_code == 200
        api_data: dict = response.json()
        db_data: dict = ShopSerializer(shop).data
        assert api_data == db_data

    def test_unauthorized_success(self, anon_client: CustomAPIClient, shop_factory, url_factory):
        shop: Shop = shop_factory()
        url: str = url_factory("shop-detail", slug=shop.slug)

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: dict = response.json()
        db_data: dict = ShopSerializer(shop).data
        assert api_data == db_data


class TestPost:
    def test_success(self, user_client: CustomAPIClient, shop_factory, url_factory):
        shop_info: dict = shop_factory(as_dict=True)
        url: str = url_factory("shop-list")

        response: Response = user_client.post(url, data=shop_info)

        assert response.status_code == 201
        api_data: dict = response.json()
        assert api_data["name"] == shop_info["name"]
        assert len(api_data["managers"]) == 1
        assert user_client.orm_user_obj.id in api_data["managers"]
        assert user_client.orm_user_obj.shops.all()[0].name == shop_info["name"]

    def test_with_managers_success(
        self, user_client: CustomAPIClient, shop_factory, user_factory, url_factory
    ):
        users_quantity = 2
        users: list[User] = user_factory(users_quantity)
        shop_info: dict = shop_factory(as_dict=True)
        shop_info["managers"] = [user.id for user in users]
        url: str = url_factory("shop-list")

        response: Response = user_client.post(url, data=shop_info)

        assert response.status_code == 201
        api_data: dict = response.json()
        assert api_data["name"] == shop_info["name"]
        assert len(api_data["managers"]) == users_quantity + 1
        users.append(user_client.orm_user_obj)
        for user in users:
            assert user.id in api_data["managers"]
            assert user.shops.all()[0].name == shop_info["name"]

    def test_fail_unauthorized(self, anon_client: CustomAPIClient, shop_factory, url_factory):
        shop_info: dict = shop_factory(as_dict=True)
        url: str = url_factory("shop-list")

        response: Response = anon_client.post(url, data=shop_info)

        assert response.status_code == 401

    def test_fail_existing_name(self, user_client: CustomAPIClient, shop_factory, url_factory):
        shop_info: dict = shop_factory(as_dict=True)
        shop_factory(**shop_info)
        url: str = url_factory("shop-list")

        response: Response = user_client.post(url, data=shop_info)

        assert response.status_code == 400

    def test_fail_no_data(self, user_client: CustomAPIClient, url_factory):
        url: str = url_factory("shop-list")

        response: Response = user_client.post(url)

        assert response.status_code == 400


class TestPatch:
    def test_success(self, user_client: CustomAPIClient, faker: Faker, shop_factory, url_factory):
        shop: Shop = shop_factory(managers__manager=user_client.orm_user_obj)
        shop_info = {"name": faker.word()}
        url: str = url_factory("shop-detail", slug=shop.slug)

        response: Response = user_client.patch(url, data=shop_info)

        assert response.status_code == 200
        api_data: dict = response.json()
        shop.refresh_from_db(fields=["name"])
        assert api_data["name"] == shop_info["name"] == shop.name

    def test_admin_success(
        self, admin_client: CustomAPIClient, faker: Faker, shop_factory, user_factory, url_factory
    ):
        user: User = user_factory()
        shop: Shop = shop_factory(managers__manager=user)
        shop_info = {"name": faker.word()}
        url: str = url_factory("shop-detail", slug=shop.slug)

        response: Response = admin_client.patch(url, data=shop_info)

        assert response.status_code == 200
        api_data: dict = response.json()
        shop.refresh_from_db(fields=["name"])
        assert api_data["name"] == shop_info["name"] == shop.name

    def test_with_managers_success(
        self, user_client: CustomAPIClient, shop_factory, user_factory, url_factory
    ):
        users_quantity = 2
        users: list[User] = user_factory(users_quantity)
        shop: Shop = shop_factory(
            managers__manager=user_client.orm_user_obj, managers__is_owner=True
        )
        shop_info = {"managers": [user.id for user in users]}
        url: str = url_factory("shop-detail", slug=shop.slug)

        response: Response = user_client.patch(url, data=shop_info)

        assert response.status_code == 200
        api_data: dict = response.json()
        assert len(api_data["managers"]) == users_quantity + 1
        users.append(user_client.orm_user_obj)
        for user in users:
            assert user.id in api_data["managers"]
            assert user.shops.all()[0].name == api_data["name"] == shop.name

    def test_fail_unauthorized(
        self, anon_client: CustomAPIClient, faker: Faker, shop_factory, url_factory
    ):
        shop: Shop = shop_factory(no_managers=True)
        shop_info = {"name": faker.word()}
        url: str = url_factory("shop-detail", slug=shop.slug)

        response: Response = anon_client.patch(url, data=shop_info)

        assert response.status_code == 401

    def test_fail_not_manager(
        self, user_client: CustomAPIClient, faker: Faker, shop_factory, url_factory
    ):
        shop: Shop = shop_factory(no_managers=True)
        shop_info = {"name": faker.word()}
        url: str = url_factory("shop-detail", slug=shop.slug)

        response: Response = user_client.patch(url, data=shop_info)

        assert response.status_code == 403


class TestDelete:
    def test_success(self, user_client: CustomAPIClient, shop_factory, url_factory):
        shop: Shop = shop_factory(managers__manager=user_client.orm_user_obj)
        url: str = url_factory("shop-detail", slug=shop.slug)

        response: Response = user_client.delete(url)

        assert response.status_code == 204

    def test_admin_success(
        self, admin_client: CustomAPIClient, shop_factory, user_factory, url_factory
    ):
        user: User = user_factory()
        shop: Shop = shop_factory(managers__manager=user)
        url: str = url_factory("shop-detail", slug=shop.slug)

        response: Response = admin_client.delete(url)

        assert response.status_code == 204

    def test_fail_unauthorized(self, anon_client: CustomAPIClient, shop_factory, url_factory):
        shop: Shop = shop_factory(no_managers=True)
        url: str = url_factory("shop-detail", slug=shop.slug)

        response: Response = anon_client.delete(url)

        assert response.status_code == 401

    def test_fail_not_owner(self, user_client: CustomAPIClient, shop_factory, url_factory):
        shop: Shop = shop_factory(no_managers=True)
        url: str = url_factory("shop-detail", slug=shop.slug)

        response: Response = user_client.delete(url)

        assert response.status_code == 403


class TestImport:
    def test_yaml_in_body_success(self, user_client: CustomAPIClient, url_factory):
        with open("tests/test_data/shop_data.yaml", encoding="utf-8") as fr:
            shop_info: dict = yaml.safe_load(fr)
        products_quantity = len(shop_info["products"])
        shop_name = shop_info["shop"]
        url: str = url_factory("shop-import")

        response: Response = user_client.post(url, data=shop_info, content_type="application/yaml")

        assert response.status_code == 200
        api_data: dict = response.json()
        task: TaskResult = TaskResult.objects.get(task_id=api_data["task_id"])
        assert Shop.objects.filter(name=shop_name).first().name == shop_name
        assert Product.objects.count() == products_quantity
        assert task.status == "SUCCESS"

    def test_json_in_body_success(self, user_client: CustomAPIClient, url_factory):
        with open("tests/test_data/shop_data.json", encoding="utf-8") as fr:
            shop_info: dict[str, str | list[dict]] = json.load(fr)
        products_quantity = len(shop_info["products"])
        shop_name = shop_info["shop"]
        url: str = url_factory("shop-import")

        response: Response = user_client.post(url, data=shop_info)

        assert response.status_code == 200
        api_data: dict = response.json()
        task = TaskResult.objects.get(task_id=api_data["task_id"])
        assert Shop.objects.filter(name=shop_name).first().name == shop_name
        assert Product.objects.count() == products_quantity
        assert task.status == "SUCCESS"

    def test_file_yaml_in_body_success(self, user_client: CustomAPIClient, url_factory):
        with open("tests/test_data/shop_data.yaml", "rb") as fr:
            file = SimpleUploadedFile("shop_data.yaml", fr.read(), "application/yaml")
        url: str = url_factory("shop-import")

        response: Response = user_client.post(url, data={"file": file}, format="multipart")

        assert response.status_code == 200
        api_data: dict = response.json()
        task = TaskResult.objects.get(task_id=api_data["task_id"])
        assert task.status == "SUCCESS"

    def test_file_json_in_body_success(self, user_client: CustomAPIClient, url_factory):
        with open("tests/test_data/shop_data.json", "rb") as fr:
            file = SimpleUploadedFile("shop_data.json", fr.read(), "application/json")
        url: str = url_factory("shop-import")

        response: Response = user_client.post(url, data={"file": file}, format="multipart")

        assert response.status_code == 200
        api_data: dict = response.json()
        task = TaskResult.objects.get(task_id=api_data["task_id"])
        assert task.status == "SUCCESS"

    def test_fail_unauthorized(self, anon_client: CustomAPIClient, faker: Faker, url_factory):
        file = SimpleUploadedFile("shop_data.yaml", faker.binary(length=64), "application/yaml")
        url: str = url_factory("shop-import")

        response: Response = anon_client.post(url, data={"file": file}, format="multipart")

        assert response.status_code == 401

    def test_fail_invalid_content_type(
        self, user_client: CustomAPIClient, faker: Faker, url_factory
    ):
        file = SimpleUploadedFile("shop_data.yaml", faker.binary(length=64), "application/yaml")
        url: str = url_factory("shop-import")

        response: Response = user_client.post(
            url, data={"file": file}, content_type="application/xml"
        )

        assert response.status_code == 415

    def test_fail_no_file(self, user_client: CustomAPIClient, url_factory):
        url: str = url_factory("shop-import")

        response: Response = user_client.post(url, content_type="multipart/form-data")

        assert response.status_code == 400

    def test_fail_no_file_content_type(
        self, user_client: CustomAPIClient, faker: Faker, url_factory
    ):
        url: str = url_factory("shop-import")
        file = SimpleUploadedFile("shop_data.yaml", faker.binary(length=64))

        response: Response = user_client.post(url, data={"file": file}, format="multipart")

        assert response.status_code == 400


class TestExport:
    def test_yaml_success(
        self, user_client: CustomAPIClient, shop_factory, stock_factory, url_factory
    ):
        shop: Shop = shop_factory(managers__manager=user_client.orm_user_obj)
        stock: list[Stock] = stock_factory(2, shop=shop)
        products_db_data: list[dict] = [
            {key: value for key, value in product.items() if key != "shop"}
            for product in StockSerializer(stock, many=True).data
        ]
        url: str = url_factory("shop-export", slug=shop.slug)

        response: Response = user_client.get(url)

        assert response.status_code == 200
        api_data: dict = response.json()
        task = TaskResult.objects.get(task_id=api_data["task_id"])
        assert task.status == "SUCCESS"

        url: str = url_factory("download-file", task_id=api_data["task_id"])

        response: Response = user_client.get(url)

        assert response.status_code == 200
        assert "Content-Disposition" in response.headers
        assert "attachment; filename=" in response.headers["Content-Disposition"]
        assert response.accepted_media_type == "application/yaml"
        api_data: dict = yaml.safe_load(response.content)
        assert api_data["shop"] == shop.name
        assert api_data["products"] == products_db_data

    def test_json_success(
        self, user_client: CustomAPIClient, shop_factory, stock_factory, url_factory
    ):
        shop: Shop = shop_factory(managers__manager=user_client.orm_user_obj)
        stock: list[Stock] = stock_factory(2, shop=shop)
        products_db_data: list[dict] = [
            {key: value for key, value in product.items() if key != "shop"}
            for product in StockSerializer(stock, many=True).data
        ]
        url: str = url_factory("shop-export", slug=shop.slug)

        response: Response = user_client.get(url)

        assert response.status_code == 200
        api_data: dict = response.json()
        task = TaskResult.objects.get(task_id=api_data["task_id"])
        assert task.status == "SUCCESS"

        url: str = url_factory("download-file", task_id=api_data["task_id"])

        response: Response = user_client.get(url, headers={"Accept": "application/json"})

        assert response.status_code == 200
        assert "Content-Disposition" in response.headers
        assert "attachment; filename=" in response.headers["Content-Disposition"]
        assert response.accepted_media_type == "application/json"
        api_data: dict = response.json()
        assert api_data["shop"] == shop.name
        assert api_data["products"] == products_db_data

    def test_admin_success(self, admin_client: CustomAPIClient, shop_factory, url_factory):
        shop: Shop = shop_factory()
        url: str = url_factory("shop-export", slug=shop.slug)

        response: Response = admin_client.get(url)

        assert response.status_code == 200
        api_data: dict = response.json()
        task = TaskResult.objects.get(task_id=api_data["task_id"])
        assert task.status == "SUCCESS"

    def test_fail_unauthorized(self, anon_client: CustomAPIClient, shop_factory, url_factory):
        shop: Shop = shop_factory(no_managers=True)
        url: str = url_factory("shop-export", slug=shop.slug)

        response: Response = anon_client.get(url)

        assert response.status_code == 401

    def test_fail_not_manager(self, user_client: CustomAPIClient, shop_factory, url_factory):
        shop: Shop = shop_factory()
        url: str = url_factory("shop-export", slug=shop.slug)

        response: Response = user_client.get(url)

        assert response.status_code == 403


class TestGetOrders:
    def test_success(self, user_client: CustomAPIClient, shop_factory, order_factory, url_factory):
        orders_quantity = 2
        shop: Shop = shop_factory(managers__manager=user_client.orm_user_obj)
        orders: list[Order] = order_factory(orders_quantity, product__shop=shop)
        url: str = url_factory("shop-get-orders", slug=shop.slug)

        response: Response = user_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = sorted_list_of_dicts_by_id(response.json()["results"])
        db_data: list[dict] = sorted_list_of_dicts_by_id(OrderSerializer(orders, many=True).data)
        assert api_data == db_data

    def test_filter_by_status_success(
        self, user_client: CustomAPIClient, shop_factory, order_factory, url_factory
    ):
        orders_quantity = 2
        shop: Shop = shop_factory(managers__manager=user_client.orm_user_obj)
        order_factory(orders_quantity, product__shop=shop)
        assembled_orders: list[Order] = order_factory(
            orders_quantity, product__shop=shop, status="assembled"
        )
        url: str = f'{url_factory("shop-get-orders", slug=shop.slug)}?status=assembled'

        response: Response = user_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = sorted_list_of_dicts_by_id(response.json()["results"])
        db_data: list[dict] = sorted_list_of_dicts_by_id(
            OrderSerializer(assembled_orders, many=True).data
        )
        assert api_data == db_data

    def test_filter_by_created_at_success(
        self, user_client: CustomAPIClient, shop_factory, order_factory, url_factory
    ):
        shop: Shop = shop_factory(managers__manager=user_client.orm_user_obj)
        order_factory(2, product__shop=shop)
        url: str = f'{url_factory("shop-get-orders", slug=shop.slug)}?created_before=2025-03-31'

        response: Response = user_client.get(url)

        assert response.status_code == 200
        assert response.json()["results"] == []

    def test_admin_success(
        self, admin_client: CustomAPIClient, shop_factory, order_factory, url_factory
    ):
        orders_quantity = 2
        shop: Shop = shop_factory()
        orders: list[Order] = order_factory(orders_quantity, product__shop=shop)
        url: str = url_factory("shop-get-orders", slug=shop.slug)

        response: Response = admin_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = sorted_list_of_dicts_by_id(response.json()["results"])
        db_data: list[dict] = sorted_list_of_dicts_by_id(OrderSerializer(orders, many=True).data)
        assert api_data == db_data

    def test_fail_unauthorized(self, anon_client: CustomAPIClient, shop_factory, url_factory):
        shop: Shop = shop_factory()
        url: str = url_factory("shop-get-orders", slug=shop.slug)

        response: Response = anon_client.get(url)

        assert response.status_code == 401

    def test_fail_not_manager(self, user_client: CustomAPIClient, shop_factory, url_factory):
        shop: Shop = shop_factory()
        url: str = url_factory("shop-get-orders", slug=shop.slug)

        response: Response = user_client.get(url)

        assert response.status_code == 403


class TestPatchProductInStock:
    def test_success(
        self, user_client: CustomAPIClient, faker: Faker, shop_factory, stock_factory, url_factory
    ):
        shop: Shop = shop_factory(managers__manager=user_client.orm_user_obj)
        stock: Stock = stock_factory(shop=shop)
        stock_info = {"quantity": faker.pyint(), "can_buy": faker.pybool()}
        url: str = url_factory("shop-update-product-in-stock", slug=shop.slug, stock_pk=stock.id)

        response: Response = user_client.patch(url, data=stock_info)

        assert response.status_code == 200
        api_data: dict = response.json()
        stock.refresh_from_db(fields=["quantity", "can_buy"])
        assert api_data["quantity"] == stock_info["quantity"] == stock.quantity
        assert api_data["can_buy"] == stock_info["can_buy"] == stock.can_buy

    def test_admin_success(
        self, admin_client: CustomAPIClient, faker: Faker, shop_factory, stock_factory, url_factory
    ):
        shop: Shop = shop_factory()
        stock: Stock = stock_factory(shop=shop)
        stock_info = {"quantity": faker.pyint(), "can_buy": faker.pybool()}
        url: str = url_factory("shop-update-product-in-stock", slug=shop.slug, stock_pk=stock.id)

        response: Response = admin_client.patch(url, data=stock_info)

        assert response.status_code == 200
        api_data: dict = response.json()
        stock.refresh_from_db(fields=["quantity", "can_buy"])
        assert api_data["quantity"] == stock_info["quantity"] == stock.quantity
        assert api_data["can_buy"] == stock_info["can_buy"] == stock.can_buy

    def test_fail_unauthorized(
        self, anon_client: CustomAPIClient, shop_factory, stock_factory, url_factory
    ):
        shop: Shop = shop_factory()
        stock: Stock = stock_factory(shop=shop)
        url: str = url_factory("shop-update-product-in-stock", slug=shop.slug, stock_pk=stock.id)

        response: Response = anon_client.patch(url)

        assert response.status_code == 401

    def test_fail_no_stock(
        self, user_client: CustomAPIClient, faker: Faker, shop_factory, url_factory
    ):
        shop: Shop = shop_factory(managers__manager=user_client.orm_user_obj)
        stock_info = {"quantity": faker.pyint(), "can_buy": faker.pybool()}
        url: str = url_factory("shop-update-product-in-stock", slug=shop.slug, stock_pk=1)

        response: Response = user_client.patch(url, data=stock_info)

        assert response.status_code == 400

    def test_fail_not_manager(
        self, user_client: CustomAPIClient, faker: Faker, shop_factory, stock_factory, url_factory
    ):
        shop: Shop = shop_factory()
        stock: Stock = stock_factory(shop=shop)
        stock_info = {"quantity": faker.pyint(), "can_buy": faker.pybool()}

        url: str = url_factory("shop-update-product-in-stock", slug=shop.slug, stock_pk=stock.id)

        response: Response = user_client.patch(url, data=stock_info)

        assert response.status_code == 403


class TestPatchOrderStatus:
    def test_success(
        self,
        user_client: CustomAPIClient,
        faker: Faker,
        shop_factory,
        order_factory,
        url_factory,
        transactional_db,
        mailoutbox,
    ):
        shop: Shop = shop_factory(managers__manager=user_client.orm_user_obj)
        order: Order = order_factory(product__shop=shop)
        order_info = {"status": faker.random_element(STATUS_CHOICES.keys())}
        url: str = url_factory("shop-update-order", slug=shop.slug, order_pk=order.id)

        response: Response = user_client.patch(url, data=order_info)

        assert response.status_code == 200
        api_data: dict = response.json()
        order.refresh_from_db(fields=["status"])
        assert api_data["status"] == order_info["status"] == order.status
        assert len(mailoutbox) == 1
        msg: EmailMessage = mailoutbox[0]
        assert msg.to == [order.customer.email]

    def test_admin_success(
        self,
        admin_client: CustomAPIClient,
        faker: Faker,
        shop_factory,
        order_factory,
        url_factory,
        transactional_db,
        mailoutbox,
    ):
        shop: Shop = shop_factory()
        order: Order = order_factory(product__shop=shop)
        order_info = {"status": faker.random_element(STATUS_CHOICES.keys())}
        url: str = url_factory("shop-update-order", slug=shop.slug, order_pk=order.id)

        response: Response = admin_client.patch(url, data=order_info)

        assert response.status_code == 200
        api_data: dict = response.json()
        order.refresh_from_db(fields=["status"])
        assert api_data["status"] == order_info["status"] == order.status
        assert len(mailoutbox) == 1
        msg: EmailMessage = mailoutbox[0]
        assert msg.to == [order.customer.email]

    def test_fail_unauthorized(
        self, anon_client: CustomAPIClient, faker: Faker, shop_factory, order_factory, url_factory
    ):
        shop: Shop = shop_factory()
        order: Order = order_factory(product__shop=shop)
        order_info = {"status": faker.random_element(STATUS_CHOICES.keys())}
        url: str = url_factory("shop-update-order", slug=shop.slug, order_pk=order.id)

        response: Response = anon_client.patch(url, data=order_info)

        assert response.status_code == 401

    def test_fail_not_manager(
        self, user_client: CustomAPIClient, faker: Faker, shop_factory, order_factory, url_factory
    ):
        shop: Shop = shop_factory()
        order: Order = order_factory(product__shop=shop)
        order_info = {"status": faker.random_element(STATUS_CHOICES.keys())}
        url: str = url_factory("shop-update-order", slug=shop.slug, order_pk=order.id)

        response: Response = user_client.patch(url, data=order_info)

        assert response.status_code == 403

    def test_fail_invalid_status(
        self, user_client: CustomAPIClient, shop_factory, order_factory, url_factory
    ):
        shop: Shop = shop_factory(managers__manager=user_client.orm_user_obj)
        order: Order = order_factory(product__shop=shop)
        order_info = {"status": "invalid_status"}
        url: str = url_factory("shop-update-order", slug=shop.slug, order_pk=order.id)

        response: Response = user_client.patch(url, data=order_info)

        assert response.status_code == 400

    def test_fail_update_delivery_address(
        self,
        user_client: CustomAPIClient,
        faker: Faker,
        shop_factory,
        order_factory,
        contact_factory,
        url_factory,
    ):
        shop: Shop = shop_factory(managers__manager=user_client.orm_user_obj)
        order: Order = order_factory(product__shop=shop)
        order_info = {
            "status": faker.random_element(STATUS_CHOICES.keys()),
            "delivery_address": contact_factory(as_dict=True),
        }
        url: str = url_factory("shop-update-order", slug=shop.slug, order_pk=order.id)

        response: Response = user_client.patch(url, data=order_info)

        assert response.status_code == 400
