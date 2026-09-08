# src/chatddx/django/repo/admin/expect.py
"""
Inline editing of Expect rows on the Case admin form.

Expect has no ModelAdmin/form of its own (see chatddx.repo.shufflers.expect)
and its identifying FK ("case") points at CaseTrailModel, not at the
CaseBranchModel/proxies.Case the Case admin actually edits -- so Django's
stock `admin.TabularInline` can't wire this up (it requires a ForeignKey
from the inline's model straight to the parent ModelAdmin's model). We use
Unfold's `NonrelatedTabularInline`, built for exactly this: a child model
related to the parent by something other than a direct ForeignKey.
"""
# pyright: basic
from typing import Any, final

from django.forms import CharField, ModelChoiceField, ModelForm
from django.http import HttpRequest
from unfold.contrib.inlines.admin import NonrelatedTabularInline
from unfold.contrib.inlines.forms import NonrelatedInlineModelFormSet
from unfold.widgets import UnfoldAdminSelect2Widget, UnfoldAdminTextareaWidget

from chatddx.repo import proxies
from chatddx.repo.branch_models import ExpectBranchModel, OutputTypeBranchModel
from chatddx.repo.shufflers.expect import dump_expect, load_expects
from chatddx.repo.shufflers.main import qs_canon


class OutputTypeChoiceField(ModelChoiceField):
    def label_from_instance(self, obj: OutputTypeBranchModel) -> str:
        return obj.name or obj.target.fingerprint[:6]


class ExpectInlineForm(ModelForm):
    """
    `output_type` and `payload` aren't real fields of ExpectBranchModel --
    the branch only carries `target` (an immutable ExpectTrailModel row).
    Same pattern as CaseForm: declare the content fields by hand and let
    the formset (below) resolve them into a trail+branch pair on save.

    Not `@final`: `ExpectInline.get_formset` subclasses this per-request to
    bind `output_type`'s queryset to the current owner.
    """

    payload = CharField(
        widget=UnfoldAdminTextareaWidget(attrs={"rows": 3}),
        label="Expected Payload",
        help_text="The expected output for this Case/Output Type pair.",
    )

    class Meta:
        model = ExpectBranchModel
        fields: list[str] = []

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            target = self.instance.target
            self.initial.setdefault("payload", target.payload)

            current = qs_canon(
                OutputTypeBranchModel.objects.filter(target_id=target.output_type_id),
                self.instance.owner.name,
            ).first()
            if current:
                self.initial.setdefault("output_type", current.pk)


@final
class ExpectInlineFormSet(NonrelatedInlineModelFormSet):
    """
    `self.instance` is the Case *branch* (proxies.Case) being edited, set by
    NonrelatedInlineModelFormSet.__init__. Both new and edited expectations
    resolve to the same operation -- get-or-create the trail content, and
    point the (case, output_type) branch at it if it changed -- since
    ExpectTrailModel rows can never be mutated in place (enforced by a DB
    trigger, see chatddx.django.orm.apps.install_trail_triggers). Editing an
    existing row here doesn't touch that row; it may make a new one canonical
    for the pair, exactly like editing a Case makes a new CaseBranchModel
    canonical for its name.
    """

    instance: proxies.Case

    def _dump(self, form: ExpectInlineForm) -> ExpectBranchModel:
        branch, _created = dump_expect(
            case=self.instance.target,  # pyright: ignore
            output_type=form.cleaned_data["output_type"].target,
            payload=form.cleaned_data["payload"],
            owner_name=self.instance.owner.name,
        )
        return branch

    def save_new(self, form: ExpectInlineForm, commit: bool = True) -> ExpectBranchModel:
        return self._dump(form)

    def save_existing(
        self,
        form: ExpectInlineForm,
        instance: ExpectBranchModel,
        commit: bool = True,
    ) -> ExpectBranchModel:
        return self._dump(form)


@final
class ExpectInline(NonrelatedTabularInline):
    model = ExpectBranchModel
    form = ExpectInlineForm
    formset = ExpectInlineFormSet
    extra = 1
    verbose_name = "Expectation"
    verbose_name_plural = "Expectations"

    def get_form_queryset(self, obj: proxies.Case):
        if obj is None or obj.pk is None:
            return ExpectBranchModel.objects.none()

        return load_expects(obj.target, obj.owner.name)  # pyright: ignore

    def save_new_instance(self, parent: proxies.Case, instance: ExpectBranchModel) -> None:
        # Unused: ExpectInlineFormSet.save_new bypasses this hook entirely,
        # since persisting an Expect is a get-or-create dance across two
        # tables, not "set one FK and save". Required by NonrelatedInlineMixin.
        raise NotImplementedError

    def get_formset(self, request: HttpRequest, obj: Any = None, **kwargs: Any):
        # Scope by the Case's own owner (not necessarily request.user, who
        # may be a collaborator) since that's who dump_expect() will credit
        # any new Expect branch to -- see ExpectInlineFormSet._dump.
        owner_name = obj.owner.name if obj is not None else request.user.username

        output_type_queryset = qs_canon(
            OutputTypeBranchModel.objects.all(),
            owner_name,
        )

        class BoundExpectInlineForm(self.form):
            output_type = OutputTypeChoiceField(
                queryset=output_type_queryset,
                widget=UnfoldAdminSelect2Widget(),
                label="Output Type",
            )

        kwargs["form"] = BoundExpectInlineForm

        return super().get_formset(request, obj, **kwargs)
