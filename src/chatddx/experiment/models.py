# src/chatddx/experiment/models.py
from __future__ import annotations

import uuid

from django.db.models import (
    PROTECT,
    CharField,
    DateTimeField,
    ForeignKey,
    ManyToManyField,
    Model,
    UUIDField,
)

from chatddx.core.choices import RunStatusChoices
from chatddx.core.models import IdentityModel
from chatddx.history.models import SessionModel
from chatddx.repo.trail_models import (
    AgentTrailModel,
    CaseTrailModel,
    ExpectTrailModel,
)


class ExperimentModel(Model):
    """A frozen, self-contained record of one Agent run against one Case.

    An Experiment is to scoring what a Session is to a live conversation:
    like SessionModel, it is never hand-authored or edited in place, only
    ever created -- here, generated when a Batch (not implemented yet) is
    saved. Once created it must stay runnable and scoreable completely
    unchanged, even a year from now, so every reference it holds has to be
    frozen at creation time.

    That is why `agent`, `case` and `expect` below point at *Trail* rows,
    never at Branch rows. A Branch (e.g. AgentBranchModel) is a mutable,
    named pointer -- editing the agent's instructions or swapping its
    connection repoints the same branch at a new trail -- so anchoring an
    Experiment to a branch would let its meaning drift out from under it
    later. Anchoring directly to the trail is what makes an Experiment's
    agent, case and expected answer permanent: those rows are enforced
    immutable at the database level (see
    chatddx.django.orm.apps.install_trail_triggers) and every trail a trail
    references is itself pinned the same way, all the way down.

    See chatddx.repo.shufflers.experiment for the (owner, tags, agent,
    case) -> Experiment construction logic, including the check for the
    piece of information this model *cannot* by itself guarantee is
    present: a matching Expect for the agent's output_type.
    """

    class Meta:
        app_label = "orm"
        db_table = "agents_experiment"

    uuid = UUIDField(
        default=uuid.uuid4,
        editable=False,
    )
    timestamp = DateTimeField(auto_now_add=True)
    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
    )
    collaborators = ManyToManyField(
        IdentityModel,
        blank=True,
        related_name="shared_experiments",
    )

    # Comma-separated labels, deliberately *not* a many-to-many to TagModel:
    # TagModel rows are live, owner-scoped and renamable/deletable (see
    # chatddx.repo.shufflers.tags), so a reference to one could change or
    # vanish out from under a supposedly-frozen experiment. Storing the
    # tag text directly keeps it frozen alongside everything else here, at
    # the cost of it no longer tracking renames of the "live" tag.
    tags = CharField(max_length=255, blank=True, default="")

    agent = ForeignKey(
        AgentTrailModel,
        on_delete=PROTECT,
        related_name="experiments",
    )
    case = ForeignKey(
        CaseTrailModel,
        on_delete=PROTECT,
        related_name="experiments",
    )
    expect = ForeignKey(
        ExpectTrailModel,
        on_delete=PROTECT,
        related_name="experiments",
    )

    @property
    def tag_list(self) -> list[str]:
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]


class RunModel(Model):
    """One attempt, tracked through pgqueuer, to execute an Experiment.

    A Run is the queue-facing counterpart to Experiment: it holds every
    piece of context pgqueuer needs to pick the job up, execute it and
    record the outcome, without pgqueuer having to know anything about
    agents, cases or trails itself.

    `session` is None until a run completes successfully, at which point
    it is set to the SessionModel the run produced -- mirroring how
    `status` starts at STORED and only reaches COMPLETED once that
    session exists. A run that ends in ERRORED never gets a session.
    """

    class Meta:
        app_label = "orm"
        db_table = "agents_run"

    uuid = UUIDField(
        default=uuid.uuid4,
        editable=False,
    )
    timestamp = DateTimeField(auto_now_add=True)
    status = CharField(
        max_length=255,
        choices=RunStatusChoices.choices,
        default=RunStatusChoices.STORED,
    )
    owner = ForeignKey(
        IdentityModel,
        on_delete=PROTECT,
    )
    collaborators = ManyToManyField(
        IdentityModel,
        blank=True,
        related_name="shared_runs",
    )

    experiment = ForeignKey(
        ExperimentModel,
        on_delete=PROTECT,
        related_name="runs",
    )
    # None until the run completes successfully; see class docstring.
    session = ForeignKey(
        SessionModel,
        default=None,
        null=True,
        blank=True,
        on_delete=PROTECT,
        related_name="runs",
    )
