import pytest
from faker import Faker
from rest_framework.response import Response

from autopurchases.models import Stock
from autopurchases.serializers import StockSerializer
from tests.utils import CustomAPIClient, sorted_list_of_dicts_by_id

pytestmark = pytest.mark.django_db


class TestGetList:
    def test_success(self, anon_client: CustomAPIClient, stock_factory, url_factory):
        stock_quantity = 5
        products: list[Stock] = stock_factory(stock_quantity)
        url: str = url_factory("stock")

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = sorted_list_of_dicts_by_id(response.json()["results"])
        db_data: list[dict] = sorted_list_of_dicts_by_id(StockSerializer(products, many=True).data)
        assert api_data == db_data

    def test_filter_by_price_success(
        self, anon_client: CustomAPIClient, faker: Faker, stock_factory, url_factory
    ):
        stock_quantity = 3
        stock_factory(stock_quantity, price=faker.pyint(max_value=500, min_value=1))
        products: list[Stock] = stock_factory(stock_quantity, price=faker.pyint(min_value=501))
        url: str = f'{url_factory("stock")}?price_min=501'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = sorted_list_of_dicts_by_id(response.json()["results"])
        db_data: list[dict] = sorted_list_of_dicts_by_id(StockSerializer(products, many=True).data)
        assert api_data == db_data

    def test_filter_by_quantity_success(
        self, anon_client: CustomAPIClient, faker: Faker, stock_factory, url_factory
    ):
        stock_quantity = 3
        stock_factory(stock_quantity, quantity=faker.pyint(max_value=50, min_value=1))
        products: list[Stock] = stock_factory(
            stock_quantity, quantity=faker.pyint(min_value=51, max_value=100)
        )
        stock_factory(stock_quantity, quantity=faker.pyint(min_value=101))
        url: str = f'{url_factory("stock")}?quantity_min=51&quantity_max=100'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = sorted_list_of_dicts_by_id(response.json()["results"])
        db_data: list[dict] = sorted_list_of_dicts_by_id(StockSerializer(products, many=True).data)
        assert api_data == db_data

    def test_filter_by_model_success(
        self, anon_client: CustomAPIClient, stock_factory, url_factory
    ):
        stock_quantity = 3
        products: list[Stock] = stock_factory(stock_quantity)
        target_product: Stock = products[0]
        url: str = f'{url_factory("stock")}?model={target_product.product.model}'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = response.json()["results"]
        db_data: list[dict] = StockSerializer(target_product).data
        assert api_data == [db_data]

    def test_filter_by_name_success(self, anon_client: CustomAPIClient, stock_factory, url_factory):
        stock_quantity = 3
        products: list[Stock] = stock_factory(stock_quantity)
        target_product: Stock = products[0]
        url: str = f'{url_factory("stock")}?name={target_product.product.name}'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = response.json()["results"]
        db_data: list[dict] = StockSerializer(target_product).data
        assert api_data == [db_data]

    def test_filter_by_category_success(
        self, anon_client: CustomAPIClient, stock_factory, url_factory
    ):
        stock_quantity = 3
        products: list[Stock] = stock_factory(stock_quantity)
        target_product: Stock = products[0]
        url: str = f'{url_factory("stock")}?category={target_product.product.category.name}'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = response.json()["results"]
        db_data: list[dict] = StockSerializer(target_product).data
        assert api_data == [db_data]

    def test_filter_by_shop_success(self, anon_client: CustomAPIClient, stock_factory, url_factory):
        stock_quantity = 3
        products: list[Stock] = stock_factory(stock_quantity)
        target_product: Stock = products[0]
        url: str = f'{url_factory("stock")}?shop={target_product.shop.name}'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = response.json()["results"]
        db_data: list[dict] = StockSerializer(target_product).data
        assert api_data == [db_data]

    def test_ordering_by_price_success(
        self, anon_client: CustomAPIClient, stock_factory, url_factory
    ):
        stock_quantity = 3
        products: list[Stock] = stock_factory(stock_quantity)
        url: str = f'{url_factory("stock")}?ordering=price'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = response.json()["results"]
        db_data: list[dict] = sorted(
            StockSerializer(products, many=True).data, key=lambda x: x["price"]
        )
        assert api_data == db_data

    def test_ordering_by_quantity_success(
        self, anon_client: CustomAPIClient, stock_factory, url_factory
    ):
        stock_quantity = 3
        products: list[Stock] = stock_factory(stock_quantity)
        url: str = f'{url_factory("stock")}?ordering=-quantity'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = response.json()["results"]
        db_data: list[dict] = sorted(
            StockSerializer(products, many=True).data, key=lambda x: x["quantity"], reverse=True
        )
        assert api_data == db_data

    def test_searching_by_model_success(
        self, anon_client: CustomAPIClient, stock_factory, url_factory
    ):
        stock_quantity = 3
        products: list[Stock] = stock_factory(stock_quantity)
        target_product: Stock = products[0]
        url: str = f'{url_factory("stock")}?search={target_product.product.model}'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = response.json()["results"]
        db_data: list[dict] = StockSerializer(target_product).data
        assert api_data == [db_data]

    def test_searching_by_name_success(
        self, anon_client: CustomAPIClient, stock_factory, url_factory
    ):
        stock_quantity = 3
        products: list[Stock] = stock_factory(stock_quantity)
        target_product: Stock = products[0]
        url: str = f'{url_factory("stock")}?search={target_product.product.name}'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = response.json()["results"]
        db_data: list[dict] = StockSerializer(target_product).data
        assert api_data == [db_data]

    def test_searching_by_category_success(
        self, anon_client: CustomAPIClient, stock_factory, url_factory
    ):
        stock_quantity = 3
        products: list[Stock] = stock_factory(stock_quantity)
        target_product: Stock = products[0]
        url: str = f'{url_factory("stock")}?category={target_product.product.category.name}'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = response.json()["results"]
        db_data: dict = StockSerializer(target_product).data
        assert api_data == [db_data]

    def test_searching_by_shop_success(
        self, anon_client: CustomAPIClient, stock_factory, url_factory
    ):
        stock_quantity = 3
        products: list[Stock] = stock_factory(stock_quantity)
        target_product: Stock = products[0]
        url: str = f'{url_factory("stock")}?shop={target_product.shop.name}'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = response.json()["results"]
        db_data: dict = StockSerializer(target_product).data
        assert api_data == [db_data]
