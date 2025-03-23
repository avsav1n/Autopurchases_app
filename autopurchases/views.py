import json
import logging
import uuid
from datetime import timedelta
from io import BytesIO

import yaml
from celery.result import AsyncResult
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotFound,
    ParseError,
    UnsupportedMediaType,
)
from rest_framework.generics import ListAPIView
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

from autopurchases.exceptions import BadRequest
from autopurchases.filters import OrderFilter, StockFilter
from autopurchases.models import (
    Cart,
    Contact,
    Order,
    PasswordResetToken,
    Shop,
    Stock,
    User,
)
from autopurchases.permissions import (
    IsCartOwnerOrAdmin,
    IsManagerOrAdmin,
    IsManagerOrAdminOrReadOnly,
    IsMeOrAdmin,
)
from autopurchases.serializers import (
    CartSerializer,
    ContactSerializer,
    EmailAuthTokenSerializer,
    EmailSerializer,
    OrderSerializer,
    PasswordResetSerializer,
    ShopSerializer,
    StockSerializer,
    UserSerializer,
)
from autopurchases.tasks import export_shop, import_shop

logger = logging.getLogger(__name__)
UserModel = get_user_model()


class UserFilterMixin:
    """Миксин фильтрации данных по пользователю, совершающему запрос.

    Для View-классов работы с корзиной (CartViewSet) и заказами (OrderView).
    """

    def get_queryset(self) -> QuerySet[Cart | Order]:
        queryset: QuerySet = super().get_queryset()
        user: User = self.request.user
        return queryset.filter(customer=user)


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
                "phone": str,       # опционально
                "first_name": str,  # опционально
                "last_name": str    # опционально
            }
    - PATCH: Изменение профиля пользователя.
    - DELETE: Удаление профиля пользователя.
    - POST /<int:user.id>/contacts/: Создание и добавление информации о контакте пользователя
        (адреса). Для этого необходимо передать название города (str), улицы (str),
        номер дома (int).
        Пример тела запроса (в формате JSON):
            {
                "city": str,
                "street": str,
                "house": int,
                "apartment": int  # опционально
            }
    - DELETE /<int:user.id>/contacts/<int:contact.id>/: Удаление выбранного контакта пользователя
        (адреса).
    - GET /reset/: Создание и получение токена сброса пароля. Для этого необходимо передать
        email (str) зарегистрированного пользователя.
        Пример тела запроса (в формате JSON):
            {
                "email": str
            }
    - PATCH /reset/confirm/: Сброс старого пароля пользователя. Для этого необходимо передать
        токен сброса пароля (str) и новый пароль (str).
        Пример тела запроса (в формате JSON):
            {
                "rtoken": str,
                "password": str
            }
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

        user.refresh_from_db(fields=["contacts"])
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
        contact: Contact | None = Contact.objects.filter(user=user, pk=int(contact_pk)).first()
        if contact is None:
            error_msg = _("Contact not found")
            logger.error(error_msg)
            raise BadRequest(error_msg)
        contact.delete()

        user.refresh_from_db(fields=["contacts"])
        user_ser = UserSerializer(user)
        return Response(user_ser.data, status=status.HTTP_200_OK)

    @action(methods=["GET"], detail=False, url_path="reset", url_name="reset-password")
    def get_password_reset_token(self, request: Request):
        email_ser = EmailSerializer(data=request.data)
        email_ser.is_valid(raise_exception=True)
        try:
            user: User | None = UserModel.objects.get(email=email_ser.validated_data["email"])
        except ObjectDoesNotExist:
            error_msg = _("User not found")
            logger.error(error_msg)
            raise NotFound(error_msg)
        PasswordResetToken.objects.update_or_create(user=user, defaults={"token": uuid.uuid4()})
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
            error_msg = _("Password reset token expired")
            logger.warning(error_msg)
            raise AuthenticationFailed(error_msg)
        user: User = rtoken.user
        user.set_password(raw_password=rtoken_ser.validated_data["password"])
        user.save()
        return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)


class ShopViewSet(ModelViewSet):
    """View-class для работы с магазином.

    Для работы требуется аутентификация пользователя.

    Поддерживаемые HTTP-методы:
    - GET /: Получение информации обо всех магазинах.
    - GET /<slug:shop.slug>/: Получение информации о конкретном магазине.
    - POST /: Регистрация нового магазина. Для этого необходимо передать название (str).
        Пример тела запроса (в формате JSON):
            {
                "name": str,
                "managers": [user.id, ...]  # опционально
            }
    - PATCH /<slug:shop.slug>/: Изменение профиля магазина. Изменению доступны поля "name" и "managers".
    - DELETE /<slug:shop.slug>/: Удаление профиля магазина.
    - POST /import/: Регистрация нового магазина со всем его ассортиментом. Для этого
        необходимо передать информацию о магазине и продуктах в теле запроса или файлом в формате
        json или yaml.
        Пример тела запроса (в формате JSON):
           {
                "shop": str,
                "products": [
                    {
                        "category": str,
                        "model": str,
                        "name": str,
                        "can_buy": str,  # опционально
                        "parameters": {
                            str: str,
                            ...
                        },
                    },
                    ...
                ]
            }
    - GET /<slug:shop.slug>/export/: Выгрузка информации о магазине со всем его ассортиментом.
        Для получения файла по окончании подготовки данных необходимо отправить GET-запрос
        на /download/<str:task.id>/. Для выбора типа файла (yaml или json) необходимо передать
        заголовок Accept в запросе (по умолчанию yaml).
    - GET /<slug:shop.slug>/orders/: Получение информации об активных/завершенных заказах (для
        выбранного магазина).
    - PATCH /<slug:shop.slug>/orders/<int:order.id>/: Изменение информации выбранного заказа.
        Изменению доступно поле "status".
    - PATCH /<slug:shop.slug>/stock/<int:stock.id>/: Изменение информации о товаре на выбранном
        складе. Изменению доступны поля "quantity", "price" и "can_buy".

    Фильтрация:
    Для метода GET /<slug:shop.slug>/orders/ доступна фильтрация результатов по следующим полям:
    - status (str): По статусу заказа (например, .../?status=created)
    - created: По дате создания заказа.
        Параметры:
        - created_before (date): Создано до (например, .../?created_before=2025-03-31)
        - created_after (date): Создано после (например, .../?created_after=2025-03-31)
    """

    serializer_class = ShopSerializer
    queryset = Shop.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly, IsManagerOrAdminOrReadOnly]
    lookup_field = "slug"

    def get_data(self, request: Request) -> dict[str, str | list[dict]]:
        content_type = request.content_type.split(";")[0]
        match content_type:
            case "multipart/form-data":
                file: BytesIO | None = request.FILES.get("file", None)
                if file is None:
                    error_msg = _("Attachment required")
                    logger.warning(error_msg)
                    raise BadRequest(error_msg)
                match file.content_type:
                    case "application/yaml":
                        data = yaml.safe_load(file.read().decode())
                    case "application/json":
                        data = json.load(file.read().decode())
                    case _:
                        error_msg = _("Attached file's content type required")
                        logger.warning(error_msg)
                        raise ParseError(error_msg)
            case "application/json" | "application/yaml":
                data = request.data
            case _ as unsupported_type:
                error_msg = _(
                    "Shop import is available with 'multipart/form-data', "
                    "'application/json' or 'application/yaml' content types"
                )
                logger.warning(error_msg)
                raise UnsupportedMediaType(unsupported_type, error_msg)
        return data

    @action(
        methods=["GET"],
        detail=True,
        url_path="orders",
        url_name="get-orders",
        permission_classes=[IsManagerOrAdmin],
    )
    def get_shop_orders(self, request: Request, slug: str) -> Response:
        shop: Shop = self.get_object()
        orders: QuerySet[Order] = Order.objects.with_dependencies().filter(product__shop=shop).all()
        filter = OrderFilter(data=request.query_params, queryset=orders)
        order_ser = OrderSerializer(filter.qs, many=True)
        return Response(order_ser.data, status=status.HTTP_200_OK)

    @action(
        methods=["PATCH"],
        detail=True,
        url_path="orders/(?P<order_pk>[^/.]+)",
        url_name="update-order",
        permission_classes=[IsManagerOrAdmin],
    )
    def update_shop_order_status(self, request: Request, slug: str, order_pk: str) -> Response:
        shop: Shop = self.get_object()
        order: Order | None = (
            Order.objects.with_dependencies().filter(product__shop=shop, pk=int(order_pk)).first()
        )
        if order is None:
            error_msg = _("Order not found")
            logger.error(error_msg)
            raise BadRequest(error_msg)
        order_ser = OrderSerializer(
            instance=order, data=request.data, partial=True, context={"request": request}
        )
        order_ser.is_valid(raise_exception=True)
        order_ser.save()
        return Response(order_ser.data, status=status.HTTP_200_OK)

    @action(
        methods=["PATCH"],
        detail=True,
        url_path="stock/(?P<stock_pk>[^/.]+)",
        url_name="update-product-on-stock",
        permission_classes=[IsManagerOrAdmin],
    )
    def update_product_on_stock(self, request: Request, slug: str, stock_pk: str):
        shop: Shop = self.get_object()
        stock = Stock.objects.with_dependencies().filter(shop=shop, pk=stock_pk).first()
        if stock is None:
            error_msg = _("Product not found")
            logger.error(error_msg)
            raise BadRequest(error_msg)
        stock_ser = StockSerializer(instance=stock, data=request.data, partial=True)
        stock_ser.is_valid(raise_exception=True)
        stock_ser.save()
        return Response(stock_ser.data, status=status.HTTP_200_OK)

    @action(
        methods=["POST"],
        detail=False,
        url_path="import",
        url_name="import",
        parser_classes=[MultiPartParser, JSONParser, YAMLParser],
    )
    def import_shop(self, request: Request) -> Response:
        data: dict[str, str | list[dict]] = self.get_data(request=request)
        user_id: int = request.user.id
        task: AsyncResult = import_shop.delay(data=data, user_id=user_id)
        return Response({"task_id": task.id, "status": task.status}, status=status.HTTP_200_OK)

    @action(
        methods=["GET"],
        detail=True,
        url_path="export",
        url_name="export",
        permission_classes=[IsManagerOrAdmin],
    )
    def export_shop(self, request: Request, slug: str) -> Response:
        shop: Shop = self.get_object()
        task: AsyncResult = export_shop.delay(shop_id=shop.id)
        return Response({"task_id": task.id, "status": task.status}, status=status.HTTP_200_OK)


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
    queryset = Stock.objects.with_dependencies().filter(can_buy=True).all()

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


class CartViewSet(UserFilterMixin, ModelViewSet):
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
    - PATCH: Изменение информации о товаре в корзине.
        Изменению доступны поля "product" и "quantity".
    - DELETE: Удаление товара из корзины.
    - POST /confirm-order/: Подтверждение заказа всех имеющихся товаров в корзине. Для этого
        необходимо передать информацию об адресе доставки.
        Пример тела запроса (в формате JSON):
            {
                "delivery_address": {
                    "city": str,
                    "street": str,
                    "house": int,
                    "apartment": int  # опционально
                }
            }
    """

    serializer_class = CartSerializer
    queryset = Cart.objects.with_dependencies().all()
    permission_classes = [IsAuthenticated, IsCartOwnerOrAdmin]

    @action(methods=["POST"], detail=False, url_path="confirm-order", url_name="confirm-order")
    def confirm_order(self, request: Request) -> Response:
        cart: QuerySet[Cart] = self.get_queryset()
        if not cart.exists():
            error_msg = _("Cart is empty")
            logger.error(error_msg)
            raise NotFound(error_msg)
        order_ser = OrderSerializer(
            data=[request.data], many=True, context={"cart": cart, "request": request}
        )
        order_ser.is_valid(raise_exception=True)
        order_ser.save()
        return Response(order_ser.data, status=status.HTTP_201_CREATED)


class OrderView(UserFilterMixin, ListAPIView):
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
    queryset = Order.objects.with_dependencies().all()
    filterset_class = OrderFilter
    permission_classes = [IsAuthenticated]


class CeleryTaskView(APIView):
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
        необходимо передать заголовок Accept в запросе (по умолчанию yaml).
    """

    renderer_classes = [YAMLRenderer, JSONRenderer]

    def get(self, request: Request, task_id: str):
        task = AsyncResult(id=task_id)
        ext = request.accepted_renderer.format
        filename = f"{task.result['shop']}_{timezone.now().date()}.{ext}"
        resp = Response(task.result)
        resp["Content-Disposition"] = f"attachment; filename={filename}"

        return resp
