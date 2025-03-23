import logging
import uuid
from functools import partial
from reprlib import repr
from typing import TypeVar

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import (
    AdminUserCreationForm,
    UserChangeForm,
    UserCreationForm,
    UsernameField,
)
from django.db import models
from django.db.models import Case, Count, F, QuerySet, Value, When
from django.forms import BaseInlineFormSet, ValidationError
from django.http import HttpRequest
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.authtoken.admin import TokenAdmin
from rest_framework.authtoken.models import TokenProxy

from autopurchases.models import (
    Cart,
    Category,
    Contact,
    Order,
    Parameter,
    PasswordResetToken,
    Product,
    Shop,
    Stock,
    User,
)

UserModel = get_user_model()
admin.site.unregister(TokenProxy)
logger = logging.getLogger(__name__)


class ShopManagersFormset(BaseInlineFormSet):
    def clean(self) -> None:
        main_flag = False
        for form in self.forms:
            if form.cleaned_data.get("DELETE"):
                continue
            if (form_flag := form.cleaned_data.get("is_owner")) and main_flag:
                error_msg = _("A shop can only have one owner.")
                logger.warning(error_msg)
                raise ValidationError(error_msg)
            main_flag = main_flag or form_flag
        return super().clean()


class UserContactsInline(admin.TabularInline):
    model = Contact
    extra = 0
    verbose_name_plural = _("User contacts")
    max_num = settings.MAX_CONTACTS_FOR_USER


class ShopManagersInline(admin.TabularInline):
    model = Shop.managers.through
    extra = 0
    verbose_name_plural = _("Shop managers")
    formset = ShopManagersFormset
    autocomplete_fields = ("manager",)


class ProductParametersInline(admin.TabularInline):
    model = Product.parameters.through
    extra = 0
    verbose_name_plural = _("Product parameters")
    autocomplete_fields = ("parameter",)


class IsManagerListFilter(admin.SimpleListFilter):
    title = _("shop manager")
    parameter_name = "is_manager"

    def lookups(
        self, request: HttpRequest, model_admin: "CustomUserAdmin"
    ) -> list[tuple[str, str]]:
        return [("yes", "Да"), ("no", "Нет")]

    def queryset(self, request: HttpRequest, queryset: QuerySet[User]) -> QuerySet[User]:
        if self.value() == "yes":
            return queryset.filter(shops_count__gte=1)
        elif self.value() == "no":
            return queryset.filter(shops_count=0)
        return queryset


class CustomAdminUserCreationForm(AdminUserCreationForm):
    class Meta:
        model = UserModel
        fields = ("email",)
        field_classes = {"email": UsernameField}


@admin.register(UserModel)
class CustomUserAdmin(UserAdmin):
    list_display = ("id", "email", "is_staff", "is_manager_display")
    list_filter = ("is_staff", IsManagerListFilter)
    list_display_links = ("email",)
    ordering = ("email",)

    readonly_fields = ("date_joined", "last_login")

    search_fields = ("email", "first_name", "last_name")
    search_help_text = _("Email, first or last name")

    add_form = CustomAdminUserCreationForm
    inlines = [UserContactsInline]

    fieldsets = (
        (_("Credentials"), {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone")}),
        (
            _("Permissions"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (_("Activity history"), {"fields": ("date_joined", "last_login")}),
    )
    add_fieldsets = (
        (
            _("Credentials"),
            {
                "classes": ("wide",),
                "fields": ("email", "usable_password", "password1", "password2"),
            },
        ),
        (
            _("Personal info"),
            {"classes": ("collapse",), "fields": ("first_name", "last_name", "phone")},
        ),
    )

    @admin.display(boolean=True, ordering="is_manager", description=_("Shop manager"))
    def is_manager_display(self, obj: User) -> bool:
        return obj.is_manager

    def get_queryset(self, request: HttpRequest) -> QuerySet[User]:
        qs = super().get_queryset(request)
        qs = qs.annotate(shops_count=Count("shops"))
        qs = qs.annotate(
            is_manager=Case(
                When(shops_count__gte=1, then=Value(True)),
                default=Value(False),
                output_field=models.BooleanField(),
            )
        )
        return qs


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("id", "city", "street", "house", "apartment", "user")
    list_filter = ("city",)
    list_display_links = ("city",)

    search_fields = ("city", "street", "house", "apartment")
    search_help_text = _("City, street, house or apartment")

    autocomplete_fields = ("user",)

    fieldsets = (
        (_("Address"), {"fields": ("city", "street", "house", "apartment")}),
        (_("User"), {"fields": ("user",)}),
    )


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "rtoken", "user", "created_at")
    list_filter = ("created_at",)
    list_display_links = ("rtoken",)
    ordering = ("-created_at",)

    search_fields = ("user__email",)
    search_help_text = _("User email")

    autocomplete_fields = ("user",)
    readonly_fields = ("rtoken", "user")

    actions = ["refresh_rtoken"]

    @admin.action(description=_("Refresh selected Password reset tokens"))
    def refresh_rtoken(self, request: HttpRequest, queryset: QuerySet[PasswordResetToken]) -> None:
        rtokens = []
        for rtoken in queryset:
            rtoken.rtoken = uuid.uuid4()
            rtoken.created_at = timezone.now()
            rtokens.append(rtoken)
        PasswordResetToken.objects.bulk_update(objs=rtokens, fields=["rtoken", "created_at"])


@admin.register(TokenProxy)
class CustomTokenAdmin(TokenAdmin):
    list_display = ("key", "user", "created")
    list_filter = ("created",)
    list_display_links = None
    ordering = ("-created",)

    search_fields = ("user__email",)
    search_help_text = _("Email address")

    autocomplete_fields = ("user",)


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "created_at", "updated_at", "managers_count_display")
    list_filter = ("created_at", "updated_at")
    list_display_links = ("name",)
    ordering = ("-created_at",)

    search_fields = ("name",)
    search_help_text = _("Shop name")

    prepopulated_fields = {"slug": ("name",)}

    inlines = [ShopManagersInline]

    fieldsets = ((_("Shop info"), {"fields": ("name", "slug")}),)

    @admin.display(description=_("Number of managers"), ordering="managers_count")
    def managers_count_display(self, obj: Shop) -> int:
        return obj.managers_count

    def get_queryset(self, request: HttpRequest) -> QuerySet[Shop]:
        qs = super().get_queryset(request)
        qs = qs.annotate(managers_count=Count("managers"))
        qs = qs.prefetch_related("managers")
        return qs


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    list_display_links = ("name",)
    ordering = ("name",)

    search_fields = ("name",)
    search_help_text = _("Category name")

    fieldsets = ((("Category info"), {"fields": ("name",)}),)


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    list_display_links = ("name",)
    ordering = ("name",)

    search_fields = ("name",)
    search_help_text = _("Parameter name")

    fieldsets = ((("Parameter info"), {"fields": ("name",)}),)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "category", "model")
    list_display_links = ("name",)
    ordering = ("name",)

    search_fields = ("name",)
    search_help_text = _("Category name")

    autocomplete_fields = ("category",)

    inlines = [ProductParametersInline]

    fieldsets = ((("Product info"), {"fields": ("name", "category", "model")}),)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Product]:
        qs = super().get_queryset(request)
        qs = qs.select_related("category")
        qs = qs.prefetch_related("parameters")
        return qs


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "shop", "quantity", "price", "can_buy")
    list_filter = ("can_buy",)
    list_display_links = ("product",)

    list_editable = ("quantity", "price", "can_buy")

    search_fields = ("shop__name", "product__name", "product__category__name")
    search_help_text = _("Shop, product or product category name")

    autocomplete_fields = ("shop", "product")

    fieldsets = (
        (
            _("Stock position info"),
            {"fields": ("product", "shop", "quantity", "price", "can_buy")},
        ),
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Stock]:
        qs = super().get_queryset(request)
        qs = qs.select_related("shop", "product__category")
        return qs


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "product", "quantity", "total_price")
    list_display_links = ("customer",)

    search_fields = (
        "product__shop__name",
        "product__product__name",
        "product__product__category__name",
        "customer__email",
    )
    search_help_text = _("Customer email, shop, product or product category name")

    fieldsets = (
        (_("Cart position info"), {"fields": ("customer", "product", "quantity", "total_price")}),
    )

    def has_change_permission(self, *args, **kwargs) -> bool:
        return False

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related("customer", "product__product__category", "product__shop")
        return qs


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "customer",
        "delivery_address",
        "product",
        "quantity",
        "total_price",
        "status",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "created_at", "updated_at")
    list_display_links = ("customer",)
    list_editable = ("status",)

    readonly_fields = (
        "customer",
        "product",
        "delivery_address",
        "quantity",
        "total_price",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "product__shop__name",
        "product__product__name",
        "product__product__category__name",
        "customer__email",
    )
    search_help_text = _("Customer email, shop, product or product category name")

    fieldsets = (
        (
            ("Order info"),
            {
                "fields": (
                    "customer",
                    "delivery_address",
                    "product",
                    "quantity",
                    "total_price",
                    "status",
                )
            },
        ),
        (("Timestamps"), {"fields": ("created_at", "updated_at")}),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related(
            "customer", "delivery_address", "product__product__category", "product__shop"
        )
        return qs
