from celery import shared_task
from django.core.mail import EmailMessage


@shared_task
def send_email(subject: str, body: str, to: list[str]):
    email = EmailMessage(subject=subject, body=body, to=to)
    email.send()
