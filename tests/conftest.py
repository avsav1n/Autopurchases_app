import functools

import pytest
from rest_framework.reverse import reverse

from tests.utils import (
    CartFactory,
    ContactFactory,
    CustomAPIClient,
    OrderFactory,
    ShopFactory,
    StockFactory,
    UserFactory,
    factory_wrapper,
)


@pytest.fixture(scope="function")
def sync_celery_worker(settings, transactional_db):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_STORE_EAGER_RESULT = True


@pytest.fixture(scope="session")
def user_factory():
    return functools.partial(factory_wrapper, _base_factory=UserFactory)


@pytest.fixture(scope="session")
def contact_factory():
    return functools.partial(factory_wrapper, _base_factory=ContactFactory)


@pytest.fixture(scope="session")
def shop_factory():
    return functools.partial(factory_wrapper, _base_factory=ShopFactory)


@pytest.fixture(scope="session")
def stock_factory():
    return functools.partial(factory_wrapper, _base_factory=StockFactory)


@pytest.fixture(scope="session")
def cart_factory():
    return functools.partial(factory_wrapper, _base_factory=CartFactory)


@pytest.fixture(scope="session")
def order_factory():
    return functools.partial(factory_wrapper, _base_factory=OrderFactory)


@pytest.fixture(scope="package")
def url_factory(request):
    """Фикстура фабрики URL

    Примечание:
        Для корректного определения namespace приложений, их тестовые модули должны располагаться
        внутри директорий с соответствующими названиями (название приложения = название директории)

    Примеры:
        >>> url_factory('user-list')
        '/api/v1/user/'
        >>> url_factory("user-delete-contact", pk=1, contact_pk=3)
        '/api/v1/user/1/contacts/3/'
    """
    app_name = request.path.parent.name

    @functools.lru_cache(maxsize=32)
    def factory(url_name: str = "", /, app_name=app_name, **kwargs):
        full_url_name = f"{app_name}:{url_name}"
        return reverse(full_url_name, kwargs=kwargs)

    return factory


@pytest.fixture(scope="function")
def admin_client() -> CustomAPIClient:
    return CustomAPIClient(role="admin")


@pytest.fixture(scope="function")
def anon_client() -> CustomAPIClient:
    return CustomAPIClient(role="anon")


@pytest.fixture(scope="function")
def user_client() -> CustomAPIClient:
    return CustomAPIClient()
