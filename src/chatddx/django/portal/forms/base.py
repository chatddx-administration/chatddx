# src/chatddx/django/portal/forms/base.py
from typing import Any, override

from django.forms import ModelForm
from django.http import HttpRequest
from pydantic import ValidationError as PydanticValidationError

from chatddx.repo.base import BaseFormDataIn, BaseFormDataOut, BranchModel, TrailModel
from chatddx.repo.main import Repo
from chatddx.repo.shufflers.main import (
    ensure_identity,
    load_form_data,
    load_trail,
    qs_canon,
)


class BaseForm(ModelForm):
    class Meta:
        fields = ["name"]

    form_data_out: type[BaseFormDataOut]
    form_data_in: type[BaseFormDataIn]
    bundle_name: str

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
        owned = qs_canon(self._meta.model.objects.all(), owner)

        self.fields["template"].choices = [("", "=== clear ===")] + [
            (model.target.pk, model.name) for model in owned
        ]

        if self.data:
            self.data = self.data.copy()
            self.data.pop("template", None)
