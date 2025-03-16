from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token

from autopurchases.models import Order, PasswordResetToken, User
from autopurchases.tasks import send_email


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def new_user_registered(sender: User, instance: User, created: bool = False, **kwargs):
    if created:
        Token.objects.create(user=instance)
        subject = "Welcome to the AutopurchasesDjangoApp!"
        body = (
            f"Hello{f', {username}' if (username := instance.username) is not None else ''}!\n\n"
            "Thank you for registering with AutopurchasesDjangoApp! "
            "We welcome you to our community!\n\n"
            "Cincerely,\n"
            "AutopurchasesDjangoApp Team."
        )
        send_email.delay(subject=subject, body=body, to=[instance.email])


@receiver(post_save, sender=PasswordResetToken)
def reset_token_created(sender: PasswordResetToken, instance: PasswordResetToken, **kwargs):
    subject = "Password reset token."
    body = (
        f"Hello{f', {username}' if (username := instance.user.username) is not None else ''}!\n\n"
        "You received this email because you requested password recovery "
        "in the AutopurchasesDjangoApp.\n\n"
        f"Password reset token: {instance.token}\n"
        f"Token is valid until: {instance.exp_time}\n\n"
        "Cincerely,\n"
        "AutopurchasesDjangoApp Team."
    )
    send_email.delay_on_commit(subject=subject, body=body, to=[instance.user.email])


@receiver(post_save, sender=Order)
def new_order_created(sender: Order, instance: Order, created: bool = False, **kwargs):
    if created:
        subject = "New order created"
        order: Order = (
            Order.objects.with_dependencies()
            .prefetch_related("product__shop__managers")
            .get(pk=instance.id)
        )
        apartment = order.delivery_address.apartment
        username = order.customer.username
        header_for_user = (
            f"Hello{f', {username}' if username is not None else ''}!\n\n"
            f"You have created a new order №{order.id} in the AutopurchasesDjangoApp.\n\n"
            f"Order details:\n"
            f"Shop: {order.product.shop.name}\n"
        )
        header_for_shop = (
            f"Hello!\n"
            f"A new order №{order.id} has been placed in your store.\n\n"
            f"Order details:\n"
            f"Customer: {order.customer.email}\n"
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
            subject=subject, body=header_for_user + order_details, to=[order.customer.email]
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
    if not created and "status" in update_fields:
        subject = "Order status changed"
        order: Order = Order.objects.with_dependencies().get(pk=instance.id)
        apartment = order.delivery_address.apartment
        username = order.customer.username
        body = (
            f"Hello{f', {username}' if username is not None else ''}!\n\n"
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
        send_email.delay_on_commit(subject=subject, body=body, to=[order.customer.email])
