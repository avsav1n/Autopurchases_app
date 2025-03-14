from django.conf import settings
from django.core.mail import EmailMessage
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
            "Thank you for registering with AutopurchasesDjangoApp!"
            "We welcome you to our community.\n\n"
            "Cincerely,\n"
            "AutopurchasesDjangoApp Team."
        )
        # FIXME
        send_email.delay(subject=subject, body=body, to=[instance.email])
        # email = EmailMessage(subject=subject, body=body, to=[instance.email])
        # email.send()


@receiver(post_save, sender=PasswordResetToken)
def reset_token_created(sender: PasswordResetToken, instance: PasswordResetToken, **kwargs):
    subject = "Password reset token."
    body = (
        f"Hello {f'{instance.user.username}'}!\n"
        "You received this email because you requested password recovery "
        "in the AutopurchasesDjangoApp.\n\n"
        f"Password reset token: {instance.token}\n"
        f"Token is valid until: {instance.exp_time}\n\n"
        "Cincerely,\n"
        "AutopurchasesDjangoApp Team."
    )
    # FIXME
    # send_email.delay_on_commit(subject=subject, body=body, to=[instance.user.email])
    email = EmailMessage(subject=subject, body=body, to=[instance.user.email])
    email.send()
