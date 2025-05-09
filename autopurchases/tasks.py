import logging

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

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
    if settings.EMAIL_BACKEND.endswith(".smtp.EmailBackend"):
        required = ("EMAIL_HOST", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD")
        missing = [param for param in required if not getattr(settings, param)]
        if missing:
            error_msg = format_lazy(
                _("SMTP not configured, missing {params}"), params=", ".join(missing)
            )
            logger.critical(error_msg)
            return

    msg = format_lazy(
        _("Celery task '{name}' {id} started"), name=self.name.split(".")[-1], id=self.request.id
    )
    logger.info(msg)

    email = EmailMessage(subject=subject, body=body, to=to)
    email.send()

    msg = format_lazy(_("Email sent to {to}"), to=", ".join(to))
    logger.info(msg)


@shared_task(bind=True)
def import_shop(self, data: dict[str, str | list[dict]], user_id: int) -> None:
    """Задача Celery, выполняющая асинхронную загрузку информации о магазине в базу данных.

    :param dict[str, str | list[dict]] data: информация о магазине
    :param int user_id: идентификатор пользователя (данный пользователь будет помечен как владелец
        магазина)
    """
    msg = format_lazy(
        _("Celery task '{name}' {id} started"), name=self.name.split(".")[-1], id=self.request.id
    )
    logger.info(msg)

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

        msg = format_lazy(_("Shop '{name}' import finished"), name=shop_info)
        logger.info(msg)

    except Exception as exc:
        error_msg = format_lazy(
            _("Exception in celery task '{name}' {id}. Error: {error}"),
            name=self.name.split(".")[-1],
            id=self.request.id,
            error=exc,
        )
        logger.exception(error_msg)


@shared_task(bind=True)
def export_shop(self, shop_id: int) -> dict[str, str | list[dict]]:
    """Задача Celery, выполняющая асинхронную выгрузку информации о магазине из базы данных.

    :param int shop_id: идентификатор магазина
    :return dict[str, str | list[dict]]: информация о магазине
    """
    msg = format_lazy(
        _("Celery task '{name}' {id} started"), name=self.name.split(".")[-1], id=self.request.id
    )
    logger.info(msg)

    shop: Shop = Shop.objects.get(pk=shop_id)
    stock: Stock = Stock.objects.with_dependencies().filter(shop_id=shop_id).all()
    stock_ser = StockSerializer(stock, many=True)
    stock_data = [
        {key: value for key, value in product.items() if key != "shop"}
        for product in stock_ser.data
    ]

    result = {"shop": shop.name, "products": stock_data}

    msg = format_lazy(_("Shop '{name}' import finished"), name=shop.name)
    logger.info(msg)

    return result
