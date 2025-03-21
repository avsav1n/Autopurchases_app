import uuid
from datetime import date, datetime, timedelta
from uuid import UUID

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.db.models import QuerySet
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

STATUS_CHOICES = {
    "created": "Создан",
    "confirmed": "Подтвержден",
    "assembled": "Собран",
    "sent": "Отправлен",
    "delivered": "Доставлен",
    "cancelled": "Отменен",
}


class UserManager(BaseUserManager):
    def _create_user(self, email: str, password: str, **extra_fields):
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        user: User = self.model(email=email, **extra_fields)
        user.password = make_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Модель таблицы User"""

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()
    username = None
    email = models.EmailField(
        verbose_name=_("Email address"),
        unique=True,
        max_length=150,
        help_text=_("Required. 150 characters or fewer."),
    )
    phone: str = models.CharField(
        verbose_name=_("Phone number"),
        max_length=50,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        swappable = "AUTH_USER_MODEL"

    def __str__(self):
        return self.email

    @property
    def hello_message(self):
        return f"Hello{f', {username}' if (username := self.first_name) else ''}!"


class Contact(models.Model):
    user: User = models.ForeignKey(
        to="User",
        on_delete=models.CASCADE,
        verbose_name=_("User"),
        related_name="contacts",
        blank=True,
        null=True,
        help_text=_("Optional. Link to the user who uses the specified address."),
    )

    city: str = models.CharField(verbose_name=_("City"), max_length=50)
    street: str = models.CharField(verbose_name=_("Street"), max_length=50)
    house: str = models.CharField(verbose_name=_("House"), max_length=50)
    apartment: str = models.CharField(
        verbose_name=_("Apartment"),
        max_length=50,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = _("Contact")
        verbose_name_plural = _("Contacts")

    def __str__(self):
        return (
            f"{self.city}, {self.street}/{self.house}, "
            f"{f'{self.apartment}' if self.apartment is not None else ''}"
        )


class PasswordResetToken(models.Model):
    """Модель таблицы PasswordResetToken"""

    user: User = models.OneToOneField(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("User"),
        related_name="rtoken",
    )
    rtoken: UUID = models.UUIDField(
        unique=True, default=uuid.uuid4(), verbose_name=_("Password reset token")
    )
    created_at: datetime = models.DateTimeField(verbose_name=_("Created"), auto_now=True)

    def is_valid(self) -> bool:
        return self.created_at + timedelta(**settings.PASSWORD_RESET_TOKEN_TTL) > timezone.now()

    class Meta:
        verbose_name = _("Password reset token")
        verbose_name_plural = _("Password reset tokens")

    def __str__(self):
        return self.rtoken


class Shop(models.Model):
    """Модель таблицы Shop"""

    name: str = models.CharField(
        verbose_name=_("Name"),
        max_length=50,
        unique=True,
        help_text=_("Required. 50 characters or fewer."),
    )
    created_at: date = models.DateField(verbose_name=_("Created"), auto_now_add=True)
    updated_at: date = models.DateField(verbose_name=_("Updated"), auto_now=True)
    slug: str = models.SlugField(
        verbose_name=_("Slug"),
        unique=True,
        blank=True,
        help_text=_(
            "This field is automatically populated based on the name. "
            "It is used to create human-readable URLs."
        ),
    )
    managers: list["User"] = models.ManyToManyField(
        to=settings.AUTH_USER_MODEL,
        through="ShopsManagers",
        related_name="shops",
        verbose_name=_("Managers"),
    )

    class Meta:
        verbose_name = _("Shop")
        verbose_name_plural = _("Shops")

    def save(self, *args, **kwargs):
        if not self.id:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ShopsManagers(models.Model):
    manager: User = models.ForeignKey(
        to="User",
        on_delete=models.CASCADE,
        verbose_name=_("Manager"),
        related_name="shops_roles",
    )
    shop: Shop = models.ForeignKey(
        to="Shop",
        on_delete=models.CASCADE,
        verbose_name=_("Shop"),
        related_name="managers_roles",
    )
    is_owner: bool = models.BooleanField(verbose_name=_("Owner"), default=False)


class Category(models.Model):
    """Модель таблицы Category"""

    name: str = models.CharField(
        verbose_name=_("Name"),
        max_length=50,
        unique=True,
        help_text=_("Required. 50 characters or fewer."),
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")


class Product(models.Model):
    """Модель таблицы Product"""

    category: Category = models.ForeignKey(
        to="Category",
        on_delete=models.CASCADE,
        verbose_name=_("Category"),
    )
    model: str = models.CharField(
        verbose_name=_("Model"),
        max_length=50,
        help_text=_("Required. 50 characters or fewer."),
    )
    name: str = models.CharField(
        verbose_name=_("Name"),
        max_length=100,
        unique=True,
        help_text=_("Required. 100 characters or fewer."),
    )
    shops: list["Shop"] = models.ManyToManyField(
        to="Shop", through="Stock", related_name="products", verbose_name=_("Shops")
    )
    parameters: list["Parameter"] = models.ManyToManyField(
        to="Parameter",
        through="ProductsParameters",
        related_name="products",
        verbose_name=_("Parameters"),
    )

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")

    def __str__(self):
        return self.name


class Parameter(models.Model):
    """Модель таблицы Parameter"""

    name: str = models.CharField(
        verbose_name=_("Name"),
        max_length=50,
        unique=True,
        help_text=_("Required. 50 characters or fewer."),
    )

    class Meta:
        verbose_name = _("Parameter")
        verbose_name_plural = _("Parameters")

    def __str__(self):
        return self.name


class ProductsParameters(models.Model):
    product: Product = models.ForeignKey(
        to="Product",
        on_delete=models.CASCADE,
        verbose_name=_("Product"),
        related_name="parameters_values",
    )
    parameter: Parameter = models.ForeignKey(
        to="Parameter",
        on_delete=models.CASCADE,
        verbose_name=_("Parameter"),
        related_name="products_values",
    )
    value: str = models.CharField(verbose_name=_("Value"), max_length=50)

    class Meta:
        verbose_name = _("Parameter")
        verbose_name_plural = _("Parameters")
        constraints = [
            models.UniqueConstraint(
                fields=["product", "parameter", "value"], name="unique-product-parameter"
            )
        ]


class StockManager(models.Manager):
    def with_dependencies(self) -> QuerySet:
        return self.select_related(
            "product__category",
            "shop",
        ).prefetch_related(
            "product__parameters",
            "product__parameters_values",
        )


class Stock(models.Model):
    """Модель таблицы Stock

    Таблица m2m отношения между Product и Shop.
    """

    objects: models.Manager = StockManager()
    shop: Shop = models.ForeignKey(
        to="Shop",
        on_delete=models.CASCADE,
        verbose_name=_("Shop"),
    )
    product: Product = models.ForeignKey(
        to="Product",
        on_delete=models.CASCADE,
        verbose_name=_("Product"),
    )
    quantity: int = models.PositiveIntegerField(
        verbose_name=_("Quantity"),
        help_text=_("Quantity of the product in stock."),
    )
    price: int = models.PositiveBigIntegerField(
        verbose_name=_("Price"),
        help_text=_("Price of the product in minimum monetary units."),
    )
    can_buy: bool = models.BooleanField(
        verbose_name=_("Available for order"),
        default=True,
        help_text=_(
            "Check this if the product is available for order. "
            "If unchecked, the product will not be displayed on the website."
        ),
    )

    class Meta:
        verbose_name = _("Products in stock")
        verbose_name_plural = _("Products in stock")
        constraints = [
            models.UniqueConstraint(fields=["shop", "product"], name="unique-shop-product")
        ]

    def __str__(self):
        return f"{self.product.name} ({self.shop.name})"


class BaseOrder(models.Model):
    customer: User = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("Customer"),
    )
    product: Stock = models.ForeignKey(
        to="Stock",
        on_delete=models.CASCADE,
        verbose_name=_("Product"),
    )
    quantity: int = models.PositiveIntegerField(verbose_name=_("Quantity"))
    total_price: int = models.PositiveBigIntegerField(verbose_name=_("Total price"))

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.customer} | {self.product}"

    def save(self, *args, **kwargs):
        self.total_price = self.product.price * self.quantity
        return super().save(*args, **kwargs)


class CartManager(models.Manager):
    def with_dependencies(self) -> QuerySet:
        return self.select_related(
            "customer",
            "product__product",
            "product__product__category",
            "product__shop",
        ).prefetch_related(
            "product__product__parameters",
            "product__product__parameters_values",
        )


class Cart(BaseOrder):
    objects = CartManager()

    class Meta:
        verbose_name = _("Products in cart")
        verbose_name_plural = _("Products in cart")


class OrderManager(CartManager):
    def with_dependencies(self) -> QuerySet:
        return super().with_dependencies().select_related("delivery_address")


class Order(BaseOrder):
    """Модель таблицы Order

    Таблица m2m отношения между Customer и Stock
    """

    objects = OrderManager()
    delivery_address: Contact = models.ForeignKey(
        to="Contact",
        on_delete=models.CASCADE,
        verbose_name=_("Delivery address"),
    )
    status: str = models.CharField(
        verbose_name=_("Order status"), max_length=50, choices=STATUS_CHOICES, default="created"
    )
    created_at: datetime = models.DateTimeField(verbose_name=_("Created"), auto_now_add=True)
    updated_at: datetime = models.DateTimeField(verbose_name=_("Updated"), auto_now=True)

    class Meta:
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{super().__str__()} -> {self.delivery_address}"
