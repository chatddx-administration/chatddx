# pyright: basic
import logging
from typing import Any

from crispy_forms.helper import FormHelper
from django.forms import ModelForm
from django.http import HttpRequest
from pydantic import ValidationError as PydanticValidationError
from unfold.contrib.inlines.forms import NonrelatedInlineModelFormSet

from chatddx.core import settings
from chatddx.core.utils import ensure_identity
from chatddx.django.orm.qs import qs_canon
from chatddx.django.portal.utils import load_form_data
from chatddx.dx.error_handling import print_pydantic_errors
from chatddx.repo.bundles import entity_of, view_of
from chatddx.repo.families.django import BranchModel, TrailModel
from chatddx.repo.families.pydantic import BaseFormDataIn
from chatddx.repo.registry import EntityName
from chatddx.repo.shufflers.trail import load_trail

logger = logging.getLogger(__name__)


class BranchFormSet(NonrelatedInlineModelFormSet):
    pass


class BranchForm(ModelForm):
    class Meta:
        fields = ("name",)

    entity_name: EntityName
    helper: FormHelper

    validated_data: BaseFormDataIn | None
    request: HttpRequest

    def __init__(self, *args: Any, **kwargs: Any):

        instance = kwargs.get("instance")

        self.request = kwargs.pop("request")
        self.validated_data = None

        fingerprint = self.request.GET.get(f"{self.entity_name}_fingerprint")
        owner = self.request.user.username

        if instance:
            kwargs["initial"] = self.get_initial(instance)
        elif fingerprint:
            new_branch = entity_of(self.entity_name).branch_model(
                id=0,
                name=fingerprint[:6],
                target=load_trail(self.entity_name, fingerprint, TrailModel),
                owner=ensure_identity(owner),
            )
            kwargs["initial"] = self.get_initial(new_branch)

        super().__init__(*args, **kwargs)

        assert self._meta.model is not None
        model_cls = self._meta.model

        owned = qs_canon(model_cls.objects.all(), owner)  # pyright: ignore[reportArgumentType]

        choices = [("", "--- clear ---")] + [
            (model.target.pk, model.name) for model in owned
        ]

        # `owned` only contains the canonical (latest) version per name, so
        # an older version currently being edited (e.g. via the version
        # navigator, or still referenced by another branch such as an
        # agent) may be missing from `choices`. Add it back so its own
        # template field renders as selected rather than falling back to
        # "--- clear ---".
        if instance is not None and instance.pk:
            instance_target_id = instance.target_id  # pyright: ignore[reportAttributeAccessIssue]
            if not any(pk == instance_target_id for pk, _ in choices[1:]):
                choices.append((instance_target_id, instance.name))

        self.fields["template"].choices = choices

        if self.data:
            self.data = self.data.copy()
            self.data.pop("template", None)

    def validate(self, data: dict[str, Any]):
        try:
            validated_data = view_of(self.entity_name).form_data_in.model_validate(
                data
            )
            return validated_data
        except PydanticValidationError as e:
            if settings.MODE == "dev":
                logger.warning("Django Admin form validation failed fyi")
                print_pydantic_errors(e, logger)

            for error in e.errors():
                field_name = str(error["loc"][0])
                if field_name in self.errors:
                    # Django's own field-level validation (e.g. a required
                    # CharField left blank) already reported an error for
                    # this field; don't pile a second, differently-worded
                    # one (pydantic's "Field required") on top of it.
                    continue
                self.add_error(field_name, error["msg"])

    def clean(self):
        cleaned = super().clean()

        if not cleaned.get("owner"):
            cleaned["owner"] = ensure_identity(self.request.user.username)

        self.validated_data = self.validate(cleaned)
        return cleaned

    def save(self, commit) -> Any:
        super().save(commit=False)
        return self.cleaned_data

    def get_initial(self, instance: BranchModel):
        return load_form_data(instance)
