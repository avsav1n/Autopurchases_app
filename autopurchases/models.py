from datetime import date, datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models

STATUS_CHOICES = {
    "in_basket": "В корзине",
    "created": "Создан",
    "confirmed": "Подтвержден",
    "assembled": "Собран",
    "sent": "Отправлен",
    "delivered": "Доставлен",
    "cancelled": "Отменен",
}


class Shop(models.Model):
    """Модель таблицы Shop"""

    user: User = models.OneToOneField(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
        related_name="shop",
    )
    name: str = models.CharField(verbose_name="Название", max_length=50, unique=True)
    description: str = models.TextField(verbose_name="Описание", blank=True, null=True)
    registered_at: date = models.DateField(verbose_name="Дата регистрации", auto_now_add=True)
    updated_at: date = models.DateField(verbose_name="Дата обновления", auto_now=True)

    class Meta:
        verbose_name = "Продавец"
        verbose_name_plural = "Продавцы"

    def __str__(self):
        return f"{self.__class__.__name__}: {self.user.username}"


class Product(models.Model):
    """Модель таблицы Product"""

    name: str = models.CharField(verbose_name="Название", max_length=50, unique=True)
    description: str = models.TextField(verbose_name="Описание", blank=True, null=True)
    shops: list["Shop"] = models.ManyToManyField(
        to="Shop", through="ShopsProducts", related_name="products"
    )

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

    def __str__(self):
        return f"{self.__class__.__name__}: {self.name}"


class ShopsProducts(models.Model):
    """Модель таблицы ShopsProductsInfo

    Таблица m2m отношения между Product и Shop.
    """

    shop: Shop = models.ForeignKey(to="Shop", on_delete=models.CASCADE, verbose_name="Продавцы")
    product: Product = models.ForeignKey(
        to="Product", on_delete=models.CASCADE, verbose_name="Товары"
    )
    quantity: int = models.PositiveIntegerField(verbose_name="Количество, ед.")
    price: int = models.PositiveBigIntegerField(
        verbose_name="Стоимость за ед.", help_text="Стоимость за единицу товара в копейках"
    )
    can_buy: bool = models.BooleanField(verbose_name="Доступно для заказа")

    class Meta:
        verbose_name_plural = "Каталог товаров"


class Customer(models.Model):
    """Модель таблицы Customer"""

    user: User = models.OneToOneField(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Пользователь",
        related_name="customer",
    )
    city: str = models.CharField(verbose_name="Город", max_length=50, blank=True, null=True)
    street: str = models.CharField(verbose_name="Улица", max_length=50, blank=True, null=True)
    house: str = models.CharField(verbose_name="Дом", max_length=50, blank=True, null=True)
    apartment: str = models.CharField(verbose_name="Квартира", max_length=50, blank=True, null=True)
    phone: str = models.CharField(verbose_name="Телефон", max_length=50)
    registered_at: date = models.DateField(verbose_name="Дата регистрации", auto_now_add=True)
    updated_at: date = models.DateField(verbose_name="Дата обновления", auto_now=True)

    class Meta:
        verbose_name = "Покупатель"
        verbose_name_plural = "Покупатели"

    def __str__(self):
        return f"{self.__class__.__name__}: {self.user.username}"


class Order(models.Model):
    """Модель таблицы Order

    Таблица m2m отношения между Customer и ShopsProducts
    """

    customer = models.ForeignKey(to="Customer", on_delete=models.CASCADE, verbose_name="Покупатель")
    product = models.ForeignKey(to="ShopsProducts", on_delete=models.CASCADE, verbose_name="Товары")
    quantity = models.PositiveIntegerField(verbose_name="Количество, ед.")
    price = models.PositiveBigIntegerField(
        verbose_name="Стоимость за ед.", help_text="Стоимость за единицу товара в копейках"
    )
    total_price = models.PositiveBigIntegerField(
        verbose_name="Общая стоимость", help_text="Общая стоимость товаров в корзине"
    )
    status = models.CharField(
        verbose_name="Статус заказа", max_length=50, choices=STATUS_CHOICES, default="in_basket"
    )
    created_at: datetime = models.DateTimeField(verbose_name="Создано", auto_now_add=True)
    updated_at: datetime = models.DateTimeField(verbose_name="Обновлено", auto_now=True)

    class Meta:
        verbose_name_plural = "Товары в корзине"
