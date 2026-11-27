from collections.abc import Mapping, Sequence

from pydantic import JsonValue

from chatddx.factors.base import (
    Component,
    Invalid,
    Missing,
    canonical_bytes,
    iter_refs,
    resolve,
)
from chatddx.factors.facts import ModelFacts
from chatddx.factors.kinds import parse_component
from chatddx.factors.request import Compilation, Recipe, compile_request
from chatddx.factors.scoring import Expectation, Scorer
from chatddx.identity import owns

from .families import stale_cases
from .model import (
    RUN_FIELDS,
    THREAD_KINDS,
    About,
    Behind,
    Divergence,
    Edit,
    Entry,
    EntryField,
    Labels,
    MovedOn,
    Part,
    Subject,
    Thread,
)
from .read import Reader, abouts, heads_holding, heads_of, labels as read_labels


def check_create(rows: Reader, digest: str) -> str:
    kind = rows.kind(digest)
    if kind is None:
        raise LookupError(f"{digest} is not in the store")
    if kind not in THREAD_KINDS:
        raise ValueError(f"{kind} components have no threads")
    return kind


def check_edit(
    rows: Reader,
    thread_id: int,
    digest: str,
    *,
    based_on: int | None = None,
    head: int | None = None,
    labels: Labels | None = None,
) -> None:
    found = thread(rows, thread_id)
    if head is not None and (current := history(rows, thread_id)[-1]).id != head:
        raise MovedOn.of(
            "thread %(thread)s has moved on since edit %(edit)s: its head is edit "
            + "%(head)s",
            thread=thread_id,
            edit=head,
            head=current.id,
        )
    if based_on is not None:
        _check_based_on(rows, found, based_on)
    _check_expectation(rows, found, digest)
    if labels:
        _check_labels(rows, found, digest, labels)


# Duplication: src/chatddx/store/migrations/0012-t2-catalog.sql repeats the language
# rule.
def check_note(rows: Reader, subject: Subject, entry: Entry) -> None:
    if entry.field == EntryField.LANGUAGE and subject.family is None:
        raise ValueError(
            "a language entry is for a family's vignette; "
            + "a component's language is kept on its digest"
        )
    if entry.field in RUN_FIELDS:
        _check_ran(rows, subject, entry)
    if subject.thread is not None and (found := rows.thread(subject.thread)):
        _check_expectation(rows, found, entry=entry)


# Duplication: src/chatddx/store/migrations/0012-t2-catalog.sql repeats this check.
def _check_based_on(rows: Reader, thread: Thread, based_on: int) -> None:
    origin = None if thread.forked_from is None else rows.edit(thread.forked_from)
    if origin is None or not any(
        e.id == based_on and e.id >= origin.id for e in rows.edits([origin.thread])
    ):
        raise ValueError(f"edit {based_on} is not in the origin of thread {thread.id}")


# Duplication: src/chatddx/store/migrations/0018-t2-catalog-label-edit.sql repeats the
# positions.
def _check_labels(rows: Reader, thread: Thread, digest: str, labels: Labels) -> None:
    if thread.kind != "scorer":
        raise ValueError(f"a {thread.kind} has no views or resources to label")
    scorer = resolve(rows.get, digest, Scorer)
    for (part, position), value in labels.items():
        parts = scorer.views if part == "view" else scorer.resources
        if not 0 <= position < len(parts):
            raise ValueError(f"{digest} has no {part} at position {position}")
        if not value and part == "view":
            raise Invalid.raw(
                "the label of view %(position)s is empty", position=position
            )
        if not value:
            raise Invalid.raw(
                "the label of resource %(position)s is empty", position=position
            )


# Duplication: src/chatddx/store/migrations/0026-t2-catalog-run-variation.sql repeats
# this check.
def _check_ran(rows: Reader, subject: Subject, entry: Entry) -> None:
    if subject.run is None:
        raise ValueError(f"a {entry.field} entry is about a run, and what it ran")
    if entry.field == EntryField.VARIED:
        found = rows.edit(int(entry.value or ""))
        if found is None or thread(rows, found.thread).kind != "skeleton":
            raise ValueError(f"edit {entry.value} is no configuration's")
        return
    # Scope: runs are the ledger's, which the catalog doesn't read: the store checks
    # this one.
    if entry.field == EntryField.WITH:
        return
    part, digest = (entry.value or "").split("=")
    model = part == "model"
    if digest and rows.kind(digest) not in (
        ("model.local", "model.remote") if model else (f"chunk.{part}",)
    ):
        what = "a model" if model else f"a chunk of {part}"
        raise ValueError(f"{digest} isn't {what} in the store")


def _check_expectation(
    rows: Reader, thread: Thread, digest: str | None = None, entry: Entry | None = None
) -> None:
    if thread.kind != "expectation":
        return
    if entry is not None and entry.field not in (EntryField.OWNER, EntryField.DELETED):
        return
    entries = [e for _, e, _ in rows.entries([Subject(thread=thread.id)])]
    about = About.of(entries if entry is None else [*entries, entry])
    owner = about.owner
    if owner is None or about.deleted:
        return
    expectation = resolve(rows.get, digest or head(rows, thread.id).digest, Expectation)
    case, schema = expectation.case, expectation.expectation_schema
    held = [
        e.thread for e, a in expecting(rows, [case], schema)[case] if owns(owner, a)
    ]
    if others := sorted(t for t in held if t != thread.id):
        raise Invalid.raw(
            "person %(owner)s owns an expectation of case %(case)s under that schema "
            + "already, in thread %(thread)s",
            owner=owner,
            case=case,
            thread=others[0],
        )


def thread(rows: Reader, id: int) -> Thread:
    found = rows.thread(id)
    if found is None:
        raise LookupError(f"no thread with id {id}")
    return found


def _edit(rows: Reader, id: int) -> Edit:
    found = rows.edit(id)
    if found is None:
        raise LookupError(f"no edit with id {id}")
    return found


def history(rows: Reader, thread: int) -> list[Edit]:
    edits = rows.edits([thread])
    if not edits:
        raise LookupError(f"no thread with id {thread}")
    return edits


def head(rows: Reader, thread: int) -> Edit:
    return history(rows, thread)[-1]


def versions(rows: Reader, thread: int) -> dict[int, int]:
    """Each edit of the thread by the version it holds, numbered by the first edit to
    hold the same, as `holds` has it, so that an earlier version brought back is that
    version again. Costs the thread's history and labels, and a recipe resolved for
    each compilation."""
    edits = history(rows, thread)
    labelled: dict[int, dict[tuple[Part, int], str]] = {e.id: {} for e in edits}
    for edit, part, position, value in rows.labels([e.id for e in edits]):
        labelled[edit][(part, position)] = value
    recipes: dict[str, Recipe | None] = {}
    held: list[tuple[str, Recipe | None, Labels]] = []
    numbered: dict[int, int] = {}
    for e in edits:
        if e.compilation is not None and e.compilation not in recipes:
            recipes[e.compilation] = recipe(rows, e)
        holding = (
            e.digest,
            None if e.compilation is None else recipes[e.compilation],
            labelled[e.id],
        )
        if holding not in held:
            held.append(holding)
        numbered[e.id] = held.index(holding) + 1
    return numbered


def heads(rows: Reader, kind: str) -> list[tuple[Edit, About]]:
    ids = [t.id for t in rows.threads(kind)]
    found = heads_of(rows, ids)
    known = abouts(rows, [Subject(thread=i) for i in ids])
    return [(found[i], known[Subject(thread=i)]) for i in ids if i in found]


def find(rows: Reader, kind: str, name: str, *, owner: int | None = None) -> list[int]:
    ids = [t.id for t in rows.threads(kind)]
    known = abouts(rows, [Subject(thread=i) for i in ids])
    return [
        i
        for i in ids
        if (a := known[Subject(thread=i)]).name == name
        and (not a.deleted if owner is None else owns(owner, a))
    ]


def picked(case: str, choices: Mapping[int, str]) -> str | None:
    match sorted(set(choices.values())):
        case []:
            return None
        case [digest]:
            return digest
        case _:
            raise Missing.of(
                "case %(case)s has expectations to choose from, in threads %(threads)s",
                case=case,
                threads=", ".join(str(t) for t in sorted(choices)),
            )


def expecting(
    rows: Reader, cases: Sequence[str], schema: str | None = None
) -> dict[str, list[tuple[Edit, About]]]:
    held = heads_holding(rows, rows.expectations(cases))
    known = abouts(rows, [Subject(thread=t) for t in held])
    read = dict(rows.components([e.digest for e in held.values()]))
    found: dict[str, list[tuple[Edit, About]]] = {c: [] for c in cases}
    for t in sorted(held):
        expectation = resolve(read.__getitem__, held[t].digest, Expectation)
        if schema is None or expectation.expectation_schema == schema:
            found[expectation.case].append((held[t], known[Subject(thread=t)]))
    return found


def forks(rows: Reader, thread: int) -> list[int]:
    edits = [e.id for e in rows.edits([thread])]
    return [t.id for t in rows.threads_forked_from(edits)]


def origin(rows: Reader, id: int) -> int | None:
    forked_from = thread(rows, id).forked_from
    return None if forked_from is None else _edit(rows, forked_from).thread


def recipe(rows: Reader, edit: Edit) -> Recipe | None:
    if edit.compilation is None:
        return None
    return resolve(rows.get, edit.compilation, Compilation).recipe


def holds(
    rows: Reader,
    edit: Edit,
    digest: str,
    compilation: str | None,
    labels: Labels | None = None,
) -> bool:
    if edit.digest != digest:
        return False
    if labels is not None and read_labels(rows, edit.id) != dict(labels):
        return False
    if compilation is None or compilation == edit.compilation:
        return True
    return recipe(rows, edit) == resolve(rows.get, compilation, Compilation).recipe


def behind(rows: Reader, thread: int) -> list[Behind]:
    current = head(rows, thread)
    refs = [(s.path, s.digest) for s in rows.get(current.digest).refs()]
    made = None
    if current.compilation is not None:
        made = resolve(rows.get, current.compilation, Compilation)
        refs += [(s.path, s.digest) for s in iter_refs(made.recipe, "/recipe")]
        if made.facts is not None:
            refs.append(("/facts", made.facts))
    refs += [
        (path + s.path, s.digest)
        for path, digest in refs
        if rows.kind(digest) == "case"
        for s in rows.get(digest).refs()
    ]
    held: dict[str, set[int]] = {}
    for e in rows.edits_holding({d for _, d in refs}):
        held.setdefault(e.digest, set()).add(e.thread)
    threads = {t for ts in held.values() for t in ts}
    found = heads_of(rows, threads)
    known = abouts(rows, [Subject(thread=t) for t in threads])
    moved = {
        (path, t, digest): Behind(path=path, digest=digest, head=found[t])
        for path, digest in refs
        for t in held.get(digest, ())
        if found[t].digest != digest
        and not known[Subject(thread=t)].deleted
        and (path != "/facts" or made is None or _sends_else(rows, made, found[t]))
    }
    ordered = [moved[k] for k in sorted(moved)]
    return sorted([*ordered, *stale_cases(rows, refs)], key=lambda b: b.path)


# Policy: facts corrected where a configuration doesn't reach leave it as it is:
# updating to them would write nothing (holds).
def _sends_else(rows: Reader, made: Compilation, facts: Edit) -> bool:
    newer = resolve(rows.get, facts.digest, ModelFacts)
    try:
        return compile_request(made.recipe, rows.get, newer).digest != made.skeleton
    except ValueError:
        return True


def divergence(rows: Reader, id: int) -> Divergence | None:
    forked_from = thread(rows, id).forked_from
    if forked_from is None:
        return None
    edits = history(rows, id)
    based_on = [e.based_on for e in edits if e.based_on is not None]
    base = _edit(rows, based_on[-1] if based_on else forked_from)
    fork = edits[-1]
    by_recipe = base.compilation is not None and fork.compilation is not None
    before, after = _shape(rows, base, by_recipe), _shape(rows, fork, by_recipe)
    origin = head(rows, base.thread)
    shaped = origin.id != base.id and (not by_recipe or origin.compilation is not None)
    return Divergence(
        base=base,
        origin_head=origin,
        varies=_changes(before, after),
        moves=_changes(before, _shape(rows, origin, by_recipe)) if shaped else {},
    )


def _changes(
    before: Mapping[str, JsonValue], after: Mapping[str, JsonValue]
) -> dict[str, tuple[JsonValue, JsonValue]]:
    return {
        path: (before.get(path), after.get(path))
        for path in sorted(before.keys() | after.keys())
        if before.get(path) != after.get(path)
    }


def proposal(rows: Reader, id: int) -> Recipe | Component | None:
    diverged = divergence(rows, id)
    if diverged is None or not diverged.moved:
        return None
    fork = head(rows, id)
    if diverged.base.compilation is not None and fork.compilation is not None:
        origin = recipe(rows, diverged.origin_head)
        if origin is None:
            return None
        changes = {
            path.removeprefix("/recipe/"): after
            for path, (_, after) in diverged.varies.items()
        }
        return Recipe.model_validate({**origin.model_dump(mode="json"), **changes})
    doc = rows.get(diverged.origin_head.digest).canonical_doc()
    for path, (_, after) in diverged.varies.items():
        if after is None:
            _ = doc.pop(path[1:], None)
        else:
            doc[path[1:]] = after
    return parse_component(canonical_bytes(doc))


def _shape(rows: Reader, edit: Edit, by_recipe: bool) -> dict[str, JsonValue]:
    if by_recipe:
        r = recipe(rows, edit)
        assert r is not None
        return {f"/recipe/{k}": v for k, v in r.model_dump(mode="json").items()}
    doc = rows.get(edit.digest).canonical_doc()
    return {f"/{k}": v for k, v in doc.items() if k not in ("kind", "v")}
