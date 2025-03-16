from reprlib import repr

from django.contrib import admin
from django.contrib.auth.forms import UserChangeForm
from django.http import HttpRequest

from autopurchases.models import Category, Order, Parameter, Product, Shop, Stock, User


class ProductsParametersInline(admin.TabularInline):
    model = Product.parameters.through
    extra = 0


class ShopManagersInline(admin.TabularInline):
    model = Shop.managers.through
    extra = 0


# @admin.register(Shop)
# class ShopAdmin(admin.ModelAdmin):
#     list_display = ["id", "name", "description_column", "created_at", "updated_at"]
#     fieldsets = [
#         ("Информация о магазине", {"fields": ("name", "description")}),
#     ]
#     inlines = [ShopManagersInline]
#     exclude = ["managers"]
#     list_display_links = ["name"]

#     @admin.display(description="Описание", ordering="description")
#     def description_column(self, obj: Shop):
#         description: str = repr(obj.description)
#         if description != "None":
#             return description
#         return self.get_empty_value_display()

#     def get_queryset(self, request: HttpRequest):
#         return Shop.objects.prefetch_related("managers").all()


# @admin.register(User)
# class UserAdmin(admin.ModelAdmin):
#     form = UserChangeForm
#     list_display = ["id", "username", "email", "is_staff"]
#     fieldsets = [
#         ("Учетные данные", {"fields": ("username", "password")}),
#         ("Персональные данные", {"fields": ("first_name", "last_name", "email", "phone")}),
#         ("Адрес", {"fields": ("city", "street", "house", "apartment")}),
#         (
#             "Права доступа",
#             {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
#         ),
#         ("История активности", {"fields": ("last_login", "date_joined")}),
#     ]
#     filter_horizontal = ["groups", "user_permissions"]
#     list_display_links = ["username"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    pass


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductsParametersInline]


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    pass


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    pass


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    pass


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    pass
