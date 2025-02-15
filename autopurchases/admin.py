from reprlib import repr

from django.contrib import admin
from django.db.models import QuerySet

from autopurchases.models import Customer, Shop


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "description_column", "registered_at"]

    @admin.display(description="Описание")
    def description_column(self, obj: Shop):
        return repr(obj.description)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["id", "city", "street", "house", "apartment", "phone", "user", "registered_at"]
