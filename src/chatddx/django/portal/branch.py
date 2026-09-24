# pyright: basic
import json
from typing import Any

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Model as DjangoModel, QuerySet
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import reverse
from unfold.contrib.inlines.admin import NonrelatedTabularInline

from chatddx.core.utils import ensure_tag
from chatddx.django.orm.qs import qs_head, qs_with_relations
from chatddx.django.portal.forms.branch_base import BranchForm
from chatddx.django.portal.mixins import ModelAdminFormWithRequest
from chatddx.django.portal.request_context import RequestContext, request_contexts
from chatddx.django.portal.typing import TypedModelAdmin
from chatddx.django.portal.utils import template_registry
from chatddx.repo.bundles import entity_of, presentation_of
from chatddx.repo.entity_names import EntityName
from chatddx.repo.families.django import BranchProxy
from chatddx.repo.families.pydantic import BranchDetails
from chatddx.repo.store import branch


class BranchModelInlineAdmin[T: BranchProxy](NonrelatedTabularInline):
    pass


class BranchModelAdmin[T: BranchProxy](
    ModelAdminFormWithRequest,
    TypedModelAdmin[T],
):
    name: EntityName

    change_form_template = "templates/branch_change_form.html"
    add_form_template = "templates/branch_change_form.html"

    list_display = (
        "name",
        "versions",
    )

    @admin.display(description="Versions")
    def versions(self, obj: BranchProxy) -> int | None:
        return obj.version_count

    def get_queryset(self, request: HttpRequest):
        qs: QuerySet[Any] = super().get_queryset(request)
        return qs_head(qs, request.user.username)

    def get_object(self, request, object_id, from_field=None):
        queryset = qs_with_relations(super().get_queryset(request))
        model = queryset.model
        field = (
            model._meta.pk if from_field is None else model._meta.get_field(from_field)  # pyright: ignore[reportAttributeAccessIssue]
        )
        assert field is not None
        try:
            object_id = field.to_python(object_id)
            return queryset.get(**{field.name: object_id})
        except (model.DoesNotExist, ValidationError, ValueError):  # pyright: ignore[reportAttributeAccessIssue]
            return None

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[DjangoModel]):
        names_subquery = queryset.values_list("name", flat=True)

        self.model.objects.filter(
            name__in=names_subquery,
            owner__name=request.user.username,
        ).delete()

        ThroughModel = self.model.collaborators.through

        ThroughModel.objects.filter(
            **{f"{self.name.replace('_', '')}branchmodel__name__in": names_subquery},
            identitymodel__name=request.user.username,
        ).delete()

    def render_change_form(
        self,
        request: HttpRequest,
        context: dict[str, Any],
        add: bool = False,
        change: bool = False,
        form_url: str = "",
        obj: BranchProxy | None = None,
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

        context["fingerprint"] = obj.target.fingerprint[:6]
        context["timestamp"] = obj.timestamp.strftime("%Y-%m-%d %H:%M")  # pyright: ignore[reportAttributeAccessIssue]

        if obj.owner.name != request.user.username:  # pyright: ignore[reportAttributeAccessIssue]
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

    def template_selectors(self) -> list[dict[str, Any]]:
        return [
            {
                "key": self.name,
                "target": "#id_template",
                "field_prefix": "",
            }
        ]

    def get_form_context(self, request: HttpRequest, obj: Any) -> dict[str, Any]:
        selectors = self.template_selectors()

        return {
            "template_data": template_registry(
                request.user.username,
                tuple(selector["key"] for selector in selectors),
            ),
            "form_info": json.dumps({"template_selectors": selectors}),
        }

    def save_form(
        self,
        request: HttpRequest,
        form: BranchForm,
        change: bool,
    ) -> BranchProxy:
        self._validated_data(form)

        return presentation_of(self.name).proxy()

    def save_model(
        self, request: HttpRequest, obj: BranchProxy, form: BranchForm, change: Any
    ):

        data = self._validated_data(form)
        schema_cls = entity_of(self.name).trail_in

        schema = schema_cls.model_validate(data.model_dump())
        branch_name = data.name or ""

        assert data.owner

        created: bool = branch.commit(
            branch_details=BranchDetails(
                name=branch_name,
                owner=data.owner.name,
            ),
            trail=schema,
        )

        canon = branch.get_branch_model(
            entity_name=self.name,
            owner_name=data.owner.name,
            branch_name=branch_name,
        )

        # consistency check
        assert schema.fingerprint == canon.target.fingerprint

        obj.pk = canon.pk
        obj.refresh_from_db()
        obj._state.adding = False

        request_contexts[request] = RequestContext(canon=canon, created=created)

    def save_related(
        self,
        request: HttpRequest,
        form: BranchForm,
        formsets: list[Any],
        change: bool,
    ) -> None:
        outcome = request_contexts[request]
        outcome.changed += self._sync_collaborators(outcome.canon, form)
        outcome.changed += self._sync_tags(outcome.canon, form)

        for formset in formsets:
            formset.instance = outcome.canon
            self.save_formset(request, form, formset, change=change)

    def _sync_collaborators(self, canon: Any, form: BranchForm) -> list[str]:
        wanted = self._validated_data(form).collaborators
        if wanted is None:
            return []

        current_ids = set(canon.collaborators.values_list("pk", flat=True))
        target_ids = {identity.id for identity in wanted}
        if current_ids == target_ids:
            return []

        canon.collaborators.set(target_ids)
        return ["collaborators"]

    def _sync_tags(self, canon: Any, form: BranchForm) -> list[str]:
        wanted = self._validated_data(form).tags
        if wanted is None:
            return []

        tags = [ensure_tag(canon.owner, self.name, name) for name in wanted]

        current_ids = set(canon.tags.values_list("pk", flat=True))
        target_ids = {tag.pk for tag in tags}
        if current_ids == target_ids:
            return []

        canon.tags.set(target_ids)
        return ["tags"]

    def _validated_data(self, form: BranchForm):
        data = form.validated_data
        if data is None:
            raise ValueError("form.validated_data is unexpectedly None")

        assert data.owner is not None

        return data

    def construct_change_message(self, request, form, formsets, add):
        outcome = request_contexts.get(request)

        if outcome is not None and not outcome.created:
            return [{"changed": {"fields": outcome.changed}}] if outcome.changed else []

        return super().construct_change_message(request, form, formsets, add)

    def log_addition(self, request, obj, message):
        outcome = request_contexts.get(request)

        if outcome is not None and not outcome.created:
            return self.log_change(request, obj, message)

        return super().log_addition(request, obj, message)

    def log_change(self, request, obj, message):
        outcome = request_contexts.get(request)

        if outcome is not None and outcome.is_noop:
            return None

        return super().log_change(request, obj, message)

    def response_add(self, request, obj, post_url_continue=None):
        self._announce_outcome(request)
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request: HttpRequest, obj: DjangoModel):
        self._announce_outcome(request)

        if "_continue" not in request.POST:
            return super().response_change(request, obj)

        opts = self.model._meta

        redirect_url = reverse(
            f"admin:{opts.app_label}_{opts.model_name}_change",
            args=(obj.pk,),
        )

        return HttpResponseRedirect(redirect_url)

    def message_user(
        self,
        request,
        message,
        level=messages.INFO,
        extra_tags="",
        fail_silently=False,
    ):
        outcome = request_contexts.get(request)

        if outcome is not None and not outcome.created and level == messages.SUCCESS:
            return

        super().message_user(request, message, level, extra_tags, fail_silently)

    def _announce_outcome(self, request: HttpRequest) -> None:
        outcome = request_contexts.get(request)
        if outcome is None:
            return

        if outcome.created:
            if outcome.changed:
                self.message_user(
                    request,
                    f"{' and '.join(outcome.changed).capitalize()} successfully set "
                    "for the new branch version.",
                    messages.SUCCESS,
                )
        elif outcome.changed:
            self.message_user(
                request,
                self.unchanged_message(outcome.changed),
                messages.INFO,
            )
        else:
            self.message_user(
                request,
                "No changes detected. The current version is up to date.",
                messages.INFO,
            )

    def unchanged_message(self, changed: list[str]) -> str:
        return f"Configuration unchanged, but updated {' and '.join(changed)}."
