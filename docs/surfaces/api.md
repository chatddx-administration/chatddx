# `api`

Written by `chatddx-dev index` from `[parts.api]`'s code in `settings.toml`, an entry for each public name, sorted alphabetically whatever its case, so that a class's members follow it, a language's after another's:

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

TypeScript and Svelte:

```
## `<name>` `async` `<<type parameters>>` `<extends or implements>` `<props' type>`
`<file>:<qualified name>`

<its JSDoc>

* `<parameter, field or prop>: <type> = <default>`
* ∟`<return type>`
```

- A module's entries are what it exports, a class's public members among them; a component's is named after its file, its props its bullets, followed by what its module script exports, and its heading gives its props' type only when the props don't spell it out.
- A type, an interface, an enum or a one-line constant is its declaration instead of bullets, fenced as TypeScript once it takes more than a line; a longer constant is its name, type and value.
- A value that takes more than a line or 60 characters is cut to `…`, a call to its callee's `(…)`.

- A stamp pending is a git conflict, from `<<<<<<< signed` to `=======` as last stamped and on to the `>>>>>>>` closing it as written now, till it is stamped.

## `again` `@router.post("/runs/{run}/again", …)`
`src/chatddx/api/runs.py:again`

* `request: Request`
* `response: Response`
* `bench: BenchDep`
* `run: UUID`
* `given: schemas.NewAgain`
* ∟`schemas.RunStartedData`

## `against`
`src/chatddx/api/standing.py:against`

What a review's gathering is to be scored by: of the scorers under the schema,
those a finished run isn't scored by as things are now, if `marked`, else none.

* `bench: Bench`
* `schema: str | None`
* `marked: bool`
* ∟`Callable[[RunStarted], list[str]]`

## `Answer` `(_Schema)`
`src/chatddx/api/schemas.py:Answer`

* `value: JsonValue = Field(…)`
* `problem: str | None = Field(…)`
* `salvaged: bool = Field(…)`

## `app`
`src/chatddx/api/app.py:app`

* `inventory: Inventory`
* `conninfo: str`
* `worker: bool = False`
* `synthetic: int | None = None`
* ∟`FastAPI`

## `appendix` `@router.post("/families/{family}/appendices", status_code=201)`
`src/chatddx/api/families.py:appendix`

* `request: Request`
* `response: Response`
* `bench: BenchDep`
* `family: int`
* `given: schemas.NewAppendix`
* ∟`schemas.MadeThread`

## `AppState` `@dataclass(frozen=True)`
`src/chatddx/api/state.py:AppState`

* `conninfo: str`
* `inventory: Inventory`
* `listener: Listener`
* `synthetic: int | None = None`

## `AppState.connect`
`src/chatddx/api/state.py:AppState.connect`

* ∟`Connection`

## `Asked` `(_Schema)`
`src/chatddx/api/schemas.py:Asked`

* `request: dict[str, JsonValue] = Field(…)`
* `picked: list[JsonValue] = Field(description="what the view picks of the data")`

## `Asking` `(_Schema)`
`src/chatddx/api/schemas.py:Asking`

* `judge: str = Field(description="a stored judge, by digest")`
* `expectation: str = Field(description="what a view picks of the expectation")`
* `data: JsonValue = Field(description="the expectation's data")`

## `baseline_cases`
`src/chatddx/api/standing.py:baseline_cases`

The World's baseline cases the person sees: the bare case of each family tagged
with its baseline tag, none when it names none. Reads the person's families.

* `bench: Bench`
* ∟`list[str]`

## `BEHIND`
`src/chatddx/api/listening.py:BEHIND`

`BEHIND = 1000`

## `Behind` `@dataclass(frozen=True)`
`src/chatddx/api/standing.py:Behind`

Why a configuration's latest gathering on the cases isn't whole in its shape as
things are now, and what Run does about it: runs it again on `rerun`'s seeds,
drawing those it doesn't hold, resumes `resume` and scores `rescore` again.

* `why: Why`
* `refusal: Exception | None = None`
* `language: str | None = None`
* `rerun: Seeds | None = None`
* `resume: tuple[UUID, ...] = ()`
* `rescore: tuple[UUID, ...] = ()`

## `bench`
`src/chatddx/api/people.py:bench`

* `request: Request`
* `conn: ConnDep`
* `person: Annotated[Person, Depends(signed_in)]`
* ∟`Bench`

## `BenchDep`
`src/chatddx/api/people.py:BenchDep`

`type BenchDep = Annotated[Bench, Depends(bench)]`

## `breakdown` `@router.get("/threads/{thread}/breakdown", dependencies=[Depends(no_store)])`
`src/chatddx/api/breakdown.py:breakdown`

How the configuration fared on the World's baseline cases: each baseline
gathering in the order they ran, each view's estimate over its cases, each case's
value and its difference from the gathering before, case by case; its means, how
far its repeats were from it, the baseline cases it left unanswered, and its
failed items, time and tokens; and the person's other configurations' latest
baselines on the views they share. Costs a read of each of the person's runs and
their scores, rows read before held.

* `bench: BenchDep`
* `thread: int`
* ∟`schemas.Broken`

Raises:
1. `NotFound`: `"this World names no baseline cases"`

## `Broken` `(_Schema)`
`src/chatddx/api/schemas.py:Broken`

* `name: str`
* `tag: str`
* `cases: int`
* `views: list[BrokenView]`
* `gatherings: list[BrokenGathering] = Field(description="in the order they ran")`
* `peers: list[BrokenPeer]`

## `BrokenGathering` `(_Schema)`
`src/chatddx/api/schemas.py:BrokenGathering`

* `digest: str = Field(description="the skeleton it ran")`
* `point: BrokenPoint`
* `estimates: list[Estimated | None] = Field(description="by view, over its cases")`
* `values: list[list[float]] = Field(description="by view, each case's value, sorted")`
* `paired: list[Estimated | None] = Field(…)`

## `BrokenLanguage` `(_Schema)`
`src/chatddx/api/schemas.py:BrokenLanguage`

* `language: str | None`
* `cases: int`

## `BrokenPeer` `(_Schema)`
`src/chatddx/api/schemas.py:BrokenPeer`

* `id: int`
* `name: str`
* `means: list[float | None] = Field(…)`
* `point: BrokenPoint`

## `BrokenPoint` `(_Schema)`
`src/chatddx/api/schemas.py:BrokenPoint`

* `started: UUID = Field(description="the gathering's first run")`
* `at: datetime`
* `version: int = Field(description="the configuration's version, from 1")`
* `means: list[float | None] = Field(description="by view, its replicates' mean")`
* `spread: list[float | None] = Field(…)`
* `alike: int = Field(description="answers its repeats gave alike to the letter")`
* `compared: int = Field(description="answers its repeats were compared on")`
* `languages: list[BrokenLanguage]`
* `failed: float = Field(description="the share of its items whose call failed")`
* `seconds: float = Field(description="an item's mean time")`
* `tokens: float | None = Field(description="an item's mean answer tokens")`
* `stale: bool = Field(description="not all of it scored as things are now")`
* `missing: int = Field(…)`

## `BrokenView` `(_Schema)`
`src/chatddx/api/schemas.py:BrokenView`

* `scorer: str`
* `view: int`
* `label: str = Field(description="the scorer's title and the view's label")`
* `field: str | None = Field(description="the expectation's field the view reads")`

## `canary_of`
`src/chatddx/api/events.py:canary_of`

* `call: CanaryCall`
* ∟`Named`

## `CanaryEndedData` `(_Schema)`
`src/chatddx/api/schemas.py:CanaryEndedData`

* `phase: str`
* `canary: int`
* `call: JsonValue`

## `Carried` `(_Schema)`
`src/chatddx/api/schemas.py:Carried`

* `language: str | None = Field(…)`
* `families: list[int]`
* `translated: bool`
* `skeleton: str | None = Field(description="the request they are sent as")`
* `refused: str | None = Field(description="why they can't be sent, and are left out")`
* `untranslated: bool = Field(…)`

## `case` `@router.post("/families/{family}/cases", status_code=201)`
`src/chatddx/api/families.py:case`

* `bench: BenchDep`
* `family: int`
* `given: schemas.NewCase`
* ∟`schemas.FamilyCase`

Raises:
1. `ValueError`: `"{given.replacing} isn't a case of family {family}"`

## `CaseTitle` `(_Schema)`
`src/chatddx/api/schemas.py:CaseTitle`

* `name: str = Field(description="its family's name, else its vignette's SOURCE/ID")`
* `appendices: list[str] = Field(description="its appendices' titles, in order")`
* `earlier: bool = Field(…)`

## `CaseTitle.of` `@classmethod`
`src/chatddx/api/schemas.py:CaseTitle.of`

* `titled: Titling`
* ∟`Self`

## `check` `@router.post("/components/check")`
`src/chatddx/api/world.py:check`

* `bench: BenchDep`
* `given: schemas.ComponentBody`
* ∟`schemas.Checked`

## `check_recipe` `@router.post("/recipes/check")`
`src/chatddx/api/world.py:check_recipe`

* `bench: BenchDep`
* `given: schemas.RecipeBody`
* ∟`schemas.Checked`

## `Checked` `(_Schema)`
`src/chatddx/api/schemas.py:Checked`

* `digest: str`
* `findings: list[Finding]`

## `Chunk`
`src/chatddx/api/schemas.py:Chunk`

`Chunk`

## `Code`
`src/chatddx/api/schemas.py:Code`

`Code`

## `CODES`
`src/chatddx/api/app.py:CODES`

`CODES: dict[int, Code] = {…}`

## `Compared` `(_Schema)`
`src/chatddx/api/schemas.py:Compared`

* `runs: list[Run]`
* `views: list[ComparedView] = Field(…)`
* `items: list[ItemKey] = Field(description="the items every run's trial holds")`
* `apart: list[HeldBySome] = Field(description="the cases only some of the runs hold")`

## `compared` `@router.get("/runs/compared")`
`src/chatddx/api/runs.py:compared`

* `bench: BenchDep`
* `run: Annotated[list[UUID], Query(min_length=1, max_length=20, description='the runs, in order')]`
* ∟`schemas.Compared`

## `ComparedView` `(_Schema)`
`src/chatddx/api/schemas.py:ComparedView`

* `scorer: str`
* `name: str`
* `view: int`
* `label: str`
* `means: list[float | None] = Field(…)`
* `values: list[list[float | None]] = Field(…)`

## `Component` `(_Schema)`
`src/chatddx/api/schemas.py:Component`

* `digest: str`
* `kind: str`
* `title: str`
* `body: JsonValue`

## `component` `@router.get("/components/{digest}")`
`src/chatddx/api/world.py:component`

* `bench: BenchDep`
* `digest: str`
* ∟`schemas.Component`

Raises:
1. `NotFound`: `"no component {digest} in the store"`

## `component_of`
`src/chatddx/api/threads.py:component_of`

* `doc: Mapping[str, JsonValue]`
* ∟`Component`

Raises:
1. `ValueError`: `"{kind!r} isn't a kind a person writes: the kinds are {", ".join(sorted(WRITTEN))}"`
2. `ValueError`: `"{kind} is at v{cls.schema_version}, not v{doc['v']}"`

## `ComponentBody`
`src/chatddx/api/schemas.py:ComponentBody`

`ComponentBody`

## `configurations`
`src/chatddx/api/standing.py:configurations`

The person's own configurations that generate, by name.

* `bench: Bench`
* ∟`list[schemas.Thread]`

## `ConnDep`
`src/chatddx/api/people.py:ConnDep`

`type ConnDep = Annotated[Connection, Depends(connection)]`

## `connection`
`src/chatddx/api/state.py:connection`

* `request: Request`
* ∟`Iterator[Connection]`

## `COOKIE`
`src/chatddx/api/people.py:COOKIE`

`COOKIE = "__Host-chatddx-session"`

## `DoneData` `(_Schema)`
`src/chatddx/api/schemas.py:DoneData`

* `halted: bool | None = Field(…)`

## `Draft` `(_Schema)`
`src/chatddx/api/schemas.py:Draft`

* `head: int | None = Field(…)`
* `before: Drafted = Field(…)`
* `after: Drafted = Field(default_factory=dict, description="the draft as it is now")`
* `translations: Into = Field(default_factory=dict)`

## `draft` `@router.post("/threads/{thread}/drafts")`
`src/chatddx/api/threads.py:draft`

The texts a configuration would hold with the chunks drafted, and the
translations given carried over to them, writing nothing.

* `bench: BenchDep`
* `thread: int`
* `given: schemas.Draft`
* ∟`schemas.Drafting`

## `Drafted`
`src/chatddx/api/schemas.py:Drafted`

`Drafted`

## `Drafting` `(_Schema)`
`src/chatddx/api/schemas.py:Drafting`

* `texts: dict[str, list[str]] = Field(…)`
* `translations: Into = Field(…)`

## `drop_cookie`
`src/chatddx/api/people.py:drop_cookie`

* `response: Response`
* ∟`None`

## `Edit` `(_Schema)`
`src/chatddx/api/schemas.py:Edit`

* `id: int`
* `digest: str`
* `compilation: str | None`
* `based_on: int | None`
* `by: str`
* `at: datetime`
* `labels: Labels | None = Field(default=None, description="a scorer edit's")`

## `edit` `@router.post("/threads/{thread}/edits", …)`
`src/chatddx/api/threads.py:edit`

* `response: Response`
* `bench: BenchDep`
* `thread: int`
* `given: schemas.NewEdit`
* ∟`schemas.MadeEdit`

Raises:
1. `HTTPException`: `422, "a configuration is written with parts, not a component"` (through `_check_given`)
2. `HTTPException`: `422, "only a configuration has parts"` (through `_check_given`)
3. `HTTPException`: `422, "only a configuration is forked from an edit: another kind from a component"` (through `_check_given`)
4. `HTTPException`: `422, "only a scorer has labels"` (through `_check_given`)
5. `ValueError`: `"an edit holds a component"`

## `edits` `@router.get("/threads/{thread}/edits")`
`src/chatddx/api/threads.py:edits`

* `bench: BenchDep`
* `thread: int`
* ∟`list[schemas.Edit]`

## `Endpoint` `(_Schema)`
`src/chatddx/api/schemas.py:Endpoint`

* `name: str`
* `engine: str`
* `title: str | None`
* `model: str | None`
* `serves: str | None = Field(description="the model its engine serves, by digest")`
* `url: str`
* `host: str | None`
* `capacity: int`
* `credential: str | None`
* `cleared_for: list[str]`
* `takes_typed: bool = Field(…)`
* `problem: str | None`

## `endpoints` `@router.get("/endpoints")`
`src/chatddx/api/world.py:endpoints`

* `bench: BenchDep`
* ∟`list[schemas.Endpoint]`

## `Error` `(_Schema)`
`src/chatddx/api/schemas.py:Error`

* `detail: str | list[JsonValue] = Field(…)`
* `code: Code`
* `pass_on: str | None = Field(…)`
* `wording: str | list[str] | None = Field(…)`
* `params: dict[str, str | int | float] | None = Field(…)`

## `Error.of` `@classmethod`
`src/chatddx/api/schemas.py:Error.of`

* `e: Exception`
* `code: Code`
* `detail: str | None = None`
* ∟`Self`

## `ErrorData` `(_Schema)`
`src/chatddx/api/schemas.py:ErrorData`

* `detail: str`

## `Estimated` `(_Schema)`
`src/chatddx/api/schemas.py:Estimated`

* `mean: float`
* `half: float | None = Field(…)`
* `n: int`

## `runs.EVENTS`
`src/chatddx/api/runs.py:EVENTS`

`` EVENTS = ", ".join(f"`{name}`" for name in schemas.EVENTS) ``

## `schemas.EVENTS`
`src/chatddx/api/schemas.py:EVENTS`

`EVENTS: dict[str, type[_Schema]] = {…}`

## `events` `@router.get("/runs/{run}/events", …)`
`src/chatddx/api/runs.py:events`

* `request: Request`
* `bench: BenchDep`
* `run: UUID`
* `last: Annotated[int | None, Header(alias='Last-Event-ID', description='the id of the last event had')] = None`
* ∟`StreamingResponse`

## `Expected` `(_Schema)`
`src/chatddx/api/schemas.py:Expected`

* `expectation_schema: str`
* `title: str`
* `expectation: str | None`
* `data: JsonValue`
* `ambiguous: str | None`
* `shared: list[Thread] = Field(…)`

## `families` `@router.get("/families")`
`src/chatddx/api/families.py:families`

* `bench: BenchDep`
* `tag: Annotated[list[str] | None, Query(description="any of these")] = None`
* `name: str | None = None`
* `deleted: Annotated[bool, Query(description="the person's own deleted families instead")] = False`
* ∟`list[schemas.Family]`

## `Family` `(_Schema)`
`src/chatddx/api/schemas.py:Family`

* `id: int`
* `name: str`
* `owner: str | None`
* `tags: list[str]`
* `language: str | None`
* `case: str`

## `family` `@router.get("/families/{family}")`
`src/chatddx/api/families.py:family`

* `bench: BenchDep`
* `family: int`
* ∟`schemas.FamilyDetail`

## `FamilyCase` `(_Schema)`
`src/chatddx/api/schemas.py:FamilyCase`

* `case: str`
* `title: str`
* `titled: CaseTitle`
* `appendices: list[str]`
* `default: bool = Field(description="the case the family stands for")`
* `expectations: list[Expected]`

## `FamilyDetail` `(Family)`
`src/chatddx/api/schemas.py:FamilyDetail`

* `description: str | None`
* `collaborators: list[str]`
* `deleted: bool`
* `cases: list[FamilyCase] = Field(…)`

## `FamilySaid` `(Said)`
`src/chatddx/api/schemas.py:FamilySaid`

* `language: str | None = Field(…)`

## `Fared` `(_Schema)`
`src/chatddx/api/schemas.py:Fared`

* `synthetic: bool = Field(description="whether any value is drawn rather than run")`
* `run: bool = Field(…)`
* `configurations: list[FaredConfiguration]`
* `metrics: list[FaredMetric]`
* `cases: list[FaredCase]`
* `rows: list[FaredRow]`

## `fared` `@router.get("/families/{family}/fared", dependencies=[Depends(no_store)])`
`src/chatddx/api/faring.py:fared`

How the case fares under each of the person's configurations on each view of the
scorers under the schema, among how every family's case fares: each the mean of its
latest gathering's replicates under a configuration, as `bench.gatherings` has it,
none where they ran but weren't scored, and, in a World that draws them, drawn where
none ran; and, under each configuration, what keeps the case's latest gathering from
being a whole 3+1 as things are now. Views in characters are left out, as they
aren't on the scale of the others.

Costs a read of each of the person's runs and their scores, finished scores held
once read, and what `standing` costs; the drawing is local.

* `request: Request`
* `bench: BenchDep`
* `family: int`
* `case: str`
* `expectation_schema: str`
* ∟`schemas.Fared`

Raises:
1. `NotFound`: `"no case {case} of family {family}"`

## `FaredBehind` `(_Schema)`
`src/chatddx/api/schemas.py:FaredBehind`

* `why: Literal['under_way', 'outdated', 'untranslated', 'refused', 'no_runs', 'not_whole', 'changed', 'halted', 'unfinished', 'unscored']`
* `refusal: Error | None = Field(default=None, description="a refused's refusal")`
* `language: str | None = Field(…)`

## `FaredCase` `(_Schema)`
`src/chatddx/api/schemas.py:FaredCase`

* `case: str`
* `family: int`
* `title: str`

## `FaredConfiguration` `(_Schema)`
`src/chatddx/api/schemas.py:FaredConfiguration`

* `id: int`
* `name: str`
* `behind: list[FaredBehind] = Field(…)`

## `FaredMetric` `(_Schema)`
`src/chatddx/api/schemas.py:FaredMetric`

* `scorer: str`
* `view: int`
* `label: str = Field(description="the scorer's title and the view's label")`
* `field: str | None = Field(description="the expectation's field the view reads")`

## `FaredReplicate` `(_Schema)`
`src/chatddx/api/schemas.py:FaredReplicate`

* `value: float | None = Field(description="null where it wasn't scored")`
* `href: str | None = Field(description="the page of its score, null where drawn")`

## `FaredRow` `(_Schema)`
`src/chatddx/api/schemas.py:FaredRow`

* `metric: int = Field(description="its metric, by position")`
* `configuration: int = Field(description="its configuration, by position")`
* `cases: list[int] = Field(description="the other cases, by position")`
* `values: list[float] = Field(description="each other case's mean, alike in order")`
* `synthetic: list[bool] = Field(description="whether each was drawn, alike in order")`
* `shown: FaredShown | None = Field(description="the case asked about, if it has one")`

## `FaredShown` `(_Schema)`
`src/chatddx/api/schemas.py:FaredShown`

* `value: float`
* `synthetic: bool`
* `replicates: list[FaredReplicate] = Field(…)`

## `Finding` `(_Schema)`
`src/chatddx/api/schemas.py:Finding`

* `level: Literal["info", "warning"]`
* `code: str`
* `message: str`
* `subject: str | None`
* `wording: str | list[str] | None = Field(…)`
* `params: dict[str, str | int | float] = Field(…)`

## `Finding.of` `@classmethod`
`src/chatddx/api/schemas.py:Finding.of`

* `finding: factors.Finding`
* ∟`Self`

## `fork` `@router.post("/threads/{thread}/forks", status_code=201)`
`src/chatddx/api/threads.py:fork`

* `request: Request`
* `response: Response`
* `bench: BenchDep`
* `thread: int`
* `given: schemas.NewFork`
* ∟`schemas.MadeThread`

Raises:
1. `HTTPException`: `422, "a configuration is written with parts, not a component"` (through `_check_given`)
2. `HTTPException`: `422, "only a configuration has parts"` (through `_check_given`)
3. `HTTPException`: `422, "only a configuration is forked from an edit: another kind from a component"` (through `_check_given`)
4. `HTTPException`: `422, "only a scorer has labels"` (through `_check_given`)

## `GatheredCase` `(_Schema)`
`src/chatddx/api/schemas.py:GatheredCase`

* `case: str`
* `language: str | None = Field(description="the language it went in")`
* `answered: bool = Field(description="whether its replicate answered without failing")`
* `alike: bool | None = Field(…)`
* `replicate: list[GatheredValue | None] = Field(description="by view")`
* `repeat: list[GatheredValue | None] = Field(description="by view")`
* `before: list[float | None] = Field(…)`

## `GatheredRun` `(_Schema)`
`src/chatddx/api/schemas.py:GatheredRun`

* `run: UUID`
* `language: str | None`
* `repeat: bool = Field(description="whether it repeats a replicate's seed")`

## `GatheredValue` `(_Schema)`
`src/chatddx/api/schemas.py:GatheredValue`

* `value: float`
* `score: UUID = Field(description="the score it is read from")`

## `Gathering` `(_Schema)`
`src/chatddx/api/schemas.py:Gathering`

* `configuration: int`
* `name: str`
* `tag: str`
* `cases: int = Field(description="the World's baseline cases now")`
* `views: list[BrokenView]`
* `gathering: BrokenGathering`
* `before: BrokenGathering | None = Field(…)`
* `runs: list[GatheredRun]`
* `rows: list[GatheredCase] = Field(…)`

## `gathering` `@router.get("/gatherings/{started}", tags=["runs"], dependencies=[Depends(no_store)])`
`src/chatddx/api/breakdown.py:gathering`

The baseline gathering begun by the run `started`: itself as its configuration's
breakdown has it, the gathering before it, its runs, each a replicate or a repeat,
and each case it sent or the World's baseline holds now, those first: the language
it went in, whether it was answered, and alike to the letter by its repeat, and by
view its replicate's value and score, its repeat's, and the gathering before's
value. Costs what the configuration's breakdown costs.

* `bench: BenchDep`
* `started: UUID`
* ∟`schemas.Gathering`

Raises:
1. `NotFound`: `"this World names no baseline cases"`
2. `NotFound`: `"no baseline of yours begun by run {started}"`

## `Graded` `(_Schema)`
`src/chatddx/api/schemas.py:Graded`

* `scorer: str`
* `name: str`
* `score: UUID | None`
* `scoring: str | None`
* `at: datetime | None`
* `finished: bool`
* `labels: list[str]`
* `means: list[float | None]`
* `items: list[ScoredItem]`
* `refused: str | None`

## `graded_of`
`src/chatddx/api/events.py:graded_of`

* `graded: benches.Graded`
* ∟`schemas.Graded`

## `halt` `@router.post("/runs/{run}/halt", …)`
`src/chatddx/api/runs.py:halt`

* `bench: BenchDep`
* `run: UUID`
* ∟`Response`

Raises:
1. `Refusing`: `409, e` (from `LookupError`)

## `Heard`
`src/chatddx/api/listening.py:Heard`

`type Heard = Message | Lagged`

## `Hearing`
`src/chatddx/api/listening.py:Hearing`

* `loop: asyncio.AbstractEventLoop`

## `Hearing.__init__`
`src/chatddx/api/listening.py:Hearing.__init__`

* `loop: asyncio.AbstractEventLoop`

## `Hearing.next`
`src/chatddx/api/listening.py:Hearing.next`

* `timeout: float`
* ∟`list[Heard]`

## `Hearing.put`
`src/chatddx/api/listening.py:Hearing.put`

* `heard: Heard`
* ∟`None`

## `HeldBySome` `(_Schema)`
`src/chatddx/api/schemas.py:HeldBySome`

* `case: str`
* `runs: list[UUID] = Field(description="the runs that hold it")`

## `Into`
`src/chatddx/api/schemas.py:Into`

`Into`

## `Item` `(_Schema)`
`src/chatddx/api/schemas.py:Item`

* `case: str`
* `replicate: int`
* `outcome: Outcome`
* `prompt_tokens: int`
* `completion_tokens: int`

## `item_ended_of`
`src/chatddx/api/events.py:item_ended_of`

* `skeleton: Skeleton`
* `item: RunItem`
* ∟`Named`

## `item_of`
`src/chatddx/api/events.py:item_of`

* `skeleton: Skeleton`
* `item: RunItem`
* ∟`schemas.Item`

## `item_started_of`
`src/chatddx/api/events.py:item_started_of`

* `case: str`
* `replicate: int`
* `seed: int`
* ∟`Named`

## `ItemDeltaData` `(_Schema)`
`src/chatddx/api/schemas.py:ItemDeltaData`

* `case: str`
* `replicate: int`
* `kind: Literal["reasoning", "content", "tool_call"]`
* `text: str`
* `tokens: int`

## `ItemDetail` `(Item)`
`src/chatddx/api/schemas.py:ItemDetail`

* `why: str | None`
* `vignette: JsonValue`
* `call: JsonValue`
* `turns: JsonValue`
* `answer: Answer`

## `ItemEndedData` `(Item)`
`src/chatddx/api/schemas.py:ItemEndedData`

* `why: str | None`

## `ItemKey` `(_Schema)`
`src/chatddx/api/schemas.py:ItemKey`

* `case: str`
* `replicate: int`

## `runs.items` `@router.get("/runs/{run}/items", dependencies=[Depends(no_store)])`
`src/chatddx/api/runs.py:items`

* `bench: BenchDep`
* `run: UUID`
* `case: Annotated[str | None, Query(description="only this case's items")] = None`
* ∟`list[schemas.ItemDetail]`

## `scores.items` `@router.get("/runs/{run}/scores/{score}/items", dependencies=[Depends(no_store)])`
`src/chatddx/api/scores.py:items`

* `bench: BenchDep`
* `run: UUID`
* `score: UUID`
* `case: Annotated[str | None, Query(description="only this case's items")] = None`
* ∟`schemas.ScoreItems`

## `ItemStartedData` `(_Schema)`
`src/chatddx/api/schemas.py:ItemStartedData`

* `case: str`
* `replicate: int`
* `seed: int`

## `ItemToolData` `(_Schema)`
`src/chatddx/api/schemas.py:ItemToolData`

* `case: str`
* `replicate: int`
* `tool: JsonValue`

## `judge_asked` `@router.post("/judges/asked")`
`src/chatddx/api/scores.py:judge_asked`

* `bench: BenchDep`
* `given: schemas.Asking`
* ∟`schemas.Asked`

Raises:
1. `NotFound`: `"no judge {given.judge} in the store"`

## `JudgeAnsweredData` `(_Schema)`
`src/chatddx/api/schemas.py:JudgeAnsweredData`

* `case: str`
* `replicate: int`
* `view: int`
* `judge: str`
* `seed_index: int`
* `verdict: JsonValue`
* `call: JsonValue`

## `JudgeAskedData` `(_Schema)`
`src/chatddx/api/schemas.py:JudgeAskedData`

* `case: str`
* `replicate: int`
* `scorer: str`
* `view: int`
* `judge: str`
* `seed_index: int`

## `judged_of`
`src/chatddx/api/events.py:judged_of`

* `event: ScoringEvent`
* ∟`Named | None`

## `JudgeDeltaData` `(_Schema)`
`src/chatddx/api/schemas.py:JudgeDeltaData`

* `case: str`
* `replicate: int`
* `kind: Literal["reasoning", "content", "tool_call"]`
* `text: str`
* `tokens: int`

## `KEEP_ALIVE`
`src/chatddx/api/telling.py:KEEP_ALIVE`

`KEEP_ALIVE = 15.0`

## `keep_cookie`
`src/chatddx/api/people.py:keep_cookie`

* `response: Response`
* `token: str`
* ∟`None`

## `Kin` `(Thread)`
`src/chatddx/api/schemas.py:Kin`

* `origin: int | None = Field(…)`
* `base: Edit | None = Field(…)`
* `varies: list[Varied] = Field(description="a fork's: what its head changes")`
* `behind: bool = Field(…)`
* `deleted: bool`

## `Kind` `(_Schema)`
`src/chatddx/api/schemas.py:Kind`

* `kind: str`
* `word: str = Field(description="the bench's word for it, as GET /api/threads takes")`
* `written: bool = Field(description="whether a person writes it")`
* `json_schema: dict[str, JsonValue] = Field(…)`

## `kinds` `@router.get("/kinds")`
`src/chatddx/api/world.py:kinds`

* `_: BenchDep`
* ∟`list[schemas.Kind]`

## `Labels` `(_Schema)`
`src/chatddx/api/schemas.py:Labels`

* `views: list[str | None] = Field(…)`
* `resources: list[str | None] = Field(…)`

## `Labels.given`
`src/chatddx/api/schemas.py:Labels.given`

* ∟`catalog.Labels`

## `Labels.of` `@classmethod`
`src/chatddx/api/schemas.py:Labels.of`

* `labels: Mapping[tuple[catalog.Part, int], str]`
* ∟`Self`

## `Lagged` `@dataclass(frozen=True)`
`src/chatddx/api/listening.py:Lagged`

## `Language`
`src/chatddx/api/schemas.py:Language`

`Language`

## `leave` `@router.post("/threads/{thread}/leave", status_code=204)`
`src/chatddx/api/threads.py:leave`

* `bench: BenchDep`
* `thread: int`
* ∟`Response`

## `leave_family` `@router.post("/families/{family}/leave", status_code=204)`
`src/chatddx/api/families.py:leave_family`

* `bench: BenchDep`
* `family: int`
* ∟`Response`

## `LeftOut` `(_Schema)`
`src/chatddx/api/schemas.py:LeftOut`

* `language: str`
* `cases: list[str]`
* `why: str`

## `lineage` `@router.get("/threads/{thread}/lineage")`
`src/chatddx/api/threads.py:lineage`

* `bench: BenchDep`
* `thread: int`
* ∟`list[schemas.Kin]`

## `Listener`
`src/chatddx/api/listening.py:Listener`

## `Listener.__init__`
`src/chatddx/api/listening.py:Listener.__init__`

* `conninfo: str`

## `Listener.heard` `@asynccontextmanager`
`src/chatddx/api/listening.py:Listener.heard`

* `run: UUID`
* ∟`AsyncGenerator[Hearing]`

## `Listener.stop`
`src/chatddx/api/listening.py:Listener.stop`

* ∟`None`

## `log`
`src/chatddx/api/listening.py:log`

`log = logging.getLogger(__name__)`

## `login`
`src/chatddx/api/threads.py:login`

* `bench: Bench`
* `person: int | None`
* ∟`str | None`

## `made`
`src/chatddx/api/threads.py:made`

* `request: Request`
* `response: Response`
* `bench: Bench`
* `thread: int`
* `findings: list[Finding]`
* ∟`schemas.MadeThread`

## `MadeEdit` `(Edit)`
`src/chatddx/api/schemas.py:MadeEdit`

* `findings: list[Finding]`
* `cases: dict[str, str] = Field(…)`

## `MadeThread` `(ThreadDetail)`
`src/chatddx/api/schemas.py:MadeThread`

* `findings: list[Finding]`

## `Me` `(_Schema)`
`src/chatddx/api/schemas.py:Me`

* `id: int`
* `login: str`
* `name: str`
* `roles: list[Role]`

## `me` `@router.get("/me")`
`src/chatddx/api/people.py:me`

* `person: Annotated[Person, Depends(signed_in)]`
* ∟`Me`

## `Me.of` `@classmethod`
`src/chatddx/api/schemas.py:Me.of`

* `person: Person`
* ∟`Self`

## `Measured` `(_Schema)`
`src/chatddx/api/schemas.py:Measured`

* `pattern: str | None`
* `problem: str | None = Field(…)`
* `answers: int = Field(description="how many answers the views read")`
* `found: int`
* `missed: int`
* `unscored: int`
* `alternatives: list[MeasuredAlternative] = Field(…)`
* `texts: list[MeasuredText] = Field(…)`

## `MeasuredAlternative` `(_Schema)`
`src/chatddx/api/schemas.py:MeasuredAlternative`

* `pattern: str`
* `found: int = Field(description="how many of what was found it finds")`

## `MeasuredMark` `(_Schema)`
`src/chatddx/api/schemas.py:MeasuredMark`

* `item: int`
* `start: int`
* `end: int`

## `MeasuredSeen` `(_Schema)`
`src/chatddx/api/schemas.py:MeasuredSeen`

* `run: UUID`
* `at: datetime`
* `replicate: int`
* `configuration: str`
* `view: str = Field(description="the scorer's title and the view's label")`
* `href: str | None = Field(description="the page of the score stored for it")`

## `MeasuredText` `(_Schema)`
`src/chatddx/api/schemas.py:MeasuredText`

* `texts: list[str] | None = Field(…)`
* `marks: list[MeasuredMark]`
* `found: bool | None = Field(…)`
* `value: float | None`
* `unit: str`
* `reason: str | None`
* `count: int = Field(description="how many times the views scored it")`
* `alternatives: list[int] = Field(…)`
* `seen: list[MeasuredSeen] = Field(…)`

## `Measuring` `(_Schema)`
`src/chatddx/api/schemas.py:Measuring`

* `case: str = Field(description="the case whose answers are read")`
* `expectation_schema: str = Field(…)`
* `data: JsonValue = Field(description="the expectation's data, as it is written now")`
* `field: str = Field(…)`

## `Metric` `(_Schema)`
`src/chatddx/api/schemas.py:Metric`

* `name: str`
* `measures: str`
* `params: dict[str, JsonValue] = Field(…)`
* `judged: bool = Field(…)`
* `unit: str | None = Field(…)`

## `ModelDigest`
`src/chatddx/api/schemas.py:ModelDigest`

`ModelDigest`

## `Named`
`src/chatddx/api/events.py:Named`

`type Named = tuple[str, BaseModel]`

## `new` `@router.post("/threads", status_code=201)`
`src/chatddx/api/threads.py:new`

* `request: Request`
* `response: Response`
* `bench: BenchDep`
* `given: schemas.NewThread`
* ∟`schemas.MadeThread`

## `NewAgain` `(Seeds)`
`src/chatddx/api/schemas.py:NewAgain`

* `score: bool = Field(…)`

## `NewAppendix` `(_Schema)`
`src/chatddx/api/schemas.py:NewAppendix`

* `text: str = Field(min_length=1)`
* `name: str = Field(min_length=1)`

## `NewCase` `(_Schema)`
`src/chatddx/api/schemas.py:NewCase`

* `appendices: list[str] | None = Field(None, description="the appendices, in order")`
* `replacing: str | None = Field(…)`

Raises:
1. `ValueError`: `"a case is built from appendices or replacing one, not both"` (through `NewCase._one`, in a `ValidationError`)

## `NewEdit` `(_Schema)`
`src/chatddx/api/schemas.py:NewEdit`

* `head: int = Field(description="the edit the change was made on: the head seen")`
* `parts: Parts = Parts()`
* `component: ComponentBody | None = None`
* `language: Language = None`
* `labels: Labels | None = Field(…)`

## `NewFork` `(_Schema)`
`src/chatddx/api/schemas.py:NewFork`

* `name: str = Field(min_length=1)`
* `head: int | None = Field(…)`
* `parts: Parts = Parts()`
* `component: ComponentBody | None = Field(…)`
* `language: Language = None`
* `labels: Labels | None = Field(…)`

## `NewResume` `(_Schema)`
`src/chatddx/api/schemas.py:NewResume`

* `score: bool = Field(…)`

## `NewRun` `(Seeds)`
`src/chatddx/api/schemas.py:NewRun`

* `configuration: int`
* `head: int | None = Field(…)`
* `parts: Parts = Parts()`
* `under: str | None = Field(…)`
* `families: list[int] | None = Field(…)`
* `tags: list[str] | None = Field(…)`
* `cases: list[str] | None = Field(…)`
* `cleanup: list[CleanupOp] | None = Field(…)`
* `concurrency: int | None = Field(…)`
* `order: Order | None = Field(…)`
* `score: bool = Field(…)`

Raises:
1. `ValueError`: `"a run takes one of families, tags or cases"` (through `NewRun._cases`, in a `ValidationError`)

## `NewSave` `(_Schema)`
`src/chatddx/api/schemas.py:NewSave`

* `head: int = Field(description="the edit the change was made on")`
* `name: str | None = Field(…)`
* `independent: bool = Field(…)`
* `chunks: Drafted = Field(default_factory=dict)`
* `model: ModelDigest = None`
* `translations: Into | None = Field(…)`

## `NewScoring` `(_Schema)`
`src/chatddx/api/schemas.py:NewScoring`

* `scorers: list[str] | None = Field(…)`

## `NewStop` `(_Schema)`
`src/chatddx/api/schemas.py:NewStop`

* `now: bool = Field(…)`

## `NewTake` `(_Schema)`
`src/chatddx/api/schemas.py:NewTake`

* `replace: bool = Field(…)`

## `NewTakes` `(_Schema)`
`src/chatddx/api/schemas.py:NewTakes`

* `families: list[int] = Field(min_length=1, description="the cases, by family")`
* `expectation_schema: str`
* `owner: str | None = Field(None, description="a login: that owner's only")`

## `NewThread` `(_Schema)`
`src/chatddx/api/schemas.py:NewThread`

* `component: ComponentBody | None = None`
* `recipe: dict[str, JsonValue] | None = Field(…)`
* `name: str | None = Field(…)`
* `language: Language = None`
* `labels: Labels | None = Field(None, description="for a scorer")`

Raises:
1. `ValueError`: `"a new thread holds a component or a recipe, not both"` (through `NewThread._one`, in a `ValidationError`)

## `NewTrialRuns` `(_Schema)`
`src/chatddx/api/schemas.py:NewTrialRuns`

* `trials: list[int] = Field(…)`
* `concurrency: int | None = Field(…)`
* `order: Order | None = Field(…)`
* `score: bool = Field(…)`

## `NewTyped` `(_Schema)`
`src/chatddx/api/schemas.py:NewTyped`

* `text: str = Field(description="the case as typed, kept as written")`
* `name: str | None = None`
* `language: str = Field(description="the language it is typed in, such as 'sv'")`
* `source: str | None = Field(…)`

## `NewUpdate` `(_Schema)`
`src/chatddx/api/schemas.py:NewUpdate`

* `head: int = Field(description="the edit the change was made on: the head seen")`
* `language: Language = None`

## `NO_STORE`
`src/chatddx/api/state.py:NO_STORE`

`NO_STORE = {"Cache-Control": "no-store"}`

## `no_store`
`src/chatddx/api/state.py:no_store`

* `response: Response`
* ∟`None`

## `OPEN`
`src/chatddx/api/standing.py:OPEN`

`OPEN = ("queued", "under way")`

## `Part` `(_Schema)`
`src/chatddx/api/schemas.py:Part`

* `part: str`
* `digest: str | None`
* `title: str | None`
* `summary: str | None`
* `replaced: bool`
* `landed: str | None = Field(…)`
* `nearest: list[str] = Field(…)`

## `Parts` `(_Schema)`
`src/chatddx/api/schemas.py:Parts`

* `instructions: Chunk = None`
* `few_shot: Chunk = None`
* `prompt: Chunk = None`
* `output: Chunk = None`
* `sampling: Chunk = None`
* `reasoning: Chunk = None`
* `passthrough: Chunk = None`
* `translations: Chunk = None`
* `toolset: Chunk = None`
* `model: ModelDigest = None`

## `Parts.given`
`src/chatddx/api/schemas.py:Parts.given`

* ∟`dict[str, str | None]`

## `pause` `@router.patch("/queue", …)`
`src/chatddx/api/queue.py:pause`

* `bench: BenchDep`
* `given: schemas.Paused`
* ∟`schemas.Queue`

## `Paused` `(_Schema)`
`src/chatddx/api/schemas.py:Paused`

* `paused: bool`

## `Picked` `(_Schema)`
`src/chatddx/api/schemas.py:Picked`

* `items: list[JsonValue] | None = Field(…)`
* `problem: str | None = Field(description="why the selector doesn't read")`

## `Picking` `(_Schema)`
`src/chatddx/api/schemas.py:Picking`

* `document: JsonValue = Field(…)`
* `selectors: list[str] = Field(…)`

## `picks` `@router.post("/picks")`
`src/chatddx/api/world.py:picks`

* `_: BenchDep`
* `given: schemas.Picking`
* ∟`list[schemas.Picked]`

## `Preview` `(_Schema)`
`src/chatddx/api/schemas.py:Preview`

* `head: int | None = Field(…)`
* `chunks: Drafted = Field(default_factory=dict)`
* `model: ModelDigest = None`
* `translations: Into | None = Field(…)`
* `language: str | None = Field(…)`

## `preview` `@router.post("/threads/{thread}/previews")`
`src/chatddx/api/threads.py:preview`

The request a configuration would send with the chunks, model and
translations drafted, writing nothing.

* `bench: BenchDep`
* `thread: int`
* `given: schemas.Preview`
* ∟`schemas.Previewed`

## `Previewed` `(_Schema)`
`src/chatddx/api/schemas.py:Previewed`

* `messages: list[PreviewMessage] = Field(…)`
* `request: dict[str, JsonValue] = Field(…)`
* `contract: dict[str, JsonValue] = Field(description="how the answer is held")`

## `PreviewMessage` `(_Schema)`
`src/chatddx/api/schemas.py:PreviewMessage`

* `role: str`
* `runs: list[Stretch]`

## `Proposal` `(_Schema)`
`src/chatddx/api/schemas.py:Proposal`

* `reasons: list[Literal['origin', 'facts', 'model', 'judge', 'engine']] = Field(…)`
* `about: str | None = Field(…)`
* `base: Edit | None = Field(…)`
* `origin_head: Edit | None`
* `varies: list[Varied] = Field(description="what its head changes of its base")`
* `clashes: list[str] = Field(…)`
* `remodelled: Remodelled | None = Field(…)`
* `recipe: JsonValue = Field(description="for a configuration, what it compiles from")`
* `component: JsonValue = Field(description="for another kind, its body")`
* `digest: str | None = Field(description="what updating comes to")`
* `compilation: str | None`
* `refused: str | None = Field(description="why updating is refused")`

## `proposal` `@router.get("/threads/{thread}/proposal")`
`src/chatddx/api/threads.py:proposal`

* `bench: BenchDep`
* `thread: int`
* ∟`schemas.Proposal | None`

## `Queue` `(_Schema)`
`src/chatddx/api/schemas.py:Queue`

* `paused: bool`
* `queued: int = Field(description="the person's jobs queued")`
* `under_way: int = Field(description="the person's jobs under way")`
* `workers: int = Field(…)`

## `queue` `@router.get("/queue")`
`src/chatddx/api/queue.py:queue`

* `bench: BenchDep`
* ∟`schemas.Queue`

## `Ran` `(_Schema)`
`src/chatddx/api/schemas.py:Ran`

* `configuration: int`
* `head: int = Field(description="the edit it varied")`
* `parts: dict[str, str | None] = Field(…)`

## `Reach` `(_Schema)`
`src/chatddx/api/schemas.py:Reach`

* `scorer: int`
* `name: str`
* `view: int`
* `label: str`
* `offered: bool`
* `cases: int`
* `missing: list[int]`
* `choosing: list[int]`

## `RecipeBody`
`src/chatddx/api/schemas.py:RecipeBody`

`RecipeBody`

## `Refusing` `(HTTPException)`
`src/chatddx/api/state.py:Refusing`

## `Refusing.__init__`
`src/chatddx/api/state.py:Refusing.__init__`

* `status: int`
* `refused: Exception`

## `Refusing.refused` `@contextmanager`
`src/chatddx/api/state.py:refused`

* `*named: type[Exception]`
* ∟`Generator[None]`

Raises:
1. `Refusing`: `422, e` (from `(ValueError, *named)`)

## `Remodelled` `(_Schema)`
`src/chatddx/api/schemas.py:Remodelled`

* `was: str = Field(description="the model its base is made for, by name")`
* `now: str = Field(description="the model its origin's head is made for, by name")`

## `rendered_again` `@router.get("/runs/{run}/rendered-again")`
`src/chatddx/api/runs.py:rendered_again`

* `bench: BenchDep`
* `run: UUID`
* ∟`list[schemas.RenderedAgain]`

## `RenderedAgain` `(_Schema)`
`src/chatddx/api/schemas.py:RenderedAgain`

* `case: str`
* `replicate: int`
* `same: bool`
* `why: str | None`

## `Replaced` `(_Schema)`
`src/chatddx/api/schemas.py:Replaced`

* `part: str`
* `title: str | None = Field(description="what it holds instead; null for nothing")`

## `resume` `@router.post("/runs/{run}/resume", …)`
`src/chatddx/api/runs.py:resume`

* `request: Request`
* `response: Response`
* `bench: BenchDep`
* `run: UUID`
* `given: schemas.NewResume`
* ∟`schemas.RunStartedData`

## `Rig` `(_Schema)`
`src/chatddx/api/schemas.py:Rig`

* `distribution: str`
* `version: str`
* `revision: str | None`

## `breakdown.router`
`src/chatddx/api/breakdown.py:router`

`router = APIRouter(tags=["threads"])`

## `families.router`
`src/chatddx/api/families.py:router`

`router = APIRouter(tags=["families"])`

## `faring.router`
`src/chatddx/api/faring.py:router`

`router = APIRouter(tags=["families"])`

## `measuring.router`
`src/chatddx/api/measuring.py:router`

`router = APIRouter(tags=["scores"])`

## `people.router`
`src/chatddx/api/people.py:router`

`router = APIRouter(tags=["people"])`

## `queue.router`
`src/chatddx/api/queue.py:router`

`router = APIRouter(tags=["queue"])`

## `runs.router`
`src/chatddx/api/runs.py:router`

`router = APIRouter(tags=["runs"])`

## `scores.router`
`src/chatddx/api/scores.py:router`

`router = APIRouter(tags=["scores"])`

## `threads.router`
`src/chatddx/api/threads.py:router`

`router = APIRouter(tags=["threads"])`

## `world.router`
`src/chatddx/api/world.py:router`

`router = APIRouter(tags=["world"])`

## `Run` `(_Schema)`
`src/chatddx/api/schemas.py:Run`

* `id: UUID`
* `at: datetime`
* `trial: str`
* `skeleton: str`
* `language: str | None = Field(description="the language its request is sent in")`
* `started_with: UUID | None = Field(…)`
* `engine: str`
* `endpoint: str | None`
* `model: str | None = Field(…)`
* `latest: bool = Field(description="whether it ran at its handle's latest engine")`
* `cases: list[str]`
* `seeds: list[int]`
* `described: str`
* `titled: Titled`
* `ran: Ran | None = Field(…)`
* `finished: bool`
* `unscored: list[Unscored] | None = Field(…)`
* `job: RunJob | None = Field(…)`

## `run` `@router.get("/runs/{run}")`
`src/chatddx/api/runs.py:run`

* `bench: BenchDep`
* `run: UUID`
* ∟`schemas.RunDetail`

## `RunDetail` `(Run)`
`src/chatddx/api/schemas.py:RunDetail`

* `rig: Rig`
* `finished_at: datetime | None`
* `noted: list[Finding]`
* `findings: list[Finding]`
* `items: list[Item]`
* `scores: list[Graded]`

## `RunFinishedData` `(_Schema)`
`src/chatddx/api/schemas.py:RunFinishedData`

* `findings: list[Finding]`

## `RunJob` `(_Schema)`
`src/chatddx/api/schemas.py:RunJob`

* `status: Literal["queued", "under way", "finished", "stopped", "failed"]`
* `why: str | None = Field(…)`
* `halt: bool = Field(description="whether it was asked to halt")`
* `ahead: int | None = Field(…)`
* `queued: datetime`
* `ended: datetime | None`

## `runs` `@router.get("/runs")`
`src/chatddx/api/runs.py:runs`

* `bench: BenchDep`
* `limit: Annotated[int, Query(ge=1, le=200)] = 20`
* `offset: Annotated[int, Query(ge=0)] = 0`
* `trial: Annotated[str | None, Query(description="a trial's digest")] = None`
* `reaching: Annotated[str | None, Query(description="a digest the run's trial is built on")] = None`
* `scored_by: Annotated[str | None, Query(description="a scorer's digest")] = None`
* `unscored: Annotated[bool, Query(description='only the finished runs left to be scored by some scorer')] = False`
* `started_with: Annotated[UUID | None, Query(alias='with', description='a run: the runs started with it, itself the first of them')] = None`
* `q: Annotated[str, Query(description="words each run's title says, whatever their case: its " + "configuration's, a part's replaced, its case's and its model's names")] = ""`
* ∟`list[schemas.Run]`

## `RunScoredData` `(_Schema)`
`src/chatddx/api/schemas.py:RunScoredData`

* `scores: list[Graded]`

## `RunStartedData` `(_Schema)`
`src/chatddx/api/schemas.py:RunStartedData`

* `run: UUID`
* `trial: str`
* `skeleton: str`
* `language: str | None = Field(description="the language its request is sent in")`
* `endpoint: str | None`
* `cases: list[str]`
* `seeds: list[int]`
* `greedy: bool`

## `Said` `(_Schema)`
`src/chatddx/api/schemas.py:Said`

* `name: str | None = Field(…)`
* `description: str | None = Field(None, description="null takes it away")`
* `tags: list[str] | None = Field(None, description="its tags")`
* `collaborators: list[str] | None = Field(…)`
* `deleted: bool | None = None`

## `said`
`src/chatddx/api/threads.py:said`

Says through `Bench.say` what `given` sets, leaving what it leaves unset as it
is. Each collaborator is looked up here as well as by the bench, so that an unknown
login is unprocessable rather than not found.

* `bench: Bench`
* `subject: Subject`
* `given: schemas.Said`
* ∟`None`

Raises:
1. `Invalid`: `"no person %(login)s", login=repr(missing[0])`

## `said_of`
`src/chatddx/api/events.py:said_of`

* `event: RunEvent`
* ∟`Named | None`

## `same_origin`
`src/chatddx/api/people.py:same_origin`

* `request: Request`
* ∟`None`

Raises:
1. `HTTPException`: `403, "a browser's request must come from this site's pages"`

## `save` `@router.post("/threads/{thread}/saves", …)`
`src/chatddx/api/threads.py:save`

Saves a configuration with the chunks given in place of its own, each written
to its own thread first, as a version of it or, named, a fork or one of its own.

* `request: Request`
* `response: Response`
* `bench: BenchDep`
* `thread: int`
* `given: schemas.NewSave`
* ∟`schemas.MadeThread`

Raises:
1. `HTTPException`: `422, "only a configuration is saved with its parts"`

## `say` `@router.patch("/threads/{thread}")`
`src/chatddx/api/threads.py:say`

Writes what the request changes of the person's own thread, a field left out
staying as it is, and answers what holds afterwards.

Costs a lookup per collaborator and what `Bench.say` reads and writes, then a read
of the thread.

* `bench: BenchDep`
* `thread: int`
* `given: schemas.Said`
* ∟`schemas.ThreadDetail`

## `say_of_family` `@router.patch("/families/{family}")`
`src/chatddx/api/families.py:say_of_family`

Writes what the request changes of the person's own family, its language too, a
field left out staying as it is, and answers what holds afterwards.

Costs a lookup per collaborator and what `Bench.say` reads and writes, then a read
of the family: each of its cases, and the expectations of each the person sees, by
expectation schema.

* `bench: BenchDep`
* `family: int`
* `given: schemas.FamilySaid`
* ∟`schemas.FamilyDetail`

## `score_item_of`
`src/chatddx/api/events.py:score_item_of`

* `item: ScoreItem`
* ∟`Named`

## `score_now` `@router.post("/runs/{run}/scores", …)`
`src/chatddx/api/scores.py:score_now`

* `request: Request`
* `response: Response`
* `bench: BenchDep`
* `run: UUID`
* `given: schemas.NewScoring`
* ∟`schemas.ScoringData`

## `score_started_of`
`src/chatddx/api/events.py:score_started_of`

* `bench: Bench`
* `scorer: str`
* `score: UUID`
* ∟`Named`

## `ScoredItem` `(_Schema)`
`src/chatddx/api/schemas.py:ScoredItem`

* `case: str`
* `replicate: int`
* `view: int`
* `value: float | None`

## `ScoreItemData` `(ScoredItem)`
`src/chatddx/api/schemas.py:ScoreItemData`

* `score: UUID`
* `detail: JsonValue`

## `ScoreItemDetail` `(ScoredItem)`
`src/chatddx/api/schemas.py:ScoreItemDetail`

* `detail: JsonValue`
* `judge_calls: JsonValue`

## `ScoreItems` `(_Schema)`
`src/chatddx/api/schemas.py:ScoreItems`

* `items: list[ScoreItemDetail]`
* `findings: list[Finding]`

## `scorer_code` `@router.get("/scorer-code")`
`src/chatddx/api/world.py:scorer_code`

* `_: BenchDep`
* ∟`list[schemas.ScorerCode]`

## `ScorerCode` `(_Schema)`
`src/chatddx/api/schemas.py:ScorerCode`

* `entry_point: str`
* `version: int`
* `metrics: list[Metric]`
* `params: dict[str, JsonValue] = Field(…)`

## `scores` `@router.get("/runs/{run}/scores")`
`src/chatddx/api/scores.py:scores`

* `bench: BenchDep`
* `run: UUID`
* `every: Annotated[bool, Query(alias='all', description='every score of the run, newest first, rather than the latest ' + 'under each scorer')] = False`
* ∟`list[schemas.Graded]`

## `ScoreStartedData` `(_Schema)`
`src/chatddx/api/schemas.py:ScoreStartedData`

* `scorer: str`
* `name: str`
* `score: UUID`
* `labels: list[str]`

## `scoring_of`
`src/chatddx/api/events.py:scoring_of`

* `bench: Bench`
* `run: RunStarted`
* `scorers: Collection[str] | None`
* ∟`schemas.ScoringData`

## `ScoringData` `(_Schema)`
`src/chatddx/api/schemas.py:ScoringData`

* `scorers: list[Unscored]`

## `schemas.Seeds` `(_Schema)`
`src/chatddx/api/schemas.py:Seeds`

* `seeds: list[int] | None = Field(…)`
* `replicates: int | None = Field(…)`

Raises:
1. `ValueError`: `"a run takes seeds or replicates, not both"` (through `Seeds._seeds_or_replicates`, in a `ValidationError`)

## `standing.Seeds`
`src/chatddx/api/standing.py:Seeds`

`type Seeds = Mapping[str, tuple[int, ...]]`

## `Session` `@dataclass(frozen=True)`
`src/chatddx/api/people.py:Session`

* `person: Person`
* `token: str`

## `session`
`src/chatddx/api/people.py:session`

* `request: Request`
* `conn: ConnDep`
* `bearer: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]`
* `cookie: Annotated[str | None, Depends(_cookie)]`
* ∟`Session`

Raises:
1. `HTTPException` (through `_unsigned`)
2. `HTTPException`: `"the session has ended: sign in again"` (through `_unsigned`)

## `sign_in` `@router.post("/session", status_code=201)`
`src/chatddx/api/people.py:sign_in`

* `request: Request`
* `response: Response`
* `given: SignIn`
* `conn: ConnDep`
* ∟`SignedIn`

Raises:
1. `HTTPException`: `"wrong login or password"` (through `_unsigned`)

## `sign_out` `@router.delete("/session", status_code=204)`
`src/chatddx/api/people.py:sign_out`

* `response: Response`
* `held: Annotated[Session, Depends(session)]`
* `conn: ConnDep`
* ∟`None`

## `signed_in`
`src/chatddx/api/people.py:signed_in`

* `held: Annotated[Session, Depends(session)]`
* ∟`Person`

## `SignedIn` `(_Schema)`
`src/chatddx/api/schemas.py:SignedIn`

* `token: str`
* `person: Me`

## `SignIn` `(_Schema)`
`src/chatddx/api/schemas.py:SignIn`

* `login: str`
* `password: str`

## `sse`
`src/chatddx/api/events.py:sse`

* `name: str`
* `data: BaseModel`
* `id: int | None = None`
* ∟`str`

## `stale`
`src/chatddx/api/standing.py:stale`

The scorers under the schema that the run, finished, isn't scored by as things
are now, by digest. Costs what `bench.unscored` costs.

* `bench: Bench`
* `run: RunStarted`
* `schema: str | None`
* ∟`list[str]`

## `Standing` `@dataclass(frozen=True)`
`src/chatddx/api/standing.py:Standing`

* `configuration: schemas.Thread`
* `runs: list[RunStarted]`
* `behind: list[Behind] = field(default_factory=list[Behind])`
* `version: int | None = None`

## `standing`
`src/chatddx/api/standing.py:standing`

How each configuration's latest gathering on the cases stands in the seedings'
shape, as `bench.latest_starts` has it: under way, or what keeps it from being
whole, in each language the cases are sent in and scored by what `left` gives, as
the cases and the configuration are now, at its version `at` when given, else at
its head. A case that can't be sent in its language keeps the whole gathering from
running.

Costs the person's runs read with their catalog rows and trials, their places in
the queue, and, for each configuration, the trial of each language built twice and
gated, and its finished runs given to `left`.

* `bench: Bench`
* `configurations: Sequence[schemas.Thread]`
* `cases: Sequence[str]`
* `seedings: tuple[Seeding, ...]`
* `left: Callable[[RunStarted], list[str]]`
* `at: int | None = None`
* ∟`list[Standing]`

Raises:
1. `NotFound`: `"no version {at}"`

## `start` `@router.post("/runs", …)`
`src/chatddx/api/runs.py:start`

* `request: Request`
* `response: Response`
* `bench: BenchDep`
* `given: schemas.NewRun`
* ∟`schemas.StartedRuns`

Raises:
1. `ValueError`: `"no case tagged {' or '.join(given.tags)} for {bench.person.login}"` (through `_new`)

## `start_trials` `@router.post("/runs/trials", …)`
`src/chatddx/api/runs.py:start_trials`

* `request: Request`
* `response: Response`
* `bench: BenchDep`
* `given: schemas.NewTrialRuns`
* ∟`schemas.StartedRuns`

## `started_of`
`src/chatddx/api/events.py:started_of`

* `started: RunStarted`
* `trial: Trial`
* `skeleton: Skeleton`
* `language: str | None`
* ∟`schemas.RunStartedData`

## `StartedRuns` `(_Schema)`
`src/chatddx/api/schemas.py:StartedRuns`

* `runs: list[RunStartedData] = Field(…)`
* `left_out: list[LeftOut] = Field(…)`

## `state`
`src/chatddx/api/state.py:state`

* `request: Request`
* ∟`AppState`

## `STATUSES`
`src/chatddx/api/app.py:STATUSES`

`STATUSES: dict[type[Exception], tuple[int, Code]] = {…}`

## `stop` `@router.post("/queue/stop", …)`
`src/chatddx/api/queue.py:stop`

* `bench: BenchDep`
* `given: schemas.NewStop`
* ∟`schemas.Stopped`

## `Stopped` `(_Schema)`
`src/chatddx/api/schemas.py:Stopped`

* `taken_out: list[UUID] = Field(…)`
* `halting: list[UUID] = Field(description="the runs under way asked to halt")`

## `STREAM`
`src/chatddx/api/runs.py:STREAM`

`STREAM = "text/event-stream"`

## `Stretch` `(_Schema)`
`src/chatddx/api/schemas.py:Stretch`

* `text: str | None = Field(…)`
* `origin: str | None = Field(default=None, description="the part the text came from")`
* `untranslated: bool = Field(…)`
* `slot: str | None = None`
* `appendix: int | None = Field(…)`

## `take` `@router.post("/threads/{thread}/takes", …)`
`src/chatddx/api/threads.py:take`

* `request: Request`
* `response: Response`
* `bench: BenchDep`
* `thread: int`
* `given: schemas.NewTake`
* ∟`schemas.ThreadDetail`

## `Taken` `(_Schema)`
`src/chatddx/api/schemas.py:Taken`

* `taken: dict[int, int] = Field(description="the thread each was taken into")`
* `kept: dict[int, int] = Field(description="the person's own, left as it is")`
* `choosing: dict[int, list[int]] = Field(…)`
* `missing: list[int] = Field(description="none shared")`

## `takes` `@router.post("/takes")`
`src/chatddx/api/families.py:takes`

* `bench: BenchDep`
* `given: schemas.NewTakes`
* ∟`schemas.Taken`

Raises:
1. `HTTPException`: `422, "no case {missing[0]} for {bench.person.login}"`

## `Telling`
`src/chatddx/api/telling.py:Telling`

* `last: int`

## `Telling.__init__`
`src/chatddx/api/telling.py:Telling.__init__`

* `bench: Bench`
* `run: UUID`
* `after: int`

## `Telling.rows`
`src/chatddx/api/telling.py:Telling.rows`

* ∟`list[str]`

## `Telling.run` `@property`
`src/chatddx/api/telling.py:Telling.run`

* ∟`UUID`

## `Telling.said`
`src/chatddx/api/telling.py:Telling.said`

* `said: Said`
* ∟`list[str]`

## `Telling.tail`
`src/chatddx/api/telling.py:Telling.tail`

* `job: Job | None`
* ∟`list[str]`

## `Thread` `(_Schema)`
`src/chatddx/api/schemas.py:Thread`

* `id: int`
* `kind: str`
* `word: str = Field(description="the word for its kind: configuration for a skeleton")`
* `name: str | None`
* `title: str`
* `owner: str | None`
* `tags: list[str]`
* `language: str | None = Field(description="its head's")`
* `translated: list[str] = Field(…)`
* `head: Edit`
* `outdated: bool = Field(…)`
* `expecting: CaseTitle | None = Field(…)`

## `thread` `@router.get("/threads/{thread}")`
`src/chatddx/api/threads.py:thread`

* `bench: BenchDep`
* `thread: int`
* ∟`schemas.ThreadDetail`

## `thread_of`
`src/chatddx/api/threads.py:thread_of`

* `bench: Bench`
* `kind: str`
* `edit: catalog.Edit`
* `about: catalog.About`
* `languages: Mapping[int, str | None] | None = None`
* ∟`schemas.Thread`

## `ThreadDetail` `(Thread)`
`src/chatddx/api/schemas.py:ThreadDetail`

* `description: str | None`
* `collaborators: list[str]`
* `forked_from: int | None`
* `recipe: JsonValue`
* `deleted: bool`

## `threads` `@router.get("/threads")`
`src/chatddx/api/threads.py:threads`

* `bench: BenchDep`
* `kind: Annotated[str, Query(description=f"one of {', '.join(KINDS)}")]`
* `name: str | None = None`
* `owner: Annotated[str | None, Query(description="a login")] = None`
* `tag: Annotated[list[str] | None, Query(description="any of these")] = None`
* `deleted: Annotated[bool, Query(description="the person's own deleted threads instead")] = False`
* `purpose: Annotated[Purpose | None, Query(description="a configuration's, generation unless given")] = None`
* `answers: Annotated[str | None, Query(description="a configuration's: the title of its answer's JSON Schema")] = None`
* ∟`list[schemas.Thread]`

Raises:
1. `HTTPException`: `422, "no kind {kind!r}: the kinds are {', '.join(KINDS)}"`
2. `HTTPException`: `422, "only a configuration has a purpose"`
3. `HTTPException`: `422, "only a configuration answers"`

## `Titled` `(_Schema)`
`src/chatddx/api/schemas.py:Titled`

* `name: str = Field(…)`
* `replaced: list[Replaced] = Field(…)`
* `at: str = Field(…)`
* `case: CaseTitle | None = Field(description="its case's title, when it ran one")`
* `cases: int`
* `translated: str | None = Field(…)`
* `greedy: bool`
* `seeds: list[int]`

## `told`
`src/chatddx/api/telling.py:told`

* `held: AppState`
* `person: Person`
* `run: UUID`
* `after: int`
* ∟`AsyncIterator[str]`

## `tool_of`
`src/chatddx/api/events.py:tool_of`

* `case: str`
* `replicate: int`
* `tool: ToolRun`
* ∟`Named`

## `Tried` `(_Schema)`
`src/chatddx/api/schemas.py:Tried`

* `run: UUID`
* `replicate: int`
* `views: list[TriedView]`

## `tried` `@router.post("/scorers/try", dependencies=[Depends(no_store)])`
`src/chatddx/api/scores.py:tried`

* `bench: BenchDep`
* `given: schemas.Trying`
* ∟`list[schemas.Tried]`

Raises:
1. `HTTPException`: `422, "only a scorer is tried"`

## `TriedView` `(_Schema)`
`src/chatddx/api/schemas.py:TriedView`

* `value: float | None`
* `detail: JsonValue`
* `judged: bool = Field(…)`

## `Trying` `(_Schema)`
`src/chatddx/api/schemas.py:Trying`

* `scorer: ComponentBody = Field(description="a scorer, as it is written")`
* `expectation: JsonValue = Field(description="what it is scored against, its data")`
* `case: str = Field(description="the case whose items are tried")`
* `runs: list[UUID] = Field(…)`

## `typed` `@router.post("/families", …)`
`src/chatddx/api/families.py:typed`

* `request: Request`
* `response: Response`
* `bench: BenchDep`
* `given: schemas.NewTyped`
* ∟`schemas.Family`

## `Unscored` `(_Schema)`
`src/chatddx/api/schemas.py:Unscored`

* `scorer: str`
* `name: str`

## `update` `@router.post("/threads/{thread}/update", …)`
`src/chatddx/api/threads.py:update`

* `bench: BenchDep`
* `thread: int`
* `given: schemas.NewUpdate`
* ∟`schemas.MadeEdit`

## `Variation` `(_Schema)`
`src/chatddx/api/schemas.py:Variation`

* `head: Edit`
* `label: str = Field(description="its name, and the chunks it replaces")`
* `skeleton: str`
* `held_by: Thread | None = Field(…)`
* `greedy: bool`
* `parts: list[Part] | None`
* `seed: int`
* `request: dict[str, JsonValue]`
* `model: str | None = Field(description="the handle it runs under")`
* `problem: str | None = Field(…)`
* `findings: list[Finding] | None`
* `languages: list[Carried] = Field(…)`
* `reach: list[Reach]`

## `variation` `@router.get("/threads/{thread}/variation")`
`src/chatddx/api/threads.py:variation`

* `bench: BenchDep`
* `thread: int`
* `query: Annotated[schemas.Varying, Query()]`
* ∟`schemas.Variation`

Raises:
1. `HTTPException`: `422, str(e)` (from `(NotFound, ValueError)`, through `_at`)

## `Varied` `(_Schema)`
`src/chatddx/api/schemas.py:Varied`

* `path: str`
* `base: JsonValue`
* `fork: JsonValue`

## `Varying` `(Parts)`
`src/chatddx/api/schemas.py:Varying`

* `head: int | None = Field(…)`
* `under: str | None = Field(…)`
* `tag: list[str] = Field(…)`
* `seed: int | None = Field(None, description="drawn when not given")`

## `Vignette` `(_Schema)`
`src/chatddx/api/schemas.py:Vignette`

* `source: str`
* `id: str`
* `text: str`
* `drifted: bool | None`

## `vignette` `@router.get("/families/{family}/vignette", dependencies=[Depends(no_store)])`
`src/chatddx/api/families.py:vignette`

* `bench: BenchDep`
* `family: int`
* ∟`schemas.Vignette`

Raises:
1. `NotFound`: `str(e)` (from `LookupError`)

## `Why`
`src/chatddx/api/standing.py:Why`

`Why`

## `api`
`frontend/src/lib/api/client.ts:api`

`const api = createClient<paths>();`

## `Schemas`
`frontend/src/lib/api/client.ts:Schemas`

`type Schemas = components["schemas"];`

## `why`
`frontend/src/lib/api/client.ts:why`

* `error: unknown`
* ∟`string`
