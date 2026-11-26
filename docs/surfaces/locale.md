# `locale`

Written by `chatddx-dev index` from `[parts.locale]`'s code in `settings.toml`, an entry for each public name, sorted alphabetically whatever its case, so that a class's members follow it, a language's after another's:

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

## `catalogs`
`src/chatddx/locale/locale.py:catalogs`

* `where: Path = _CATALOGS`
* ∟`list[Path]`

## `check`
`src/chatddx/locale/locale.py:check`

* ∟`None`

Raises:
1. `ValueError`: `"{where}:{lineno}: {msgid!r} is said both counted and not, which gettext holds as one message: give one a context"` (through `_extracted`)
2. `SystemExit`: `"locale: messages said alike: one message for one scenario, raised with upfirst where it starts a heading, a label or a sentence, or a context for what tells them apart"`
3. `SystemExit`: `"locale: {shown} behind the code: run chatddx locale write"`

## `CHOSEN`
`src/chatddx/locale/locale.py:CHOSEN`

`CHOSEN = "__Host-chatddx-locale"`

## `Coded` `(Protocol)`
`src/chatddx/locale/locale.py:Coded`

## `Coded.code` `@property`
`src/chatddx/locale/locale.py:Coded.code`

* ∟`str`

## `Coded.message` `@property`
`src/chatddx/locale/locale.py:Coded.message`

* ∟`str`

## `Coded.params` `@property`
`src/chatddx/locale/locale.py:Coded.params`

* ∟`Mapping[str, object]`

## `Coded.wording` `@property`
`src/chatddx/locale/locale.py:Coded.wording`

* ∟`str | Sequence[str] | None`

## `display_language`
`src/chatddx/locale/locale.py:display_language`

* `tag: str`
* ∟`str`

## `display_list`
`src/chatddx/locale/locale.py:display_list`

* `items: Sequence[str]`
* ∟`str`

## `gettext`
`src/chatddx/locale/locale.py:gettext`

* `message: str`
* ∟`str`

## `Locale` `@dataclass(frozen=True)`
`src/chatddx/locale/locale.py:Locale`

* `tag: str`
* `translations: NullTranslations`
* `islands: dict[str, str | list[str]] = field(default_factory=dict)`

## `Locale.name` `@property`
`src/chatddx/locale/locale.py:Locale.name`

* ∟`str`

## `Locales`
`src/chatddx/locale/locale.py:Locales`

* `by_tag: dict[str, Locale]`

## `Locales.__init__`
`src/chatddx/locale/locale.py:Locales.__init__`

* `catalogs: Path = _CATALOGS`

Raises:
1. `ValueError`: `"{path}: {e}"` (from `(PoFileError, ValueError)`, through `_locale`)
2. `ValueError`: `"{path}: {'; '.join(wrong)}"` (through `_locale`)

## `Locales.negotiate`
`src/chatddx/locale/locale.py:Locales.negotiate`

* `accept_language: str | None`
* `chosen: str | None = None`
* ∟`Locale`

## `localized`
`src/chatddx/locale/locale.py:localized`

* `coded: Coded`
* ∟`str`

## `Localizing`
`src/chatddx/locale/locale.py:Localizing`

* `app: ASGIApp`

## `localizing` `@contextmanager`
`src/chatddx/locale/locale.py:localizing`

* `locale: Locale`
* ∟`Generator[None]`

## `Localizing.__call__`
`src/chatddx/locale/locale.py:Localizing.__call__`

* `scope: Scope`
* `receive: Receive`
* `send: Send`
* ∟`None`

## `Localizing.__init__`
`src/chatddx/locale/locale.py:Localizing.__init__`

* `app: ASGIApp`

## `N_`
`src/chatddx/locale/locale.py:N_`

* `message: str`
* ∟`str`

## `ngettext`
`src/chatddx/locale/locale.py:ngettext`

* `singular: str`
* `plural: str`
* `n: int`
* ∟`str`

## `npgettext`
`src/chatddx/locale/locale.py:npgettext`

* `context: str`
* `singular: str`
* `plural: str`
* `n: int`
* ∟`str`

## `pending`
`src/chatddx/locale/locale.py:pending`

* ∟`None`

Raises:
1. `SystemExit`: `1`

## `pgettext`
`src/chatddx/locale/locale.py:pgettext`

* `context: str`
* `message: str`
* ∟`str`

## `pgettext_noop`
`src/chatddx/locale/locale.py:pgettext_noop`

* `_context: str`
* `message: str`
* ∟`str`

## `Proof` `@dataclass(frozen=True)`
`src/chatddx/locale/locale.py:Proof`

* `path: Path`
* `current: str | None`
* `written: str`
* `untranslated: int`

## `Proof.behind` `@property`
`src/chatddx/locale/locale.py:Proof.behind`

* ∟`bool`

## `proofs`
`src/chatddx/locale/locale.py:proofs`

* `tags: Iterable[str] = ()`
* `root: Path = settings.PROJECT_ROOT`
* `catalogs: Path = _CATALOGS`
* ∟`list[Proof]`

Raises:
1. `ValueError`: `"{where}:{lineno}: {msgid!r} is said both counted and not, which gettext holds as one message: give one a context"` (through `_extracted`)

## `refusal`
`src/chatddx/locale/locale.py:refusal`

* `wording: str | Sequence[str]`
* `params: Mapping[str, object]`
* ∟`str`

## `restamped`
`src/chatddx/locale/locale.py:restamped`

* `tag: str`
* `then: str | None`
* `now: str`
* `root: Path = settings.PROJECT_ROOT`
* ∟`str`

Raises:
1. `ValueError`: `"{where}:{lineno}: {msgid!r} is said both counted and not, which gettext holds as one message: give one a context"` (through `_extracted`)

## `said_alike`
`src/chatddx/locale/locale.py:said_alike`

The groups of a catalog's messages said alike: their words the same but for
case and the punctuation that ends them, in the same context or in one that says
only where the message comes from. What fills a message is named as it is said,
as a translation inflects by it. Costs a pass over the catalog.

* `catalog: Catalog`
* ∟`list[list[Message]]`

## `tr`
`src/chatddx/locale/locale.py:tr`

* `message: str`
* `/`
* `**values: object`
* ∟`str`

## `upfirst`
`src/chatddx/locale/locale.py:upfirst`

* `said: str`
* ∟`str`

## `whoops`
`src/chatddx/locale/locale.py:whoops`

* `message: str`
* ∟`str`

## `write`
`src/chatddx/locale/locale.py:write`

* `tags: Iterable[str]`
* ∟`None`

## `Catalog`
`frontend/src/lib/locale.ts:Catalog`

`type Catalog = { tag: string; messages: Record<string, string | string[]> };`

## `displayLanguage`
`frontend/src/lib/locale.ts:displayLanguage`

* `tag: string`
* ∟`string`

## `displayList`
`frontend/src/lib/locale.ts:displayList`

* `items: string[]`
* `type: "conjunction" | "disjunction" = "conjunction"`
* ∟`string`

## `localized`
`frontend/src/lib/locale.ts:localized`

* `coded: Coded`
* ∟`string`

## `refusal`
`frontend/src/lib/locale.ts:refusal`

* `detail: string`
* `wording: string | string[]`
* `params: Given`
* ∟`string`

## `speaking`
`frontend/src/lib/locale.ts:speaking`

* `given: Catalog`
* ∟`void`

## `t`
`frontend/src/lib/locale.ts:t`

* `message: string`
* `given: Given = {}`
* ∟`string`

## `th`
`frontend/src/lib/locale.ts:th`

* `message: string`
* `given: Given = {}`
* ∟`string`

## `tn`
`frontend/src/lib/locale.ts:tn`

* `singular: string`
* `plural: string`
* `n: number`
* `given: Given = {}`
* ∟`string`

## `tnp`
`frontend/src/lib/locale.ts:tnp`

* `context: string`
* `singular: string`
* `plural: string`
* `n: number`
* `given: Given = {}`
* ∟`string`

## `tp`
`frontend/src/lib/locale.ts:tp`

* `context: string`
* `message: string`
* `given: Given = {}`
* ∟`string`

## `upFirst`
`frontend/src/lib/locale.ts:upFirst`

* `said: string`
* ∟`string`

## `whoops`
`frontend/src/lib/locale.ts:whoops`

* `message: string`
* ∟`string`
