import json
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from pprint import pp

import yaml
from celery.result import AsyncResult
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Prefetch, QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView, ListCreateAPIView
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from rest_framework_yaml.parsers import YAMLParser
from rest_framework_yaml.renderers import YAMLRenderer

from autopurchases.filters import OrderFilter, StockFilter
from autopurchases.models import (
    Category,
    Contact,
    Order,
    Parameter,
    PasswordResetToken,
    Product,
    ProductsParameters,
    Shop,
    Stock,
    User,
)
from autopurchases.permissions import (
    IsAdminOrReadOnly,
    IsCartOwnerOrAdmin,
    IsManagerOrAdmin,
    IsManagerOrAdminOrReadOnly,
    IsMeOrAdmin,
)
from autopurchases.serializers import (
    CartSerialaizer,
    ContactSerializer,
    EmailAuthTokenSerializer,
    EmailSerializer,
    OrderSerializer,
    PasswordResetSerializer,
    ProductSerializer,
    ShopSerializer,
    StockSerializer,
    UserSerializer,
)
from autopurchases.tasks import export_shop, import_shop


class UserViewSet(ModelViewSet):
    """View-class для работы с профилем пользователя.

    Для работы требуется аутентификация пользователя.

    Поддерживаемые HTTP-методы:
    - GET-list: Получение информации о всех зарегистрированных пользователях.
    - GET-detail: Получение информации о конкретном пользователе.
    - POST: Регистрация нового пользователя. Для этого необходимо передать email (str) и
        пароль (str).
        Пример тела запроса (в формате JSON):
            {
                "email": str,
                "password": str,
                "username": str,  # опционально
                "phone": str      # опционально
            }
    - PATCH: Изменение профиля пользователя.
    - DELETE: Удаление профиля пользователя.
    - POST /<int:user.id>/contacts/: Создание и добавление информации о контакте пользователя
        (адреса доставки). Для этого необходимо передать название города (str), улицы (str),
        номер дома (int).
        Пример тела запроса (в формате JSON):
            {
                "city": str,
                "street": str,
                "house": int,
                "apartment": int  # опционально
            }
    - DELETE /<int:user.id>/contacts/<int:contact.id>/: Удаление контакта пользователя (адреса
        доставки).
    """

    serializer_class = UserSerializer
    queryset = User.objects.prefetch_related("contacts").all()
    permission_classes = [IsMeOrAdmin]

    @action(methods=["POST"], detail=True, url_path="contacts", url_name="create-contact")
    def create_contact(self, request: Request, pk: int) -> Response:
        user: User = self.get_object()
        contact_ser = ContactSerializer(data=request.data, context={"request": self.request})
        contact_ser.is_valid(raise_exception=True)
        contact_ser.save()

        user_ser = UserSerializer(user)
        return Response(user_ser.data, status=status.HTTP_201_CREATED)

    @action(
        methods=["DELETE"],
        detail=True,
        url_path="contacts/(?P<contact_pk>[^/.]+)",
        url_name="delete-contact",
    )
    def delete_contact(self, request: Request, pk: int, contact_pk: str) -> Response:
        user: User = self.get_object()
        contact: Contact | None = user.contacts.filter(pk=int(contact_pk)).first()
        if contact is None:
            return Response(
                {"error": "Only contact owners can make changes"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        contact.delete()

        user_ser = UserSerializer(user)
        return Response(user_ser.data, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=False, url_path="reset", url_name="reset-password")
    def get_password_reset_token(self, request: Request):
        email_ser = EmailSerializer(data=request.data)
        email_ser.is_valid(raise_exception=True)
        user: User = get_object_or_404(User, email=email_ser.validated_data["email"])
        PasswordResetToken.objects.update_or_create(
            user=user,
            defaults={"token": uuid.uuid4(), "exp_time": timezone.now() + timedelta(hours=1)},
        )
        return Response(
            {"message": f"Password reset token sent to {email_ser.validated_data["email"]}"},
            status=status.HTTP_200_OK,
        )

    @action(
        methods=["PATCH"],
        detail=False,
        url_path="reset/confirm",
        url_name="reset-password-confirm",
    )
    def update_password(self, request: Request):
        rtoken_ser = PasswordResetSerializer(data=request.data)
        rtoken_ser.is_valid(raise_exception=True)
        rtoken = get_object_or_404(PasswordResetToken, rtoken=rtoken_ser.validated_data["rtoken"])
        if not rtoken.is_valid():
            return Response(
                {"error": "Password reset token expired"}, status=status.HTTP_400_BAD_REQUEST
            )
        user: User = rtoken.user
        user.set_password(raw_password=rtoken_ser.validated_data["password"])
        user.save()
        return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)


class ShopViewSet(ModelViewSet):
    """FIXME"""

    serializer_class = ShopSerializer
    queryset = Shop.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly, IsManagerOrAdminOrReadOnly]

    def get_data(self, request: Request) -> dict[str, str | list[dict]]:
        content_type = request.content_type.split(";")[0]
        match content_type:
            case "multipart/form-data":
                file: BytesIO | None = request.FILES.get("file", None)
                if file is None:
                    return Response(
                        {"error": "Attachment required"}, status=status.HTTP_400_BAD_REQUEST
                    )
                match file.content_type:
                    case "application/yaml":
                        data = yaml.safe_load(file.read().decode())
                    case "application/json":
                        data = json.load(file.read().decode())
                    case _:
                        return Response(
                            {"error": "Attached file's content type required"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
            case "application/json" | "application/yaml":
                data = request.data
            case _:
                return Response(
                    {
                        "error": "Shop import is available with 'multipart/form-data', "
                        "'application/json' or 'application/yaml' content types"
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return data

    @action(
        methods=["GET"],
        detail=True,
        url_path="orders",
        url_name="orders",
        permission_classes=[IsManagerOrAdmin],
    )
    def get_shop_orders(self, request: Request, pk: int) -> Response:
        shop: Shop = self.get_object()
        orders: QuerySet[Order] = (
            Order.objects.filter(product__shop=shop).exclude(status="in_cart").all()
        )
        order_ser = OrderSerializer(orders, many=True)
        return Response(order_ser.data)

    @action(
        methods=["POST"],
        detail=False,
        url_path="import",
        url_name="import",
        parser_classes=[MultiPartParser, JSONParser, YAMLParser],
    )
    def import_shop_from_file(self, request: Request) -> Response:
        data: dict[str, str | list[dict]] = self.get_data(request=request)
        user_id: int = request.user.id
        task: AsyncResult = import_shop.delay(data=data, user_id=user_id)
        return Response({"task_id": task.id, "status": task.status})

    @action(methods=["GET"], detail=True, url_path="export", url_name="export")
    def export_shop_to_file(self, request: Request, pk: int) -> Response:
        shop: Shop = self.get_object()
        task: AsyncResult = export_shop.delay(shop_id=shop.id)
        return Response({"task_id": task.id, "status": task.status})


class StockView(ListAPIView):
    """View-class для просмотра товаров.

    Поддерживаемые HTTP-методы:
    - GET-list: Получение информации о магазинах, товарах,
        их характеристиках, количестве и стоимости.

    Фильтрация:
    Доступна фильтрация результатов по следующим полям:
    - price: По стоимости товара.
        Параметры:
        - price_min (int): Минимальная стоимость (например, .../?price_min=1000)
        - price_max (int): Максимальная стоимость (например, .../?price_max=1000)
    - quantity: По количеству товара.
        Параметры:
        - quantity_min (int): Минимальное количество (например, .../?quantity_min=10)
        - quantity_max (int): Максимальное количество (например, .../?quantity_max=10)
    - model (str): По моделе (например, .../?model=iphone)
    - name (str): По названию (например, .../?name=iphone)
    - category (str): По категории (например, .../?category=смартфоны)
    - shop (str): По магазину (например, .../?shop=dns)

    Поиск:
    Доступен поиск по следующим полям:
    - model (str): По моделе (например, .../?search=iphone)
    - name (str): По названию (например, .../?search=iphone)
    - category (str): По категории (например, .../?search=смартфоны)
    - shop (str): По магазину (например, .../?search=dns)

    Сортировка:
    Доступна сортировка результатов по следующим полям:
    - price: По стоимости товара (например, .../?order_by=price (по возрастанию))
    - quantity: По количеству товара (например, .../?order_by=-quantity (по убыванию))
    """

    serializer_class = StockSerializer
    queryset = (
        Stock.objects.filter(can_buy=True)
        .select_related("product__category", "shop")
        .prefetch_related(
            Prefetch("product__parameters", queryset=Parameter.objects.all()),
            Prefetch("product__parameters_values", queryset=ProductsParameters.objects.all()),
        )
        .all()
    )
    search_fields = ["product__model", "product__name", "product__category__name", "shop__name"]
    ordering_fields = ["price", "quantity"]
    filterset_class = StockFilter


class EmailObtainAuthToken(ObtainAuthToken):
    """View-class для получения токена аутентификации по email и паролю.

    Поддерживаемые HTTP-методы:
    - POST: Создание и получение токена. Для этого необходимо передать email
        зарегистрированного пользователя (str) и пароль (str).
        Пример тела запроса (в формате JSON):
            {
                "email": str,
                "password": str
            }
    """

    serializer_class = EmailAuthTokenSerializer


class CartViewSet(ModelViewSet):
    """View-class для работы с товарами в корзине пользователя.

    Для работы требуется аутентификация пользователя.

    Поддерживаемые HTTP-методы:
    - GET-list: Получение информации о товарах в корзине.
    - GET-detail: Получение информации о конкретном товаре в корзине.
    - POST: Добавление товара в корзину. Для этого необходимо передать информацию о
        добавляемом продукте (stock.id) и количестве (int).
        Пример тела запроса (в формате JSON):
            {
                "product": stock.id,
                "quantity": int
            }
    - PATCH: Изменение существующей записи о товаре в корзине.
        Изменению доступны поля "product" и "quantity".
    - DELETE: Удаление товара из корзины.
    - POST /confirm/: Подтверждение заказа всех имеющихся товаров в корзине. Для этого
        необходимо передать информацию об адресе доставки (contact.id):
        Пример тела запроса (в формате JSON):
            {
                "delivery_address": contact.id
            }
    """

    serializer_class = CartSerialaizer
    queryset = Order.objects.filter(status="in_cart").all()
    permission_classes = [IsAuthenticated, IsCartOwnerOrAdmin]

    def get_queryset(self) -> QuerySet[Order]:
        queryset: QuerySet = super().get_queryset()
        return queryset.filter(customer=self.request.user)

    def get_confirm_data(self) -> dict[str, str | datetime]:
        return {"status": "created", "created_at": timezone.now()}

    def create_order(self, orders: list[Order], data: list[dict]) -> OrderSerializer:
        order_ser = OrderSerializer(
            instance=orders,
            data=data,
            many=True,
            context={"request": self.request, "confirm_data": self.get_confirm_data()},
        )
        order_ser.is_valid(raise_exception=True)
        order_ser.save()
        return order_ser

    @action(methods=["POST"], detail=False, url_path="confirm", url_name="confirm-order")
    def confirm_order(self, request: Request) -> Response:
        orders: QuerySet[Order] = self.get_queryset()
        data: dict = self.get_confirm_data()
        data.update(request.data)
        order_ser: OrderSerializer = self.create_order(orders=orders, data=[data])
        return Response(order_ser.data, status=status.HTTP_201_CREATED)


class OrdersView(ListAPIView):
    """View-class для просмотра активных/завершенных заказов пользователя.

    Для работы требуется аутентификация пользователя.

    Поддерживаемые HTTP-методы:
    - GET-list: Получение информации об активных/завершенных заказах.

    Фильтрация:
    Доступна фильтрация результатов по следующим полям:
    - status (str): По статусу заказа (например, .../?status=created)
    - created: По дате создания заказа.
        Параметры:
        - created_before (date): Создано до (например, .../?created_before=2025-03-31)
        - created_after (date): Создано после (например, .../?created_after=2025-03-31)
    """

    serializer_class = OrderSerializer
    queryset = (
        Order.objects.exclude(status="in_cart")
        .order_by("-created_at")
        .select_related(
            "customer",
            "product__product",
            "product__product__category",
            "product__shop",
            "delivery_address",
        )
        .prefetch_related(
            Prefetch("product__product__parameters", queryset=Parameter.objects.all()),
            Prefetch(
                "product__product__parameters_values", queryset=ProductsParameters.objects.all()
            ),
        )
        .all()
    )
    filterset_class = OrderFilter
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> QuerySet[Order]:
        queryset: QuerySet[Order] = super().get_queryset()
        return queryset.filter(customer=self.request.user)


class CeleryView(APIView):
    """View-class для отслеживания статуса выполения асинхронных задач Celery.

    Поддерживаемые HTTP-методы:
    - GET-detail: Получение информации о статусе задачи по указанному task_id.
    """

    def get(self, request: Request, task_id: str):
        task = AsyncResult(id=task_id)
        response = {"task_id": task.id, "status": task.status}
        if task.ready() and task.result is not None:
            response.update(
                {
                    "link": f"http://localhost:8000{reverse('autopurchases:download-file', kwargs={"task_id": task.id})}"
                }
            )
        return Response(response)


class DownloadFileView(APIView):
    """View-class для получения выгрузки данных о магазине в виде файла.

    Поддерживаемые HTTP-методы:
    - GET-detail: Получение файла с данными о магазине. Для выбора типа файла (yaml или json)
        необходимо передать заголовок Accept в запросе.
    """

    renderer_classes = [YAMLRenderer, JSONRenderer]

    def get(self, request: Request, task_id: str):
        task = AsyncResult(id=task_id)
        ext = request.accepted_renderer.format
        filename = f"{task.result['shop']}_{timezone.now().date()}.{ext}"
        resp = Response(task.result)
        resp["Content-Disposition"] = f"attachment; filename={filename}"

        return resp
