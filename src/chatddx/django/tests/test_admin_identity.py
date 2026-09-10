import pytest
from django.contrib.auth.models import Group, Permission, User
from django.test import Client
from django.urls import reverse

from chatddx.core.models import IdentityModel


@pytest.fixture
def restricted_user(db) -> User:
    user = User.objects.create_user(
        username="restricted",
        password="password",
        is_staff=True,
    )
    group, _created = Group.objects.get_or_create(name="users")
    group.permissions.add(
        *Permission.objects.filter(
            content_type__app_label="orm",
            codename__in=["view_identity", "change_identity"],
        )
    )
    user.groups.add(group)
    return user


@pytest.fixture
def restricted_client(restricted_user: User) -> Client:
    client = Client()
    client.force_login(restricted_user)
    return client


@pytest.mark.django_db
def test_restricted_group_changelist_redirects_to_own_identity_form(
    restricted_user: User,
    restricted_client: Client,
):
    """A member of the "users" group never sees the identity list -- hitting
    the changelist takes them straight to their own identity's form."""
    identity = IdentityModel.objects.create(name=restricted_user.username)
    IdentityModel.objects.create(name="someone-else")

    response = restricted_client.get(reverse("admin:orm_identity_changelist"))

    assert response.status_code == 302
    assert response.url == reverse(  # pyright: ignore[reportAttributeAccessIssue]
        "admin:orm_identity_change", args=(identity.pk,)
    )


@pytest.mark.django_db
def test_restricted_group_cannot_reach_another_identity(
    restricted_user: User,
    restricted_client: Client,
):
    """Even navigating straight to another identity's change URL is a
    dead end for a restricted user -- get_queryset() filters it out, so the
    object is treated as not found (redirecting to the admin index, per
    Django's own not-found handling) rather than rendered."""
    IdentityModel.objects.create(name=restricted_user.username)
    other = IdentityModel.objects.create(name="someone-else")

    response = restricted_client.get(
        reverse("admin:orm_identity_change", args=(other.pk,))
    )

    assert response.status_code == 302
    assert response.url == reverse(  # pyright: ignore[reportAttributeAccessIssue]
        "admin:index"
    )


@pytest.mark.django_db
def test_superuser_changelist_lists_all_identities(admin_client: Client):
    """Superusers keep the ordinary list view, covering every identity."""
    IdentityModel.objects.create(name="alex")
    IdentityModel.objects.create(name="olof")

    response = admin_client.get(reverse("admin:orm_identity_changelist"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "alex" in content
    assert "olof" in content
