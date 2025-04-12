import uuid
from datetime import datetime, timedelta
from uuid import UUID

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractUser, BaseUserManager
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
    """Class менеджера модели User.

    Изменения:
    - переопределены методы, меняющие поведение создания новых User, при использовании
        в качестве USERNAME_FIELD поля 'email'.
    """

    def _create_user(self, email: str, password: str, **extra_fields):
        if not email:
            raise ValueError(_("The given email must be set"))
        email = email.lower()
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
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Модель таблицы пользователей (User).

    Изменения:
    - в качестве USERNAME_FIELD используется обязательное поле 'email';
    - поле 'username' не используется;
    - добавлено поле 'phone';
    - менеджер модели заменен на другой, корректно обрабатывающий примененные выше изменения.
    """

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
    first_name = models.CharField(_("First name"), max_length=150, blank=True, null=True)
    last_name = models.CharField(_("Last name"), max_length=150, blank=True, null=True)

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        swappable = "AUTH_USER_MODEL"
        ordering = ["id"]

    def __str__(self):
        return self.email

    @property
    def hello_message(self):
        return f"Hello{f', {username}' if (username := self.first_name) else ''}!"


class Contact(models.Model):
    """Модель таблицы контактов (адресов)."""

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
            f"{self.city}, {self.street}/{self.house}"
            f"{f', {self.apartment}' if self.apartment is not None else ''}"
        )


class PasswordResetToken(models.Model):
    """Модель таблицы токенов сброса паролей пользователей."""

    user: User = models.OneToOneField(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("User"),
        related_name="rtoken",
    )
    rtoken: UUID = models.UUIDField(
        unique=True, default=uuid.uuid4, verbose_name=_("Password reset token")
    )
    created_at: datetime = models.DateTimeField(verbose_name=_("Created"), auto_now=True)

    def is_valid(self) -> bool:
        return self.created_at + timedelta(**settings.PASSWORD_RESET_TOKEN_TTL) > timezone.now()

    class Meta:
        verbose_name = _("Password reset token")
        verbose_name_plural = _("Password reset tokens")

    def __str__(self):
        return str(self.rtoken)


class Shop(models.Model):
    """Модель таблицы магазинов."""

    name: str = models.CharField(
        verbose_name=_("Name"),
        max_length=50,
        unique=True,
        help_text=_("Required. 50 characters or fewer."),
    )
    created_at: datetime = models.DateTimeField(verbose_name=_("Created"), auto_now_add=True)
    updated_at: datetime = models.DateTimeField(verbose_name=_("Updated"), auto_now=True)
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
        ordering = ["id"]

    def save(self, *args, **kwargs):
        if not self.id:
            self.slug = slugify(self.name)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ShopsManagers(models.Model):
    """Модель ассоциативной таблицы (m2m отношения) таблиц магазинов и пользователей.

    Дополнительные поля:
    - информация о роли пользователя у магазина.
    """

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
    """Модель таблицы категорий товаров."""

    name: str = models.CharField(
        verbose_name=_("Name"),
        max_length=50,
        unique=True,
        help_text=_("Required. 50 characters or fewer."),
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Products category")
        verbose_name_plural = _("Products categories")


class Product(models.Model):
    """Модель таблицы товаров."""

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
        to="Parameter", through="ProductsParameters", verbose_name=_("Parameters")
    )

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")

    def __str__(self):
        return self.name


class Parameter(models.Model):
    """Модель таблицы параметров товаров."""

    name: str = models.CharField(
        verbose_name=_("Name"),
        max_length=50,
        unique=True,
        help_text=_("Required. 50 characters or fewer."),
    )

    class Meta:
        verbose_name = _("Products parameter")
        verbose_name_plural = _("Products parameters")

    def __str__(self):
        return self.name


class ProductsParameters(models.Model):
    """Модель ассоциативной таблицы (m2m отношения) таблиц товаров и параметров.

    Дополнительные поля:
    - информация о значениях параметров у товара.
    """

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
        verbose_name = _("Products parameter")
        verbose_name_plural = _("Products parameters")
        constraints = [
            models.UniqueConstraint(
                fields=["product", "parameter", "value"], name="unique-product-parameter"
            )
        ]


class StockManager(models.Manager):
    """Class менеджера модели Stock.

    Изменения:
    - добавлен метод 'wth_dependencies', который оптимизирует загрузку связанных объектов,
    уменьшая количество запросов к базе данных.
    """

    def with_dependencies(self) -> QuerySet:
        return self.select_related(
            "product__category",
            "shop",
        ).prefetch_related(
            "product__parameters",
            "product__parameters_values",
        )


class Stock(models.Model):
    """Модель ассоциативной таблицы (m2m отношения) таблиц товаров и магазинов.

    Дополнительные поля:
    - информация о количестве товара у магазина;
    - информация о стоимости товара у магазина;
    - информация о возможности заказать товар у магазина.
    """

    objects: models.Manager = StockManager()
    shop: Shop = models.ForeignKey(
        to="Shop",
        on_delete=models.CASCADE,
        verbose_name=_("Shop"),
        help_text=_("Link to the shop."),
    )
    product: Product = models.ForeignKey(
        to="Product",
        on_delete=models.CASCADE,
        verbose_name=_("Product"),
        help_text=_("Link to the product."),
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
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["shop", "product"], name="unique-shop-product")
        ]

    def __str__(self):
        return f"{self.product.name} ({self.shop.name})"


class BaseOrder(models.Model):
    """Базовая модель для таблиц заказов."""

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
    """Class менеджера модели Cart.

    Изменения:
    - добавлен метод 'wth_dependencies', который оптимизирует загрузку связанных объектов,
    уменьшая количество запросов к базе данных.
    """

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
    """Модель ассоциативной таблицы (m2m отношения) таблиц товаров, магазинов и пользователей.

    Дополнительные поля:
    - информация о количестве товара в корзине у пользователя;
    - информация об итоговой стоимости товаров в корзине у пользователя.
    """

    objects = CartManager()

    class Meta:
        verbose_name = _("Products in cart")
        verbose_name_plural = _("Products in cart")
        ordering = ["id"]


class OrderManager(CartManager):
    """Class менеджера модели Order.

    Изменения:
    - добавлен метод 'wth_dependencies', который оптимизирует загрузку связанных объектов,
    уменьшая количество запросов к базе данных.
    """

    def with_dependencies(self) -> QuerySet:
        return super().with_dependencies().select_related("delivery_address")


class Order(BaseOrder):
    """Модель ассоциативной таблицы (m2m отношения) таблиц товаров, магазинов и пользователей.


    Дополнительные поля:
    - информация об адресе доставки заказа;
    - информация о статусе заказа;
    - информация о дате создания заказа;
    - информация о дате обновления заказа.
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
        ordering = ["id"]

    def __str__(self):
        return f"{super().__str__()} -> {self.delivery_address}"
