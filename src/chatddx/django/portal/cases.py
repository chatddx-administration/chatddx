# pyright: basic
"""
A case as the portal shows it to its owner: its timeline, each version and
what changed in it; what saving under a name does, and which other cases
hold the vignette; what holds a version or the case where it is to be
deleted, and deleting it; and the runs of a vignette, with the scores that
go with the targets they are held to now.
"""

import difflib
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from django.db import transaction
from django.db.models import F, Func, TextField, Value
from django.db.models.functions import Replace
from django.utils.translation import gettext, gettext_lazy as _

from chatddx.bench.bench import Bench
from chatddx.django.portal.status import value_of
from chatddx.history.models import RunModel, ScoreModel
from chatddx.repo.entities.case.django import CaseBranchModel, CaseTrailModel
from chatddx.repo.entities.case.pydantic import (
    TARGET_KINDS,
    CaseBranchDetails,
    CaseDetails,
    CaseTrailIn,
    Expected,
    Target,
    TargetKind,
)
from chatddx.repo.queries import deleted, head_of
from chatddx.repo.store.branch import commit
from chatddx.scoring.score import Scoring
from chatddx.scoring.scorers.patterns import unread_pattern
from chatddx.worker.models import JobModel

# what the page calls each kind of target
KINDS: dict[TargetKind, Any] = {
    "diagnosis": _("Diagnosis"),
    "warning": _("Warning"),
    "disposition": _("Disposition"),
    "dont_miss": _("Don't miss"),
}

# the whitespace a vignette is saved without, around it
AROUND = " \t\n\r\f\v"

# the most runs a case's page lists, the latest
SHOWN_RUNS = 10

# what a vignette is compared by: its words, the spaces and the marks between
_TOKEN = re.compile(r"\w+|\s+|[^\w\s]+")

# how many of a vignette's words are kept, at least, for its change to go
# word by word
REWRITTEN = 0.4
_WORD = re.compile(r"\w+")


def versions_of(owner: str, name: str) -> list[CaseBranchModel]:
    """The owner's case of the name: its timeline, the first version first."""
    return list(
        CaseBranchModel.objects.filter(owner__name=owner, name=name)
        .select_related("owner", "trail")
        .prefetch_related("tags")
        .order_by("timestamp", "id")
    )


@dataclass(frozen=True)
class Shown:
    """A target as the page shows it: none expected, or its text and pattern."""

    kind: TargetKind
    none: bool = False
    text: str | None = None
    pattern: str | None = None

    @property
    def label(self) -> Any:
        return KINDS[self.kind]

    @property
    def missing(self) -> bool:
        return not (self.none or self.text or self.pattern)

    @property
    def unread(self) -> str | None:
        """Why the pattern doesn't parse, if it doesn't."""
        return None if self.pattern is None else unread_pattern(self.pattern)


def shown_of(kind: TargetKind, target: Target | None) -> Shown:
    match target:
        case False:
            return Shown(kind, none=True)
        case Expected(text=text, pattern=pattern):
            return Shown(kind, text=text, pattern=pattern)
        case _:
            return Shown(kind)


@dataclass(frozen=True)
class Version:
    """A version of a case: which of how many, and what it holds."""

    row: CaseBranchModel
    number: int
    of: int

    @property
    def is_head(self) -> bool:
        return self.number == self.of

    @property
    def details(self) -> CaseDetails:
        return CaseDetails.model_validate(self.row.details)

    @property
    def vignette(self) -> str:
        return self.row.trail.vignette

    @property
    def language(self) -> str | None:
        return self.details.language

    @property
    def targets(self) -> list[Shown]:
        targets = self.details.targets

        return [shown_of(kind, targets.get(kind)) for kind in TARGET_KINDS]

    @property
    def tags(self) -> list[str]:
        return sorted(tag.name for tag in self.row.tags.all())

    @property
    def deleted(self) -> bool:
        return self.details.deleted


@dataclass(frozen=True)
class Draft:
    """A case as a page would save it, beside the case it would replace."""

    vignette: str
    language: str | None
    targets: list[Shown]
    tags: list[str]
    deleted: bool = False


class Content(Protocol):
    """What a version or a draft holds, as a change is told of it."""

    @property
    def vignette(self) -> str: ...

    @property
    def language(self) -> str | None: ...

    @property
    def targets(self) -> list[Shown]: ...

    @property
    def tags(self) -> list[str]: ...

    @property
    def deleted(self) -> bool: ...


@dataclass(frozen=True)
class Timeline:
    """A case's versions, the first first."""

    rows: list[CaseBranchModel]

    @classmethod
    def of(cls, row: CaseBranchModel) -> "Timeline":
        return cls(versions_of(row.owner.name, row.name))

    @property
    def name(self) -> str:
        return self.rows[-1].name

    @property
    def head(self) -> Version:
        return self.version(len(self.rows))

    def version(self, number: int) -> Version:
        return Version(self.rows[number - 1], number, len(self.rows))

    def version_of(self, row: CaseBranchModel) -> Version:
        [number] = [i for i, each in enumerate(self.rows, 1) if each.pk == row.pk]
        return self.version(number)

    def before(self, version: Version) -> Version | None:
        return self.version(version.number - 1) if version.number > 1 else None

    def after(self, version: Version) -> Version | None:
        return self.version(version.number + 1) if not version.is_head else None


@dataclass(frozen=True)
class Change:
    """What changed of one part of a case from a version to the next."""

    label: Any
    before: str = ""
    after: str = ""
    # the vignette, word by word: each kept, gone or new
    words: list[tuple[str, str]] = field(default_factory=list)
    # the vignette, rewritten too far to show word by word
    whole: bool = False


def changes(before: Content | None, after: Content) -> list[Change]:
    """What changed from `before` to `after`: nothing, where `after` is the first."""
    if before is None:
        return []

    found: list[Change] = []

    if before.vignette != after.vignette:
        found.append(vignette_change(before.vignette, after.vignette))

    if before.language != after.language:
        found.append(Change(_("Language"), before.language or "", after.language or ""))

    for was, now in zip(before.targets, after.targets, strict=True):
        if was == now:
            continue

        if not (was.none or now.none or was.missing or now.missing):
            for part, label in (("text", _("text")), ("pattern", _("pattern"))):
                if getattr(was, part) != getattr(now, part):
                    found.append(
                        Change(
                            f"{now.label}: {label}",
                            getattr(was, part) or "",
                            getattr(now, part) or "",
                        )
                    )
        else:
            found.append(Change(now.label, said_of(was), said_of(now)))

    if before.tags != after.tags:
        found.append(Change(_("Tags"), " ".join(before.tags), " ".join(after.tags)))

    if before.deleted != after.deleted:
        found.append(
            Change(
                _("Deleted"),
                gettext("yes") if before.deleted else gettext("no"),
                gettext("yes") if after.deleted else gettext("no"),
            )
        )

    return found


def said_of(target: Shown) -> str:
    """A target in a few words, as a change shows it."""
    if target.none:
        return gettext("none expected")

    if target.missing:
        return gettext("missing")

    return " · ".join(part for part in (target.text, target.pattern) if part)


def vignette_change(before: str, after: str) -> Change:
    """
    What changed of the vignette: word by word, as it came of `before` (kept,
    gone or new), or whole, where too little of it is kept to follow.
    """
    kept = difflib.SequenceMatcher(
        None, _WORD.findall(before), _WORD.findall(after), autojunk=False
    ).ratio()

    if kept < REWRITTEN:
        return Change(_("Vignette"), whole=True)

    was, now = _TOKEN.findall(before), _TOKEN.findall(after)
    matcher = difflib.SequenceMatcher(None, was, now, autojunk=False)

    found: list[tuple[str, str]] = []

    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            found.append(("kept", "".join(was[i1:i2])))
            continue

        if i2 > i1:
            found.append(("gone", "".join(was[i1:i2])))

        if j2 > j1:
            found.append(("new", "".join(now[j1:j2])))

    return Change(_("Vignette"), words=found)


def needs_of(details: dict[str, Any]) -> dict[str, list[TargetKind]]:
    """
    What a case's targets still want, by kind: a text, a pattern, or a
    pattern that parses. A target none is expected of wants nothing.
    """
    targets = CaseDetails.model_validate(details).targets
    needs: dict[str, list[TargetKind]] = {"text": [], "pattern": [], "unread": []}

    for kind in TARGET_KINDS:
        target = shown_of(kind, targets.get(kind))

        if target.none:
            continue

        if not target.text:
            needs["text"].append(kind)

        if not target.pattern:
            needs["pattern"].append(kind)
        elif target.unread is not None:
            needs["unread"].append(kind)

    return needs


class Saving(StrEnum):
    # a new version of the case the page is of
    SAME = "same"
    # a new case, the page's own staying as it is
    NEW = "new"
    # a new version of another case of the owner's
    ONTO = "onto"
    # a new version of a case the owner deleted, which brings it back
    BACK = "back"


@dataclass(frozen=True)
class Said:
    """What saving the page under a name does, said before it is done."""

    saving: Saving
    name: str
    # the version the save makes of the case it saves to
    version: int
    # the head of the case saved onto, where it is another
    onto: CaseBranchModel | None = None
    # the version the page began from, where it is an earlier one
    since: int | None = None
    # the page's case, where it is of one
    edited: str | None = None
    # the owner's other cases whose names differ from it in capitals alone
    capitals: list[str] = field(default_factory=list)

    @property
    def confirms(self) -> bool:
        """Whether the save asks first: it replaces another case's content."""
        return self.saving in (Saving.ONTO, Saving.BACK)

    @property
    def line(self) -> str:
        said = {"name": self.name, "version": self.version, "since": self.since}

        match self.saving:
            case _ if not self.name:
                return gettext("Name the case to save it.")
            case Saving.SAME if self.since is not None:
                return (
                    gettext(
                        "Saving makes version %(version)d of this case, from version "
                        + "%(since)d."
                    )
                    % said
                )
            case Saving.SAME:
                return gettext("Saving makes version %(version)d of this case.") % said
            case Saving.NEW if self.edited is not None:
                return (
                    gettext(
                        "Saving makes a new case, %(name)s, and this one stays as it is."
                    )
                    % said
                )
            case Saving.NEW:
                return gettext("Saving makes a new case, %(name)s.") % said
            case Saving.ONTO:
                return (
                    gettext(
                        "Saving makes version %(version)d of %(name)s, another case of "
                        + "yours, replacing its vignette and targets."
                    )
                    % said
                )
            case Saving.BACK:
                return (
                    gettext(
                        "Saving brings back %(name)s, which you deleted, as its "
                        + "version %(version)d, replacing its vignette and targets."
                    )
                    % said
                )

    @property
    def button(self) -> str:
        said = {"name": self.name, "version": self.version}

        match self.saving:
            case Saving.SAME:
                return gettext("Save as version %(version)d") % said
            case Saving.NEW:
                return gettext("Save as a new case")
            case Saving.ONTO:
                return gettext("Save onto %(name)s…") % said
            case Saving.BACK:
                return gettext("Bring %(name)s back…") % said


def said(
    owner: str, name: str, edited: str | None = None, since: int | None = None
) -> Said:
    """What saving under `name` does, the page being of `edited`, where it is."""
    name = name.strip()
    rows = CaseBranchModel.objects.filter(owner__name=owner)
    count = rows.filter(name=name).count() if name else 0
    capitals = sorted(
        other
        for other in set(
            rows.filter(name__iexact=name)
            .exclude(name=name)
            .values_list("name", flat=True)
        )
        if other != edited
        and (head := head_of(rows, owner, other)) is not None
        and not deleted(head)
    )

    if edited is not None and name == edited:
        return Said(Saving.SAME, name, count + 1, None, since, edited, capitals)

    head = head_of(rows, owner, name) if count else None

    if head is None:
        return Said(Saving.NEW, name, 1, None, None, edited, capitals)

    saving = Saving.BACK if deleted(head) else Saving.ONTO

    return Said(saving, name, count + 1, head, None, edited, capitals)


def vignette_of(owner: str, vignette: str) -> str:
    """
    The vignette as it is saved: its line endings made plain and the
    whitespace around it gone; or, where it is a vignette of a case the owner
    can see, but for its line endings and that whitespace, that one exactly,
    so the two are one.
    """
    bare = _plain(vignette).strip(AROUND)
    trails = CaseTrailModel.objects.annotate(
        bare=Func(
            Replace(
                Replace(F("vignette"), Value("\r\n"), Value("\n")),
                Value("\r"),
                Value("\n"),
            ),
            Value(AROUND),
            function="btrim",
            output_field=TextField(),
        )
    ).filter(bare=bare)

    for held in (
        trails.filter(branches__owner__name=owner),
        trails.filter(branches__collaborators__name=owner),
    ):
        found = held.order_by("pk").values_list("vignette", flat=True).first()

        if found is not None:
            return found

    return bare


def _plain(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


@dataclass(frozen=True)
class Sharer:
    """Another case whose head has the vignette: the owner's, or shared with them."""

    name: str
    owner: str
    pk: int
    own: bool
    tagged: bool


def sharers(
    owner: str, vignette: str, name: str, edited: str | None = None
) -> list[Sharer]:
    """
    The cases, the owner's own and those shared with them, whose head has
    the vignette, bar the page's own and the one it saves to: a shared one
    named as the page names its case gives way to it.
    """
    trail = (
        CaseTrailModel.objects.filter(
            fingerprint=CaseTrailIn(vignette=vignette).fingerprint
        )
        .values_list("pk", flat=True)
        .first()
    )

    if trail is None:
        return []

    found: list[Sharer] = []

    for head in Bench(owner).usable("case"):
        own = head.owner.name == owner

        if head.trail_id != trail or head.name == name or (own and head.name == edited):
            continue

        found.append(
            Sharer(
                head.name, head.owner.name, head.pk, own, bool(list(head.tags.all()))
            )
        )

    return found


@dataclass(frozen=True)
class Held:
    """
    What of the owner's reads a version, or a case: the scores held to it,
    and the runs and the trials of their batches on its vignette.
    """

    scores: int = 0
    runs: int = 0
    trials: int = 0

    def __bool__(self) -> bool:
        return bool(self.scores or self.runs or self.trials)


def version_held(row: CaseBranchModel) -> Held:
    """What holds a version: its scores, and its vignette's runs where no other version has it."""
    scores = ScoreModel.objects.filter(case_branch=row).count()
    another = (
        CaseBranchModel.objects.filter(
            owner_id=row.owner_id, name=row.name, trail_id=row.trail_id
        )
        .exclude(pk=row.pk)
        .exists()
    )

    return Held(scores) if another else Held(scores, *_on(row.owner_id, {row.trail_id}))


def case_held(rows: list[CaseBranchModel]) -> Held:
    """What holds a case: the scores held to its versions, and its vignettes' runs."""
    return Held(
        ScoreModel.objects.filter(case_branch__in=rows).count(),
        *_on(rows[0].owner_id, {row.trail_id for row in rows}),
    )


def _on(owner_id: int, trails: set[int]) -> tuple[int, int]:
    return (
        RunModel.objects.filter(owner_id=owner_id, trial__case_id__in=trails).count(),
        JobModel.objects.filter(owner_id=owner_id, case_trail_id__in=trails).count(),
    )


class Deleted(StrEnum):
    # nothing read it: its versions are gone
    GONE = "gone"
    # taken out of sight, kept for what reads it
    HIDDEN = "hidden"


def delete_case(owner: str, name: str) -> Deleted:
    """
    The owner's case deleted: gone, where nothing reads it, and else taken
    out of sight, a version of it deleted made its head.
    """
    rows = versions_of(owner, name)

    with transaction.atomic():
        if not case_held(rows):
            _ = CaseBranchModel.objects.filter(pk__in=[row.pk for row in rows]).delete()
            return Deleted.GONE

        head = rows[-1]
        _ = commit(head.trail, _details(head, deleted=True))

        return Deleted.HIDDEN


def restore(owner: str, name: str) -> None:
    """
    The owner's deleted case brought back: its deleting undone, where
    nothing has read that since, and else a version of it not deleted.
    """
    rows = versions_of(owner, name)
    head = rows[-1]

    if not deleted(head):
        return

    with transaction.atomic():
        if len(rows) > 1 and not ScoreModel.objects.filter(case_branch=head).exists():
            _ = head.delete()
        else:
            _ = commit(head.trail, _details(head, deleted=False))


def untagged(row: CaseBranchModel) -> None:
    """The case's tags taken off its head, in place: batches by tag pass it by."""
    head = versions_of(row.owner.name, row.name)[-1]
    _ = commit(head.trail, _details(head, tags=[]))


def _details(row: CaseBranchModel, **changed: Any) -> CaseBranchDetails:
    return CaseBranchDetails.model_validate(
        {**row.details, "name": row.name, "owner": row.owner.name, **changed}
    )


# what a score not yet made, for the target a run is held to now, shows
OUTSTANDING = _("outstanding")


@dataclass(frozen=True)
class RunRow:
    """A run of the vignette: when, which trial, and its score for each scorer shown."""

    run: RunModel
    cell: str
    scores: list[str]


@dataclass(frozen=True)
class Runs:
    """The owner's runs of a vignette, the latest first, and how they stand."""

    rows: list[RunRow]
    scorers: list[str]
    total: int
    outstanding: int
    # the runs of the case's other vignettes, which keep their targets
    earlier: int


def runs_of(owner: str, trail: int, others: set[int]) -> Runs:
    """
    The owner's runs of the vignette, each with its scores for the targets
    it is held to now, as scoring has them; and those of the case's other
    vignettes, counted.
    """
    scoring = Scoring(owner)
    runs = list(
        RunModel.objects.filter(owner__name=owner, trial__case_id=trail)
        .select_related("trial__configuration__output", "conversation")
        .prefetch_related("scores")
        .order_by("-timestamp", "-pk")
    )
    found: list[tuple[RunModel, dict[str, str]]] = []

    for run in runs[:SHOWN_RUNS]:
        scores: dict[str, str] = {}

        for scorer, target, _case in scoring.applicable(run):
            matching = [
                score
                for score in run.scores.all()
                if score.owner_id == scoring.owner_id
                and score.scorer_id == scorer.trail.pk
                and score.target == target
            ]
            scores[scorer.name] = (
                value_of(max(matching, key=lambda score: score.pk).value)
                if matching
                else str(OUTSTANDING)
            )

        found.append((run, scores))

    named = {name for _run, scores in found for name in scores}
    scorers = [scorer.name for scorer in scoring.scorers if scorer.name in named]

    return Runs(
        rows=[
            RunRow(
                run,
                (run.conversation.description if run.conversation else None) or "—",
                [scores.get(scorer, "—") for scorer in scorers],
            )
            for run, scores in found
        ],
        scorers=scorers,
        total=len(runs),
        outstanding=sum(bool(scoring.outstanding(run)) for run in runs),
        earlier=RunModel.objects.filter(
            owner__name=owner, trial__case_id__in=others - {trail}
        ).count(),
    )


def score_again(owner: str, trail: int) -> int:
    """The owner's runs of the vignette scored where they are outstanding: how many scores."""
    scoring = Scoring(owner)
    runs = (
        RunModel.objects.filter(owner__name=owner, trial__case_id=trail)
        .select_related("trial__configuration__output")
        .prefetch_related("scores")
    )

    return sum(len(scoring.score(run)) for run in runs)
