import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from functools import partial
from typing import Literal, get_args
from uuid import UUID

from pydantic import JsonValue

from chatddx.catalog import About, Edit, Subject, read, threads, titles
from chatddx.catalog.language import language_of, languages_of, recipe_language
from chatddx.catalog.titles import CaseTitle, display_digest
from chatddx.factors.base import (
    Component,
    Finding,
    Invalid,
    StructuralError,
    Worded,
    iter_refs,
    resolve,
)
from chatddx.factors.bundle import Registry
from chatddx.factors.cases import Appendix, Case, CleanupOp, Vignette
from chatddx.factors.engine import Model, model_of, served_model_name
from chatddx.factors.facts import Landing, ModelFacts
from chatddx.factors.request import (
    RECIPE_PARTS,
    Compilation,
    Output,
    Purpose,
    Recipe,
    Skeleton,
    compile_request,
    compiled as compile_recipe,
    landings,
    translated,
)
from chatddx.factors.scoring import Expectation, Judge, JudgeEngine, Scorer, Scoring
from chatddx.factors.trial import Trial, replicates
from chatddx.facts import Facts, lints
from chatddx.identity import Person, collaborates, owns, preferred, sees
from chatddx.inventory import Inventory
from chatddx.ledger import ItemKey, RunStarted, ScoreStarted
from chatddx.rig import rig
from chatddx.runner import STOPPED, Refused, judge_at
from chatddx.scorers.shipped import problems, read_by
from chatddx.store import Catalog, People, Rows, Store
from chatddx.store.store import Connection
from chatddx.whoops import Whoops

from .errors import Ambiguous, NotFound
from .model import (
    KINDS,
    MODEL,
    PLACEHOLDERS,
    Carried,
    Endpoint,
    Family,
    Graded,
    Handle,
    Reach,
    Replaced,
    Titled,
    word_of,
)
from .variation import TriedVariation

# Dependency: a case's title, as src/chatddx/catalog/titles.py:_describe_case writes it.
WITH = re.compile(r"^(?P<family>.+?) with (?P<appendices>.+)$")

NONE = "none"

_ALL_KINDS = tuple(kind for held in KINDS.values() for kind in held)


class Seen:
    def __init__(self, conn: Connection, person: Person, inventory: Inventory) -> None:
        self.conn: Connection = conn
        self.person: Person = person
        self.inventory: Inventory = inventory
        self.store: Store = Store(conn)
        self.catalog: Catalog = Catalog(conn)
        self.rows: Rows = Rows(conn)
        self.people: People = People(conn)
        self._logins: dict[int, str] = {}
        self._models: dict[str, Model] = {}
        self._handles: dict[str, Handle] = {}

    def login(self, person: int | None) -> str:
        if person is None:
            return "nobody"
        if person not in self._logins:
            self._logins[person] = self.people.get(person).login
        return self._logins[person]

    # Policy: read when asked, so that facts corrected while a connection lasts are
    # used.
    @property
    def facts(self) -> Facts:
        live = [(e, a) for e, a in threads.heads(self.rows, "facts") if not a.deleted]
        fetched = dict(self.rows.components([e.digest for e, _ in live]))
        return Facts.of(
            resolve(fetched.__getitem__, e.digest, ModelFacts)
            for e, _ in sorted(live, key=lambda found: found[0].id)
        )

    def threads(
        self,
        word: str,
        *,
        deleted: bool = False,
        purpose: Purpose | None = None,
        answering: str | None = None,
    ) -> list[tuple[Edit, About]]:
        found = [f for kind in KINDS[word] for f in self._visible(kind, deleted)]
        if purpose is None and answering is None:
            return found
        if word != "configuration":
            raise ValueError(
                f"only a configuration has a purpose and an answer: {word}"
            )
        fetched = dict(self.rows.components([e.digest for e, _ in found]))
        held = {
            e.digest: resolve(fetched.__getitem__, e.digest, Skeleton) for e, _ in found
        }
        return [
            (e, a)
            for e, a in found
            if (purpose is None or held[e.digest].purpose == purpose)
            and (
                answering is None or _titled(held[e.digest].output_schema) == answering
            )
        ]

    def _visible(self, kind: str, deleted: bool = False) -> list[tuple[Edit, About]]:
        return [
            (e, a)
            for e, a in threads.heads(self.rows, kind)
            if (
                a.deleted and a.owner == self.person.id
                if deleted
                else sees(self.person.id, a)
            )
        ]

    def thread(
        self, found: int | str, word: str | None = None, *, deleted: bool = False
    ) -> tuple[Edit, About]:
        if isinstance(found, str):
            return self._named_thread(found, word)
        about = read.about(self.rows, Subject(thread=found))
        held = self.rows.thread(found)
        seen = sees(self.person.id, about) or (
            deleted and about.deleted and about.owner == self.person.id
        )
        if (
            held is None
            or not seen
            or (word is not None and held.kind not in KINDS[word])
        ):
            raise NotFound(f"no {word or 'thread'} {found} for {self.person.login}")
        return threads.head(self.rows, found), about

    def _named_thread(self, name: str, word: str | None) -> tuple[Edit, About]:
        kinds = KINDS[word] if word is not None else _ALL_KINDS
        what = word or "thread"
        seen = {kind: self._visible(kind) for kind in kinds}
        addresses = {
            kind: {
                address
                for _, a in found
                for address in (a.name, self._qualified(a.name, a.owner))
                if address is not None
            }
            for kind, found in seen.items()
        }
        match [kind for kind, held in addresses.items() if name in held]:
            case [kind]:
                return self._named(
                    [((e, a), a.name, a) for e, a in seen[kind]], name, what
                )
            case []:
                raise NotFound(f"no {what} {name!r} for {self.person.login}")
            case several:
                raise Ambiguous(f"{what} {name!r} names a {' and a '.join(several)}")

    def _qualified(self, name: str | None, owner: int | None) -> str | None:
        if name is None or owner is None:
            return None
        return f"{self.login(owner)}/{name}"

    def _named[T](
        self, seen: list[tuple[T, str | None, About]], name: str, word: str
    ) -> T:
        called = [(found, a.owner) for found, n, a in seen if n == name] or [
            (found, a.owner)
            for found, n, a in seen
            if self._qualified(n, a.owner) == name
        ]
        match preferred(self.person.id, called):
            case [one]:
                return one
            case []:
                raise NotFound(f"no {word} {name!r} for {self.person.login}")
            case several:
                raise Ambiguous(
                    f"{word} {name!r} names {len(several)}; name one as OWNER/NAME"
                )

    def holder(
        self, digest: str, recipe: Recipe | None = None
    ) -> tuple[Edit, About] | None:
        held = [
            (found, owner)
            for found, owner in self._held(digest)
            if recipe is None or threads.recipe(self.rows, found[0]) == recipe
        ]
        return next(iter(preferred(self.person.id, held)), None)

    def title(self, digest: str) -> str:
        named = [(a.name, o) for (_, a), o in self._held(digest) if a.name is not None]
        found = next(iter(preferred(self.person.id, named)), None)
        return titles.title_of(self.rows, digest) if found is None else found

    def _held(self, digest: str) -> list[tuple[tuple[Edit, About], int | None]]:
        held = read.heads_holding(self.rows, [digest])
        known = read.abouts(self.rows, [Subject(thread=t) for t in held])
        return [
            ((e, a), a.owner)
            for t, e in held.items()
            if sees(self.person.id, a := known[Subject(thread=t)])
        ]

    def endpoint(self, name: str) -> Endpoint:
        try:
            spec = self.inventory.endpoint(name)
        except LookupError as e:
            raise NotFound(str(e)) from None
        model = self._model_of(spec.engine)
        if model is None:
            raise NotFound(
                f"endpoint {name!r} serves engine {display_digest(spec.engine)}, which isn't in "
                + "the store: load its World with sync-archive"
            )
        return Endpoint(name, spec, model)

    def _model_of(self, engine: str) -> Model | None:
        if engine not in self._models:
            if self.rows.kind(engine) is None:
                return None
            self._models[engine] = model_of(engine, self.store.get)
        return self._models[engine]

    def _served_model(self, engine: str) -> str | None:
        model = self._model_of(engine)
        return None if model is None else model.digest

    def handle(self, weights: str) -> Handle:
        if weights not in self._handles:
            held = sorted({e.thread for e in self.rows.edits_holding([weights])})
            if not held:
                raise Whoops(
                    "The model has no handle and can't be used.",
                    pass_on=f"{display_digest(weights)} is held by no model thread: check the "
                    + "RuntimeErrors",
                )
            if len(held) > 1:
                raise RuntimeError(
                    f"{display_digest(weights)} is held by {len(held)} model threads, not one: "
                    + "fix boot-check src/chatddx/bench/handles.py:broken"
                )
            about = read.about(self.rows, Subject(thread=held[0]))
            head = read.heads_of(self.rows, held)[held[0]]
            name = about.name or str(held[0])
            self._handles[weights] = Handle(name, held[0], head.digest, about.deleted)
        return self._handles[weights]

    def handle_named(self, name: str) -> Handle:
        edit, about = self.thread(name, "model")
        return Handle(about.name or name, edit.thread, edit.digest)

    def handles(self) -> list[tuple[Handle, Endpoint | None]]:
        found: list[tuple[Handle, Endpoint | None]] = []
        for edit, about in self.threads("model"):
            handle = Handle(about.name or str(edit.thread), edit.thread, edit.digest)
            try:
                found.append((handle, self.served(handle)))
            except ValueError:
                found.append((handle, None))
        return sorted(found, key=lambda f: f[0].name)

    def served(self, handle: Handle) -> Endpoint:
        if handle.deleted:
            raise Invalid.of(
                "model %(model)s is deleted: pick another", model=handle.name
            )
        # Policy: Several endpoints serving it are ruled out as a process starts
        # (src/chatddx/inventory/check.py:broken), so none does.
        try:
            name = self.inventory.serving(handle.weights, self._served_model)
        except LookupError:
            raise Invalid.of(
                "no endpoint here serves model %(model)s: pick another",
                model=handle.name,
            ) from None
        return self.endpoint(name)

    def latest(self, handle: Handle) -> str | None:
        try:
            return self.served(handle).engine
        except ValueError:
            return None

    def judged(self, judge: Judge) -> Endpoint:
        handle = self.handle(judge.model)
        if handle.weights != judge.model:
            raise Invalid.of(
                "%(name)s is out of date: update it on its page",
                name=self.title(judge.digest),
            )
        return self.served(handle)

    def under(self, engine: str) -> tuple[Handle | None, bool]:
        weights = self._served_model(engine)
        if weights is None:
            return None, False
        handle = self.handle(weights)
        return handle, self.latest(handle) == engine

    # Policy: Only scripted runs name an endpoint; a researcher names a handle, and only
    # for a hand-written configuration.
    def at(
        self,
        variation: TriedVariation,
        endpoint: str | None = None,
        model: str | None = None,
    ) -> Endpoint:
        weights = variation.held("model")
        if endpoint is not None:
            found = self.endpoint(endpoint)
            if weights is not None and found.model.digest != weights:
                raise ValueError(
                    f"endpoint {endpoint!r} serves another model than "
                    + f"{variation.label}'s, {self.title(weights)}"
                )
            return found
        if weights is None:
            if model is None:
                raise Invalid.of(
                    "%(configuration)s names no model: name the one to run it under",
                    configuration=variation.label,
                )
            return self.served(self.handle_named(model))
        if model is not None:
            raise ValueError(
                f"{variation.label} runs under its model's handle: set its model instead"
            )
        handle = self.handle(weights)
        if handle.weights != weights:
            raise Invalid.of(
                "%(name)s is out of date: update it on its page",
                name=variation.label,
            )
        return self.served(handle)

    def variation(
        self,
        configuration: int | str,
        parts: Mapping[str, str | None] | None = None,
        head: int | None = None,
    ) -> TriedVariation:
        edit, about = self.thread(configuration, "configuration")
        if isinstance(configuration, str):
            name = configuration.removeprefix(f"{self.person.login}/")
        else:
            name = about.name or titles.title(self.rows, edit.thread)
        if head is not None and head != edit.id:
            earlier = self.rows.edit(head)
            if earlier is None or earlier.thread != edit.thread:
                raise NotFound(f"no edit {head} of configuration {edit.thread}")
            edit = earlier
        found = TriedVariation(edit, name, threads.recipe(self.rows, edit))
        for part, digest in (parts or {}).items():
            if part not in RECIPE_PARTS:
                raise ValueError(
                    f"no part {part!r}: the parts are {', '.join(RECIPE_PARTS)}"
                )
            if digest is not None and self.rows.kind(digest) not in KINDS[part]:
                what = "model" if part == "model" else f"chunk of {part}"
                raise ValueError(f"{digest} isn't a stored {what}")
            found = found.set(
                part, digest, NONE if digest is None else self.title(digest)
            )
        return found

    def skeleton(self, variation: TriedVariation, into: str | None = None) -> Skeleton:
        recipe = variation.varied
        if into is None and (not variation.parts or recipe is None):
            return resolve(self.store.get, variation.configuration.digest, Skeleton)
        if recipe is None:
            raise StructuralError.of(
                "%(name)s has no translation into %(languages)s",
                name=variation.label,
                languages=str(into),
            )
        registry = self.store.load(s.digest for s in iter_refs(recipe))
        return compile_request(
            recipe, registry.get, compiled_with(self, variation), into
        )

    def cleanup(self, cases: Sequence[str]) -> tuple[CleanupOp, ...]:
        if not any(s.cleanup for s in self.inventory.sources.values()):
            return ()
        registry = self.store.load(cases)
        asked = {
            op
            for case in cases
            for op in self.inventory.source(
                resolve(registry.get, case, Case).vignette.source
            ).cleanup
        }
        return tuple(op for op in get_args(CleanupOp) if op in asked)

    def landed(self, variation: TriedVariation) -> dict[str, Landing]:
        recipe = variation.varied
        if recipe is None:
            return {}
        registry = self.store.load(s.digest for s in iter_refs(recipe))
        found = landings(recipe, registry.get, compiled_with(self, variation))
        return {p: at for p, at in zip(("reasoning", "sampling"), found) if at}

    def languages(
        self, variation: TriedVariation, cases: Sequence[str]
    ) -> list[Carried]:
        recipe = variation.varied
        own = (
            language_of(self.rows, variation.configuration.digest)
            if recipe is None
            else recipe_language(self.rows, recipe)
        )
        held = self._languages_of(cases)
        into = [] if recipe is None else list(translated(recipe, self.store.get))

        def sent_in(language: str | None) -> str | None:
            if language is None or language == own:
                return None
            if language not in into and own is None:
                return None
            return language

        sent = {case: sent_in(held.get(case)) for case in cases}
        found: list[Carried] = []
        if written := [c for c in cases if sent[c] is None]:
            found.append(Carried(own, written, self.skeleton(variation)))
        for language in sorted({s for s in sent.values() if s is not None}):
            some = [c for c in cases if sent[c] == language]
            if language not in into:
                refused = f"{variation.label} has no translation into {language}"
                found.append(
                    Carried(language, some, refused=refused, untranslated=True)
                )
                continue
            try:
                skeleton = self.skeleton(variation, language)
            except StructuralError as e:
                found.append(Carried(language, some, refused=str(e)))
                continue
            found.append(Carried(language, some, skeleton, translated=True))
        return found

    # Optimization: Reusing families' language reduces query-load.
    def _languages_of(self, cases: Sequence[str]) -> dict[str, str | None]:
        known = {c: f.about.language for f in self.families() for c in f.cases}
        if rest := [c for c in cases if c not in known]:
            known |= languages_of(self.rows, rest)
        return {c: known[c] for c in cases}

    def request(
        self, variation: TriedVariation, engine: str | None, seed: int
    ) -> dict[str, JsonValue]:
        model = MODEL if engine is None else served_model_name(engine, self.store.get)
        return self.skeleton(variation).render(
            model=model, seed=seed, fills=PLACEHOLDERS
        )

    def findings(
        self,
        variation: TriedVariation,
        engine: str,
        seed: int,
        carried: Sequence[Carried] | None = None,
    ) -> list[Finding]:
        skeleton = self.skeleton(variation)
        by_hand = variation.recipe is None
        if skeleton.purpose == "judge":
            registry = self.store.load([engine, *(s.digest for s in skeleton.refs())])
            _ = registry.add(skeleton)
            if by_hand:
                add_compilations(self, registry, skeleton.digest)
            model = model_of(engine, registry.get).digest
            judge = Judge(skeleton=skeleton.digest, model=model, seeds=(seed,))
            _ = registry.add(judge)
            at = {judge.digest: engine}
            return lints(registry, self.facts, [judge.digest], engines=at)
        if carried is None:
            first = next(iter(self.families()), None)
            if first is None:
                return missing(self, variation, ())
            registry, made = trial(self, skeleton, engine, [first.case], (seed,))
            if by_hand:
                add_compilations(self, registry, skeleton.digest)
            found = lints(registry, self.facts, [made.digest])
            return found + missing(self, variation, ())
        known = self._languages_of([c for each in carried for c in each.cases])
        found: list[Finding] = []
        said: set[Finding] = set()
        for each in carried:
            if each.skeleton is None:
                continue
            registry, made = trial(self, each.skeleton, engine, each.cases, (seed,))
            if by_hand:
                add_compilations(self, registry, each.skeleton.digest)
            languages = partial(
                _language_in,
                {**known, made.skeleton: each.language},
                partial(language_of, self.rows),
            )
            # Policy: each language's trial is a subject of its own, but a finding that
            # is the same in two is said once.
            for finding in lints(registry, self.facts, [made.digest], languages):
                if (
                    unsubjected := finding.model_copy(update={"subject": None})
                ) not in said:
                    said.add(unsubjected)
                    found.append(finding)
        return found + missing(self, variation, carried)

    # Accommodating for a discovered fact: a schema's title is translated with its
    # other texts.
    def answers(self, skeleton: Skeleton) -> str | None:
        for compilation in self.store.compilations(skeleton.digest):
            if compilation.into is not None:
                output = resolve(self.store.get, compilation.recipe.output, Output)
                return _titled(output.json_schema)
        return _titled(skeleton.output_schema)

    def reach(self, variation: TriedVariation, families: list[Family]) -> list[Reach]:
        skeleton = self.skeleton(variation)
        if skeleton.purpose == "judge":
            return []
        schema = skeleton.output_schema
        cases = [f.case for f in families]
        data: dict[str, tuple[dict[str, JsonValue], set[str]]] = {}
        found: list[Reach] = []
        named = [
            (e, a.name or titles.title(self.rows, e.thread), s)
            for e, a, s in self.scorers()
        ]
        for edit, name, scorer in sorted(named, key=lambda s: s[1]):
            labels = labels_of(self, edit)
            expected = scorer.expectation_schema
            for i, view in enumerate(scorer.views):
                offered = view.offered_by(schema)
                if offered and expected not in data:
                    data[expected] = self._expected(cases, expected)
                held, several = data.get(expected, ({}, set[str]()))
                choosing = [f for f in families if offered and f.case in several]
                missing = [
                    f
                    for f in families
                    if offered and f.case not in several
                    if (x := held.get(f.case)) is None or not view.expectation_items(x)
                ]
                label = labels.get(i, f"view {i}")
                found.append(
                    Reach(
                        edit.thread,
                        name,
                        i,
                        label,
                        offered,
                        len(families),
                        missing,
                        choosing,
                    )
                )
        return found

    def _expected(
        self, cases: list[str], schema: str
    ) -> tuple[dict[str, JsonValue], set[str]]:
        heads: dict[str, str] = {}
        several: set[str] = set()
        for case, held in choices(self, cases, schema).items():
            try:
                digest = threads.picked(case, held)
            except LookupError:
                several.add(case)
                continue
            if digest is not None:
                heads[case] = digest
        fetched = dict(self.rows.components(list(heads.values())))
        data = {
            c: resolve(fetched.__getitem__, d, Expectation).data
            for c, d in heads.items()
        }
        return data, several

    def families(
        self, tags: Iterable[str] = (), *, deleted: bool = False
    ) -> list[Family]:
        wanted = set(tags)
        tagged = [
            (f, a) for f, a in self._families(deleted) if not wanted or wanted & a.tags
        ]
        held = self._cases([f for f, _ in tagged])
        found = [Family(f, a, *held[f]) for f, a in tagged if f in held]
        return sorted(found, key=lambda f: f.name)

    def _families(self, deleted: bool = False) -> list[tuple[int, About]]:
        ids = self.rows.families()
        known = read.abouts(self.rows, [Subject(family=f) for f in ids])
        found = [(f, known[Subject(family=f)]) for f in ids]
        if deleted:
            return [(f, a) for f, a in found if a.deleted and a.owner == self.person.id]
        return [(f, a) for f, a in found if sees(self.person.id, a)]

    def _cases(
        self, families: list[int]
    ) -> dict[int, tuple[Vignette, tuple[str, ...]]]:
        current = {b.family: b.vignette for b in self.rows.bindings(families)}
        held: dict[Vignette, list[str]] = {}
        for digest, vignette in self.rows.bound_to(current.values(), "case"):
            held.setdefault(vignette, []).append(digest)
        found: dict[int, tuple[Vignette, tuple[str, ...]]] = {}
        for family, vignette in current.items():
            bare = Case(vignette=vignette).digest
            cases = sorted(held.get(vignette, []), key=lambda d: (d != bare, d))
            if cases:
                found[family] = (vignette, tuple(cases))
        return found

    def family(self, found: int | str, *, deleted: bool = False) -> Family:
        if isinstance(found, str):
            return self._named(
                [(f, f.name, f.about) for f in self.families()], found, "case"
            )
        about = read.about(self.rows, Subject(family=found))
        seen = sees(self.person.id, about) or (
            deleted and about.deleted and about.owner == self.person.id
        )
        held = self._cases([found]).get(found) if seen else None
        if held is None:
            raise NotFound(f"no case {found} for {self.person.login}")
        return Family(found, about, *held)

    def case_titled(self, title: str) -> tuple[Family, str]:
        found = WITH.match(title)
        if found is None:
            family = self.family(title)
            return family, family.case
        family = self.family(found["family"])
        names = [name.strip() for name in found["appendices"].split(",")]
        held = {
            about.name: edit.digest
            for edit, about in self._visible("appendix")
            if about.name is not None
            and resolve(self.store.get, edit.digest, Appendix).vignette
            == family.vignette
        }
        if missing := [name for name in names if name not in held]:
            raise NotFound(f"no appendix {', '.join(missing)} of {family.name}")
        appendices = tuple(held[n] for n in names)
        made = Case(vignette=family.vignette, appendices=appendices).digest
        if made not in family.cases:
            raise NotFound(f"no case {title} for {self.person.login}")
        return family, made

    def expectation_schemas(self, case: str) -> list[str]:
        heads = [
            e.digest
            for e, a in threads.expecting(self.rows, [case])[case]
            if sees(self.person.id, a)
        ]
        held = (resolve(self.store.get, d, Expectation) for d in heads)
        return sorted({e.expectation_schema for e in held})

    def expectation(self, case: str, schema: str) -> Expectation | None:
        digest = picked(self, [case], schema)[case]
        return None if digest is None else resolve(self.store.get, digest, Expectation)

    def shared(self, case: str, schema: str) -> list[tuple[Edit, About]]:
        held = threads.expecting(self.rows, [case], schema)[case]
        return [(e, a) for e, a in held if collaborates(self.person.id, a)]

    def scorers(
        self, run: RunStarted | None = None
    ) -> list[tuple[Edit, About, Scorer]]:
        found = [
            (e, a, resolve(self.store.get, e.digest, Scorer))
            for e, a in self.threads("scorer")
        ]
        if run is None:
            return found
        trial = resolve(self.store.get, run.trial, Trial)
        schema = resolve(self.store.get, trial.skeleton, Skeleton).output_schema
        return [s for s in found if self._applies(s[2], trial, schema)]

    # Policy: A judge behind its handle still applies, so that its scorer stays left to
    # score and scoring says why.
    def _applies(self, scorer: Scorer, trial: Trial, schema: JsonValue) -> bool:
        if not all(v.offered_by(schema) for v in scorer.views):
            return False
        try:
            for judge in scorer.judges:
                weights = resolve(self.store.get, judge, Judge).model
                engine = self.served(self.handle(weights)).engine
                _ = judge_at(self.inventory, self.store.get, trial, judge, engine)
        except (ValueError, Refused):
            return False
        return True

    def labels(self, scorer: str) -> dict[int, str]:
        held = self.holder(scorer)
        if held is not None:
            return labels_of(self, held[0])
        seen = {e.thread: a.owner for e, a in self.threads("scorer")}
        earlier = [
            (e, seen[e.thread])
            for e in self.rows.edits_holding([scorer])
            if e.thread in seen
        ]
        held_before = sorted(preferred(self.person.id, earlier), key=lambda e: e.id)
        return labels_of(self, held_before[-1]) if held_before else {}

    def runs(
        self,
        *,
        reaching: str | None = None,
        scored_by: str | None = None,
        started_with: UUID | None = None,
    ) -> list[RunStarted]:
        involved = [s for s in self.rows.involving(self.person.id) if s.run]
        known = read.abouts(self.rows, involved)
        found = self.store.started(
            [
                s.run
                for s in involved
                if s.run is not None and owns(self.person.id, known[s])
            ]
        )
        if reaching is not None:
            trials = set(self.store.reaching(reaching, "trial"))
            for made in self.store.reaching(reaching, "compilation"):
                skeleton = resolve(self.store.get, made, Compilation).skeleton
                trials.update(self.store.reaching(skeleton, "trial"))
            found = [r for r in found if r.trial in trials]
        if scored_by is not None:
            scorings = set(self.store.reaching(scored_by, "scoring"))
            found = [
                r
                for r in found
                if any(s.scoring in scorings for s in self.store.scores_of(r.run))
            ]
        if started_with is not None:
            found = [
                r
                for r in found
                if started_with in (r.run, known[Subject(run=r.run)].started_with)
            ]
        return found

    def run(self, found: UUID | str | None = None) -> RunStarted:
        if isinstance(found, UUID):
            about = read.about(self.rows, Subject(run=found))
            started = self.store.started([found])
            if not owns(self.person.id, about) or not started:
                raise NotFound(f"no run {found} of yours")
            return started[0]
        runs = self.runs()
        if found is None:
            if not runs:
                raise NotFound(f"{self.person.login} has no runs")
            return runs[0]
        match [r for r in runs if str(r.run).startswith(found)]:
            case [run]:
                return run
            case []:
                raise NotFound(f"no run of yours starts with {found!r}")
            case several:
                raise Ambiguous(f"{len(several)} runs of yours start with {found!r}")

    # Policy: a run is titled by what it ran, its configuration and what its variation
    # replaced but the model, which is said apart as what it ran under, and its own name
    # when no variation of a configuration ran.
    def titled(self, run: RunStarted) -> Titled:
        trial = resolve(self.store.get, run.trial, Trial)
        handle, _ = self.under(trial.engine)
        about = read.about(self.rows, Subject(run=run.run))
        varied = None if about.varied is None else self.rows.edit(about.varied)
        name = (
            about.name or self.title(trial.skeleton)
            if varied is None
            else titles.title(self.rows, varied.thread)
        )
        replaced = [
            Replaced(part, None if digest is None else self.title(digest))
            for part, digest in about.replaced.items()
            if part != "model" and varied is not None
        ]
        into = {c.into for c in self.store.compilations(trial.skeleton)}
        return Titled(
            name=name,
            replaced=replaced,
            at=handle.name
            if handle is not None
            else self.title(trial.engine)
            if run.endpoint is None
            else run.endpoint.name,
            case=self.titled_case(trial.cases[0]) if len(trial.cases) == 1 else None,
            cases=len(trial.cases),
            translated=next(iter(into))
            if len(into) == 1 and None not in into
            else None,
            greedy=resolve(self.store.get, trial.skeleton, Skeleton).greedy,
            seeds=trial.seeds,
        )

    def titled_case(self, case: str) -> CaseTitle:
        found = titles.case_title(self.rows, case)
        return CaseTitle(self.title(case), (), False) if found is None else found

    def described(self, run: RunStarted) -> str:
        trial = resolve(self.store.get, run.trial, Trial)
        handle, _ = self.under(trial.engine)
        where = (
            handle.name
            if handle is not None
            else self.title(trial.engine)
            if run.endpoint is None
            else run.endpoint.name
        )
        cases = (
            self.title(trial.cases[0])
            if len(trial.cases) == 1
            else f"{len(trial.cases)} cases"
        )
        n = len(trial.seeds)
        seeds = (
            ("greedy" if n == 1 else f"greedy, {n} replicates")
            if resolve(self.store.get, trial.skeleton, Skeleton).greedy
            else "seed " + ", ".join(str(seed) for seed in trial.seeds)
        )
        name = read.about(self.rows, Subject(run=run.run)).name or self.title(
            trial.skeleton
        )
        into = {c.into for c in self.store.compilations(trial.skeleton)}
        sent = (
            f", in {next(iter(into))}, translated"
            if len(into) == 1 and None not in into
            else ""
        )
        return f"{name} × {where} × {cases}{sent} ({seeds})"

    def unscored(self, run: RunStarted) -> list[str]:
        given = self.store.scores_of(run.run)
        keys: set[ItemKey] | None = None
        found: list[str] = []
        for edit, _, scorer in self.scorers(run):
            try:
                built = scoring(self, run, edit.digest)
            except (Ambiguous, ValueError):
                found.append(edit.digest)
                continue
            if built is None:
                continue
            under = [s for s in given if self._scored_alike(s.scoring, built, scorer)]
            if under and keys is None:
                keys = {i.key for i in self.store.run(run.run).items}
            views = len(scorer.views)
            if not any(self._whole(s, keys or set(), views) for s in under):
                found.append(edit.digest)
        return found

    # Policy: a score under another scoring of the same scorer and judges' engines holds
    # when each of its views reads the expectations as they are alike, so that a change
    # to what no view reads leaves nothing to score.
    def _scored_alike(self, held: str, built: Scoring, scorer: Scorer) -> bool:
        if held == built.digest:
            return True
        then = resolve(self.store.get, held, Scoring)
        if (then.scorer, then.engines) != (built.scorer, built.engines):
            return False
        before = self._by_case(then.expectations)
        now = self._by_case(built.expectations)
        try:
            return before.keys() == now.keys() and all(
                read_by(scorer, before[c]) == read_by(scorer, now[c]) for c in now
            )
        except LookupError:
            return False

    def _by_case(self, expectations: Iterable[str]) -> dict[str, JsonValue]:
        held = (resolve(self.store.get, e, Expectation) for e in expectations)
        return {e.case: e.data for e in held}

    def _whole(self, started: ScoreStarted, keys: set[ItemKey], views: int) -> bool:
        score = self.store.score(started.score)
        if score.finished is None:
            return False
        calls = (c.call for i in score.items for c in i.judge_calls)
        if any(call.error == STOPPED for call in calls):
            return False
        expected = {(k, v) for k in keys for v in range(views)}
        return expected <= {(i.key, i.view) for i in score.items}

    def outstanding(self) -> list[tuple[RunStarted, list[str]]]:
        runs = self.runs()
        finished = self.store.finished([r.run for r in runs])
        return [
            (run, scorers)
            for run in runs
            if run.run in finished and (scorers := self.unscored(run))
        ]

    def scores_of(self, run: RunStarted, every: bool = False) -> list[Graded]:
        given = self.store.scores_of(run.run)
        if every:
            return [self._graded(started) for started in given]
        found: dict[str, ScoreStarted] = {}
        for started in given:
            scorer = resolve(self.store.get, started.scoring, Scoring).scorer
            _ = found.setdefault(scorer, started)
        return sorted((self._graded(s) for s in found.values()), key=lambda g: g.name)

    def score_of(self, run: RunStarted, score: UUID) -> Graded:
        given = self.store.scores_of(run.run)
        found = next((s for s in given if s.score == score), None)
        if found is None:
            raise NotFound(f"no score {score} of run {run.run}")
        return self._graded(found)

    def _graded(self, started: ScoreStarted) -> Graded:
        scorer = resolve(self.store.get, started.scoring, Scoring).scorer
        return Graded(
            self.title(scorer),
            resolve(self.store.get, scorer, Scorer),
            self.labels(scorer),
            self.store.score(started.score),
        )


def choices(seen: Seen, cases: Sequence[str], schema: str) -> dict[str, dict[int, str]]:
    return {
        case: {e.thread: e.digest for e, a in held if owns(seen.person.id, a)}
        for case, held in threads.expecting(seen.rows, cases, schema).items()
    }


def picked(seen: Seen, cases: Sequence[str], schema: str) -> dict[str, str | None]:
    try:
        return {
            case: threads.picked(case, held)
            for case, held in choices(seen, cases, schema).items()
        }
    except LookupError as e:
        if isinstance(e, Worded) and e.wording is not None:
            raise Ambiguous.of(e.wording, **e.params) from None
        raise Ambiguous(str(e)) from None


def scoring(seen: Seen, run: RunStarted, scorer: str) -> Scoring | None:
    trial = resolve(seen.store.get, run.trial, Trial)
    found = resolve(seen.store.get, scorer, Scorer)
    held = picked(seen, list(trial.cases), found.expectation_schema)
    expectations = tuple(e for e in held.values() if e is not None)
    if not expectations:
        return None
    engines = tuple(
        JudgeEngine(
            judge=j, engine=seen.judged(resolve(seen.store.get, j, Judge)).engine
        )
        for j in found.judges
    )
    return Scoring(scorer=scorer, expectations=expectations, engines=engines)


def labels_of(seen: Seen, edit: Edit) -> dict[int, str]:
    return {
        position: label
        for (part, position), label in read.labels(seen.rows, edit.id).items()
        if part == "view"
    }


def worded(seen: Seen, thread: int) -> tuple[Edit, About, str]:
    found = seen.rows.thread(thread)
    word = word_of(None if found is None else found.kind)
    edit, about = seen.thread(thread, None if word == "thread" else word)
    return edit, about, word


def compiled_with(seen: Seen, variation: TriedVariation) -> ModelFacts | None:
    recipe = variation.varied
    if recipe is None:
        return None
    made = variation.configuration.compilation
    if not variation.parts and made is not None:
        pinned = resolve(seen.store.get, made, Compilation).facts
        return None if pinned is None else resolve(seen.store.get, pinned, ModelFacts)
    return seen.facts.about(recipe.model, seen.store.get)


def compiled(
    seen: Seen,
    recipe: Recipe,
    facts: ModelFacts | None | Literal["current"] = "current",
    into: str | None = None,
) -> tuple[Registry, Compilation]:
    registry = seen.store.load(s.digest for s in iter_refs(recipe))
    if facts == "current":
        facts = seen.facts.about(recipe.model, seen.store.get)
    if facts is not None:
        _ = registry.add(facts)
    skeleton, compilation = compile_recipe(recipe, registry.get, rig(), facts, into)
    _ = registry.add(skeleton)
    _ = registry.add(compilation)
    return registry, compilation


def trial(
    seen: Seen,
    skeleton: Skeleton,
    engine: str,
    cases: list[str],
    seeds: Sequence[int],
    cleanup: tuple[CleanupOp, ...] = (),
) -> tuple[Registry, Trial]:
    registry = seen.store.load([engine, *cases, *(s.digest for s in skeleton.refs())])
    _ = registry.add(skeleton)
    made = Trial(
        skeleton=skeleton.digest,
        engine=engine,
        cases=tuple(cases),
        cleanup=cleanup,
        seeds=replicates(skeleton, seeds),
    )
    _ = registry.add(made)
    return registry, made


def linted(seen: Seen, digest: str) -> list[Finding]:
    registry = seen.store.load([digest])
    if isinstance(paired := registry.get(digest), Trial | Judge):
        add_compilations(seen, registry, paired.skeleton)
    engines = judging(seen, paired, registry) if isinstance(paired, Judge) else {}
    languages = partial(language_of, seen.rows)
    return lints(registry, seen.facts, [digest], languages, engines)


# Policy: A judge's skeleton is linted on its handle's latest engine, where it would
# judge, and on none where it can't.
def judging(seen: Seen, judge: Judge, registry: Registry) -> dict[str, str]:
    try:
        engine = seen.judged(judge).engine
    except ValueError:
        return {}
    held = seen.store.load([engine])
    for digest in held:
        if digest not in registry:
            _ = registry.add(held.get(digest))
    return {judge.digest: engine}


# Dependency: src/chatddx/factors/lint.py:_made_for reads them from the registry.
def add_compilations(seen: Seen, registry: Registry, skeleton: str) -> None:
    for compilation in seen.store.compilations(skeleton):
        _ = registry.add(compilation)
        if compilation.facts is not None:
            _ = registry.add(seen.store.get(compilation.facts))
        if compilation.recipe.model not in registry:
            _ = registry.add(seen.store.get(compilation.recipe.model))


def check_scorer(scorer: Scorer) -> None:
    if found := problems(scorer):
        raise ValueError("; ".join(found))


def check_kind(
    seen: Seen, thread: int, word: str, held: Component | TriedVariation
) -> None:
    kind = threads.thread(seen.rows, thread).kind
    given = "skeleton" if isinstance(held, TriedVariation) else held.kind_name
    if kind != given:
        raise ValueError(f"{word} {thread} holds {kind} components, not {given}")


def check_expecting(
    seen: Seen,
    expectation: Expectation,
    thread: int | None,
    restoring: bool = False,
) -> None:
    case, schema = expectation.case, expectation.expectation_schema
    held = choices(seen, [case], schema)[case]
    if (others := sorted(t for t in held if t != thread)) and restoring:
        raise Invalid.of(
            "%(login)s has their own expectation of %(case)s under %(schema)s "
            + "already, in thread %(thread)s",
            login=seen.person.login,
            case=seen.title(case),
            schema=seen.title(schema),
            thread=others[0],
        )
    if others:
        raise Invalid.of(
            "%(login)s has their own expectation of %(case)s under %(schema)s "
            + "already, in thread %(thread)s",
            login=seen.person.login,
            case=seen.title(case),
            schema=seen.title(schema),
            thread=others[0],
        )


# Policy: the cases left out are said with what is sent
# (src/chatddx/bench/model.py:Carried.refused), so what is found is a translation that
# doesn't compile into a language no case of them is in.
def missing(
    seen: Seen, variation: TriedVariation, carried: Sequence[Carried]
) -> list[Finding]:
    recipe = variation.varied
    if recipe is None:
        return []
    looked = {c.language for c in carried} | {recipe_language(seen.rows, recipe)}
    found: list[Finding] = []
    for language in translated(recipe, seen.store.get):
        if language in looked:
            continue
        try:
            _ = seen.skeleton(variation, language)
        except StructuralError as e:
            found.append(
                Finding(
                    code="translations.missing",
                    message=str(e),
                    subject=variation.configuration.digest,
                )
            )
    return found


def _language_in(
    known: Mapping[str, str | None], otherwise: Callable[[str], str | None], digest: str
) -> str | None:
    return known[digest] if digest in known else otherwise(digest)


def _titled(schema: JsonValue) -> str | None:
    match schema:
        case {"title": str() as title}:
            return title
        case _:
            return None
