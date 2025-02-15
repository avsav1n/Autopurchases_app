from django.contrib.auth.models import User
from rest_framework.viewsets import ModelViewSet

from autopurchases.models import Customer, Shop
from autopurchases.serializers import CustomerSerializer, ShopSerializer, UserSerializer


class CustomerView(ModelViewSet):
    serializer_class = CustomerSerializer
    queryset = Customer.objects.all()


class ShopView(ModelViewSet):
    serializer_class = ShopSerializer
    queryset = Shop.objects.all()


class UserView(ModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()
