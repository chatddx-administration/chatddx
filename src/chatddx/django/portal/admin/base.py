# src/chatddx/django/portal/admin/base.py
# pyright: basic
import json
from typing import Any, cast, no_type_check, override

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Model as DjangoModel
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse
from unfold.admin import ModelAdmin

from chatddx.django.orm.qs import qs_canon
from chatddx.django.portal.forms.base import BaseForm
from chatddx.django.portal.utils import load_template_data
from chatddx.repo.base import BranchModel, BranchProxy, TrailModel, TrailSchema
from chatddx.repo.main import BundleName, Repo
from chatddx.repo.shufflers.main import dump_branch


class TypedModelAdmin[T: DjangoModel](ModelAdmin):
    @override
    def get_queryset(self, request: HttpRequest) -> QuerySet[T]:
        return cast(QuerySet[T], super().get_queryset(request))


class TrailModelAdmin[T: TrailModel](TypedModelAdmin[T]):
    @override
    def get_queryset(self, request: HttpRequest) -> QuerySet[T]:
        qs: QuerySet[T] = super().get_queryset(request)
        return qs


class BranchModelAdmin[T: BranchModel](TypedModelAdmin[T]):
    name: BundleName
    change_form_template = "templates/branch_change_form.html"
    add_form_template = "templates/branch_change_form.html"
    list_display = [
        "name",
        "versions",
    ]

    @admin.display(description="Versions")
    def versions(self, obj: DjangoModel) -> int | None:
        return getattr(obj, "_version_count", None)

    def get_queryset(self, request: HttpRequest):
        qs: QuerySet[Any] = super().get_queryset(request)
        return qs_canon(qs, request.user.username)

    def get_object(self, request, object_id, from_field=None):
        """
        This is django's get_object() almost verbatim, except it uses super()'s get_queryset
        instead of self, so non-canonical entries can be retreived.
        """
        queryset = super().get_queryset(request)
        model = queryset.model
        field = (
            model._meta.pk if from_field is None else model._meta.get_field(from_field)
        )
        assert field is not None
        try:
            object_id = field.to_python(object_id)
            return queryset.get(**{field.name: object_id})
        except (model.DoesNotExist, ValidationError, ValueError):
            return None

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[DjangoModel]):
        names_subquery = queryset.values_list("name", flat=True)

        self.model.objects.filter(
            name__in=names_subquery,
            owner__name=request.user.username,
        ).delete()

        ThroughModel = self.model.collaborators.through

        ThroughModel.objects.filter(
            **{f"{self.name}branchmodel__name__in": names_subquery},
            identitymodel__name=request.user.username,
        ).delete()

    def get_form(
        self,
        request: HttpRequest,
        obj: DjangoModel | None = None,
        change: bool = False,
        **kwargs: Any,
    ):
        Form = super().get_form(request, obj, **kwargs)

        class FormWithRequest(Form):
            def __new__(cls, *args: Any, **fkwargs: Any):
                fkwargs["request"] = request
                return Form(*args, **fkwargs)

        return FormWithRequest

    def save_form(
        self,
        request: HttpRequest,
        form: BaseForm,
        change: bool,
    ) -> BranchProxy:
        if form.validated_data is None:
            raise ValueError("form.validated_data is unexpectedly None")

        # BaseForm.clean() always fills in an owner before validating, so
        # this is never actually None here.
        assert form.validated_data.owner is not None

        schema_cls = Repo(self.name, TrailSchema)
        proxy_cls = Repo(self.name, BranchProxy)
        schema = schema_cls.model_validate(form.validated_data.model_dump())

        obj, created = dump_branch(
            self.name,
            form.validated_data.name or "",
            form.validated_data.owner.name,
            schema,
        )

        new_collaborators = form.validated_data.collaborators
        changed: list[str] = []

        if new_collaborators is not None:
            current_ids = set(obj.collaborators.values_list("pk", flat=True))
            target_ids = {identity.id for identity in new_collaborators}

            if current_ids != target_ids:
                obj.collaborators.set(target_ids)
                changed.append("collaborators")

        changed += self.sync_extra_relations(obj, form)

        if not created:
            if changed:
                self.message_user(
                    request,
                    self.unchanged_message(changed),
                    level=messages.INFO,
                )
                request._skip_success_message = True  # pyright: ignore[reportAttributeAccessIssue]
            else:
                self.message_user(
                    request,
                    "No changes detected. The current version is up to date.",
                    level=messages.INFO,
                )
                request._skip_success_message = True  # pyright: ignore[reportAttributeAccessIssue]

        elif changed:
            self.message_user(
                request,
                f"{' and '.join(changed).capitalize()} successfully set for the new branch version.",
                level=messages.SUCCESS,
            )

        return obj.as_proxy(proxy_cls)

    def sync_extra_relations(self, obj: DjangoModel, form: BaseForm) -> list[str]:
        """Hook for subclasses carrying relations beyond `collaborators`
        (e.g. Case's `tags`): sync them against `obj` and return the label
        of each one that actually changed, for the messages `save_form()`
        builds above. The base implementation has nothing extra to sync.
        """
        return []

    def unchanged_message(self, changed: list[str]) -> str:
        """The message shown when the branch's own content (fingerprint)
        didn't change, but something listed in `changed` did. Subclasses
        may override for more specific wording."""
        return f"Branch content unchanged, but updated {' and '.join(changed)}."

    def save_related(self, request, form, formsets, change):
        pass

    def response_change(self, request: HttpRequest, obj: DjangoModel):
        if "_continue" not in request.POST:
            return super().response_change(request, obj)

        msg = 'The %(name)s "%(obj)s" is a new version.' % {
            "name": obj._meta.verbose_name,
            "obj": str(obj),
        }
        self.message_user(request, msg, messages.SUCCESS)
        opts = self.model._meta
        redirect_url = reverse(
            f"admin:{opts.app_label}_{opts.model_name}_change",
            args=(obj.pk,),
        )
        return HttpResponseRedirect(redirect_url)

    def response_add(self, request, obj, post_url_continue=None):
        if "_continue" not in request.POST:
            return super().response_add(request, obj, post_url_continue)

        return self.response_change(request, obj)

    def get_form_context(self, request: HttpRequest, obj: Any) -> dict[str, Any]:
        owner = request.user.username
        return {
            "template_data": load_template_data(owner).model_dump_json(by_alias=True),
            "form_info": json.dumps(
                {
                    "template_selectors": [
                        {
                            "key": self.name,
                            "target": "#id_template",
                            "field_prefix": "",
                        }
                    ]
                }
            ),
        }

    def render_change_form(
        self,
        request: HttpRequest,
        context: dict[str, Any],
        add: bool = False,
        change: bool = False,
        form_url: str = "",
        obj: DjangoModel | None = None,
    ):
        context = {**context, **self.get_form_context(request, obj)}
        if obj is None:
            fingerprint = request.GET.get(f"{self.name}_fingerprint")
            if fingerprint:
                context["fingerprint"] = fingerprint[:6]
                context["version_info"] = {"current": 0, "total": 0}
            return super().render_change_form(
                request, context, add, change, form_url, obj
            )

        # obj is generically typed DjangoModel to match the base admin's
        # signature, but this admin (and its `obj`) is always a BranchModel.
        obj = cast(BranchModel, obj)

        context["fingerprint"] = obj.target.fingerprint[:6]
        context["timestamp"] = obj.timestamp.strftime("%Y-%m-%d %H:%M")

        if obj.owner.name != request.user.username:
            context["version_info"] = {"current": 1, "total": 1}
            return super().render_change_form(
                request, context, add, change, form_url, obj
            )

        timeline = list(
            self.model.objects.filter(
                owner__name=request.user.username,
                name=obj.name,
            )
            .order_by("timestamp")
            .values_list("pk", "timestamp")
        )

        pks = [item[0] for item in timeline]

        idx = pks.index(obj.pk)

        if idx > 0:
            prev_pk, prev_ts = timeline[idx - 1]
            context["prev_"] = {
                "pk": prev_pk,
                "text": f"Older ({prev_ts.strftime('%Y-%m-%d %H:%M')})",
            }
            context["first_"] = {"pk": pks[0]}

        if idx < len(pks) - 1:
            next_pk, next_ts = timeline[idx + 1]
            context["next_"] = {
                "pk": next_pk,
                "text": f"Newer ({next_ts.strftime('%Y-%m-%d %H:%M')})",
            }
            context["last_"] = {"pk": pks[-1]}

        context["version_info"] = {"current": idx + 1, "total": len(pks)}

        return super().render_change_form(request, context, add, change, form_url, obj)

    @no_type_check
    def message_user(self, request, message, level=messages.SUCCESS, **kwargs):
        if (
            getattr(request, "_skip_success_message", False)
            and level == messages.SUCCESS
        ):
            return
        return super().message_user(request, message, level=level, **kwargs)
