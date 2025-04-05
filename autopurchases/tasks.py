import logging

from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db import transaction

from autopurchases.models import Shop, Stock, User
from autopurchases.serializers import ProductSerializer, ShopSerializer, StockSerializer

logger = logging.getLogger(__name__)
UserModel = get_user_model()


@shared_task(bind=True)
def send_email(self, subject: str, body: str, to: list[str]) -> None:
    """Задача Celery, выполняющая асинхронную отправку письма по электронной почте.

    :param str subject: тема
    :param str body: содержание
    :param list[str] to: список email получателей
    """
    logger.info("Celery task '%s' %s started", self.name.split(".")[-1], self.request.id)

    email = EmailMessage(subject=subject, body=body, to=to)
    email.send()

    logger.info("Email sent to %s", ", ".join(to))


@shared_task(
    bind=True,
)
def import_shop(self, data: dict[str, str | list[dict]], user_id: int) -> None:
    """Задача Celery, выполняющая асинхронную загрузку информации о магазине в базу данных.

    :param dict[str, str | list[dict]] data: информация о магазине
    :param int user_id: идентификатор пользователя (данный пользователь будет помечен как владелец
        магазина)
    """
    logger.info("Celery task '%s' %s started", self.name.split(".")[-1], self.request.id)
    try:
        with transaction.atomic():
            user: User = UserModel.objects.get(pk=user_id)
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
    except Exception as exc:
        logger.exception(
            "Exception in celery task '%s' %s. Error: %s",
            self.name.split(".")[-1],
            self.request.id,
            exc,
        )


@shared_task(bind=True)
def export_shop(self, shop_id: int) -> dict[str, str | list[dict]]:
    """Задача Celery, выполняющая асинхронную выгрузку информации о магазине из базы данных.

    :param int shop_id: идентификатор магазина
    :return dict[str, str | list[dict]]: информация о магазине
    """
    logger.info("Celery task '%s' %s started", self.name.split(".")[-1], self.request.id)

    shop: Shop = Shop.objects.get(pk=shop_id)
    stock: Stock = Stock.objects.with_dependencies().filter(shop_id=shop_id).all()
    stock_ser = StockSerializer(stock, many=True)
    stock_data = [
        {key: value for key, value in product.items() if key != "shop"}
        for product in stock_ser.data
    ]

    result = {"shop": shop.name, "products": stock_data}
    logger.info("Shop '%s' export finished", shop.name)

    return result
