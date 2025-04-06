from datetime import timedelta

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token

from autopurchases.models import Order, PasswordResetToken, User
from autopurchases.tasks import send_email


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def new_user_registered(sender: User, instance: User, created: bool = False, **kwargs):
    """Сигнальная функция.

    Триггер:
    - создание нового пользователя (модель User) в приложении.

    Действия:
    - создание токена авторизации для нового пользователя;
    - асинхронная отправка привественного письма на email нового пользователя.
    """
    if created:
        Token.objects.create(user=instance)
        subject = "Welcome to the AutopurchasesDjangoApp!"
        body = (
            f"{instance.hello_message}\n\n"
            "Thank you for registering with AutopurchasesDjangoApp! "
            "We welcome you to our community!\n\n"
            "Cincerely,\n"
            "AutopurchasesDjangoApp Team."
        )
        send_email.delay_on_commit(subject=subject, body=body, to=[instance.email])


@receiver(post_save, sender=PasswordResetToken)
def reset_token_created(sender: PasswordResetToken, instance: PasswordResetToken, **kwargs):
    """Сигнальная функция.

    Триггер:
    - создание/обновление токена сброса пароля (модель PasswordResetToken).

    Действия:
    - асинхронная отправка запрошенного токена сброса пароля на email пользователя.
    """
    subject = "Password reset token."
    user: User = instance.user
    body = (
        f"{user.hello_message}\n\n"
        "You received this email because you requested password recovery "
        "in the AutopurchasesDjangoApp.\n\n"
        f"Password reset token: {instance.rtoken}\n"
        f"Token is valid until: {instance.created_at + timedelta(hours=1)}\n\n"
        "Cincerely,\n"
        "AutopurchasesDjangoApp Team."
    )
    send_email.delay_on_commit(subject=subject, body=body, to=[user.email])


@receiver(post_save, sender=Order)
def new_order_created(sender: Order, instance: Order, created: bool = False, **kwargs):
    """Сигнальная функция.

    Триггер:
    - создание нового заказа (модель Order).

    Действия:
    - асинхронная отправка уведомлений о новом заказе на email заказчика и менеджерам магазина.
    """
    if created:
        subject = "New order created!"
        order: Order = (
            Order.objects.with_dependencies()
            .prefetch_related("product__shop__managers")
            .get(pk=instance.id)
        )
        apartment: int | None = order.delivery_address.apartment
        customer: User = order.customer
        header_for_user = (
            f"{customer.hello_message}\n\n"
            f"You have created a new order №{order.id} in the AutopurchasesDjangoApp.\n\n"
            f"Order details:\n"
            f"Shop: {order.product.shop.name}\n"
        )
        header_for_shop = (
            f"Hello!\n"
            f"A new order №{order.id} has been placed in your store.\n\n"
            f"Order details:\n"
            f"Customer: {customer.email}\n"
        )
        order_details = (
            f"Product:\n"
            f"\tModel: {order.product.product.model}\n"
            f"\tName: {order.product.product.name}\n"
            f"\tQuantity: {order.quantity}\n"
            f"\tTotal price: {order.total_price}\n"
            f"Delivery address:\n"
            f"\tCity: {order.delivery_address.city}\n"
            f"\tStreet: {order.delivery_address.street}\n"
            f"\tHouse: {order.delivery_address.house}\n"
            f"{f'\tApartment: {apartment}\n\n' if apartment is not None else '\n'}"
            "Cincerely,\n"
            "AutopurchasesDjangoApp Team."
        )
        send_email.delay_on_commit(
            subject=subject, body=header_for_user + order_details, to=[customer.email]
        )

        managers_emails = [manager.email for manager in order.product.shop.managers.all()]
        send_email.delay_on_commit(
            subject=subject, body=header_for_shop + order_details, to=managers_emails
        )


@receiver(post_save, sender=Order)
def order_updated(
    sender: Order,
    instance: Order,
    update_fields: frozenset | None = None,
    created: bool = False,
    **kwargs,
):
    """Сигнальная функция.

    Триггер:
    - обновление статуса заказа (модель Order).

    Действия:
    - асинхронная отправка уведомления о смене статуса заказа на email заказчика.
    """
    if not created and update_fields is not None and "status" in update_fields:
        subject = "Order status changed."
        order: Order = Order.objects.with_dependencies().get(pk=instance.id)
        apartment: int | None = order.delivery_address.apartment
        customer: User = order.customer
        body = (
            f"{customer.hello_message}\n\n"
            f"Order status №{order.id} changed to '{order.status}'.\n\n"
            f"Order details:\n"
            f"Shop: {order.product.shop.name}\n"
            f"Product:\n"
            f"\tModel: {order.product.product.model}\n"
            f"\tName: {order.product.product.name}\n"
            f"\tQuantity: {order.quantity}\n"
            f"\tTotal price: {order.total_price}\n"
            f"Delivery address:\n"
            f"\tCity: {order.delivery_address.city}\n"
            f"\tStreet: {order.delivery_address.street}\n"
            f"\tHouse: {order.delivery_address.house}\n"
            f"{f'\tApartment: {apartment}\n\n' if apartment is not None else '\n'}"
            "Cincerely,\n"
            "AutopurchasesDjangoApp Team."
        )
        send_email.delay_on_commit(subject=subject, body=body, to=[customer.email])
