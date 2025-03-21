from django.apps import AppConfig


class AutopurchasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "autopurchases"
    verbose_name = "Автозакупки"

    def ready(self):
        from autopurchases.signals import (
            new_order_created,
            new_user_registered,
            order_updated,
            reset_token_created,
        )
