from uuid import UUID

import pytest
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import EmailMessage
from faker import Faker
from rest_framework.response import Response

from autopurchases.models import Contact, PasswordResetToken, User
from autopurchases.serializers import UserSerializer
from tests.utils import CustomAPIClient

pytestmark = pytest.mark.django_db


class TestGetList:
    def test_success(self, anon_client: CustomAPIClient, user_factory, url_factory):
        users_quantity = 5

        users: list[User] = user_factory(users_quantity)
        url: str = url_factory("user-list")

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = response.json()
        assert "count" in api_data
        assert "next" in api_data
        assert "previous" in api_data
        assert "results" in api_data
        assert api_data["count"] == users_quantity
        db_data: list[dict] = UserSerializer(users, many=True).data
        for user_info in api_data["results"]:
            assert user_info in db_data

    def test_second_page_success(
        self, anon_client: CustomAPIClient, user_factory, url_factory, settings
    ):
        difference = 5
        users_quantity = settings.REST_FRAMEWORK["PAGE_SIZE"] + difference

        user_factory(users_quantity)
        url: str = f'{url_factory("user-list")}?page=2'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: list[dict] = response.json()
        assert len(api_data["results"]) == difference
        assert api_data["next"] is None
        assert api_data["previous"] is not None

    def test_fail_invalid_page(self, anon_client: CustomAPIClient, url_factory):
        url: str = f'{url_factory("user-list")}?page=2'

        response: Response = anon_client.get(url)

        assert response.status_code == 404


class TestGetDetail:
    def test_success(self, anon_client: CustomAPIClient, url_factory, user_factory):
        user: User = user_factory()
        url: str = url_factory("user-detail", pk=user.id)

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        api_data: dict = response.json()
        db_data: dict = UserSerializer(user).data
        assert api_data == db_data


class TestPost:
    def test_success(
        self,
        anon_client: CustomAPIClient,
        user_factory,
        url_factory,
        locmem_email_backend,
        sync_celery_worker,
        mailoutbox,
    ):
        user_info: dict = user_factory(as_dict=True)
        url: str = url_factory("user-list")

        response: Response = anon_client.post(url, data=user_info)

        assert response.status_code == 201
        api_data: dict = response.json()
        assert "password" not in api_data
        assert api_data["email"] == user_info["email"]
        assert len(mailoutbox) == 1
        msg: EmailMessage = mailoutbox[0]
        assert msg.to == [user_info["email"]]

    def test_fail_existing_email(self, anon_client: CustomAPIClient, user_factory, url_factory):
        user_info: dict = user_factory(as_dict=True)
        user_factory(**user_info)
        url: str = url_factory("user-list")

        response: Response = anon_client.post(url, data=user_info)

        assert response.status_code == 400

    def test_fail_no_password(self, anon_client: CustomAPIClient, user_factory, url_factory):
        user_info: dict = user_factory(as_dict=True)
        user_info.pop("password")
        url: str = url_factory("user-list")

        response: Response = anon_client.post(url, data=user_info)

        assert response.status_code == 400

    def test_fail_simple_password(self, anon_client: CustomAPIClient, user_factory, url_factory):
        user_info: dict = user_factory(password="simple", as_dict=True)
        url: str = url_factory("user-list")

        response: Response = anon_client.post(url, data=user_info)

        assert response.status_code == 400


class TestPatch:
    def test_success(self, user_client: CustomAPIClient, user_factory, url_factory):
        user: User = user_client.orm_user_obj
        user_info: dict = user_factory(as_dict=True)
        user_info.pop("last_name")
        user_info.pop("phone")
        url: str = url_factory("user-detail", pk=user.id)

        response: Response = user_client.patch(url, data=user_info)

        assert response.status_code == 200
        api_data: dict = response.json()
        user.refresh_from_db(fields=["email", "first_name"])
        assert api_data["email"] == user_info["email"] == user.email
        assert api_data["first_name"] == user_info["first_name"] == user.first_name
        assert api_data["phone"] == user.phone
        assert api_data["last_name"] == user.last_name

    def test_admin_success(self, admin_client: CustomAPIClient, user_factory, url_factory):
        user: User = user_factory()
        user_info: dict = user_factory(as_dict=True)
        user_info.pop("first_name")
        user_info.pop("email")
        url: str = url_factory("user-detail", pk=user.id)

        response: Response = admin_client.patch(url, data=user_info)

        assert response.status_code == 200
        api_data: dict = response.json()
        user.refresh_from_db(fields=["phone", "last_name"])
        assert api_data["phone"] == user_info["phone"] == user.phone
        assert api_data["last_name"] == user_info["last_name"] == user.last_name
        assert api_data["email"] == user.email
        assert api_data["first_name"] == user.first_name

    def test_fail_unauthorized(self, anon_client: CustomAPIClient, user_factory, url_factory):
        user: User = user_factory()
        user_info: dict = user_factory(as_dict=True)
        url: str = url_factory("user-detail", pk=user.id)

        response: Response = anon_client.patch(url, data=user_info)

        assert response.status_code == 401

    def test_fail_not_owner(self, user_client: CustomAPIClient, user_factory, url_factory):
        user: User = user_factory()
        user_info: dict = user_factory(as_dict=True)
        url: str = url_factory("user-detail", pk=user.id)

        response: Response = user_client.patch(url, data=user_info)

        assert response.status_code == 403


class TestDelete:
    def test_success(self, user_client: CustomAPIClient, url_factory):
        url: str = url_factory("user-detail", pk=user_client.orm_user_obj.id)

        response: Response = user_client.delete(url)

        assert response.status_code == 204

    def test_admin_success(self, admin_client: CustomAPIClient, user_factory, url_factory):
        user: User = user_factory()
        url: str = url_factory("user-detail", pk=user.id)

        response: Response = admin_client.delete(url)

        assert response.status_code == 204

    def test_fail_unauthorized(self, anon_client: CustomAPIClient, user_factory, url_factory):
        user: User = user_factory()
        url: str = url_factory("user-detail", pk=user.id)

        response: Response = anon_client.delete(url)

        assert response.status_code == 401

    def test_fail_not_owner(self, user_client: CustomAPIClient, user_factory, url_factory):
        user: User = user_factory()
        url: str = url_factory("user-detail", pk=user.id)

        response: Response = user_client.delete(url)

        assert response.status_code == 403


class TestContacts:
    def test_create_success(self, user_client: CustomAPIClient, contact_factory, url_factory):
        contact_info: dict = contact_factory(as_dict=True)
        url: str = url_factory("user-create-contact", pk=user_client.orm_user_obj.id)

        response: Response = user_client.post(url, data=contact_info)

        assert response.status_code == 201
        api_data: dict = response.json()
        assert api_data["email"] == user_client.orm_user_obj.email
        contact_info = {key: str(value) for key, value in contact_info.items()}
        contact_info["id"] = api_data["contacts"][0]["id"]
        assert api_data["contacts"][0] == contact_info

    def test_create_admin_success(
        self, admin_client: CustomAPIClient, contact_factory, user_factory, url_factory
    ):
        user: User = user_factory()
        contact_info: dict = contact_factory(as_dict=True)
        url: str = url_factory("user-create-contact", pk=user.id)

        response: Response = admin_client.post(url, data=contact_info)

        assert response.status_code == 201
        api_data: dict = response.json()
        assert api_data["email"] == user.email
        contact_info = {key: str(value) for key, value in contact_info.items()}
        contact_info["id"] = api_data["contacts"][0]["id"]
        assert api_data["contacts"][0] == contact_info

    def test_create_fail_not_owner(
        self, user_client: CustomAPIClient, contact_factory, user_factory, url_factory
    ):
        user: User = user_factory()
        contact_info: dict = contact_factory(as_dict=True)
        url: str = url_factory("user-create-contact", pk=user.id)

        response: Response = user_client.post(url, data=contact_info)

        assert response.status_code == 403

    def test_create_fail_unauthorized(
        self, anon_client: CustomAPIClient, contact_factory, user_factory, url_factory
    ):
        user: User = user_factory()
        contact_info: dict = contact_factory(as_dict=True)
        url: str = url_factory("user-create-contact", pk=user.id)

        response: Response = anon_client.post(url, data=contact_info)

        assert response.status_code == 401

    def test_delete_success(self, user_client: CustomAPIClient, contact_factory, url_factory):
        contacts_quantity = 2
        user: User = user_client.orm_user_obj
        contacts: list[Contact] = contact_factory(contacts_quantity, user=user)
        assert user.contacts.count() == contacts_quantity
        target_contact_id: int = contacts[0].id
        url: str = url_factory("user-delete-contact", pk=user.id, contact_pk=target_contact_id)

        response: Response = user_client.delete(url)

        assert response.status_code == 204
        assert user.contacts.count() == contacts_quantity - 1
        with pytest.raises(ObjectDoesNotExist):
            Contact.objects.get(pk=target_contact_id)

    def test_delete_admin_success(
        self, admin_client: CustomAPIClient, contact_factory, user_factory, url_factory
    ):
        contacts_quantity = 2
        user: User = user_factory()
        contacts: list[Contact] = contact_factory(contacts_quantity, user=user)
        assert user.contacts.count() == contacts_quantity
        target_contact_id: int = contacts[0].id
        url: str = url_factory("user-delete-contact", pk=user.id, contact_pk=target_contact_id)

        response: Response = admin_client.delete(url)

        assert response.status_code == 204
        assert user.contacts.count() == contacts_quantity - 1
        with pytest.raises(ObjectDoesNotExist):
            Contact.objects.get(pk=target_contact_id)

    def test_delete_fail_unauthorized(
        self, anon_client: CustomAPIClient, contact_factory, user_factory, url_factory
    ):
        contacts_quantity = 2
        user: User = user_factory()
        contacts: list[Contact] = contact_factory(contacts_quantity, user=user)
        assert user.contacts.count() == contacts_quantity
        target_contact_id: int = contacts[0].id
        url: str = url_factory("user-delete-contact", pk=user.id, contact_pk=target_contact_id)

        response: Response = anon_client.delete(url)

        assert response.status_code == 401

    def test_delete_fail_not_owner(
        self, user_client: CustomAPIClient, contact_factory, user_factory, url_factory
    ):
        contacts_quantity = 2
        user: User = user_factory()
        contacts: list[Contact] = contact_factory(contacts_quantity, user=user)
        assert user.contacts.count() == contacts_quantity
        target_contact_id: int = contacts[0].id
        url: str = url_factory("user-delete-contact", pk=user.id, contact_pk=target_contact_id)

        response: Response = user_client.delete(url)

        assert response.status_code == 403


class TestResetToken:
    def test_create_success(
        self,
        anon_client: CustomAPIClient,
        user_factory,
        url_factory,
        locmem_email_backend,
        sync_celery_worker,
        mailoutbox,
    ):
        user: User = user_factory()
        url: str = f'{url_factory("user-get-rtoken")}?email={user.email}'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        assert len(mailoutbox) == 1
        msg: EmailMessage = mailoutbox[0]
        assert msg.to == [user.email]
        assert str(user.rtoken) in msg.body

    def test_create_extra_data_success(
        self,
        anon_client: CustomAPIClient,
        user_factory,
        url_factory,
        locmem_email_backend,
        sync_celery_worker,
        mailoutbox,
    ):
        user: User = user_factory()
        url: str = f'{url_factory("user-get-rtoken")}?email={user.email}&phone=12345'

        response: Response = anon_client.get(url)

        assert response.status_code == 200
        assert len(mailoutbox) == 1
        msg: EmailMessage = mailoutbox[0]
        assert msg.to == [user.email]
        assert str(user.rtoken) in msg.body

    def test_create_fail_no_data(self, anon_client: CustomAPIClient, user_factory, url_factory):
        user_factory()
        url: str = url_factory("user-get-rtoken")

        response: Response = anon_client.get(url)

        assert response.status_code == 400

    def test_create_fail_user_not_exist(
        self, anon_client: CustomAPIClient, faker: Faker, url_factory
    ):
        url: str = f'{url_factory("user-get-rtoken")}?email={faker.email()}'

        response: Response = anon_client.get(url)

        assert response.status_code == 404

    def test_reset_success(
        self, anon_client: CustomAPIClient, faker: Faker, user_factory, url_factory
    ):
        user: User = user_factory()
        rtoken: UUID = PasswordResetToken.objects.create(user=user).rtoken
        new_password: str = faker.password()
        reset_info = {"rtoken": rtoken, "password": new_password}
        url: str = url_factory("user-reset-password")

        response: Response = anon_client.patch(url, data=reset_info)

        assert response.status_code == 200
        user.refresh_from_db(fields=["password"])
        assert check_password(new_password, user.password)

    def test_reset_fail_invalid_token(
        self, anon_client: CustomAPIClient, faker: Faker, url_factory
    ):
        reset_info = {"rtoken": faker.uuid4(), "password": faker.password()}
        url: str = url_factory("user-reset-password")

        response: Response = anon_client.patch(url, data=reset_info)

        assert response.status_code == 404

    def test_reset_fail_simple_password(
        self, anon_client: CustomAPIClient, user_factory, url_factory
    ):
        user: User = user_factory()
        rtoken: UUID = PasswordResetToken.objects.create(user=user).rtoken
        reset_info = {"rtoken": rtoken, "password": "simple"}
        url: str = url_factory("user-reset-password")

        response: Response = anon_client.patch(url, data=reset_info)

        assert response.status_code == 400


class TestLogin:
    def test_success(self, anon_client: CustomAPIClient, faker: Faker, user_factory, url_factory):
        password: str = faker.password()
        user: User = user_factory(password=password, hashed=True)
        url: str = url_factory("login")
        login_info = {"email": user.email, "password": password}

        response: Response = anon_client.post(url, data=login_info)

        assert response.status_code == 200
        api_data: dict = response.json()
        assert api_data["token"] == user.auth_token.key

    def test_fail_invalid_password(
        self, anon_client: CustomAPIClient, faker: Faker, user_factory, url_factory
    ):
        user: User = user_factory(hashed=True)
        url: str = url_factory("login")
        login_info = {"email": user.email, "password": faker.password()}

        response: Response = anon_client.post(url, data=login_info)

        assert response.status_code == 400

    def test_fail_no_data(
        self, anon_client: CustomAPIClient, faker: Faker, user_factory, url_factory
    ):
        user_factory(hashed=True)
        url: str = url_factory("login")

        response: Response = anon_client.post(url)

        assert response.status_code == 400
