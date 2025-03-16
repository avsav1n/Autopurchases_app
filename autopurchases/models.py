import secrets
import uuid
from datetime import date, datetime, timedelta
from uuid import UUID

from django.apps import apps
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
    email = models.EmailField(verbose_name="Электронная почта", unique=True)
    username = models.CharField(
        _("username"),
        max_length=150,
        help_text=_("Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."),
        validators=[UnicodeUsernameValidator()],
        blank=True,
        null=True,
    )
    phone: str = models.CharField(
        verbose_name="Номер телефона",
        max_length=50,
        blank=True,
        null=True,
    )

    def __str__(self):
        return f"{self.__class__.__name__}: {self.email}"


class Contact(models.Model):
    user: User = models.ForeignKey(
        to="User",
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
        related_name="contacts",
        blank=True,
        null=True,
    )

    city: str = models.CharField(verbose_name="Город", max_length=50)
    street: str = models.CharField(verbose_name="Улица", max_length=50)
    house: str = models.CharField(verbose_name="Дом", max_length=50)
    apartment: str = models.CharField(
        verbose_name="Квартира",
        max_length=50,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = "Контакты пользователя"
        verbose_name_plural = "Контакты пользователей"
        # FIXME
        # constraints = [
        #     models.UniqueConstraint(
        #         fields=["city", "street", "house", "appartment"],
        #         name="unique_address",
        #         nulls_distinct=False,
        #     )
        # ]


class PasswordResetToken(models.Model):
    """Модель таблицы PasswordResetToken"""

    user: User = models.OneToOneField(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
        related_name="rtoken",
    )
    rtoken: UUID = models.UUIDField(unique=True, verbose_name="Токен сброса пароля")
    exp_time: datetime = models.DateTimeField(verbose_name="Действителен до")

    def is_valid(self):
        return timezone.now() < self.exp_time

    class Meta:
        verbose_name = "Токен сброса пароля"
        verbose_name_plural = "Токены сброса пароля"


class Shop(models.Model):
    """Модель таблицы Shop"""

    name: str = models.CharField(verbose_name="Название", max_length=50, unique=True)
    created_at: date = models.DateField(verbose_name="Дата создания", auto_now_add=True)
    updated_at: date = models.DateField(verbose_name="Обновлено", auto_now=True)
    slug: str = models.SlugField(verbose_name="Slug", unique=True)
    managers: list["User"] = models.ManyToManyField(
        to=settings.AUTH_USER_MODEL,
        through="ShopsManagers",
        related_name="shops",
        verbose_name="Управляющие",
    )

    class Meta:
        verbose_name = "Магазин"
        verbose_name_plural = "Магазины"

    def save(self, *args, **kwargs):
        if not self.id:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.__class__.__name__}: {self.name}"


class ShopsManagers(models.Model):
    manager: User = models.ForeignKey(
        to="User", on_delete=models.CASCADE, verbose_name="Управляющие"
    )
    shop: Shop = models.ForeignKey(
        to="Shop", on_delete=models.CASCADE, verbose_name="Магазины", related_name="managers_roles"
    )
    is_owner: bool = models.BooleanField(verbose_name="Собственник", default=False)


class Category(models.Model):
    """Модель таблицы Category"""

    name: str = models.CharField(verbose_name="Название", max_length=50, unique=True)

    def __str__(self):
        return f"{self.__class__.__name__}: {self.name}"

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"


class Product(models.Model):
    """Модель таблицы Product"""

    model: str = models.CharField(verbose_name="Модель", max_length=50)
    name: str = models.CharField(verbose_name="Название", max_length=100, unique=True)
    category: Category = models.ForeignKey(
        to="Category", on_delete=models.CASCADE, verbose_name="Категория"
    )
    shops: list["Shop"] = models.ManyToManyField(
        to="Shop", through="Stock", related_name="products", verbose_name="Магазины"
    )
    parameters: list["Parameter"] = models.ManyToManyField(
        to="Parameter",
        through="ProductsParameters",
        related_name="products",
        verbose_name="Параметры",
    )

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

    def __str__(self):
        return f"{self.__class__.__name__}: {self.name}"


class Parameter(models.Model):
    """Модель таблицы Parameter"""

    name: str = models.CharField(verbose_name="Название", max_length=50, unique=True)

    class Meta:
        verbose_name = "Параметр"
        verbose_name_plural = "Параметры"

    def __str__(self):
        return f"{self.__class__.__name__}: {self.name}"


class ProductsParameters(models.Model):
    product: Product = models.ForeignKey(
        to="Product",
        on_delete=models.CASCADE,
        verbose_name="Товар",
        related_name="parameters_values",
    )
    parameter: Parameter = models.ForeignKey(
        to="Parameter",
        on_delete=models.CASCADE,
        verbose_name="Параметр",
        related_name="products_values",
    )
    value: str = models.CharField(verbose_name="Значение", max_length=50)

    class Meta:
        verbose_name = "Параметр"
        verbose_name_plural = "Параметры"
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
        verbose_name="Магазин",
    )
    product: Product = models.ForeignKey(
        to="Product",
        on_delete=models.CASCADE,
        verbose_name="Товар",
    )
    quantity: int = models.PositiveIntegerField(verbose_name="Количество")
    price: int = models.PositiveBigIntegerField(verbose_name="Цена")
    can_buy: bool = models.BooleanField(verbose_name="Доступен для заказа", default=True)

    class Meta:
        verbose_name_plural = "Каталог товаров"
        constraints = [
            models.UniqueConstraint(fields=["shop", "product"], name="unique-shop-product")
        ]


class BaseOrder(models.Model):
    customer: User = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Заказчик",
    )
    product: Stock = models.ForeignKey(
        to="Stock",
        on_delete=models.CASCADE,
        verbose_name="Товар",
    )
    quantity: int = models.PositiveIntegerField(verbose_name="Количество")
    total_price: int = models.PositiveBigIntegerField(verbose_name="Итоговая стоимость")

    class Meta:
        abstract = True

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
        verbose_name_plural = "Товары в корзине"


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
        verbose_name="Адрес доставки",
    )
    status: str = models.CharField(
        verbose_name="Статус заказа", max_length=50, choices=STATUS_CHOICES, default="created"
    )
    created_at: datetime = models.DateTimeField(verbose_name="Дата создания", auto_now_add=True)
    updated_at: datetime = models.DateTimeField(verbose_name="Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]
