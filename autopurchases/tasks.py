import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import QuerySet
from rest_framework.request import Request

from autopurchases.models import Product, Shop, User
from autopurchases.serializers import ProductSerializer, ShopSerializer

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def send_email(self, subject: str, body: str, to: list[str]):
    logger.info("Celery task '%s' %s started", self.name.split(".")[-1], self.request.id)

    email = EmailMessage(subject=subject, body=body, to=to)
    email.send()

    logger.info("Email sent to %s", ", ".join(to))


@shared_task(bind=True)
def import_shop(self, data: dict[str, str | list[dict]], user_id: int):
    logger.info("Celery task '%s' %s started", self.name.split(".")[-1], self.request.id)

    with transaction.atomic():
        user: User = User.objects.get(pk=user_id)
        shop_info: str = data["shop"]
        shop_ser = ShopSerializer(data=shop_info, context={"owner": user})
        shop_ser.is_valid(raise_exception=True)
        shop_ser.save()

        products_info: list[dict] = data["products"]
        products_ser = ProductSerializer(
            data=products_info, many=True, context={"shop": shop_ser.instance}
        )
        products_ser.is_valid(raise_exception=True)
        products_ser.save()

    logger.info("Shop '%s' import finished", shop_info)


@shared_task(bind=True)
def export_shop(self, shop_id: int):
    logger.info("Celery task '%s' %s started", self.name.split(".")[-1], self.request.id)

    shop: Shop = Shop.objects.get(pk=shop_id)
    products: QuerySet[Product] = shop.products.all()
    shop_ser = ShopSerializer(shop)
    products_ser = ProductSerializer(products, many=True)
    result = {"shop": shop_ser.data["name"], "products": products_ser.data}

    logger.info("Shop '%s' export finished", shop.name)

    return result
