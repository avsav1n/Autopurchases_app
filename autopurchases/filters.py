from django_filters import rest_framework as filters

from autopurchases.models import Order, Stock


class StockFilter(filters.FilterSet):
    """Class фильтра для модели Stock

    Позволяет осуществлять фильтрацию результатов HTTP-запросов путем передачи в query string
        следующих параметров:
    - price_min (int), например, .../?price_min=1000;
    - price_max (int), например, .../?price_max=1000;
    - quantity_min (int), например, .../?quantity_min=10;
    - quantity_max (int), например, .../?quantity_max=10;
    - model (str), например, .../?model=iphone;
    - name (str), например, .../?name=iphone;
    - category (str), например, .../?category=смартфоны;
    - shop (str), например, .../?shop=dns.
    """

    price = filters.RangeFilter()
    quantity = filters.RangeFilter()
    model = filters.CharFilter(field_name="product__model", lookup_expr="icontains")
    name = filters.CharFilter(field_name="product__name", lookup_expr="icontains")
    category = filters.CharFilter(field_name="product__category__name", lookup_expr="icontains")
    shop = filters.CharFilter(field_name="shop__name", lookup_expr="icontains")

    class Meta:
        model = Stock
        fields = []


class OrderFilter(filters.FilterSet):
    """Class фильтра для модели Order

    Позволяет осуществлять фильтрацию результатов HTTP-запросов путем передачи в query string
        следующих параметров:
    - status (str), например, .../?status=created;
    - created_before (date), например, .../?created_before=2025-03-31;
    - created_after (date), например, .../?created_after=2025-03-31.
    """

    status = filters.CharFilter(field_name="status", lookup_expr="icontains")
    created = filters.DateFromToRangeFilter(field_name="created_at")

    class Meta:
        model = Order
        fields = []
