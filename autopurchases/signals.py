from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from autopurchases.models import PasswordResetToken

from autopurchases.models import Order, User
from autopurchases.tasks import send_email


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def new_user_registered(sender: User, instance: User = None, created: bool = False, **kwargs):
    if created:
        Token.objects.create(user=instance)
        subject = (
            f"Welcome{f', {username}' if (username := instance.username) is not None else ''}!"
        )
        body = (
            f"Hello{f', {username}' if (username := instance.username) is not None else ''}!\n\n"
            "Thank you for registering with AupurchasesDjangoApp!"
            "We welcome you to our community.\n\n"
            "Cincerely,\n"
            "AupurchasesDjangoApp Team."
        )
        send_email.delay_on_commit(subject=subject, body=body, to=[instance.email])


@receiver(post_save, sender=PasswordResetToken)
def reset_token_created(sender: PasswordResetToken, instance: PasswordResetToken = None, **kwargs):
    pass
