from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import path

from .api import api

MAIN_SITE_URL = "/"


def auth_check(request: HttpRequest):
    if request.user.is_authenticated:
        return HttpResponse(status=200)
    else:
        return HttpResponse(status=401)


def admin_login(request: HttpRequest):
    # Send a plain admin login to the main site instead of the admin
    # index, but preserve `next` when the login was triggered by trying
    # to reach a specific admin page while logged out. The unfold login
    # form posts back to the page's own URL (including its query string)
    # rather than carrying a hidden `next` field, so `next` has to be
    # threaded through the query string via a real redirect rather than
    # by mutating request.GET in place.
    if request.method == "GET" and admin.site.has_permission(request):
        return HttpResponseRedirect(MAIN_SITE_URL)
    if request.method == "GET" and "next" not in request.GET:
        return HttpResponseRedirect(f"{request.path}?next={MAIN_SITE_URL}")
    return admin.site.login(request)


urlpatterns = [
    path("admin/login/", admin_login),
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path("auth/", auth_check, name="auth_check"),
]
urlpatterns += staticfiles_urlpatterns()
