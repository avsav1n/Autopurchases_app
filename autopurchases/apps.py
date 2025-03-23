from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AutopurchasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "autopurchases"
    verbose_name = _("Autopurchases")

    def ready(self):
        from autopurchases.signals import (
            new_order_created,
            new_user_registered,
            order_updated,
            reset_token_created,
        )
