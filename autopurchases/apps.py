from django.apps import AppConfig


class AutopurchasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "autopurchases"

    def ready(self):
        from autopurchases.signals import create_auth_token
