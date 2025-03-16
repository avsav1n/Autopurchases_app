import logging
import uuid
from collections import defaultdict
from typing import TypeAlias

from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import F, QuerySet
from django.forms import model_to_dict
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from autopurchases.models import (
    Cart,
    Category,
    Contact,
    Order,
    Parameter,
    PasswordResetToken,
    Product,
    ProductsParameters,
    Shop,
    ShopsManagers,
    Stock,
    User,
)

logger = logging.getLogger(__name__)


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "city", "street", "house", "apartment"]

    def to_internal_value(self, data: dict[str, str | int]):
        if "apartment" not in data:
            data["apartment"] = None
        return super().to_internal_value(data)

    def create(self, validated_data: dict):
        user: User = self.context["request"].user
        contact = Contact.objects.create(user=user, **validated_data)
        return contact


class UserSerializer(serializers.ModelSerializer):
    contacts = ContactSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "phone", "contacts"]
        extra_kwargs = {"password": {"write_only": True}, "username": {"required": False}}

    def validate_password(self, value: str):
        # FIXME
        # validate_password(value)
        return value

    def create(self, validated_data: dict):
        validated_data["password"] = make_password(password=validated_data["password"])
        return super().create(validated_data=validated_data)

    def update(self, instance: User, validated_data: dict):
        if password := validated_data.get("password"):
            validated_data["password"] = make_password(password=password)
        return super().update(instance=instance, validated_data=validated_data)


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class PasswordResetSerializer(serializers.Serializer):
    rtoken = serializers.UUIDField()
    password = serializers.CharField(max_length=128)

    def validate_password(self, value: str):
        # FIXME
        # validate_password(value)
        print("validate password")
        return value


class ShopSerializer(serializers.ModelSerializer):
    managers = serializers.PrimaryKeyRelatedField(
        many=True, queryset=User.objects.all(), required=False
    )

    class Meta:
        model = Shop
        fields = ["id", "name", "created_at", "updated_at", "managers"]

    def to_internal_value(self, data: dict | str):
        if isinstance(data, str):
            data = {"name": data}
        return super().to_internal_value(data)

    @transaction.atomic
    def create(self, validated_data: dict):
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

    def update(self, instance: Shop, validated_data: dict):
        if "managers" in validated_data:
            for manager in instance.managers_roles.select_related("manager").all():
                if manager.is_owner:
                    validated_data["managers"].append(manager.manager)
                    break
        return super().update(instance, validated_data)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]
        extra_kwargs = {"name": {"validators": []}}

    def to_internal_value(self, data: dict | str):
        if isinstance(data, str):
            data = {"name": data.capitalize()}
        return super().to_internal_value(data)

    def to_representation(self, instance: Category):
        return instance.name


class ParameterListSerializer(serializers.ListSerializer):
    def to_internal_value(self, data: dict[str, str | int]):
        data = [{"name": key, "value": str(value)} for key, value in data.items()]
        return super().to_internal_value(data)

    def to_representation(self, data):
        params: list[dict[str, str]] = super().to_representation(data)

        repr = {}
        for param in params:
            repr.update(param)
        return repr


class ParameterSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=50)

    class Meta:
        model = ProductsParameters
        fields = ["id", "name", "value"]
        list_serializer_class = ParameterListSerializer

    def to_representation(self, instance: ProductsParameters):
        repr = {instance.parameter.name: instance.value}
        return repr


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer()
    parameters = ParameterSerializer(source="parameters_values", many=True)
    price = serializers.IntegerField(write_only=True)
    quantity = serializers.IntegerField(write_only=True)
    can_buy = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = Product
        fields = ["id", "category", "model", "name", "price", "quantity", "parameters", "can_buy"]
        extra_kwargs = {"name": {"validators": []}}

    def to_representation(self, instance: Product):
        repr: dict[str, str | dict] = super().to_representation(instance=instance)

        if shop := self.context.get("shop"):
            stock = Stock.objects.get(product=instance, shop=shop)
            repr["price"] = stock.price
            repr["quantity"] = stock.quantity
            repr["can_buy"] = stock.can_buy

        return repr

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
    """Сериализатор аутентификации по email и password."""

    email = serializers.CharField(label=_("Email"), write_only=True)
    password = serializers.CharField(
        label=_("Password"),
        style={"input_type": "password"},
        trim_whitespace=False,
        write_only=True,
    )
    token = serializers.CharField(label=_("Token"), read_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            user = authenticate(request=self.context.get("request"), email=email, password=password)

            if not user:
                msg = _("Unable to log in with provided credentials.")
                raise ValidationError(msg, code="authorization")
        else:
            msg = _('Must include "username" and "password".')
            raise ValidationError(msg, code="authorization")

        attrs["user"] = user
        return attrs


class StockSerializer(serializers.ModelSerializer):
    shop = ShopSerializer(read_only=True)
    product = ProductSerializer(read_only=True)

    class Meta:
        model = Stock
        fields = ["id", "shop", "product", "quantity", "price", "can_buy"]

    def to_representation(self, instance: Stock):
        repr: dict[str, int | dict] = super().to_representation(instance)

        repr["shop"] = repr["shop"]["name"]

        product_info: dict = repr.pop("product")
        repr["category"] = product_info["category"]
        repr["model"] = product_info["model"]
        repr["name"] = product_info["name"]
        repr["parameters"] = product_info["parameters"]

        return repr


class CartSerialaizer(serializers.ModelSerializer):
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
            except ValidationError as error:
                logger.error(error.detail)
                continue
            with transaction.atomic():
                stock.quantity -= product.quantity
                stock.save(update_fields=["quantity"])
                order = Order.objects.create(
                    customer=product.customer,
                    product=product.product,
                    quantity=product.quantity,
                    delivery_address=delivery_address,
                )
                product.delete()
                created_orders.append(order)

        return created_orders


class OrderSerializer(serializers.ModelSerializer):
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
        repr: dict[str, int | dict] = super().to_representation(instance)

        repr["customer"] = repr["customer"]["email"]

        product_info: dict = repr.pop("product")
        repr["shop"] = product_info["shop"]
        repr["category"] = product_info["category"]
        repr["model"] = product_info["model"]
        repr["name"] = product_info["name"]

        repr["delivery_address"].pop("id")
        return repr

    def validate_status(self, value: str):
        request: Request = self.context["request"]
        if not request.path.startswith("/api/v1/shop"):
            raise ValidationError("Only shops can update the order status")
        return value

    def update(self, instance: Order, validated_data: dict):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save(update_fields=validated_data.keys())
        return instance


def check_quantity(on_stock: int, in_order: int) -> None:
    if on_stock < in_order:
        raise ValidationError("The selected shop does not have enough products in stock")


def check_availability(can_buy: bool) -> None:
    if not can_buy:
        raise ValidationError("The selected product is not available for order")
