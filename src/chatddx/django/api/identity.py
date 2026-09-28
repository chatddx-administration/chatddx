# pyright: basic
from typing import Any, cast

from django.conf import settings
from django.http import HttpRequest
from ninja.errors import HttpError
from ninja.security import APIKeyCookie
from ninja.utils import check_csrf

from chatddx.core.utils import ensure_identity

GUEST = "guest"

SAFE = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class Identified(APIKeyCookie):
    param_name: str = settings.SESSION_COOKIE_NAME

    def __init__(self) -> None:
        super().__init__(csrf=False)

    def authenticate(self, request: HttpRequest, key: str | None) -> str:
        user = request.user

        if not user.is_authenticated:
            return ensure_identity(GUEST).name

        if request.method not in SAFE and check_csrf(request) is not None:
            raise HttpError(403, "the session's CSRF token is missing or wrong")

        return ensure_identity(user.get_username()).name


def identity_of(request: HttpRequest) -> str:
    return cast(str, cast(Any, request).auth)
