import pytest
from rest_framework.response import Response

from autopurchases.models import Order
from autopurchases.serializers import OrderSerializer
from tests.utils import CustomAPIClient, sorted_list_of_dicts_by_id

pytestmark = pytest.mark.django_db


class TestGetList:
    def test_success(self, user_client: CustomAPIClient, order_factory, url_factory):
        orders_quantity = 3
        orders: list[Order] = order_factory(orders_quantity, customer=user_client.orm_user_obj)
        url: str = url_factory("order")

        response: Response = user_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = sorted_list_of_dicts_by_id(response.json()["results"])
        db_data: list[dict] = sorted_list_of_dicts_by_id(OrderSerializer(orders, many=True).data)
        assert api_data == db_data

    def test_filter_by_status_success(
        self, user_client: CustomAPIClient, order_factory, url_factory
    ):
        orders_quantity = 3
        order_factory(orders_quantity, customer=user_client.orm_user_obj)
        assembled_orders: list[Order] = order_factory(
            orders_quantity, customer=user_client.orm_user_obj, status="assembled"
        )
        url: str = f'{url_factory("order")}?status=assembled'

        response: Response = user_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = sorted_list_of_dicts_by_id(response.json()["results"])
        db_data: list[dict] = sorted_list_of_dicts_by_id(
            OrderSerializer(assembled_orders, many=True).data
        )
        assert api_data == db_data

    def test_filter_by_created_at_success(
        self, user_client: CustomAPIClient, order_factory, url_factory
    ):
        orders_quantity = 3
        order_factory(orders_quantity, customer=user_client.orm_user_obj)
        url: str = f'{url_factory("order")}?created_before=2025-03-31'

        response: Response = user_client.get(url)

        assert response.status_code == 200
        assert response.json()["results"] == []

    def test_fail_unauthorized(self, anon_client: CustomAPIClient, url_factory):
        url: str = url_factory("order")

        response: Response = anon_client.get(url)

        assert response.status_code == 401
