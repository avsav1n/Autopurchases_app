from typing import Literal, TypeAlias

import factory
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from factory.django import DjangoModelFactory, Password, mute_signals
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from autopurchases.models import (
    Cart,
    Category,
    Contact,
    Order,
    Parameter,
    Product,
    ProductsParameters,
    Shop,
    ShopsManagers,
    Stock,
    User,
)

UserModel = get_user_model()


class _CategoryFactory(DjangoModelFactory):
    """Фабрика модели Category."""

    name: str = factory.Faker("word")

    class Meta:
        model = Category
        django_get_or_create = ("name",)


class _ParameterFactory(DjangoModelFactory):
    """Фабрика модели Parameter."""

    name: str = factory.Faker("word")

    class Meta:
        model = Parameter
        django_get_or_create = ("name",)


class _ShopsManagersFactory(DjangoModelFactory):
    """Фабрика модели ShopsManagers."""

    manager: User = factory.SubFactory(factory="tests.utils.UserFactory")
    shop: Shop = factory.SubFactory(factory="tests.utils.ShopFactory")

    class Meta:
        model = ShopsManagers


class _ProductsParametersFactory(DjangoModelFactory):
    """Фабрика модели ProductsParameters."""

    product: Product = factory.SubFactory(factory="tests.utils._ProductFactory")
    parameter: Parameter = factory.SubFactory(factory="tests.utils._ParameterFactory")
    value: str = factory.Faker("word")

    class Meta:
        model = ProductsParameters


class _ProductFactory(DjangoModelFactory):
    """Фабрика модели Product."""

    category: Category = factory.SubFactory(factory="tests.utils._CategoryFactory")
    model: str = factory.Faker("word")
    name: str = factory.Faker("text", max_nb_chars=20)
    parameters: list["Parameter"] = factory.RelatedFactoryList(
        factory=_ProductsParametersFactory, factory_related_name="product"
    )

    class Meta:
        model = Product
        skip_postgeneration_save = True


class ContactFactory(DjangoModelFactory):
    """Фабрика модели Contact."""

    city: str = factory.Faker("city")
    street: str = factory.Faker("street_name")
    house: int = factory.Faker("numerify", text=r"%%%")
    apartment: int = factory.Faker("numerify", text=r"%%")

    class Meta:
        model = Contact


@mute_signals(post_save)
class UserFactory(DjangoModelFactory):
    """Фабрика модели User.

    Примеры использования:
        >>> user = UserFactory()
        >>> user.password
        # сгенерированный пароль
        '!1LKvSmi9j'
        >>> user = UserFactory(hashed=True)
        >>> user.password
        # хеш сгенерированного пароля
        'pbkdf2_sha256$870000$g5rykR1s9apTTg3O0w6BXS$9rtfrc+xWP50bT6NLF22sJDE6zamOOu+lsdFkuVqP+o='
        >>> user = UserFactory(hashed=True, password="qwerty")
        >>> user.password
        # хеш явно заданного пароля "qwerty"
        'pbkdf2_sha256$870000$uPvspHkUCBwCjgRKjmhd7O$4PoB2AxgxC4Z06Nge44880HKtTTKZQ+EHsHnKxPskkc='
        >>> from django.contrib.auth.hashers import check_password
        >>> check_password('qwerty', user.password)
        True
    """

    email: str = factory.Faker("free_email")
    _password: str = factory.Maybe(
        decider="hashed",
        yes_declaration=Password(factory.SelfAttribute("password")),
        no_declaration=factory.SelfAttribute("password"),
    )
    first_name: str = factory.Faker("first_name")
    last_name: str = factory.Faker("last_name")
    phone: str = factory.Faker("phone_number")

    class Meta:
        model = UserModel
        django_get_or_create = ("email",)
        rename = {"_password": "password"}

    class Params:
        hashed = False
        password = factory.Faker("password")


@mute_signals(post_save)
class ShopFactory(DjangoModelFactory):
    """Фабрика модели Shop."""

    name: str = factory.Faker("word")
    managers: list["User"] = factory.RelatedFactory(
        factory=_ShopsManagersFactory, factory_related_name="shop"
    )

    class Meta:
        model = Shop
        django_get_or_create = ("name",)
        skip_postgeneration_save = True

    class Params:
        no_managers = factory.Trait(managers=None)


@mute_signals(post_save)
class StockFactory(DjangoModelFactory):
    """Фабрика модели Stock."""

    shop: Shop = factory.SubFactory(factory=ShopFactory)
    product: Product = factory.SubFactory(factory=_ProductFactory)
    quantity: int = factory.Faker("pyint", min_value=10)
    price: int = factory.Faker("pyint", min_value=10)

    class Meta:
        model = Stock
        skip_postgeneration_save = True


@mute_signals(post_save)
class CartFactory(DjangoModelFactory):
    """Фабрика модели Cart."""

    customer: User = factory.SubFactory(factory=UserFactory)
    product: Stock = factory.SubFactory(factory=StockFactory)
    quantity: int = factory.Faker("pyint", min_value=1, max_value=10)

    class Meta:
        model = Cart
        skip_postgeneration_save = True


@mute_signals(post_save)
class OrderFactory(CartFactory):
    """Фабрика модели Order."""

    delivery_address: Contact = factory.SubFactory(factory=ContactFactory)

    class Meta:
        model = Order
        skip_postgeneration_save = True


class CustomAPIClient(APIClient):
    """Расширенный APIClient для тестирования API с поддержкой разных ролей пользователей.

    Особенности:
    - aвтоматическая аутентификация при создании;
    - поддержка разных ролей: admin, user, anon (анонимный);
    - хеширование паролей объектов пользователей при необходимости.
    """

    def __init__(self, role: Literal["user", "admin", "anon"] = "user", **defaults):
        super().__init__(**defaults)
        self.orm_user_obj: User | None = None
        self._client_dispatcher(role=role)

    def _client_dispatcher(self, role: str):
        match role:
            case "admin":
                self._create_admin_client()
            case "user":
                self._create_user_client()
            case "anon":
                return
        self._set_credentials()

    def _set_credentials(self):
        token: Token = Token.objects.create(user=self.orm_user_obj)
        self.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def _create_admin_client(self):
        with mute_signals(post_save):
            admin: User = UserFactory(is_staff=True, is_superuser=True)
        self.orm_user_obj = admin

    def _create_user_client(self):
        with mute_signals(post_save):
            user: User = UserFactory()
        self.orm_user_obj = user

    def set_hashed_password(self) -> str | None:
        """Метод хеширования пароля объекта пользователя self.orm_user_obj.

        Доступ к старому паролю.
            Вызов метода возвращает старый нехешированный пароль при наличии объекта
            пользователя self.orm_user_obj или None.

        Примеры:
            >>> user_client.orm_user_obj.password
            'z+67Zly42G'
            >>> raw_password = user_client.set_hashed_password()
            >>> user_client.orm_user_obj.password
            'pbkdf2_sha256$870000$ymL8SK5HuFlZYvSTAtS2Cu$K9vMHP3MW2euzkG56/UDFjQj4Ad/EMUjAJNtc8vpq+w='
            >>> user_client.orm_user_obj._password
            'z+67Zly42G'
            >>> raw_password
            'z+67Zly42G'
        """
        if self.orm_user_obj is None:
            return
        raw_password = self.orm_user_obj.password
        self.orm_user_obj.set_password(self.orm_user_obj.password)
        self.orm_user_obj.save(update_fields=["password"])
        return raw_password


FACTORIES: TypeAlias = UserFactory | ShopFactory | ContactFactory | StockFactory


def factory_wrapper(size: int | None = None, /, _base_factory: FACTORIES | None = None, **kwargs):
    if kwargs.pop("as_dict", None) is not None:
        return _base_factory.stub(**kwargs).__dict__
    if size is not None:
        return _base_factory.create_batch(size, **kwargs)
    return _base_factory.create(**kwargs)
