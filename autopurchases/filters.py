from django_filters import rest_framework as filters

from autopurchases.models import Order, Stock


class StockFilter(filters.FilterSet):
    price = filters.RangeFilter()
    quantity = filters.RangeFilter()
    model = filters.CharFilter(field_name="product__model", lookup_expr="icontains")
    name = filters.CharFilter(field_name="product__name", lookup_expr="icontains")
    category = filters.CharFilter(field_name="product__category__name", lookup_expr="icontains")
    shop = filters.CharFilter(field_name="shop__name", lookup_expr="icontains")

    class Meta:
        model = Stock
        fields = []


class OrderFilter(filters.Filter):
    status = filters.CharFilter(field_name="status", lookup_expr="icontains")
    created = filters.DateFromToRangeFilter(field_name="created_at")

    class Meta:
        model = Order
        fields = []
