import pytest

pytestmark = pytest.mark.django_db


class TestGetList:
    def test_success(self, user_client):

        assert True
