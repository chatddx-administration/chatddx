# pyright: basic
from django.apps import apps


def test_the_minimal_settings_hold_nothing_of_the_portal_s():
    assert not apps.is_installed("chatddx.django.portal")
    assert not apps.is_installed("unfold")
    assert not apps.is_installed("corsheaders")
