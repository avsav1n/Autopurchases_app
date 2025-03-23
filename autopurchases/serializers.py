import logging
from typing import ClassVar

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.db import models, transaction
from django.db.models import QuerySet
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.reverse import reverse
from rest_framework.validators import UniqueValidator

from autopurchases.models import (
    Cart,
    Category,
    Contact,
    Order,
    Parameter,
    Product,
    ProductsParameters,
    Shop,
    ShopsManagers,
    Stock,
    User,
)

logger = logging.getLogger(__name__)
UserModel = get_user_model()


class NormalizedEmailField(serializers.EmailField):
    """Class кастомного EmailField поля сериализатора.

    Изменения:
    - добавлена автоматическая нормализация (приведение к нижнему регистру) адреса
        электронной почты.
    """

    def to_internal_value(self, data: str) -> str:
        data: str = super().to_internal_value(data)
        return data.lower()


class CustomModelSerializer(serializers.ModelSerializer):
    """Class кастомного CustomModelSerializer.

    Изменения:
    - изменена таблица соответствия поля ORM EmailFiels и поля сериализатора NormalizedEmailField.
    """

    serializer_field_mapping = {**serializers.ModelSerializer.serializer_field_mapping}
    serializer_field_mapping[models.EmailField] = NormalizedEmailField


class ContactSerializer(CustomModelSerializer):
    """Сериализатор для работы с контактами (адресами).

    Пример принимаемых данных для десериализации (в формате JSON):
        {
            "city": str,
            "street": str,
            "house": str,
            "apartment": str  # опционально
        }

    Пример сериализованных данных (в формате JSON):
        {
            "id": int,
            "city": str,
            "street": str,
            "house": str,
            "apartment": str | null
        }

    Дополнительная валидация:
    - валидация на уровне объекта:
        Единовременное количество объектов Contact, связанных с UserModel не может быть
        больше settings.MAX_CONTACTS_FOR_USER.
    """

    class Meta:
        model = Contact
        fields = ["id", "city", "street", "house", "apartment"]

    def validate(self, attrs: dict) -> dict:
        user: User = self.context["request"].user
        if user.contacts.count() >= settings.MAX_CONTACTS_FOR_USER:
            error_msg = format_lazy(
                _("A user can not have more than {quantity} contacts at a time."),
                quantity=settings.MAX_CONTACTS_FOR_USER,
            )
            logger.warning(error_msg)
            raise ValidationError(error_msg)
        return attrs

    def create(self, validated_data: dict) -> Contact:
        user: User = self.context["request"].user
        contact = Contact.objects.create(user=user, **validated_data)
        return contact


class UserSerializer(CustomModelSerializer):
    """Сериализатор для работы с пользователями.

    Пример принимаемых данных для десериализации (в формате JSON):
        {
            "email": str,
            "password": str,
            "first_name": str,  # опционально
            "last_name": str,   # опционально
            "phone": str        # опционально
        }

    Пример сериализованных данных (в формате JSON):
        {
            "id": int,
            "email": str,
            "first_name": str | null,
            "last_name": str | null,
            "phone": str | null,
            "contacts": [
                {
                    "id": int,
                    "city": str,
                    "street": str,
                    "house": str,
                    "apartment": str | null
                },
                ...
            ]
        }

    Дополнительная валидация:
    - валидация на уровне поля 'password':
        Проверка сложности пароля в соответствии settings.AUTH_PASSWORD_VALIDATORS.
        Требования к паролю:
        - не должен быть похож на email/first_name/last_name;
        - минимум 8 символов;
        - не должен быть распространенным;
        - не должен состоять только из цифр.
    """

    contacts = ContactSerializer(many=True, read_only=True)

    class Meta:
        model = UserModel
        fields = ["id", "email", "first_name", "last_name", "password", "phone", "contacts"]
        extra_kwargs = {"password": {"write_only": True, "validators": [validate_password]}}

    def create(self, validated_data: dict[str, str]) -> User:
        return self.Meta.model.objects.create_user(**validated_data)

    def update(self, instance: User, validated_data: dict[str, str]) -> User:
        if "password" in validated_data:
            validated_data["password"] = make_password(password=validated_data["password"])
        return super().update(instance=instance, validated_data=validated_data)


class EmailSerializer(serializers.Serializer):
    """Сериализатор для валидации email.

    Пример принимаемых данных для десериализации (в формате JSON):
        {
            "email": str
        }
    """

    email = NormalizedEmailField(max_length=150)


class PasswordResetSerializer(serializers.Serializer):
    """Сериализатор для валидации токена сброса пароля и пароля для замены.

    Пример принимаемых данных для десериализации (в формате JSON):
        {
            "rtoken": str,
            "password": str
        }
    """

    rtoken = serializers.UUIDField()
    password = serializers.CharField(
        write_only=True, max_length=128, validators=[validate_password]
    )


class ShopSerializer(CustomModelSerializer):
    """Сериализатор для работы с магазинами.

    Пример принимаемых данных для десериализации (в формате JSON):
        {
            "name": str,
            "managers": list[int]  # опционально
        }

    Пример сериализованных данных (в формате JSON):
        {
            "id": int,
            "name": str,
            "created_at": str,
            "updated_at": str,
            "managers": list[int]
        }
    """

    managers = serializers.PrimaryKeyRelatedField(
        many=True, queryset=UserModel.objects.all(), required=False
    )

    class Meta:
        model = Shop
        fields = ["id", "name", "created_at", "updated_at", "managers"]

    def to_internal_value(self, data: dict | str):
        """Метод преобразования входных данных для десериализации.

        Поддерживает следующие форматы входных данных:
        - str (только для программного использования)
            Пример десериализации:
                shop_ser = ShopSerializer(data="example_shop_name")
                shop_ser.is_valid(raise_exception=True)
                ...
        - dict (для API)
            Пример десериализации:
                shop_ser = ShopSerializer(data={"name": "example_shop_name"})
                shop_ser.is_valid(raise_exception=True)
                ...
        """
        if isinstance(data, str):
            data = {"name": data}
        return super().to_internal_value(data)

    @transaction.atomic
    def create(self, validated_data: dict[str, str | list[int]]) -> Shop:
        managers: list["User"] | None = validated_data.pop("managers", None)
        shop: Shop = super().create(validated_data=validated_data)
        owner: User = (
            self.context["owner"] if "owner" in self.context else self.context["request"].user
        )
        if managers is not None:
            all_managers = [
                ShopsManagers(shop=shop, manager=manager)
                for manager in managers
                if manager != owner
            ]
        else:
            all_managers = []
        all_managers.append(ShopsManagers(shop=shop, manager=owner, is_owner=True))
        ShopsManagers.objects.bulk_create(all_managers)
        return shop

    def update(self, instance: Shop, validated_data: dict[str, str | list[int]]) -> Shop:
        if "managers" in validated_data:
            for manager in instance.managers_roles.select_related("manager").all():
                if manager.is_owner:
                    validated_data["managers"].append(manager.manager)
                    break
        return super().update(instance, validated_data)


class CategorySerializer(CustomModelSerializer):
    """Сериализатор для работы с категориями товаров.

    Только для программного использования в качестве вложенного.
    """

    class Meta:
        model = Category
        fields = ["id", "name"]
        extra_kwargs = {"name": {"validators": []}}

    def to_internal_value(self, data: dict | str):
        """Метод преобразования входных данных для десериализации.

        Поддерживает следующие форматы входных данных:
        - str
            Пример десериализации:
                category_ser = CategorySerializer(data="smartphones")
                category_ser.is_valid(raise_exception=True)
                ...
        - dict
            Пример десериализации:
                category_ser = CategorySerializer(data={"name": "smartphones"})
                category_ser.is_valid(raise_exception=True)
                ...
        """
        if isinstance(data, str):
            data = {"name": data}
        return super().to_internal_value(data)

    def to_representation(self, instance: Category) -> str:
        """Метод возврата сериализованных данных.

        Изменения:
            Формат выходных данных по умолчанию:
                {
                    "id": int,
                    "name": str
                }
            Измененный формат:
                str
        """
        return instance.name


class ParameterListSerializer(serializers.ListSerializer):
    """Сериализатор списка ParameterSerializer."""

    def to_internal_value(self, data: dict[str, str | int]):
        """Метод преобразования входных данных для десериализации.

        Поддерживает следующие форматы входных данных:
        - dict[str, str | int]
            Пример десериализации:
                data = {
                    "colour": "black",
                    "size": 120x140,
                    "weight": 20
                }
                parameter_ser = ParameterSerializer(data=data, many=True)
                parameter_ser.is_valid(raise_exception=True)
                ...
        """
        data = [{"name": key.capitalize(), "value": str(value)} for key, value in data.items()]
        return super().to_internal_value(data)

    def to_representation(self, data: list[dict[str, str | int]]) -> dict[str, str]:
        """Метод возврата сериализованных данных.

        Изменения:
            Формат выходных данных по умолчанию:
                [
                    {
                        "id": int,
                        "name": str,
                        "value": str
                    },
                    ...
                ]
            Измененный формат:
                {
                    "parameter.name": str,
                    ...
                }
        """
        params: list[dict[str, str | int]] = super().to_representation(data)

        repr = {}
        for param in params:
            repr.update(param)
        return repr


class ParameterSerializer(CustomModelSerializer):
    """Сериализатор для работы с параметрами товаров.

    Только для программного использования в качестве вложенного.
    """

    name = serializers.CharField(max_length=50)

    class Meta:
        model = ProductsParameters
        fields = ["id", "name", "value"]
        list_serializer_class = ParameterListSerializer

    def to_representation(self, instance: ProductsParameters) -> dict[str, str]:
        """Метод возврата сериализованных данных.

        Изменения:
            Формат выходных данных по умолчанию:
                {
                    "id": int,
                    "name": str,
                    "value": str
                }
            Измененный формат:
                {
                    "parameter.name": str
                }
        """
        repr = {instance.parameter.name: instance.value}
        return repr


class ProductSerializer(CustomModelSerializer):
    """Сериализатор для работы с товарами.

    Пример принимаемых данных для десериализации (в формате JSON):
        {
            "category": str,
            "model": str,
            "name": str,
            "price": int,
            "quantity": int,
            "parameters": {
                parameter.name: str,
                ...
            }
            "can_buy": bool,  # опционально
        }

    Пример сериализованных данных (в формате JSON):
        {
            "id": int,
            "category": str,
            "model": str,
            "name": str,
            "parameters": {
                parameter.name: str,
                ...
            }
        }
    """

    category = CategorySerializer()
    parameters = ParameterSerializer(source="parameters_values", many=True)
    price = serializers.IntegerField(write_only=True)
    quantity = serializers.IntegerField(write_only=True)
    can_buy = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = Product
        fields = ["id", "category", "model", "name", "price", "quantity", "parameters", "can_buy"]
        extra_kwargs = {"name": {"validators": []}}

    @transaction.atomic
    def create(self, validated_data: dict):
        shop: Shop = self.context["shop"]

        category, _ = Category.objects.get_or_create(**validated_data["category"])

        product, _ = Product.objects.get_or_create(
            category=category, model=validated_data["model"], name=validated_data["name"]
        )
        for params in validated_data["parameters_values"]:
            parameter, _ = Parameter.objects.get_or_create(name=params["name"])
            if not ProductsParameters.objects.filter(
                product=product, parameter=parameter, value=params["value"]
            ).exists():
                ProductsParameters.objects.create(
                    product=product, parameter=parameter, value=params["value"]
                )

        stock_kwargs = {
            "shop": shop,
            "product": product,
            "price": validated_data["price"],
            "quantity": validated_data["quantity"],
        }
        if "can_buy" in validated_data:
            stock_kwargs["can_buy"] = validated_data["can_buy"]
        Stock.objects.create(**stock_kwargs)

        return product


class EmailAuthTokenSerializer(serializers.Serializer):
    """Сериализатор для работы с токенами аутентификации.

    Пример принимаемых данных для десериализации (в формате JSON):
        {
            "email": str,
            "password": str
        }

    Пример сериализованных данных (в формате JSON):
        {
            "token": str
        }
    """

    email = NormalizedEmailField(label=_("Email"), write_only=True)
    password = serializers.CharField(
        label=_("Password"),
        style={"input_type": "password"},
        trim_whitespace=False,
        write_only=True,
    )
    token = serializers.CharField(label=_("Token"), read_only=True)

    def validate(self, attrs: dict[str, str]) -> dict[str, str]:
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            user = authenticate(request=self.context.get("request"), email=email, password=password)

            if not user:
                error_msg = _("Unable to log in with provided credentials.")
                logger.error(error_msg)
                raise ValidationError(error_msg, code="authorization")
        else:
            error_msg = _('Must include "email" and "password".')
            logger.error(error_msg)
            raise ValidationError(error_msg, code="authorization")

        attrs["user"] = user
        return attrs


class StockSerializer(CustomModelSerializer):
    """Сериализатор для работы со складами - ассоциативной таблицей товаров и магазинов.

    Пример сериализованных данных (в формате JSON):
        {
            "id": int,
            "shop": str,
            "quantity": int,
            "price": int,
            "can_buy": bool,
            "category": str,
            "model": str,
            "name": str,
            "parameters": {
                "parameter.name": str,
                ...
            }
        }
    """

    shop = ShopSerializer(read_only=True)
    product = ProductSerializer(read_only=True)

    class Meta:
        model = Stock
        fields = ["id", "shop", "product", "quantity", "price", "can_buy"]

    def to_representation(self, instance: Stock):
        """Метод возврата сериализованных данных.

        Изменения:
            Формат выходных данных по умолчанию:
                {
                    "id": int,
                    "shop": {
                        "id": int,
                        "name": str,
                        "created_at": str,
                        "updated_at": str,
                        "managers": list[int]
                    }
                    "quantity": int,
                    "price": int,
                    "can_buy": bool,
                    'product': {
                        "id": int,
                        "category": str,
                        "model": str,
                        "name": str,
                        "parameters": {
                            parameter.name: str,
                            ...
                        }
                    }

            Измененный формат:
                {
                    "id": int,
                    "shop": str,
                    "quantity": int,
                    "price": int,
                    "can_buy": bool,
                    "category": str,
                    "model": str,
                    "name": str,
                    "parameters": {
                        "parameter.name": str,
                        ...
                    }
                }
        """
        repr: dict[str, int | dict] = super().to_representation(instance)

        repr["shop"] = repr["shop"]["name"]

        product_info: dict = repr.pop("product")
        repr["category"] = product_info["category"]
        repr["model"] = product_info["model"]
        repr["name"] = product_info["name"]
        repr["parameters"] = product_info["parameters"]

        return repr


class CartSerializer(CustomModelSerializer):
    """Сериализатор для работы с корзиной пользователя.

    Пример принимаемых данных для десериализации (в формате JSON):
        {
            "product": int,
            "quantity": int
        }

    Пример сериализованных данных (в формате JSON):
        {
            "id": int,
            "customer": str,
            "quantity": int,
            "total_price": int,
            "shop": str,
            "category": str,
            "model": str,
            "name": str
        }

    Дополнительная валидация:
    - валидация на уровне объекта:
        Товар, добавляемый в корзину, доступен для заказа.
    - валидация на уровне объекта:
        Количество товаров, добавляемое в корзину, не может быть больше чем количество товаров
        на складе.
    """

    customer_read = UserSerializer(source="customer", read_only=True)
    product_read = StockSerializer(source="product", read_only=True)

    class Meta:
        model = Cart
        fields = [
            "id",
            "customer",
            "product",
            "quantity",
            "total_price",
            "customer_read",
            "product_read",
        ]
        read_only_fields = ["total_price", "customer"]

    def validate(self, attrs: dict):
        stock: Stock = attrs["product"]
        check_availability(can_buy=stock.can_buy)
        check_quantity(on_stock=stock.quantity, in_order=attrs["quantity"])
        return attrs

    def create(self, validated_data: dict):
        validated_data["customer"] = self.context["request"].user
        return super().create(validated_data)

    def to_representation(self, instance: Cart):
        """Метод возврата сериализованных данных.

        Изменения:
            Формат выходных данных по умолчанию:
                {
                    "id": int,
                    "customer": int,
                    "product": int,
                    "quantity": int,
                    "total_price": int,
                    "customer_read": {
                        "id": int,
                        "email": str,
                        "first_name": str | null,
                        "last_name": str | null,
                        "phone": str | null,
                        "contacts": [
                            {
                                "id": int,
                                "city": str,
                                "street": str,
                                "house": str,
                                "apartment": str | null
                            },
                            ...
                        ]
                    },
                    "product_read": {
                        "id": int,
                        "shop": str,
                        "quantity": int,
                        "price": int,
                        "can_buy": bool,
                        "category": str,
                        "model": str,
                        "name": str,
                        "parameters": {
                            "parameter.name": str,
                            ...
                        }
                    }

            Измененный формат:
                {
                    "id": int,
                    "shop": str,
                    "quantity": int,
                    "price": int,
                    "can_buy": bool,
                    "category": str,
                    "model": str,
                    "name": str,
                    "parameters": {
                        "parameter.name": str,
                        ...
                    }
                }
        """
        repr: dict[str, int | dict] = super().to_representation(instance)

        customer_info: dict = repr.pop("customer_read")
        repr["customer"] = customer_info["email"]

        repr.pop("product")
        product_info: dict = repr.pop("product_read")
        repr["shop"] = product_info["shop"]
        repr["category"] = product_info["category"]
        repr["model"] = product_info["model"]
        repr["name"] = product_info["name"]

        return repr


class OrderListSerializer(serializers.ListSerializer):
    def create(self, validated_data: list[dict]):
        validated_data: dict = validated_data[0]
        delivery_address, _ = Contact.objects.get_or_create(**validated_data["delivery_address"])
        cart: QuerySet[Cart] = self.context["cart"]
        created_orders = []
        for product in cart:
            stock: Stock = product.product
            # Из-за кеширования через select_related требуется обновление объекта stock
            stock.refresh_from_db(fields=["quantity", "can_buy"])
            try:
                check_availability(can_buy=stock.can_buy)
                check_quantity(on_stock=stock.quantity, in_order=product.quantity)
            except ValidationError:
                continue
            with transaction.atomic():
                stock.quantity -= product.quantity
                stock.save(update_fields=["quantity"])
                order = self.child.Meta.model.objects.create(
                    customer=product.customer,
                    product=product.product,
                    quantity=product.quantity,
                    delivery_address=delivery_address,
                )
                product.delete()
                created_orders.append(order)

        return created_orders


class OrderSerializer(CustomModelSerializer):
    """Сериализатор для работы с заказами.

    Пример принимаемых данных для десериализации (в формате JSON):
        {
            "delivery_address": {
                "city": str,
                "street": str,
                "house": str,
                "apartment": str  # опционально
            },
            "status" : str
        }

    Пример сериализованных данных (в формате JSON):
        {
            "id": int,
            "customer": str,
            "quantity": int,
            "total_price": int,
            "delivery_address": {
                "city": str,
                "street": str,
                "house": str,
                "apartment": str | null
                },
            "status": str,
            "created_at": str,
            "updated_at": str,
            "shop": str,
            "category": str,
            "model": str,
            "name": str
        }

    Дополнительная валидация:
    - валидация на уровне поля 'delivery_address':
        Адрес доставки можно передать только при создании (POST) заказа, его обновление (PATCH)
        недоступно.
    - валидация на уровне поля 'status':
        Пользователь не может сменить (PATCH) статус заказа, эта опция доступна только магазинам.
    """

    customer = UserSerializer(read_only=True)
    product = StockSerializer(read_only=True)
    delivery_address = ContactSerializer()

    class Meta:
        model = Order
        fields = [
            "id",
            "customer",
            "product",
            "quantity",
            "total_price",
            "delivery_address",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["customer", "product", "quantity", "total_price"]
        list_serializer_class = OrderListSerializer

    def to_representation(self, instance: Order):
        """Метод возврата сериализованных данных.

        Изменения:
            Формат выходных данных по умолчанию:
                {
                    "id": int,
                    "customer": {
                        "id": int,
                        "email": str,
                        "first_name": str | null,
                        "last_name": str | null,
                        "phone": str | null,
                        "contacts": [
                            {
                                "id": int,
                                "city": str,
                                "street": str,
                                "house": str,
                                "apartment": str | null
                            },
                            ...
                        ]
                    },
                    "product": {
                        "id": int,
                        "shop": str,
                        "quantity": int,
                        "price": int,
                        "can_buy": bool,
                        "category": str,
                        "model": str,
                        "name": str,
                        "parameters": {
                            "parameter.name": str,
                            ...
                        }
                    }
                    "quantity": int,
                    "total_price": int,
                    "delivery_address": {
                        "city": str,
                        "street": str,
                        "house": str,
                        "apartment": str  # опционально
                    },
                    "status": str,
                    "created_at": str,
                    "updated_at": str
                }

            Измененный формат:
                {
                    "id": int,
                    "shop": str,
                    "quantity": int,
                    "price": int,
                    "can_buy": bool,
                    "category": str,
                    "model": str,
                    "name": str,
                    "parameters": {
                        "parameter.name": str,
                        ...
                    }
                }
        """
        repr: dict[str, int | dict] = super().to_representation(instance)
        print("123")
        repr["customer"] = repr["customer"]["email"]

        product_info: dict = repr.pop("product")
        repr["shop"] = product_info["shop"]
        repr["category"] = product_info["category"]
        repr["model"] = product_info["model"]
        repr["name"] = product_info["name"]

        repr["delivery_address"].pop("id")
        return repr

    def validate_delivery_address(self, value: dict[str, str | int]) -> dict[str, str | int]:
        request: Request = self.context["request"]
        if request.method == "PATCH":
            error_msg = _("Changing the delivery address of the created order is not available")
            logger.error(error_msg)
            raise ValidationError(error_msg)
        return value

    def validate_status(self, value: str) -> str:
        request: Request = self.context["request"]
        if not request.path.startswith(reverse("autopurchases:shop-list")):
            error_msg = _("Only shops can update the order status")
            logger.error(error_msg)
            raise ValidationError(error_msg)
        return value

    def update(self, instance: Order, validated_data: dict[str, str]) -> Order:
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save(update_fields=validated_data.keys())
        return instance


def check_quantity(on_stock: int, in_order: int) -> None:
    if on_stock < in_order:
        error_msg = _("The selected shop does not have enough products in stock")
        logger.error(error_msg)
        raise ValidationError(error_msg)


def check_availability(can_buy: bool) -> None:
    if not can_buy:
        error_msg = _("The selected product is not available for order")
        logger.error(error_msg)
        raise ValidationError(error_msg)
