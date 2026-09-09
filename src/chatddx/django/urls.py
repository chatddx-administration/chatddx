from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.http import HttpRequest, HttpResponse
from django.urls import path

from .api import api


def auth_check(request: HttpRequest):
    if request.user.is_authenticated:
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=401)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("auth/", auth_check, name="auth_check"),
]
urlpatterns += staticfiles_urlpatterns()
