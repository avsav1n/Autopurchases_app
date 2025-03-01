from pprint import pp

import yaml
from django.db import transaction
from rest_framework import status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import ListAPIView, ListCreateAPIView
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework_yaml.parsers import YAMLParser

from autopurchases.models import Category, Contact, Product, Shop, Stock, User
from autopurchases.permissions import IsManagerOrAdminOrReadOnly, IsMeOrAdmin
from autopurchases.serializers import (
    ContactSerializer,
    EmailAuthTokenSerializer,
    ProductSerializer,
    ShopSerializer,
    UserSerializer,
)


class UserViewSet(ModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()
    permission_classes = [IsMeOrAdmin]

    @action(methods=["POST"], detail=True, url_path="contacts", url_name="create-contact")
    def create_contact(self, request: Request, pk: int):
        user: User = self.get_object()
        data: dict[str, str] = request.data
        contact_ser = ContactSerializer(data=data, context={"request": self.request})
        contact_ser.is_valid(raise_exception=True)
        contact_ser.save()

        user_ser = UserSerializer(user)
        return Response(user_ser.data)

    @action(
        methods=["DELETE"],
        detail=True,
        url_path="contacts/(?P<contact_pk>[^/.]+)",
        url_name="delete-contact",
    )
    def delete_contact(self, request: Request, pk: int, contact_pk: int):
        user: User = self.get_object()
        contact: Contact = user.contacts.filter(pk=int(contact_pk)).first()
        if contact is None:
            return Response(
                {
                    "error": f"Записи о контактах с id={contact_pk} у пользователя с id={pk} не найдено"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        contact.delete()

        user_ser = UserSerializer(user)
        return Response(user_ser.data)


class ShopView(ModelViewSet):
    main_model = Shop
    serializer_class = ShopSerializer
    queryset = main_model.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly, IsManagerOrAdminOrReadOnly]

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @action(methods=["POST"], detail=False, url_path="import", url_name="import")
    @transaction.atomic
    def import_shop_from_file(self, request: Request):
        data: dict[str, str | list[dict]] = request.data

        shop_info: str = data["shop"]
        shop_ser = ShopSerializer(data=shop_info, context={"request": self.request})
        shop_ser.is_valid(raise_exception=True)
        shop_ser.save()

        products_info: list[dict] = data["products"]
        products_ser = ProductSerializer(
            data=products_info,
            many=True,
            context={"request": self.request, "shop": shop_ser.instance},
        )
        products_ser.is_valid(raise_exception=True)
        products_ser.save()

        repr = {"shop": shop_ser.data["name"], "products": products_ser.data}
        return Response(repr)

    @action(methods=["GET"], detail=True, url_path="export", url_name="export")
    def export_shop_to_file(self, request: Request, pk: int):
        shop: Shop = self.get_object()
        products: list[Product] = shop.products.all()

        shop_ser = ShopSerializer(shop, context={"request": self.request})
        products_ser = ProductSerializer(
            products,
            many=True,
            context={"request": self.request, "shop": shop_ser.instance},
        )

        repr = {"shop": shop_ser.data["name"], "products": products_ser.data}
        return Response(repr)


class EmailObtainAuthToken(ObtainAuthToken):
    serializer_class = EmailAuthTokenSerializer
