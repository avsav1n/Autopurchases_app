from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

from autopurchases.models import Customer, Shop


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(max_length=128, write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]


class CustomerSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Customer
        fields = ["id", "city", "street", "house", "apartment", "phone", "user"]

    @transaction.atomic
    def create(self, validated_data: dict):
        user_data: dict | None = validated_data.pop("user", None)
        if user_data is not None:
            user_serializer: UserSerializer = UserSerializer(data=user_data)
            user_serializer.is_valid(raise_exception=True)
            validated_data["user"] = user_serializer.save()
        return super().create(validated_data)


class ShopSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Shop
        fields = ["id", "description", "user"]
