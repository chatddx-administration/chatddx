# pyright: basic
from typing import Any

from django.db.models import Model
from django.http import HttpRequest
from unfold.admin import ModelAdmin


class ModelAdminFormWithRequest:
    def get_form(
        self,
        request: HttpRequest,
        obj: Model | None = None,
        change: bool = False,
        **kwargs: Any,
    ):
        Form = super().get_form(request, obj, **kwargs)

        class FormWithRequest(Form):
            def __new__(cls, *args: Any, **fkwargs: Any):
                fkwargs["request"] = request
                return Form(*args, **fkwargs)

        return FormWithRequest


class SharedMixin:
    def get_queryset(self, request: HttpRequest):
        qs = super(ModelAdmin, self).get_queryset(request)

        return qs.filter(
            collaborators__name=request.user.username,
        )
