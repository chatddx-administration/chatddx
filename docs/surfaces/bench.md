# `bench`

Written by `chatddx-dev index` from `[parts.bench]`'s code in `settings.toml`, an entry for each public name, sorted alphabetically whatever its case, so that a class's members follow it, a language's after another's:

Python:

```
## `<name>` `@<decorator>` `[<type parameters>]` `(<bases>)`
`<file>:<qualified name>`

* `<parameter or field>: <type> = <default>`
* ∟`<return type>`

Raises:
1. `<exception>`: `<arguments>` (from `<exception caught>`, through `<private helper>`, in a `ValidationError`)

Finds:
1. `<code>`: `<message>` (`<level>`, from `<exception caught>`, through `<private helper>`)
```

- A constant or a type alias is its definition instead of bullets; a class and its `__init__` leave out ∟, and a method its instance; `*`: the parameters after it are keyword-only, `/`: those before it positional-only.
- Raises and Finds are the function's own and its private helpers', in the order the code reaches them, each once, a `Whoops` left out; what a public function it calls raises is in that function's entry.
- Text is quoted, a value in it as `{<expression>}`, and an argument that isn't text is as written; a finding is a warning unless it gives its level.

- A stamp pending is a git conflict, from `<<<<<<< signed` to `=======` as last stamped and on to the `>>>>>>>` closing it as written now, till it is stamped.

## `add_compilations`
`src/chatddx/bench/seen.py:add_compilations`

* `seen: Seen`
* `registry: Registry`
* `skeleton: str`
* ∟`None`

## `Ambiguous` `(Worded, LookupError)`
`src/chatddx/bench/errors.py:Ambiguous`

## `APPENDICES`
`src/chatddx/bench/composing.py:APPENDICES`

`APPENDICES = ("‹appendix 1›", "‹appendix 2›")`

## `Baseline` `@dataclass(frozen=True)`
`src/chatddx/bench/breakdown.py:Baseline`

One baseline gathering of a configuration as a page shows it: itself as its
breakdown has it, the one before it, its runs, and each case it sent or the
baseline holds now, those the baseline holds first.

* `configuration: int`
* `views: tuple[View, ...]`
* `gathered: Gathered`
* `before: Gathered | None`
* `runs: tuple[GatheredRun, ...]`
* `cases: tuple[GatheredCase, ...]`

## `Bench` `@final` `(Seen)`
`src/chatddx/bench/bench.py:Bench`

## `Bench.again`
`src/chatddx/bench/runs.py:again`

Begins a run of the run's skeleton and cases under other seeds, at its handle's
latest endpoint, and sends nothing.

Stores the run's trial, start record and entries once the gate has confirmed the
endpoint with a request to it.

Heads-up: the gate's `Refused` passes through.

* `run: RunStarted`
* `seeds: Sequence[int]`
* ∟`Running`

Raises:
1. `ValueError`: `"run {run.run} was sent to no endpoint, so it can't run again"`
2. `NotFound`: `"no case {missing[0]} for {seen.person.login}"`
3. `Invalid`: `"run %(run)s is out of date: run its configuration instead, once that is updated", run=str(run.run)`

## `Bench.baseline`
`src/chatddx/bench/breakdown.py:baseline`

The person's baseline gathering begun by `started` on the cases, with the
configuration's gathering before it, None if it is no such gathering. Costs what
`breakdown` costs.

* `started: UUID`
* `cases: Collection[str]`
* ∟`Baseline | None`

## `Bench.behind_own`
`src/chatddx/bench/updating.py:behind_own`

* ∟`list[int]`

## `Bench.breakdown`
`src/chatddx/bench/breakdown.py:breakdown`

How the configuration fared on the cases, as the baseline gatherings of its
versions and of the peers' latest have it. A baseline is a start of runs of none
but the cases on one seed each, as Run starts one, of no parts replaced. Costs what
`observed` costs for each of the person's runs, cached rows costing nothing, and
each configuration's head resolved.

* `thread: int`
* `cases: Collection[str]`
* `peers: Collection[int] = ()`
* ∟`Breakdown`

## `Bench.case`
`src/chatddx/bench/cases.py:case`

* `family: int`
* `appendices: Sequence[str]`
* ∟`str`

Raises:
1. `NotFound`: `"no appendix {digest} for {seen.person.login}"`

## `Bench.check`
`src/chatddx/bench/components.py:check`

* `component: Component | Recipe`
* ∟`Checked`

Raises:
1. `ValueError`: `"{digest} isn't a stored {what}"` (through `_stored_parts`)
2. `ValueError`: `"a person doesn't write {component.kind_name} components"`
3. `NotFound`: `"no case {missing[0]} for {seen.person.login}"` (through `_carried`)
4. `Invalid`: `"a trial's cases are in one language, not in %(languages)s", languages=", ".join(known)` (through `_carried`)
5. `Invalid`: `"%(name)s has no translation into %(languages)s", name=seen.title(trial.skeleton), languages=into` (through `_carried`)

Finds:
1. `expectation.unreadable`: `str(e)` (through `_unreadable`)

## `Bench.check_quota`
`src/chatddx/bench/runs.py:check_quota`

Refuses with `OverQuota` runs of these many items each that the person's quota
doesn't hold; reads how many runs they started in the last day.

* `runs: Sequence[int]`
* ∟`None`

Raises:
1. `OverQuota`: `"a run holds at most %(num)s item, not %(given)s" / "a run holds at most %(num)s items, not %(given)s", num=settings.ITEMS_PER_RUN, given=items`
2. `OverQuota`: `"over the day's quota: %(used)s of %(limit)s", used=started + len(runs), limit=settings.RUNS_PER_DAY`

## `Bench.compose`
`src/chatddx/bench/composing.py:compose`

Saves the configuration with the chunks given in place of its own at `head`:
a version of it, or a fork of it named `name`, or, `independent`, a configuration
of its own named so, forked from nothing. Each chunk that changed is written to
the thread its own came from, as a new version where that is the person's, or
else as a fork of it under its name; a fork of the configuration forks those it
changes, and an independent one starts a thread of each, named after it. Its translations are `into` when given, or else its own carried over to
the texts that changed. One transaction, locking each thread it writes.

* `thread: int`
* `head: int`
* `chunks: Drafts`
* `model: str | None = None`
* `into: Mapping[str, Mapping[str, str]] | None = None`
* `name: str | None = None`
* `independent: bool = False`
* ∟`Written`

Raises:
1. `ValueError`: `"{variation.name} has no recipe to save its parts in"`
2. `ValueError`: `"an independent configuration needs a name"`
3. `ValueError`: `"no part {stray[0]!r}: the parts are {', '.join(CHUNK_PARTS)}"`

## `Bench.drafted`
`src/chatddx/bench/composing.py:drafted`

The texts a configuration's recipe would hold with the chunks drafted in
place of its own, by part, and the translations given for the texts `before`
held carried over to them. Reads the recipe's chunks; writes nothing.

* `thread: int`
* `head: int | None`
* `before: Drafts`
* `after: Drafts`
* `into: Mapping[str, Mapping[str, str]]`
* ∟`tuple[dict[str, tuple[str, ...]], dict[str, dict[str, str]]]`

Raises:
1. `NotFound`: `"no recipe of configuration {thread}"` (through `_recipe`)

## `Bench.edit`
`src/chatddx/bench/components.py:edit`

* `thread: int`
* `head: int`
* `held: Component | TriedVariation`
* `language: str | None = None`
* `labels: Labels | None = None`
* ∟`Written`

Raises:
1. `NotFound`: `"no {word} {thread} of yours"`
2. `ValueError`: `"a compiled configuration's language comes from its recipe"` (through `_configured`)
3. `ValueError`: `"only a scorer's views and resources have labels"` (through `_configured`)
4. `ValueError`: `"a person doesn't write {kind} components"` (through `_written`)
5. `ValueError`: `"{kind} components have no language of their own"` (through `_written`)
6. `ValueError`: `"{new.case} isn't a case of the family {old.case} is of"` (through `_written`)
7. `NotFound`: `"no case {missing[0]} for {seen.person.login}"` (through `_written`)
8. `Invalid`: `"a trial's cases are in one language, not in %(languages)s", languages=", ".join(known)` (through `_written`)
9. `Invalid`: `"%(name)s has no translation into %(languages)s", name=seen.title(trial.skeleton), languages=into` (through `_written`)

## `Bench.fork`
`src/chatddx/bench/components.py:fork`

* `thread: int`
* `name: str`
* `held: Component | TriedVariation | None = None`
* `language: str | None = None`
* `labels: Labels | None = None`
* ∟`Written`

Raises:
1. `ValueError`: `"{held.label} isn't a variation of configuration {thread}"`
2. `ValueError`: `"a compiled configuration's language comes from its recipe"` (through `_configured`)
3. `ValueError`: `"only a scorer's views and resources have labels"` (through `_configured`)
4. `ValueError`: `"a person doesn't write {kind} components"` (through `_written`)
5. `ValueError`: `"{kind} components have no language of their own"` (through `_written`)
6. `ValueError`: `"{new.case} isn't a case of the family {old.case} is of"` (through `_written`)
7. `NotFound`: `"no case {missing[0]} for {seen.person.login}"` (through `_written`)
8. `Invalid`: `"a trial's cases are in one language, not in %(languages)s", languages=", ".join(known)` (through `_written`)
9. `Invalid`: `"%(name)s has no translation into %(languages)s", name=seen.title(trial.skeleton), languages=into` (through `_written`)

## `Bench.gathering`
`src/chatddx/bench/gathering.py:gathering`

The person's runs about the center gathered into the seedings, a group for each
configuration they varied and the latest run first, kept to those started with
`started_with` and among `among` when given. A component's runs are those whose
trial or a score reaches it, a seed's those whose trial holds it. Reads the
person's runs twice for a component and once for a seed, and each run's trial for
a seed and its configuration's edit.

* `center: Center`
* `seedings: tuple[Seeding, ...]`
* `started_with: UUID | None = None`
* `among: Collection[UUID] | None = None`
* ∟`Gathering | None`

## `Bench.gatherings`
`src/chatddx/bench/gathering.py:gatherings`

Each case's latest gathering under each configuration the person varied and ran
it under, by case and the configuration's thread, the latest run first. Reads the
person's runs, their catalog rows and each one's trial.

* `cases: Collection[str]`
* ∟`dict[tuple[str, int], list[RunStarted]]`

## `Bench.latest_starts`
`src/chatddx/bench/gathering.py:latest_starts`

Under each configuration the person varied, the runs of its latest start in the
seedings' shape on the cases, each a trial of none but the cases on as many seeds
as a seeding holds, and, for a configuration in `compiled`, of a version that
compiles to the skeleton named; by the configuration's thread, the latest run
first. Reads the person's runs, their catalog rows and each one's trial.

* `cases: Collection[str]`
* `seedings: tuple[Seeding, ...]`
* `compiled: Mapping[int, str] | None = None`
* ∟`dict[int, list[RunStarted]]`

## `Bench.leave`
`src/chatddx/bench/saying.py:leave`

Takes the person out of what they see of a thread or a family shared with them,
by an entry of their own, until its owner shares it with them again.

Reads the subject's entries before and after, and writes one entry.

* `subject: Subject`
* ∟`About`

Raises:
1. `NotFound`: `"no {_what(seen, subject)} shared with {seen.person.login}"`

## `Bench.lineage`
`src/chatddx/bench/updating.py:lineage`

* `thread: int`
* ∟`list[Kin]`

## `Bench.new`
`src/chatddx/bench/components.py:new`

* `component: Component | Recipe`
* `name: str | None`
* `language: str | None = None`
* `labels: Labels | None = None`
* ∟`Written`

Raises:
1. `ValueError`: `"only an expectation goes unnamed: the case it is for says which it is"`
2. `ValueError`: `"a compiled configuration's language comes from its recipe"` (through `_configured`)
3. `ValueError`: `"only a scorer's views and resources have labels"` (through `_configured`)
4. `ValueError`: `"{digest} isn't a stored {what}"` (through `_stored_parts`)
5. `ValueError`: `"a person doesn't write {kind} components"` (through `_written`)
6. `ValueError`: `"{kind} components have no language of their own"` (through `_written`)
7. `ValueError`: `"{new.case} isn't a case of the family {old.case} is of"` (through `_written`)
8. `NotFound`: `"no case {missing[0]} for {seen.person.login}"` (through `_written`)
9. `Invalid`: `"a trial's cases are in one language, not in %(languages)s", languages=", ".join(known)` (through `_written`)
10. `Invalid`: `"%(name)s has no translation into %(languages)s", name=seen.title(trial.skeleton), languages=into` (through `_written`)

## `Bench.observed`
`src/chatddx/bench/observed.py:observed`

The runs that finished, each with its finished scores and what it isn't scored
by as things are now, in the order given. Held rows cost nothing to read again;
each run not held reads its log once with its catalog rows, each score not held
reads its log, and each run's scores are listed once, and, once the catalog has
changed, what `seen.unscored` costs.

* `runs: Sequence[RunStarted]`
* ∟`list[Observed]`

## `Bench.outdated`
`src/chatddx/bench/updating.py:outdated`

* `edit: Edit`
* `kind: str`
* ∟`bool`

## `Bench.preview`
`src/chatddx/bench/composing.py:preview`

The request a configuration would send with the chunks, model and
translations drafted in place of its own, its own where not given, in `language` as far as it is
translated, its slots holding placeholders and its appendices `APPENDICES`. Reads
the recipe's chunks and the models served; writes nothing.

* `thread: int`
* `head: int | None`
* `chunks: Drafts`
* `model: str | None`
* `into: Mapping[str, Mapping[str, str]] | None`
* `language: str | None`
* ∟`Previewed`

Raises:
1. `NotFound`: `"no recipe of configuration {thread}"` (through `_recipe`)
2. `ValueError`: `"no part {stray[0]!r}: the parts are {', '.join(parts)}"` (through `_check_parts`)

## `Bench.proposal`
`src/chatddx/bench/updating.py:proposal`

* `thread: int`
* ∟`Proposed | None`

## `Bench.queue`
`src/chatddx/bench/runs.py:queue`

* `running: Running`
* `score: bool = True`
* ∟`Job`

## `Bench.queue_scoring`
`src/chatddx/bench/runs.py:queue_scoring`

* `run: RunStarted`
* `scorers: Collection[str] | None = None`
* ∟`list[str]`

Raises:
1. `ValueError`: `"run {run.run} hasn't finished"`
2. `ValueError`: `"scorer {missing[0]} doesn't apply to run {run.run}"`
3. `ValueError`: `"no scorer applies to run {run.run}"`

## `Bench.replacement`
`src/chatddx/bench/cases.py:replacement`

* `case: str`
* ∟`str`

Raises:
1. `NotFound`: `"no case {case} for {seen.person.login}"`

## `Bench.resume`
`src/chatddx/bench/runs.py:resume`

* `run: RunStarted`
* ∟`Running`

## `Bench.save`
`src/chatddx/bench/configurations.py:save`

* `variation: TriedVariation`
* `name: str`
* ∟`Written`

Raises:
1. `Ambiguous`: `"{seen.person.login} has {len(mine)} configurations named {name!r}"`

## `Bench.say`
`src/chatddx/bench/saying.py:say`

Writes what holds of the thread or family itself in one transaction.
`...` leaves a name or a description as it is and `None` takes it away.

Reads the subject's entries before and after, a person per collaborator, and for a
restored expectation thread the person's expectations of its case and schema.

Heads-up:
- Only families take language.
- A family's tags and language are said by those it is shared with as well as by
  its owner; the rest of it, and of a thread, by its owner alone.
- An expectation thread is refused while the person owns another of its case and
  schema.

* `subject: Subject`
* `*`
* `name: str | None | EllipsisType = ...`
* `description: str | None | EllipsisType = ...`
* `tags: Collection[str] | None = None`
* `collaborators: Collection[str] | None = None`
* `deleted: bool | None = None`
* `language: str | None = None`
* ∟`About`

Raises:
1. `NotFound`: `"no {what} of yours"`
2. `ValueError`: `"{what} is deleted: restore it to say more of it"`
3. `ValueError`: `"a name can't be empty: none takes it away"`
4. `ValueError`: `"a description can't be empty: none takes it away"`
5. `ValueError`: `"a tag can't be empty"`
6. `NotFound`: `"no person %(login)s", login=repr(login)` (through `_sharing`)
7. `ValueError`: `"{what} is yours: it is shared with others"`

## `Bench.score`
`src/chatddx/bench/runs.py:score`

Scores the run under each scorer that applies, or each of those given, one after
another in the calling thread.

Sends each judged view's requests to its judge's endpoint once the gate has confirmed
it with a request to it, and writes each score's records as it goes.

Heads-up: a scorer refused is returned with why in `Graded.refused`, not raised, and
so is each one after a halt or an interrupt, as stopped.

* `run: RunStarted`
* `scorers: Collection[str] | None = None`
* `on_event: Callable[[ScoringEvent], None] | None = None`
* `halt: Halt | None = None`
* ∟`list[Graded]`

## `Bench.start`
`src/chatddx/bench/runs.py:start`

Begins a run for each language the cases are sent in, and sends nothing; given
`joining`, the first run of an earlier start, its runs are listed as of that start.

Compiles the variation into each language, and stores each run's trial, start record
and entries, and the compilations of what it begins, in one transaction, which holds
while the gate confirms the endpoint with a request to it for each run.

Heads-up: the gate's `Refused` passes through.

* `variation: TriedVariation`
* `endpoint: str | None`
* `cases: list[str]`
* `seeds: Sequence[int]`
* `cleanup: Sequence[CleanupOp] | None = None`
* `execution: Execution | None = None`
* `canaries: str | None = None`
* `joining: UUID | None = None`
* ∟`Started`

Raises:
1. `ValueError`: `"{variation.label} is a judge configuration: a judge is asked as runs are scored, and isn't run on cases"`
2. `NotFound`: `"no case {missing[0]} for {seen.person.login}"`
3. `Invalid`: `"%(name)s has no translation into %(languages)s", name=variation.label, languages=", ".join(str(c.language) for c in left_out)`
4. `Invalid`: `"no case can be sent: %(refused)s", refused="; ".join(c.refused or "" for c in left_out)`

## `Bench.start_trials`
`src/chatddx/bench/runs.py:start_trials`

Begins a run of each trial version at the endpoint serving its engine, and sends
nothing.

Stores each run's start record and entries in one transaction, which holds while the
gate confirms the endpoint with a request to it for each run.

Heads-up: the gate's `Refused` passes through.

* `versions: Sequence[int]`
* `concurrency: int | None = None`
* `order: Order | None = None`
* ∟`list[Running]`

Raises:
1. `NotFound`: `"no trial version {id} for {seen.person.login}"`
2. `ValueError`: `"a start runs one trial or more"`
3. `NotFound`: `"no case {missing[0]} for {seen.person.login}"`
4. `Invalid`: `"%(name)s is out of date: update it on its page", name=name`

## `Bench.take`
`src/chatddx/bench/taking.py:take`

* `cases: Iterable[str]`
* `schema: str`
* `owner: str | None = None`
* ∟`Taken`

Raises:
1. `ValueError`: `"{schema} isn't a stored expectation schema"`
2. `NotFound`: `"no person {owner!r}"`

## `Bench.take_from`
`src/chatddx/bench/taking.py:take_from`

* `thread: int`
* `replace: bool = False`
* ∟`int`

Raises:
1. `ValueError`: `"expectation {thread} is yours already"`
2. `Conflict`: `"%(login)s has their own expectation of %(case)s under %(schema)s already, in thread %(thread)s", login=seen.person.login, case=seen.title(case), schema=seen.title(schema), thread=mine[0]`

## `Bench.type_case`
`src/chatddx/bench/cases.py:type_case`

* `text: str`
* `*`
* `language: str`
* `name: str | None = None`
* `source: str | None = None`
* ∟`Family`

Raises:
1. `Invalid`: `"a typed case holds text"`
2. `Invalid`: `"U+0000 can't be stored"`
3. `Invalid`: `"a typed case holds at most %(num)s character, not %(given)s" / "a typed case holds at most %(num)s characters, not %(given)s", num=settings.TYPED_TEXT_LIMIT, given=len(text)`
4. `Invalid`: `"a name can't be empty: none leaves the case unnamed"`
5. `ValueError`: `str(e)` (from `LookupError`)
6. `OverQuota`: `"over the day's quota: %(used)s of %(limit)s", used=typed + 1, limit=settings.TYPED_PER_DAY`

## `Bench.update`
`src/chatddx/bench/updating.py:update`

* `thread: int`
* `head: int`
* `language: str | None = None`
* ∟`Written`

Raises:
1. `NotFound`: `"no {word} {thread} of yours"`
2. `ValueError`: `"{word} {thread} has nothing to update"`
3. `ValueError`: `"a compiled configuration's language comes from its recipe"` (through `_kept`)
4. `ValueError`: `"{kind} components have no language of their own"` (through `_kept`)

## `Bench.update_all`
`src/chatddx/bench/updating.py:update_all`

* ∟`list[Updated]`

## `bound`
`src/chatddx/bench/components.py:bound`

* `seen: Seen`
* `appendix: Appendix`
* ∟`Appendix`

Raises:
1. `ValueError`: `"an appendix is bound to the current vignette of a case you see"`

## `Breakdown` `@dataclass(frozen=True)`
`src/chatddx/bench/breakdown.py:Breakdown`

How a configuration fared on the baseline cases: the views its skeleton offers,
its baseline gatherings in the order they ran, a version once for each time it
ran, and its peers among the configurations given.

* `views: tuple[View, ...]`
* `timeline: tuple[Gathered, ...]`
* `peers: tuple[Peer, ...]`

## `broken`
`src/chatddx/bench/handles.py:broken`

* `rows: Rows`
* `inventory: Inventory`
* ∟`list[str]`

## `Carried` `@dataclass(frozen=True)`
`src/chatddx/bench/model.py:Carried`

* `language: str | None`
* `cases: list[str]`
* `skeleton: Skeleton | None = None`
* `translated: bool = False`
* `refused: str | None = None`
* `untranslated: bool = False`

## `check_expecting`
`src/chatddx/bench/seen.py:check_expecting`

* `seen: Seen`
* `expectation: Expectation`
* `thread: int | None`
* `restoring: bool = False`
* ∟`None`

Raises:
1. `Invalid`: `"%(login)s has their own expectation of %(case)s under %(schema)s already, in thread %(thread)s", login=seen.person.login, case=seen.title(case), schema=seen.title(schema), thread=others[0]`

## `check_kind`
`src/chatddx/bench/seen.py:check_kind`

* `seen: Seen`
* `thread: int`
* `word: str`
* `held: Component | TriedVariation`
* ∟`None`

Raises:
1. `ValueError`: `"{word} {thread} holds {kind} components, not {given}"`

## `check_scorer`
`src/chatddx/bench/seen.py:check_scorer`

* `scorer: Scorer`
* ∟`None`

Raises:
1. `ValueError`: `"; ".join(found)`

## `Checked` `@dataclass(frozen=True)`
`src/chatddx/bench/model.py:Checked`

* `digest: str`
* `findings: list[Finding]`

## `choices`
`src/chatddx/bench/seen.py:choices`

* `seen: Seen`
* `cases: Sequence[str]`
* `schema: str`
* ∟`dict[str, dict[int, str]]`

## `compiled`
`src/chatddx/bench/seen.py:compiled`

* `seen: Seen`
* `recipe: Recipe`
* `facts: ModelFacts | None | Literal["current"] = "current"`
* `into: str | None = None`
* ∟`tuple[Registry, Compilation]`

## `COMPILED_LANGUAGE`
`src/chatddx/bench/model.py:COMPILED_LANGUAGE`

`COMPILED_LANGUAGE = "a compiled configuration's language comes from its recipe"`

## `compiled_with`
`src/chatddx/bench/seen.py:compiled_with`

* `seen: Seen`
* `variation: TriedVariation`
* ∟`ModelFacts | None`

## `Conflict` `(Worded, ValueError)`
`src/chatddx/bench/errors.py:Conflict`

## `Drafts`
`src/chatddx/bench/composing.py:Drafts`

`type Drafts = Mapping[str, Component | None]`

## `Endpoint` `@dataclass(frozen=True)`
`src/chatddx/bench/model.py:Endpoint`

* `name: str`
* `spec: EndpointSpec`
* `model: Model`

## `Endpoint.engine` `@property`
`src/chatddx/bench/model.py:Endpoint.engine`

* ∟`str`

## `Estimate` `@dataclass(frozen=True)`
`src/chatddx/bench/breakdown.py:Estimate`

A mean of `n` values, each a case's, with the half-width of its 95% interval,
None for fewer than two.

* `mean: float`
* `half: float | None`
* `n: int`

## `estimate`
`src/chatddx/bench/breakdown.py:estimate`

The mean of values, one a case, with Student's t interval over them: a case's
replicates aren't independent draws of how a configuration fares, so they are
averaged before they get here. None for none.

* `values: Sequence[float]`
* ∟`Estimate | None`

## `Family` `@dataclass(frozen=True)`
`src/chatddx/bench/model.py:Family`

* `id: int`
* `about: About`
* `vignette: Vignette`
* `cases: tuple[str, ...]`

## `Family.case` `@property`
`src/chatddx/bench/model.py:Family.case`

* ∟`str`

## `Family.name` `@property`
`src/chatddx/bench/model.py:Family.name`

* ∟`str`

## `Gathered` `@dataclass(frozen=True)`
`src/chatddx/bench/breakdown.py:Gathered`

One baseline gathering of the configuration, `digest` the skeleton it ran:
each view's estimate over its cases, each case's value, and its mean difference
from the gathering before it on the cases both sent, case by case.

* `digest: str`
* `point: Point`
* `estimates: dict[View, Estimate]`
* `values: dict[View, dict[str, float]]`
* `paired: dict[View, Estimate]`

## `GatheredCase` `@dataclass(frozen=True)`
`src/chatddx/bench/breakdown.py:GatheredCase`

A baseline case in one gathering: the language it went in, whether its
replicate answered without failing, whether its repeat answered alike to the
letter, None where either said nothing, and by view its replicate's value, its
repeat's and the gathering before's.

* `case: str`
* `language: str | None`
* `answered: bool`
* `alike: bool | None`
* `replicate: dict[View, Scored]`
* `repeat: dict[View, Scored]`
* `before: dict[View, float]`

## `GatheredRun` `@dataclass(frozen=True)`
`src/chatddx/bench/breakdown.py:GatheredRun`

* `run: UUID`
* `language: str | None`
* `repeat: bool`

## `Graded` `@dataclass(frozen=True)`
`src/chatddx/bench/model.py:Graded`

* `name: str`
* `scorer: Scorer`
* `labels: dict[int, str]`
* `score: Score | None = None`
* `findings: list[Finding] = field(default_factory=list[Finding])`
* `refused: str | None = None`

## `Graded.label`
`src/chatddx/bench/model.py:Graded.label`

* `view: int`
* ∟`str`

## `Handle` `@dataclass(frozen=True)`
`src/chatddx/bench/model.py:Handle`

* `name: str`
* `thread: int`
* `weights: str`
* `deleted: bool = False`

## `judging`
`src/chatddx/bench/seen.py:judging`

* `seen: Seen`
* `judge: Judge`
* `registry: Registry`
* ∟`dict[str, str]`

## `keep_compilation`
`src/chatddx/bench/configurations.py:keep_compilation`

* `seen: Seen`
* `variation: TriedVariation`
* `into: str | None = None`
* ∟`str | None`

## `keep_language`
`src/chatddx/bench/components.py:keep_language`

* `seen: Seen`
* `digest: str`
* `language: str`
* ∟`None`

Raises:
1. `Invalid`: `"%(text)s is in %(held)s already: a text's language is the same wherever it is held", text=seen.title(digest), held=held`

## `kept`
`src/chatddx/bench/configurations.py:kept`

* `seen: Seen`
* `variation: TriedVariation`
* `thread: int | None`
* `name: str | None`
* `head: int | None = None`
* `*`
* `forked: bool = True`
* ∟`Written`

## `Kin` `@dataclass(frozen=True)`
`src/chatddx/bench/model.py:Kin`

* `edit: Edit`
* `about: About`
* `origin: int | None`
* `divergence: Divergence | None`
* `behind: bool`

## `KINDS`
`src/chatddx/bench/model.py:KINDS`

`KINDS: dict[str, tuple[str, ...]] = {…}`

## `LABELLED`
`src/chatddx/bench/model.py:LABELLED`

`LABELLED: tuple[Part, ...] = ("view", "resource")`

## `labels_of`
`src/chatddx/bench/seen.py:labels_of`

* `seen: Seen`
* `edit: Edit`
* ∟`dict[int, str]`

## `linted`
`src/chatddx/bench/seen.py:linted`

* `seen: Seen`
* `digest: str`
* ∟`list[Finding]`

## `missing`
`src/chatddx/bench/seen.py:missing`

* `seen: Seen`
* `variation: TriedVariation`
* `carried: Sequence[Carried]`
* ∟`list[Finding]`

Finds:
1. `translations.missing`: `str(e)` (from `StructuralError`)

## `MODEL`
`src/chatddx/bench/model.py:MODEL`

`MODEL = "‹model›"`

## `NONE`
`src/chatddx/bench/seen.py:NONE`

`NONE = "none"`

## `NotFound` `(Worded, LookupError)`
`src/chatddx/bench/errors.py:NotFound`

## `Observed` `@dataclass(frozen=True)`
`src/chatddx/bench/observed.py:Observed`

A finished run with the latest finished score of each scorer, and the scorers
it isn't scored by as things are now.

* `ran: Ran`
* `scores: tuple[Valued, ...]`
* `unscored: frozenset[str]`

## `OverQuota` `(Worded, ValueError)`
`src/chatddx/bench/errors.py:OverQuota`

## `Peer` `@dataclass(frozen=True)`
`src/chatddx/bench/breakdown.py:Peer`

Another configuration's latest baseline gathering, on the views it shares with
the one broken down.

* `configuration: int`
* `point: Point`
* `shared: tuple[View, ...]`

## `picked`
`src/chatddx/bench/seen.py:picked`

* `seen: Seen`
* `cases: Sequence[str]`
* `schema: str`
* ∟`dict[str, str | None]`

Raises:
1. `Ambiguous`: `e.wording, **e.params` (from `LookupError`)
2. `Ambiguous`: `str(e)` (from `LookupError`)

## `PLACEHOLDERS`
`src/chatddx/bench/model.py:PLACEHOLDERS`

`PLACEHOLDERS: dict[SlotName, str] = {…}`

## `Point` `@dataclass(frozen=True)`
`src/chatddx/bench/breakdown.py:Point`

One baseline gathering of a configuration: `means` over its replicates alone,
`spread` and `alike` its repeats against them, `missing` the baseline cases none
of its replicates answered without failing.

* `started: UUID`
* `at: datetime`
* `version: int`
* `means: dict[View, float]`
* `spread: dict[View, float]`
* `alike: tuple[int, int]`
* `languages: dict[str | None, int]`
* `failed: float`
* `seconds: float`
* `tokens: float | None`
* `stale: bool`
* `missing: int`

## `Previewed` `@dataclass(frozen=True)`
`src/chatddx/bench/composing.py:Previewed`

* `traced: Traced`
* `request: dict[str, JsonValue]`

## `Proposed` `@dataclass(frozen=True)`
`src/chatddx/bench/model.py:Proposed`

* `reasons: tuple[Reason, ...]`
* `about: str | None`
* `divergence: Divergence | None`
* `remodelled: tuple[str, str] | None`
* `proposal: Recipe | Component | None`
* `digest: str | None`
* `compilation: str | None`
* `refused: ValueError | None`

## `Ran` `@dataclass(frozen=True)`
`src/chatddx/bench/observed.py:Ran`

A finished run as a breakdown reads it, `digest` its version's skeleton and
`started_with` its own id where it began its start.

* `run: UUID`
* `at: datetime`
* `trial: str`
* `skeleton: str`
* `language: str | None`
* `cases: tuple[str, ...]`
* `seeds: tuple[int, ...]`
* `configuration: int | None`
* `version: int | None`
* `digest: str | None`
* `replaced: bool`
* `started_with: UUID`
* `items: tuple[Sent, ...]`

## `Reach` `@dataclass(frozen=True)`
`src/chatddx/bench/model.py:Reach`

* `thread: int`
* `scorer: str`
* `view: int`
* `label: str`
* `offered: bool`
* `cases: int`
* `missing: list[Family]`
* `choosing: list[Family]`

## `Reach.have` `@property`
`src/chatddx/bench/model.py:Reach.have`

* ∟`int`

## `Reason`
`src/chatddx/bench/model.py:Reason`

`Reason = Literal["origin", "facts", "model", "judge", "engine"]`

## `REFUSALS`
`src/chatddx/bench/runs.py:REFUSALS`

`REFUSALS = (LookupError, TypeError, ValueError, NotImplementedError, Refused)`

## `Replaced` `@dataclass(frozen=True)`
`src/chatddx/bench/model.py:Replaced`

* `part: str`
* `title: str | None`

## `SAVED`
`src/chatddx/bench/model.py:SAVED`

`SAVED: dict[Kept, Literal['created', 'a new version', 'unchanged']] = {…}`

## `Scored` `@dataclass(frozen=True)`
`src/chatddx/bench/breakdown.py:Scored`

A case's value under a view, with the score it is read from.

* `value: float`
* `score: UUID`

## `ScorerStarted` `@dataclass(frozen=True)`
`src/chatddx/bench/runs.py:ScorerStarted`

* `scorer: str`
* `name: str`
* `score: UUID`

## `scoring`
`src/chatddx/bench/seen.py:scoring`

* `seen: Seen`
* `run: RunStarted`
* `scorer: str`
* ∟`Scoring | None`

## `ScoringEvent`
`src/chatddx/bench/runs.py:ScoringEvent`

`type ScoringEvent = ScoreEvent | ScorerStarted`

## `Seen`
`src/chatddx/bench/seen.py:Seen`

* `conn: Connection`
* `person: Person`
* `inventory: Inventory`
* `store: Store`
* `catalog: Catalog`
* `rows: Rows`
* `people: People`

## `Seen.__init__`
`src/chatddx/bench/seen.py:Seen.__init__`

* `conn: Connection`
* `person: Person`
* `inventory: Inventory`

## `Seen.answers`
`src/chatddx/bench/seen.py:Seen.answers`

* `skeleton: Skeleton`
* ∟`str | None`

## `Seen.at`
`src/chatddx/bench/seen.py:Seen.at`

* `variation: TriedVariation`
* `endpoint: str | None = None`
* `model: str | None = None`
* ∟`Endpoint`

Raises:
1. `ValueError`: `"endpoint {endpoint!r} serves another model than {variation.label}'s, {self.title(weights)}"`
2. `Invalid`: `"%(configuration)s names no model: name the one to run it under", configuration=variation.label`
3. `ValueError`: `"{variation.label} runs under its model's handle: set its model instead"`
4. `Invalid`: `"%(name)s is out of date: update it on its page", name=variation.label`

## `Seen.case_titled`
`src/chatddx/bench/seen.py:Seen.case_titled`

* `title: str`
* ∟`tuple[Family, str]`

Raises:
1. `NotFound`: `"no appendix {', '.join(missing)} of {family.name}"`
2. `NotFound`: `"no case {title} for {self.person.login}"`

## `Seen.cleanup`
`src/chatddx/bench/seen.py:Seen.cleanup`

* `cases: Sequence[str]`
* ∟`tuple[CleanupOp, ...]`

## `Seen.described`
`src/chatddx/bench/seen.py:Seen.described`

* `run: RunStarted`
* ∟`str`

## `Seen.endpoint`
`src/chatddx/bench/seen.py:Seen.endpoint`

* `name: str`
* ∟`Endpoint`

Raises:
1. `NotFound`: `str(e)` (from `LookupError`)
2. `NotFound`: `"endpoint {name!r} serves engine {display_digest(spec.engine)}, which isn't in the store: load its World with sync-archive"`

## `Seen.expectation`
`src/chatddx/bench/seen.py:Seen.expectation`

* `case: str`
* `schema: str`
* ∟`Expectation | None`

## `Seen.expectation_schemas`
`src/chatddx/bench/seen.py:Seen.expectation_schemas`

* `case: str`
* ∟`list[str]`

## `Seen.facts` `@property`
`src/chatddx/bench/seen.py:Seen.facts`

* ∟`Facts`

## `Seen.families`
`src/chatddx/bench/seen.py:Seen.families`

* `tags: Iterable[str] = ()`
* `*`
* `deleted: bool = False`
* ∟`list[Family]`

## `Seen.family`
`src/chatddx/bench/seen.py:Seen.family`

* `found: int | str`
* `*`
* `deleted: bool = False`
* ∟`Family`

Raises:
1. `NotFound`: `"no {word} {name!r} for {self.person.login}"` (through `Seen._named`)
2. `Ambiguous`: `"{word} {name!r} names {len(several)}; name one as OWNER/NAME"` (through `Seen._named`)
3. `NotFound`: `"no case {found} for {self.person.login}"`

## `Seen.findings`
`src/chatddx/bench/seen.py:Seen.findings`

* `variation: TriedVariation`
* `engine: str`
* `seed: int`
* `carried: Sequence[Carried] | None = None`
* ∟`list[Finding]`

## `Seen.handle`
`src/chatddx/bench/seen.py:Seen.handle`

* `weights: str`
* ∟`Handle`

Raises:
1. `RuntimeError`: `"{display_digest(weights)} is held by {len(held)} model threads, not one: fix boot-check src/chatddx/bench/handles.py:broken"`

## `Seen.handle_named`
`src/chatddx/bench/seen.py:Seen.handle_named`

* `name: str`
* ∟`Handle`

## `Seen.handles`
`src/chatddx/bench/seen.py:Seen.handles`

* ∟`list[tuple[Handle, Endpoint | None]]`

## `Seen.holder`
`src/chatddx/bench/seen.py:Seen.holder`

* `digest: str`
* `recipe: Recipe | None = None`
* ∟`tuple[Edit, About] | None`

## `Seen.judged`
`src/chatddx/bench/seen.py:Seen.judged`

* `judge: Judge`
* ∟`Endpoint`

Raises:
1. `Invalid`: `"%(name)s is out of date: update it on its page", name=self.title(judge.digest)`

## `Seen.labels`
`src/chatddx/bench/seen.py:Seen.labels`

* `scorer: str`
* ∟`dict[int, str]`

## `Seen.landed`
`src/chatddx/bench/seen.py:Seen.landed`

* `variation: TriedVariation`
* ∟`dict[str, Landing]`

## `Seen.languages`
`src/chatddx/bench/seen.py:Seen.languages`

* `variation: TriedVariation`
* `cases: Sequence[str]`
* ∟`list[Carried]`

## `Seen.latest`
`src/chatddx/bench/seen.py:Seen.latest`

* `handle: Handle`
* ∟`str | None`

## `Seen.login`
`src/chatddx/bench/seen.py:Seen.login`

* `person: int | None`
* ∟`str`

## `Seen.outstanding`
`src/chatddx/bench/seen.py:Seen.outstanding`

* ∟`list[tuple[RunStarted, list[str]]]`

## `Seen.reach`
`src/chatddx/bench/seen.py:Seen.reach`

* `variation: TriedVariation`
* `families: list[Family]`
* ∟`list[Reach]`

## `Seen.request`
`src/chatddx/bench/seen.py:Seen.request`

* `variation: TriedVariation`
* `engine: str | None`
* `seed: int`
* ∟`dict[str, JsonValue]`

## `Seen.run`
`src/chatddx/bench/seen.py:Seen.run`

* `found: UUID | str | None = None`
* ∟`RunStarted`

Raises:
1. `NotFound`: `"no run {found} of yours"`
2. `NotFound`: `"{self.person.login} has no runs"`
3. `NotFound`: `"no run of yours starts with {found!r}"`
4. `Ambiguous`: `"{len(several)} runs of yours start with {found!r}"`

## `Seen.runs`
`src/chatddx/bench/seen.py:Seen.runs`

* `*`
* `reaching: str | None = None`
* `scored_by: str | None = None`
* `started_with: UUID | None = None`
* ∟`list[RunStarted]`

## `Seen.score_of`
`src/chatddx/bench/seen.py:Seen.score_of`

* `run: RunStarted`
* `score: UUID`
* ∟`Graded`

Raises:
1. `NotFound`: `"no score {score} of run {run.run}"`

## `Seen.scorers`
`src/chatddx/bench/seen.py:Seen.scorers`

* `run: RunStarted | None = None`
* ∟`list[tuple[Edit, About, Scorer]]`

## `Seen.scores_of`
`src/chatddx/bench/seen.py:Seen.scores_of`

* `run: RunStarted`
* `every: bool = False`
* ∟`list[Graded]`

## `Seen.served`
`src/chatddx/bench/seen.py:Seen.served`

* `handle: Handle`
* ∟`Endpoint`

Raises:
1. `Invalid`: `"model %(model)s is deleted: pick another", model=handle.name`
2. `Invalid`: `"no endpoint here serves model %(model)s: pick another", model=handle.name`

## `Seen.shared`
`src/chatddx/bench/seen.py:Seen.shared`

* `case: str`
* `schema: str`
* ∟`list[tuple[Edit, About]]`

## `Seen.skeleton`
`src/chatddx/bench/seen.py:Seen.skeleton`

* `variation: TriedVariation`
* `into: str | None = None`
* ∟`Skeleton`

Raises:
1. `StructuralError`: `"%(name)s has no translation into %(languages)s", name=variation.label, languages=str(into)`

## `Seen.thread`
`src/chatddx/bench/seen.py:Seen.thread`

* `found: int | str`
* `word: str | None = None`
* `*`
* `deleted: bool = False`
* ∟`tuple[Edit, About]`

Raises:
1. `NotFound`: `"no {word} {name!r} for {self.person.login}"` (through `Seen._named_thread`)
2. `Ambiguous`: `"{word} {name!r} names {len(several)}; name one as OWNER/NAME"` (through `Seen._named_thread`)
3. `NotFound`: `"no {what} {name!r} for {self.person.login}"` (through `Seen._named_thread`)
4. `Ambiguous`: `"{what} {name!r} names a {' and a '.join(several)}"` (through `Seen._named_thread`)
5. `NotFound`: `"no {word or 'thread'} {found} for {self.person.login}"`

## `Seen.threads`
`src/chatddx/bench/seen.py:Seen.threads`

* `word: str`
* `*`
* `deleted: bool = False`
* `purpose: Purpose | None = None`
* `answering: str | None = None`
* ∟`list[tuple[Edit, About]]`

Raises:
1. `ValueError`: `"only a configuration has a purpose and an answer: {word}"`

## `Seen.title`
`src/chatddx/bench/seen.py:Seen.title`

* `digest: str`
* ∟`str`

## `Seen.titled`
`src/chatddx/bench/seen.py:Seen.titled`

* `run: RunStarted`
* ∟`Titled`

## `Seen.titled_case`
`src/chatddx/bench/seen.py:Seen.titled_case`

* `case: str`
* ∟`CaseTitle`

## `Seen.under`
`src/chatddx/bench/seen.py:Seen.under`

* `engine: str`
* ∟`tuple[Handle | None, bool]`

## `Seen.unscored`
`src/chatddx/bench/seen.py:Seen.unscored`

* `run: RunStarted`
* ∟`list[str]`

## `Seen.variation`
`src/chatddx/bench/seen.py:Seen.variation`

* `configuration: int | str`
* `parts: Mapping[str, str | None] | None = None`
* `head: int | None = None`
* ∟`TriedVariation`

Raises:
1. `NotFound`: `"no edit {head} of configuration {edit.thread}"`
2. `ValueError`: `"no part {part!r}: the parts are {', '.join(RECIPE_PARTS)}"`
3. `ValueError`: `"{digest} isn't a stored {what}"`

## `Sent` `@dataclass(frozen=True)`
`src/chatddx/bench/observed.py:Sent`

An item of a run as a breakdown reads it, `said` None where it answered
nothing.

* `case: str`
* `replicate: int`
* `failed: bool`
* `seconds: float`
* `tokens: int | None`
* `said: str | None`

## `Started` `@dataclass(frozen=True)`
`src/chatddx/bench/model.py:Started`

* `runs: list[tuple[Carried, Running]]`
* `left_out: list[Carried]`

## `Started.first` `@property`
`src/chatddx/bench/model.py:Started.first`

* ∟`Running`

## `t975`
`src/chatddx/bench/breakdown.py:t975`

Student's t at 0.975 for `df` degrees of freedom: tabled to 30, then by the
Cornish-Fisher expansion, within 0.001.

* `df: int`
* ∟`float`

Raises:
1. `ValueError`: `"df must be at least 1, not {df}"`

## `Taken` `@dataclass(frozen=True)`
`src/chatddx/bench/model.py:Taken`

* `taken: dict[str, int]`
* `kept: dict[str, int]`
* `choosing: dict[str, list[int]]`
* `missing: list[str]`

## `Titled` `@dataclass(frozen=True)`
`src/chatddx/bench/model.py:Titled`

* `name: str`
* `replaced: list[Replaced]`
* `at: str`
* `case: CaseTitle | None`
* `cases: int`
* `translated: str | None`
* `greedy: bool`
* `seeds: tuple[int, ...]`

## `trial`
`src/chatddx/bench/seen.py:trial`

* `seen: Seen`
* `skeleton: Skeleton`
* `engine: str`
* `cases: list[str]`
* `seeds: Sequence[int]`
* `cleanup: tuple[CleanupOp, ...] = ()`
* ∟`tuple[Registry, Trial]`

## `TriedVariation` `@dataclass(frozen=True)`
`src/chatddx/bench/variation.py:TriedVariation`

* `configuration: Edit`
* `name: str`
* `recipe: Recipe | None = None`
* `parts: Mapping[str, tuple[str | None, str]] = field(…)`

## `TriedVariation.held`
`src/chatddx/bench/variation.py:TriedVariation.held`

* `part: str`
* ∟`str | None`

## `TriedVariation.label` `@property`
`src/chatddx/bench/variation.py:TriedVariation.label`

* ∟`str`

## `TriedVariation.set`
`src/chatddx/bench/variation.py:TriedVariation.set`

* `part: str`
* `digest: str | None`
* `name: str`
* ∟`"TriedVariation"`

Raises:
1. `ValueError`: `"{self.name} has no recipe to set its {part} in"`
2. `ValueError`: `"a configuration always holds its {part}"`

## `TriedVariation.varied` `@property`
`src/chatddx/bench/variation.py:TriedVariation.varied`

* ∟`Recipe | None`

## `Updated` `@dataclass(frozen=True)`
`src/chatddx/bench/updating.py:Updated`

* `thread: int`
* `written: Written | None`
* `refused: ValueError | None`
* `remodelled: tuple[str, str] | None`

## `Valued` `@dataclass(frozen=True)`
`src/chatddx/bench/observed.py:Valued`

A finished score as a breakdown reads it, each value with its case, replicate
and view.

* `score: UUID`
* `at: datetime`
* `scorer: str`
* `values: tuple[tuple[str, int, int, float | None], ...]`

## `View`
`src/chatddx/bench/breakdown.py:View`

`type View = tuple[str, int]`

## `WITH`
`src/chatddx/bench/seen.py:WITH`

`WITH = re.compile(r"^(?P<family>.+?) with (?P<appendices>.+)$")`

## `word_of`
`src/chatddx/bench/model.py:word_of`

* `kind: str | None`
* ∟`str`

## `worded`
`src/chatddx/bench/seen.py:worded`

* `seen: Seen`
* `thread: int`
* ∟`tuple[Edit, About, str]`

## `WRITTEN`
`src/chatddx/bench/model.py:WRITTEN`

`WRITTEN: frozenset[str] = frozenset(…)`

## `Written` `@dataclass(frozen=True)`
`src/chatddx/bench/model.py:Written`

* `edit: Edit`
* `what: Literal["created", "a new version", "unchanged"]`
* `findings: list[Finding]`
* `cases: dict[str, str] = field(default_factory=dict)`
