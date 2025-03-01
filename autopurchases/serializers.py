from typing import TypeAlias

from django.contrib.auth import authenticate
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from autopurchases.models import (
    Category,
    Contact,
    Parameter,
    Product,
    ProductsParameters,
    Shop,
    ShopsManagers,
    Stock,
    User,
)


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "city", "street", "house", "apartment"]

    def create(self, validated_data: dict):
        user: User = self.context["request"].user
        contact = Contact.objects.create(user=user, **validated_data)
        return contact


class UserSerializer(serializers.ModelSerializer):
    contacts = ContactSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "phone", "contacts"]
        extra_kwargs = {"password": {"write_only": True}}

    def validate_password(self, value: str):
        validate_password(value)
        return value

    def create(self, validated_data: dict):
        validated_data["password"] = make_password(password=validated_data["password"])
        user: User = super().create(validated_data=validated_data)
        return user

    def update(self, instance: User, validated_data: dict):
        if password := validated_data.get("password"):
            validated_data["password"] = make_password(password=password)
        user: User = super().update(instance=instance, validated_data=validated_data)
        return user


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

        creator: User = self.context["request"].user
        all_managers = []
        if managers is not None:
            all_managers = [
                ShopsManagers(shop=shop, manager=manager)
                for manager in managers
                if manager != creator
            ]
        all_managers.append(ShopsManagers(shop=shop, manager=creator, is_owner=True))
        ShopsManagers.objects.bulk_create(all_managers)

        return shop


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

    def create(self, validated_data: dict):
        instance, _ = self.Meta.model.objects.get_or_create(**validated_data)
        return instance


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
    category = CategorySerializer(validators=[])
    parameters = ParameterSerializer(source="parameters_values", many=True)
    price = serializers.IntegerField(write_only=True)
    quantity = serializers.IntegerField(write_only=True)

    class Meta:
        model = Product
        fields = ["id", "category", "model", "name", "price", "quantity", "parameters"]
        extra_kwargs = {"name": {"validators": []}}

    def to_representation(self, instance: Product):
        # TODO: кеширование создаваемых объектов
        # TODO: доделать сериализатор, чтобы отдавал данные в том числе без привязки к магазину
        repr: dict[str, str | dict] = super().to_representation(instance=instance)
        if shop := self.context.get("shop"):
            stock = Stock.objects.get(product=instance, shop=shop)
            repr["price"] = stock.price
            repr["quantity"] = stock.quantity
        return repr

    @transaction.atomic
    def create(self, validated_data: dict):
        shop: Shop = self.context["shop"]

        category, _ = Category.objects.get_or_create(validated_data["category"])

        product, _ = Product.objects.get_or_create(
            category=category, model=validated_data["model"], name=validated_data["name"]
        )
        # TODO: если товар уже есть надо просто обновить его параметры или не трогать их
        # TODO: скорее всего товар уже хранится с какимито параметрами
        for params in validated_data["parameters_values"]:
            parameter, _ = Parameter.objects.get_or_create(name=params["name"])
            ProductsParameters.objects.get_or_create(
                product=product, parameter=parameter, value=params["value"]
            )

        Stock.objects.create(
            shop=shop,
            product=product,
            price=validated_data["price"],
            quantity=validated_data["quantity"],
        )

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
                raise serializers.ValidationError(msg, code="authorization")
        else:
            msg = _('Must include "username" and "password".')
            raise serializers.ValidationError(msg, code="authorization")

        attrs["user"] = user
        return attrs
