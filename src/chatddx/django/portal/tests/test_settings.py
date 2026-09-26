# pyright: basic
from django.conf import settings

from chatddx.django.settings import base


def test_the_portal_s_settings_are_the_minimal_ones_and_more():
    assert set(base.INSTALLED_APPS) < set(settings.INSTALLED_APPS)
    assert settings.DATABASES["default"]["TEST"]["NAME"] == "test_chatddx_portal"
    # the minimal ones as they were: the portal's took a copy
    assert "TEST" not in base.DATABASES["default"]
