from functools import partial

from chatddx.catalog import LANGUAGE_KINDS, Labels, Subject, families, read, threads
from chatddx.catalog.language import language_of, languages_of, recipe_language
from chatddx.factors.base import Component, Finding, Invalid, Param, Worded, resolve
from chatddx.factors.bundle import Registry
from chatddx.factors.cases import Appendix, Case
from chatddx.factors.facts import ModelFacts
from chatddx.factors.request import RECIPE_PARTS, Recipe, Skeleton, translated
from chatddx.factors.scoring import Expectation, Judge, Scorer
from chatddx.factors.select import field
from chatddx.factors.trial import Trial, replicates
from chatddx.facts import lints
from chatddx.identity import owns, sees
from chatddx.scorers.shipped import refused

from .configurations import kept
from .errors import NotFound
from .model import COMPILED_LANGUAGE, KINDS, SAVED, WRITTEN, Checked, Written
from .seen import (
    Seen,
    add_compilations,
    check_expecting,
    check_kind,
    check_scorer,
    compiled,
    judging,
    linted,
    worded,
)
from .variation import TriedVariation

_UNLABELLED = "only a scorer's views and resources have labels"


def check(seen: Seen, component: Component | Recipe) -> Checked:
    engines: dict[str, str] = {}
    unreadable: list[Finding] = []
    match component:
        case Recipe():
            _stored_parts(seen, component)
            registry, compilation = compiled(seen, component)
            digest = compilation.skeleton
        case _ if component.kind_name not in WRITTEN:
            raise ValueError(f"a person doesn't write {component.kind_name} components")
        case Scorer():
            check_scorer(component)
            registry, digest = _registered(seen, component)
        case Appendix():
            registry, digest = _registered(seen, bound(seen, component))
        case Expectation():
            registry, digest = _registered(seen, component)
            unreadable = _unreadable(seen, component)
        case Judge():
            registry, digest = _registered(seen, component)
            add_compilations(seen, registry, component.skeleton)
            engines = judging(seen, component, registry)
        case Trial():
            held, registry, _ = _carried(seen, component)
            digest = registry.add(held)
            add_compilations(seen, registry, held.skeleton)
        case _:
            registry, digest = _registered(seen, component)
    languages = partial(language_of, seen.rows)
    findings = lints(registry, seen.facts, [digest], languages, engines)
    return Checked(digest, [*unreadable, *findings])


# Policy: an expectation is refused when a scorer under its schema can't read it, as what
# a scorer reads, such as a pattern, is the scorer's to say and not the schema's; checked,
# it is a finding by the field the view reads, so that it can be shown by it.
def _unreadable(seen: Seen, expectation: Expectation) -> list[Finding]:
    found: dict[tuple[str | None, str], Finding] = {}
    for _, _, scorer in seen.scorers():
        if scorer.expectation_schema != expectation.expectation_schema:
            continue
        for selector, e in refused(scorer, expectation.data):
            at = field(selector)
            params: dict[str, Param] = dict(e.params) if isinstance(e, Worded) else {}
            if at is not None:
                params["field"] = at
            made = Finding(
                code="expectation.unreadable",
                message=str(e),
                subject=expectation.digest,
                wording=e.wording if isinstance(e, Worded) else None,
                params=params,
            )
            _ = found.setdefault((at, made.message), made)
    return list(found.values())


def _readable(seen: Seen, expectation: Expectation) -> None:
    for _, _, scorer in seen.scorers():
        if scorer.expectation_schema != expectation.expectation_schema:
            continue
        for _, e in refused(scorer, expectation.data):
            raise e


def _registered(seen: Seen, component: Component) -> tuple[Registry, str]:
    registry = seen.store.load(s.digest for s in component.refs())
    _ = registry.add(component)
    registry.check(registry.closure([component.digest]))
    return registry, component.digest


def new(
    seen: Seen,
    component: Component | Recipe,
    name: str | None,
    language: str | None = None,
    labels: Labels | None = None,
) -> Written:
    if name is None and not isinstance(component, Expectation):
        raise ValueError(
            "only an expectation goes unnamed: the case it is for says which it is"
        )
    match component:
        case Recipe():
            _configured(language, labels)
            _stored_parts(seen, component)
            registry, compilation = compiled(seen, component)
            with seen.conn.transaction():
                _ = seen.store.add(registry, [compilation.digest])
                edit = seen.catalog.create(
                    compilation.skeleton,
                    seen.person.id,
                    compilation=compilation.digest,
                    name=name,
                )
            return Written(edit, "created", linted(seen, compilation.skeleton))
        case _:
            return _written(
                seen, component, None, name=name, language=language, labels=labels
            )


def _stored_parts(seen: Seen, recipe: Recipe) -> None:
    for part in RECIPE_PARTS:
        digest = getattr(recipe, part)
        if digest is not None and seen.rows.kind(digest) not in KINDS[part]:
            what = "model" if part == "model" else f"chunk of {part}"
            raise ValueError(f"{digest} isn't a stored {what}")


def fork(
    seen: Seen,
    thread: int,
    name: str,
    held: Component | TriedVariation | None = None,
    language: str | None = None,
    labels: Labels | None = None,
) -> Written:
    edit, _, word = worded(seen, thread)
    if held is None:
        held = (
            seen.variation(thread)
            if word == "configuration"
            else seen.store.get(edit.digest)
        )
    check_kind(seen, thread, word, held)
    if isinstance(held, TriedVariation):
        if held.configuration.thread != thread:
            raise ValueError(
                f"{held.label} isn't a variation of configuration {thread}"
            )
        _configured(language, labels)
        return kept(seen, held, None, name)
    if labels is None and isinstance(held, Scorer) and held.digest == edit.digest:
        labels = read.labels(seen.rows, edit.id)
    return _written(
        seen,
        held,
        None,
        name=name,
        language=language,
        forked_from=edit.id,
        labels=labels,
    )


def edit(
    seen: Seen,
    thread: int,
    head: int,
    held: Component | TriedVariation,
    language: str | None = None,
    labels: Labels | None = None,
) -> Written:
    _, about, word = worded(seen, thread)
    if not owns(seen.person.id, about):
        raise NotFound(f"no {word} {thread} of yours")
    check_kind(seen, thread, word, held)
    if isinstance(held, TriedVariation):
        _configured(language, labels)
        return kept(seen, held, thread, None, head)
    return _written(seen, held, thread, language=language, head=head, labels=labels)


def _configured(language: str | None, labels: Labels | None) -> None:
    if language is not None:
        raise ValueError(COMPILED_LANGUAGE)
    if labels is not None:
        raise ValueError(_UNLABELLED)


def _written(
    seen: Seen,
    component: Component,
    thread: int | None,
    *,
    name: str | None = None,
    language: str | None = None,
    forked_from: int | None = None,
    head: int | None = None,
    labels: Labels | None = None,
) -> Written:
    kind = component.kind_name
    if kind not in WRITTEN:
        raise ValueError(f"a person doesn't write {kind} components")
    if language is not None and kind not in LANGUAGE_KINDS:
        raise ValueError(f"{kind} components have no language of their own")
    if labels is not None and not isinstance(component, Scorer):
        raise ValueError(_UNLABELLED)
    if isinstance(component, Scorer):
        check_scorer(component)
    old = None if thread is None else threads.head(seen.rows, thread).digest
    if isinstance(component, Expectation):
        _readable(seen, component)
        if old is not None:
            _check_family(seen, resolve(seen.store.get, old, Expectation), component)
        check_expecting(seen, component, thread)
    if isinstance(component, Appendix):
        component = bound(seen, component)
    compilations: list[str] = []
    if isinstance(component, Trial):
        component, registry, compilations = _carried(seen, component)
    else:
        registry = seen.store.load(s.digest for s in component.refs())
    _ = registry.add(component)
    with seen.conn.transaction():
        _ = seen.store.add(registry, [component.digest, *compilations])
        if language is not None:
            keep_language(seen, component.digest, language)
        edit, kept = seen.catalog.keep(
            component.digest,
            seen.person.id,
            thread,
            name=name,
            forked_from=forked_from,
            head=head,
            labels=labels,
        )
        replaced = (
            _replaced(seen, old, component)
            if isinstance(component, Appendix) and old and kept == "edited"
            else {}
        )
    return Written(edit, SAVED[kept], linted(seen, component.digest), replaced)


def _carried(seen: Seen, trial: Trial) -> tuple[Trial, Registry, list[str]]:
    seen_cases = {c for f in seen.families() for c in f.cases}
    if missing := [c for c in trial.cases if c not in seen_cases]:
        raise NotFound(f"no case {missing[0]} for {seen.person.login}")
    skeleton = resolve(seen.store.get, trial.skeleton, Skeleton)
    if (seeds := replicates(skeleton, trial.seeds)) != trial.seeds:
        trial = trial.model_copy(update={"seeds": seeds})
    held = languages_of(seen.rows, [*trial.cases, trial.skeleton])
    known = sorted(set(filter(None, (held[c] for c in trial.cases))))
    if len(known) > 1:
        raise Invalid.of(
            "a trial's cases are in one language, not in %(languages)s",
            languages=", ".join(known),
        )
    made = seen.rows.compilations(trial.skeleton)
    recipe = made[0].recipe if made else None
    own = held[trial.skeleton] if recipe is None else recipe_language(seen.rows, recipe)
    into = None if not known or known[0] == own else known[0]
    if into is not None and (
        recipe is None or into not in translated(recipe, seen.store.get)
    ):
        if own is not None:
            raise Invalid.of(
                "%(name)s has no translation into %(languages)s",
                name=seen.title(trial.skeleton),
                languages=into,
            )
        # Policy: as a start does, a skeleton of no language of its own is sent as
        # written into a language its translations don't go into.
        into = None
    if recipe is None or any(m.into == into for m in made):
        return trial, seen.store.load(s.digest for s in trial.refs()), []
    pinned = made[0].facts
    facts = None if pinned is None else resolve(seen.store.get, pinned, ModelFacts)
    registry, compilation = compiled(seen, recipe, facts, into)
    loaded = seen.store.load([trial.engine, *trial.cases])
    for digest in loaded:
        _ = registry.add(loaded.get(digest))
    carried = Trial(
        skeleton=compilation.skeleton,
        engine=trial.engine,
        cases=trial.cases,
        cleanup=trial.cleanup,
        seeds=trial.seeds,
    )
    return carried, registry, [compilation.digest]


def _check_family(seen: Seen, old: Expectation, new: Expectation) -> None:
    if new.case == old.case:
        return
    family = families.family_of(seen.rows, old.case)
    if family is None or families.family_of(seen.rows, new.case) != family:
        raise ValueError(f"{new.case} isn't a case of the family {old.case} is of")


def bound(seen: Seen, appendix: Appendix) -> Appendix:
    vignette = appendix.vignette
    held = {b.family for b in seen.rows.bindings_sharing(vignette)}
    if not any(
        seen.rows.bindings([f])[-1].vignette == vignette
        and sees(seen.person.id, read.about(seen.rows, Subject(family=f)))
        for f in held
    ):
        raise ValueError(
            "an appendix is bound to the current vignette of a case you see"
        )
    text = appendix.text.replace("\r\n", "\n").replace("\r", "\n")
    return Appendix(vignette=vignette, text=text)


def _replaced(seen: Seen, old: str, new: Appendix) -> dict[str, str]:
    replaced: dict[str, str] = {}
    for digest in seen.store.reaching(old, "case"):
        case = resolve(seen.store.get, digest, Case)
        if case.vignette != new.vignette:
            continue
        held = tuple(new.digest if a == old else a for a in case.appendices)
        made = Case(vignette=case.vignette, appendices=held)
        registry = seen.store.load(held)
        _ = seen.store.add(registry, [registry.add(made)])
        replaced[digest] = made.digest
    return replaced


def keep_language(seen: Seen, digest: str, language: str) -> None:
    held = language_of(seen.rows, digest)
    if held is not None and held != language:
        raise Invalid.of(
            "%(text)s is in %(held)s already: a text's language is the same wherever "
            + "it is held",
            text=seen.title(digest),
            held=held,
        )
    if held is None:
        seen.catalog.language(digest, language, seen.person.id)
