# src/chatddx/django/portal/forms/base.py
# pyright: basic
from typing import Any, cast, override

from crispy_forms.helper import FormHelper
from django.forms import ModelForm
from django.http import HttpRequest
from pydantic import ValidationError as PydanticValidationError

from chatddx.django.orm.qs import qs_canon
from chatddx.django.portal.utils import load_form_data
from chatddx.repo.base import BaseFormDataIn, BaseFormDataOut, BranchModel, TrailModel
from chatddx.repo.main import Repo
from chatddx.repo.shufflers.main import (
    ensure_identity,
    load_trail,
)


class BaseForm(ModelForm):
    class Meta:
        fields = ["name"]

    form_data_out: type[BaseFormDataOut]
    form_data_in: type[BaseFormDataIn]
    bundle_name: str
    # Every concrete subform provides a crispy_forms layout helper.
    helper: FormHelper

    validated_data: BaseFormDataIn | None
    request: HttpRequest

    def validate(self, data: dict[str, Any]):
        try:
            validated_data = self.form_data_in.model_validate(data)
            return validated_data
        except PydanticValidationError as e:
            for error in e.errors():
                self.add_error(str(error["loc"][0]), error["msg"])

    @override
    def clean(self):
        cleaned = super().clean()

        if not cleaned.get("owner"):
            cleaned["owner"] = ensure_identity(self.request.user.username)

        self.validated_data = self.validate(cleaned)
        return cleaned

    @override
    def save(self, commit: bool = True) -> Any:
        super().save(commit)
        return self.cleaned_data

    def get_initial(self, instance: BranchModel):
        return load_form_data(instance).model_dump(by_alias=True)

    def __init__(self, *args: Any, **kwargs: Any):
        instance = kwargs.get("instance")
        self.request = kwargs.pop("request")
        self.validated_data = None

        fingerprint = self.request.GET.get(f"{self.bundle_name}_fingerprint")
        owner = self.request.user.username

        if instance:
            kwargs["initial"] = self.get_initial(instance)
        elif fingerprint:
            new_branch = Repo(self.bundle_name, BranchModel)(
                id=0,
                name=fingerprint[:6],
                target=load_trail(self.bundle_name, fingerprint, TrailModel),
                owner=ensure_identity(owner),
            )
            kwargs["initial"] = self.get_initial(new_branch)

        super().__init__(*args, **kwargs)
        # Every concrete form's Meta.model is a BranchModel subclass;
        # ModelFormOptions.model is only typed as `type[Model] | None`
        # because it's generic across all ModelForms.
        model_cls = cast(type[BranchModel], self._meta.model)
        owned = qs_canon(model_cls.objects.all(), owner)

        self.fields["template"].choices = [("", "=== clear ===")] + [
            (model.target.pk, model.name) for model in owned
        ]

        if self.data:
            self.data = self.data.copy()
            self.data.pop("template", None)
