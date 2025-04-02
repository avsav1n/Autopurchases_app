import functools

import pytest
from rest_framework.reverse import reverse

from tests.utils import (
    ContactFactory,
    CustomAPIClient,
    ShopFactory,
    StockFactory,
    UserFactory,
)


@pytest.fixture(scope="session")
def sync_celery(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_STORE_EAGER_RESULT = True


def email_backend(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"


@pytest.fixture(scope="session")
def user_factory():
    def factory(size: int = None, /, **kwargs):
        if kwargs.pop("raw", None) is not None:
            return UserFactory.stub(**kwargs).__dict__
        if size:
            return UserFactory.create_batch(size, **kwargs)
        return UserFactory.create(**kwargs)

    return factory


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

    @functools.lru_cache
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
