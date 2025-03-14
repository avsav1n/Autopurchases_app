from celery import shared_task
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import QuerySet
from rest_framework.request import Request

from autopurchases.models import Product, Shop, User
from autopurchases.serializers import ProductSerializer, ShopSerializer


@shared_task
def send_email(subject: str, body: str, to: list[str]):
    # FIXME
    to = ["head32@mail.ru"]
    email = EmailMessage(subject=subject, body=body, to=to)
    email.send()


@shared_task
def import_shop(data: dict[str, str | list[dict]], user_id: int):
    with transaction.atomic():
        user: User = User.objects.get(pk=user_id)
        shop_info: str = data["shop"]
        shop_ser = ShopSerializer(data=shop_info, context={"creator": user})
        shop_ser.is_valid(raise_exception=True)
        shop_ser.save()

        products_info: list[dict] = data["products"]
        products_ser = ProductSerializer(
            data=products_info, many=True, context={"shop": shop_ser.instance}
        )
        products_ser.is_valid(raise_exception=True)
        products_ser.save()


@shared_task
def export_shop(shop_id: int):
    shop: Shop = Shop.objects.get(pk=shop_id)
    products: QuerySet[Product] = shop.products.all()
    shop_ser = ShopSerializer(shop)

    products_ser = ProductSerializer(products, many=True)

    result = {"shop": shop_ser.data["name"], "products": products_ser.data}
    return result
