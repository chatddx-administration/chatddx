# `catalog`

Written by `chatddx-dev index` from `[parts.catalog]`'s code in `settings.toml`, an entry for each public name, sorted alphabetically whatever its case, so that a class's members follow it, a language's after another's:

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

## `About` `(_Frozen)`
`src/chatddx/catalog/model.py:About`

* `name: str | None = None`
* `description: str | None = None`
* `tags: frozenset[str] = frozenset()`
* `owner: int | None = None`
* `collaborators: frozenset[int] = frozenset()`
* `deleted: bool = False`
* `language: str | None = None`
* `varied: int | None = None`
* `replaced: dict[str, str | None] = Field(default_factory=dict[str, str | None])`
* `started_with: UUID | None = None`

## `about`
`src/chatddx/catalog/read.py:about`

* `rows: Reader`
* `subject: Subject`
* ∟`About`

## `About.of` `@classmethod`
`src/chatddx/catalog/model.py:About.of`

* `entries: Iterable[Entry]`
* ∟`Self`

## `abouts`
`src/chatddx/catalog/read.py:abouts`

* `rows: Reader`
* `subjects: Collection[Subject]`
* ∟`dict[Subject, About]`

## `Behind` `(_Frozen)`
`src/chatddx/catalog/model.py:Behind`

* `path: str`
* `digest: str`
* `head: Edit | None = None`
* `binding: Binding | None = None`
* `replacement: str | None = None`

Raises:
1. `ValueError`: `"behind either a newer head or a newer binding"` (through `Behind._one`, in a `ValidationError`)
2. `ValueError`: `"a replacement case goes with a newer binding, and only with it"` (through `Behind._one`, in a `ValidationError`)

## `behind`
`src/chatddx/catalog/threads.py:behind`

* `rows: Reader`
* `thread: int`
* ∟`list[Behind]`

## `Binding` `(_Frozen)`
`src/chatddx/catalog/model.py:Binding`

* `id: int`
* `family: int`
* `vignette: Vignette`
* `by: int`
* `at: datetime`

## `case_title`
`src/chatddx/catalog/titles.py:case_title`

* `rows: Reader`
* `digest: str`
* ∟`CaseTitle | None`

## `CaseTitle` `@dataclass(frozen=True)`
`src/chatddx/catalog/titles.py:CaseTitle`

* `name: str`
* `appendices: tuple[str, ...]`
* `earlier: bool`

## `check_adoptable`
`src/chatddx/catalog/families.py:check_adoptable`

* `rows: Reader`
* `case: str`
* `*`
* `by_content: bool = True`
* ∟`Vignette`

Raises:
1. `LookupError`: `"{case} is not a stored case"`
2. `ValueError`: `"{case} gives family {other}'s vignette {change}; rebind the family"`

## `check_create`
`src/chatddx/catalog/threads.py:check_create`

* `rows: Reader`
* `digest: str`
* ∟`str`

Raises:
1. `LookupError`: `"{digest} is not in the store"`
2. `ValueError`: `"{kind} components have no threads"`

## `check_edit`
`src/chatddx/catalog/threads.py:check_edit`

* `rows: Reader`
* `thread_id: int`
* `digest: str`
* `*`
* `based_on: int | None = None`
* `head: int | None = None`
* `labels: Labels | None = None`
* ∟`None`

Raises:
1. `MovedOn`: `"thread %(thread)s has moved on since edit %(edit)s: its head is edit %(head)s", thread=thread_id, edit=head, head=current.id`
2. `ValueError`: `"edit {based_on} is not in the origin of thread {thread.id}"` (through `_check_based_on`)
3. `Self`: `"person %(owner)s owns an expectation of case %(case)s under that schema already, in thread %(thread)s", owner=owner, case=case, thread=others[0]` (through `_check_expectation`)
4. `ValueError`: `"a {thread.kind} has no views or resources to label"` (through `_check_labels`)
5. `ValueError`: `"{digest} has no {part} at position {position}"` (through `_check_labels`)
6. `Self`: `"the label of view %(position)s is empty", position=position` (through `_check_labels`)
7. `Self`: `"the label of resource %(position)s is empty", position=position` (through `_check_labels`)

## `check_language`
`src/chatddx/catalog/language.py:check_language`

* `rows: Reader`
* `digest: str`
* `value: str`
* ∟`str`

Raises:
1. `LookupError`: `"{digest} is not in the store"`
2. `ValueError`: `"{kind} components have no language of their own"`
3. `ValueError`: `"{digest}: a compiled skeleton's language comes from its recipe"`

## `check_note`
`src/chatddx/catalog/threads.py:check_note`

* `rows: Reader`
* `subject: Subject`
* `entry: Entry`
* ∟`None`

Raises:
1. `ValueError`: `"a language entry is for a family's vignette; a component's language is kept on its digest"`
2. `ValueError`: `"a {entry.field} entry is about a run, and what it ran"` (through `_check_ran`)
3. `ValueError`: `"edit {entry.value} is no configuration's"` (through `_check_ran`)
4. `ValueError`: `"{digest} isn't {what} in the store"` (through `_check_ran`)
5. `Self`: `"person %(owner)s owns an expectation of case %(case)s under that schema already, in thread %(thread)s", owner=owner, case=case, thread=others[0]` (through `_check_expectation`)

## `describe`
`src/chatddx/catalog/titles.py:describe`

* `component: Component`
* `title: Title`
* ∟`str`

## `display_count`
`src/chatddx/catalog/titles.py:display_count`

* `n: int`
* `one: str`
* `many: str | None = None`
* ∟`str`

## `display_digest`
`src/chatddx/catalog/titles.py:display_digest`

* `digest: str`
* ∟`str`

## `Divergence` `(_Frozen)`
`src/chatddx/catalog/model.py:Divergence`

* `base: Edit`
* `origin_head: Edit`
* `varies: dict[str, tuple[JsonValue, JsonValue]]`
* `moves: dict[str, tuple[JsonValue, JsonValue]]`

## `divergence`
`src/chatddx/catalog/threads.py:divergence`

* `rows: Reader`
* `id: int`
* ∟`Divergence | None`

Raises:
1. `LookupError`: `"no edit with id {id}"` (through `_edit`)

## `Divergence.clashes` `@property`
`src/chatddx/catalog/model.py:Divergence.clashes`

* ∟`list[str]`

## `Divergence.moved` `@property`
`src/chatddx/catalog/model.py:Divergence.moved`

* ∟`bool`

## `Edit` `(_Frozen)`
`src/chatddx/catalog/model.py:Edit`

* `id: int`
* `thread: int`
* `digest: str`
* `compilation: str | None`
* `based_on: int | None`
* `by: int`
* `at: datetime`

## `edit_languages`
`src/chatddx/catalog/language.py:edit_languages`

* `rows: Reader`
* `edits: Collection[Edit]`
* ∟`dict[int, str | None]`

## `Entry` `(_Frozen)`
`src/chatddx/catalog/model.py:Entry`

* `field: EntryField`
* `value: str | None = None`
* `person: int | None = None`
* `present: bool = True`

Raises:
1. `ValueError`: `"wrong value or person for {self.field}"` (through `Entry._shape`, in a `ValidationError`)
2. `ValueError`: `"{self.field} can't be removed, only replaced"` (through `Entry._shape`, in a `ValidationError`)
3. `ValueError`: `"{self.field} can't be empty"` (through `Entry._shape`, in a `ValidationError`)
4. `ValueError`: `"{self.value!r} is not an edit's id"` (through `Entry._shape`, in a `ValidationError`)
5. `ValueError`: `"{self.value!r} is not PART=DIGEST, or PART= for a part taken out"` (through `Entry._shape`, in a `ValidationError`)
6. `ValueError`: `"{self.value!r} is not a run's id"` (through `Entry._shape`, in a `ValidationError`)

## `Entry.replaced` `@classmethod`
`src/chatddx/catalog/model.py:Entry.replaced`

* `part: str`
* `digest: str | None`
* ∟`Self`

## `Entry.started_with` `@classmethod`
`src/chatddx/catalog/model.py:Entry.started_with`

* `run: UUID`
* ∟`Self`

## `Entry.varied` `@classmethod`
`src/chatddx/catalog/model.py:Entry.varied`

* `edit: int`
* ∟`Self`

## `EntryField` `(StrEnum)`
`src/chatddx/catalog/model.py:EntryField`

* `NAME = "name"`
* `DESCRIPTION = "description"`
* `TAG = "tag"`
* `OWNER = "owner"`
* `COLLABORATOR = "collaborator"`
* `DELETED = "deleted"`
* `LANGUAGE = "language"`
* `VARIED = "varied"`
* `REPLACED = "replaced"`
* `WITH = "with"`

## `expecting`
`src/chatddx/catalog/threads.py:expecting`

* `rows: Reader`
* `cases: Sequence[str]`
* `schema: str | None = None`
* ∟`dict[str, list[tuple[Edit, About]]]`

## `family_of`
`src/chatddx/catalog/families.py:family_of`

* `rows: Reader`
* `case: str`
* ∟`int | None`

## `find`
`src/chatddx/catalog/threads.py:find`

* `rows: Reader`
* `kind: str`
* `name: str`
* `*`
* `owner: int | None = None`
* ∟`list[int]`

## `forks`
`src/chatddx/catalog/threads.py:forks`

* `rows: Reader`
* `thread: int`
* ∟`list[int]`

## `head`
`src/chatddx/catalog/threads.py:head`

* `rows: Reader`
* `thread: int`
* ∟`Edit`

## `heads`
`src/chatddx/catalog/threads.py:heads`

* `rows: Reader`
* `kind: str`
* ∟`list[tuple[Edit, About]]`

## `heads_holding`
`src/chatddx/catalog/read.py:heads_holding`

* `rows: Reader`
* `digests: Collection[str]`
* ∟`dict[int, Edit]`

## `heads_of`
`src/chatddx/catalog/read.py:heads_of`

* `rows: Reader`
* `threads: Collection[int]`
* ∟`dict[int, Edit]`

## `history`
`src/chatddx/catalog/threads.py:history`

* `rows: Reader`
* `thread: int`
* ∟`list[Edit]`

Raises:
1. `LookupError`: `"no thread with id {thread}"`

## `holds`
`src/chatddx/catalog/threads.py:holds`

* `rows: Reader`
* `edit: Edit`
* `digest: str`
* `compilation: str | None`
* `labels: Labels | None = None`
* ∟`bool`

## `Labels`
`src/chatddx/catalog/model.py:Labels`

`Labels = Mapping[tuple[Part, int], str]`

## `labels`
`src/chatddx/catalog/read.py:labels`

* `rows: Reader`
* `edit: int`
* ∟`Labels`

## `LANGUAGE_KINDS`
`src/chatddx/catalog/model.py:LANGUAGE_KINDS`

`LANGUAGE_KINDS = frozenset(…)`

## `language_of`
`src/chatddx/catalog/language.py:language_of`

* `rows: Reader`
* `digest: str`
* ∟`str | None`

## `languages_of`
`src/chatddx/catalog/language.py:languages_of`

* `rows: Reader`
* `digests: Collection[str]`
* ∟`dict[str, str | None]`

## `MovedOn` `(Worded, ValueError)`
`src/chatddx/catalog/model.py:MovedOn`

## `origin`
`src/chatddx/catalog/threads.py:origin`

* `rows: Reader`
* `id: int`
* ∟`int | None`

Raises:
1. `LookupError`: `"no edit with id {id}"` (through `_edit`)

## `Part`
`src/chatddx/catalog/model.py:Part`

`Part = Literal["view", "resource"]`

## `picked`
`src/chatddx/catalog/threads.py:picked`

* `case: str`
* `choices: Mapping[int, str]`
* ∟`str | None`

Raises:
1. `Missing`: `"case %(case)s has expectations to choose from, in threads %(threads)s", case=case, threads=", ".join(str(t) for t in sorted(choices))`

## `plan_repair`
`src/chatddx/catalog/families.py:plan_repair`

* `rows: Reader`
* `family: int`
* `*`
* `id: str | None = None`
* `fingerprint: Fingerprint | None = None`
* ∟`RepairPlan`

Raises:
1. `LookupError`: `"no family with id {family}"` (through `_current`)
2. `ValueError`: `"a repair changes exactly one of the id or the fingerprint"`
3. `ValueError`: `"family {other} already has {taken}"`

## `proposal`
`src/chatddx/catalog/threads.py:proposal`

* `rows: Reader`
* `id: int`
* ∟`Recipe | Component | None`

## `Reader` `(Protocol)`
`src/chatddx/catalog/read.py:Reader`

## `Reader.bindings`
`src/chatddx/catalog/read.py:Reader.bindings`

* `families: Collection[int]`
* ∟`list[Binding]`

## `Reader.bindings_in`
`src/chatddx/catalog/read.py:Reader.bindings_in`

* `source: str`
* ∟`list[Binding]`

## `Reader.bindings_sharing`
`src/chatddx/catalog/read.py:Reader.bindings_sharing`

* `vignette: Vignette`
* ∟`list[Binding]`

## `Reader.bound_to`
`src/chatddx/catalog/read.py:Reader.bound_to`

* `vignettes: Collection[Vignette]`
* `kind: str`
* ∟`list[tuple[str, Vignette]]`

## `Reader.compilations`
`src/chatddx/catalog/read.py:Reader.compilations`

* `skeleton: str`
* ∟`list[Compilation]`

## `Reader.components`
`src/chatddx/catalog/read.py:Reader.components`

* `digests: Collection[str]`
* ∟`list[tuple[str, Component]]`

## `Reader.edit`
`src/chatddx/catalog/read.py:Reader.edit`

* `id: int`
* ∟`Edit | None`

## `Reader.edits`
`src/chatddx/catalog/read.py:Reader.edits`

* `threads: Collection[int]`
* ∟`list[Edit]`

## `Reader.edits_holding`
`src/chatddx/catalog/read.py:Reader.edits_holding`

* `digests: Collection[str]`
* ∟`list[Edit]`

## `Reader.entries`
`src/chatddx/catalog/read.py:Reader.entries`

* `subjects: Collection[Subject]`
* ∟`list[tuple[Subject, Entry, int]]`

## `Reader.expectations`
`src/chatddx/catalog/read.py:Reader.expectations`

* `cases: Collection[str]`
* ∟`list[str]`

## `Reader.get`
`src/chatddx/catalog/read.py:Reader.get`

* `digest: str`
* ∟`Component`

## `Reader.kind`
`src/chatddx/catalog/read.py:Reader.kind`

* `digest: str`
* ∟`str | None`

## `Reader.labels`
`src/chatddx/catalog/read.py:Reader.labels`

* `edits: Collection[int]`
* ∟`list[tuple[int, Part, int, str]]`

## `Reader.languages`
`src/chatddx/catalog/read.py:Reader.languages`

* `digests: Collection[str]`
* ∟`list[tuple[str, str]]`

## `Reader.thread`
`src/chatddx/catalog/read.py:Reader.thread`

* `id: int`
* ∟`Thread | None`

## `Reader.threads`
`src/chatddx/catalog/read.py:Reader.threads`

* `kind: str`
* ∟`list[Thread]`

## `Reader.threads_forked_from`
`src/chatddx/catalog/read.py:Reader.threads_forked_from`

* `edits: Collection[int]`
* ∟`list[Thread]`

## `recipe`
`src/chatddx/catalog/threads.py:recipe`

* `rows: Reader`
* `edit: Edit`
* ∟`Recipe | None`

## `recipe_language`
`src/chatddx/catalog/language.py:recipe_language`

* `rows: Reader`
* `recipe: Recipe`
* ∟`str | None`

## `RepairPlan` `@dataclass(frozen=True)`
`src/chatddx/catalog/families.py:RepairPlan`

* `vignette: Vignette`
* `registry: Registry`
* `cases: dict[str, str]`
* `appendices: dict[str, str]`
* `moves: list[tuple[int, str]]`

## `replacement`
`src/chatddx/catalog/families.py:replacement`

* `rows: Reader`
* `case: str`
* ∟`tuple[str, Registry]`

Raises:
1. `LookupError`: `"{case} has no family"`
2. `LookupError`: `"no family with id {family}"` (through `_current`)
3. `ValueError`: `"{case} is at its family's current vignette already"`

## `RUN_FIELDS`
`src/chatddx/catalog/model.py:RUN_FIELDS`

`RUN_FIELDS = frozenset({EntryField.VARIED, EntryField.REPLACED, EntryField.WITH})`

## `stale_cases`
`src/chatddx/catalog/families.py:stale_cases`

* `rows: Reader`
* `refs: list[tuple[str, str]]`
* ∟`list[Behind]`

Raises:
1. `LookupError`: `"no family with id {family}"` (through `_current`)

## `Subject` `(_Frozen)`
`src/chatddx/catalog/model.py:Subject`

* `thread: int | None = None`
* `family: int | None = None`
* `run: UUID | None = None`
* `score: UUID | None = None`

Raises:
1. `ValueError`: `"a subject is exactly one of a thread, a family, a run or a score"` (through `Subject._one`, in a `ValidationError`)

## `Survey` `(_Frozen)`
`src/chatddx/catalog/model.py:Survey`

* `unchanged: tuple[int, ...] = ()`
* `changed: tuple[tuple[int, str, Fingerprint], ...] = ()`
* `renamed: tuple[tuple[int, str, str], ...] = ()`
* `new: tuple[str, ...] = ()`
* `gone: tuple[int, ...] = ()`

## `survey`
`src/chatddx/catalog/families.py:survey`

* `rows: Reader`
* `source: str`
* `listing: Mapping[str, Fingerprint]`
* ∟`Survey`

## `tags_given`
`src/chatddx/catalog/read.py:tags_given`

* `rows: Reader`
* `subject: Subject`
* ∟`dict[str, int]`

## `Thread` `(_Frozen)`
`src/chatddx/catalog/model.py:Thread`

* `id: int`
* `kind: str`
* `forked_from: int | None`
* `by: int`
* `at: datetime`

## `thread`
`src/chatddx/catalog/threads.py:thread`

* `rows: Reader`
* `id: int`
* ∟`Thread`

Raises:
1. `LookupError`: `"no thread with id {id}"`

## `THREAD_KINDS`
`src/chatddx/catalog/model.py:THREAD_KINDS`

`THREAD_KINDS = frozenset(…)`

## `Title`
`src/chatddx/catalog/titles.py:Title`

`Title = Callable[[str], str]`

## `title`
`src/chatddx/catalog/titles.py:title`

* `rows: Reader`
* `thread: int`
* ∟`str`

## `title_of`
`src/chatddx/catalog/titles.py:title_of`

* `rows: Reader`
* `digest: str`
* ∟`str`

## `versions`
`src/chatddx/catalog/threads.py:versions`

Each edit of the thread by the version it holds, numbered by the first edit to
hold the same, as `holds` has it, so that an earlier version brought back is that
version again. Costs the thread's history and labels, and a recipe resolved for
each compilation.

* `rows: Reader`
* `thread: int`
* ∟`dict[int, int]`
