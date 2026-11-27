# `portal`

Written by `chatddx-dev index` from `[parts.portal]`'s code in `settings.toml`, an entry for each public name, sorted alphabetically whatever its case, so that a class's members follow it, a language's after another's:

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

## `answeredChoices`
`frontend/src/lib/scorer/scorers.ts:answeredChoices`

* `outputs: Output[]`
* ∟`Choice[]`

## `asked`
`frontend/src/lib/scorer/texts.ts:asked`

* `instructions: { role: string; segs: Seg[] } | null`
* `prompt: Seg[]`
* `guidance: Seg[] | null`
* `picked: unknown[] | null`
* ∟`Said[]`

## `Change`
`frontend/src/lib/thread/diff.ts:Change`

```ts
type Change =
  | { path: string; was: "added"; after: unknown }
  | { path: string; was: "removed"; before: unknown }
  | { path: string; was: "changed"; before: unknown; after: unknown; words: Words | null };
```

## `Changed`
`frontend/src/lib/thread/Changed.svelte:Changed`

* `before: unknown`
* `after: unknown`

## `changes`
`frontend/src/lib/thread/diff.ts:changes`

* `before: unknown`
* `after: unknown`
* `path = ""`
* ∟`Change[]`

## `Choice`
`frontend/src/lib/scorer/selectors.ts:Choice`

`type Choice = { label: string; selector: string };`

## `choices`
`frontend/src/lib/scorer/selectors.ts:choices`

* `schema: Schema | null`
* `data: unknown`
* `whole: string`
* ∟`Choice[]`

## `chosen`
`frontend/src/lib/scorer/selectors.ts:chosen`

* `selector: string`
* `among: Choice[]`
* ∟`Choice | undefined`

## `Chunk`
`frontend/src/lib/scorer/rewriting.ts:Chunk`

```ts
type Chunk = {
  digest: string;
  body: Record<string, unknown>;
  name: string;
  thread: number | null;
  head?: number;
  mine?: boolean;
  language?: string | null;
};
```

## `cn`
`frontend/src/lib/utils.ts:cn`

* `...inputs: ClassValue[]`

## `configurationChoices`
`frontend/src/lib/scorer/judging.ts:configurationChoices`

* `judging: Judging[]`
* `me: string`
* `held: Holding | null = null`
* ∟`Option[]`

## `editable`
`frontend/src/lib/scorer/texts.ts:editable`

* `segs: Seg[]`
* ∟`Seg[]`

## `FIELD`
`frontend/src/lib/utils.ts:FIELD`

`const FIELD = "h-8 rounded-md border border-input bg-transparent px-2";`

## `filled`
`frontend/src/lib/scorer/texts.ts:filled`

* `segs: Seg[]`
* `fills: Record<string, string>`
* ∟`string`

## `fillText`
`frontend/src/lib/scorer/texts.ts:fillText`

* `items: unknown[]`
* ∟`string`

## `Holding`
`frontend/src/lib/scorer/judging.ts:Holding`

`type Holding = { skeleton: string; configuration: string; weights: string; handle: string | null };`

## `Home`
`frontend/src/islands/Home.svelte:Home`

* `limit: number`
* `models: { name: string; weights: string }[]`

## `INSERTS`
`frontend/src/lib/scorer/texts.ts:INSERTS`

`INSERTS: Record<string, string> = {…}`

## `isInsert`
`frontend/src/lib/scorer/texts.ts:isInsert`

* `s: Seg`
* ∟`s is Insert`

## `isSlot`
`frontend/src/lib/scorer/texts.ts:isSlot`

* `s: Seg`
* ∟`s is Slot`

## `JudgeChoice`
`frontend/src/lib/scorer/judging.ts:JudgeChoice`

```ts
type JudgeChoice = {
  digest: string;
  thread: number;
  name: string;
  owner: string | null;
  configuration: string;
  model: string | null;
  seeds: number[];
  output_schema: Schema | null;
};
```

## `JudgeEditing`
`frontend/src/lib/scorer/JudgeEditor.svelte:JudgeEditing`

```ts
type JudgeEditing = Editing & {
    kind: "judge";
    body: { skeleton: string; model: string; seeds: number[]; fill?: string } | null;
    configuration: string | null;
    handle: string | null;
    problem: string | null;
    judging: Judging[];
    models: Serving[];
    me: string;
  };
```

## `JudgeEditor`
`frontend/src/lib/scorer/JudgeEditor.svelte:JudgeEditor`

* `editor: JudgeEditing`
* `digest?: string | null = null`
* `made?: (judge: JudgeChoice) => void`

## `JudgeFields`
`frontend/src/lib/scorer/JudgeFields.svelte:JudgeFields`

* `configurations: Option[]`
* `models: Option[]`
* `made: Record<string, string>`
* `hint?: string | null = null`
* `configuration: string = $bindable()`
* `weights: string = $bindable()`
* `seeds: string = $bindable()`

## `JudgeTexts`
`frontend/src/lib/scorer/JudgeTexts.svelte:JudgeTexts`

* `judge: Rewriting`
* `expectation: string`
* `data: unknown`
* `me: string`
* `made: (judge: Rewriting) => void`
* `left: () => void`

## `Judging`
`frontend/src/lib/scorer/judging.ts:Judging`

```ts
type Judging = {
  digest: string;
  thread: number;
  name: string;
  owner: string | null;
  output_schema: Schema | null;
  weights: string | null;
};
```

## `madeFor`
`frontend/src/lib/scorer/judging.ts:madeFor`

* `judging: Judging[]`
* `models: Serving[]`
* ∟`Record<string, string>`

## `merged`
`frontend/src/lib/scorer/texts.ts:merged`

* `segs: Seg[]`
* ∟`Seg[]`

## `modelChoices`
`frontend/src/lib/scorer/judging.ts:modelChoices`

* `models: Serving[]`
* `held: Holding | null = null`
* ∟`Option[]`

## `Option`
`frontend/src/lib/scorer/judging.ts:Option`

`type Option = { key: string; value: string; label: string };`

## `Part`
`frontend/src/lib/scorer/rewriting.ts:Part`

`type Part = keyof Texts["parts"];`

## `Rewriting`
`frontend/src/lib/scorer/JudgeTexts.svelte:Rewriting`

`type Rewriting = JudgeChoice & { texts: Texts; body: Record<string, unknown>; head: number };`

## `rewritten` `async`
`frontend/src/lib/scorer/rewriting.ts:rewritten`

* `judge: JudgeChoice & { texts: Texts; body: Record<string, unknown>; head: number }`
* `bodies: Partial<Record<Part, Record<string, unknown>>>`
* `me: string`
* ∟`Promise< { judge: JudgeChoice & { texts: Texts; body: Record<string, unknown>; head: number } } | { problem: string } >`

## `Said`
`frontend/src/lib/scorer/texts.ts:Said`

`type Said = { role: string; content: string };`

## `same`
`frontend/src/lib/scorer/selectors.ts:same`

* `selector: string`
* ∟`string`

## `same`
`frontend/src/lib/thread/diff.ts:same`

* `a: unknown`
* `b: unknown`
* ∟`boolean`

## `ScorerBody`
`frontend/src/lib/scorer/scorers.ts:ScorerBody`

```ts
type ScorerBody = {
  kind: "scorer";
  entry_point: string;
  version: number;
  expectation_schema: string;
  views: ScorerView[];
  resources?: string[];
  params?: Record<string, unknown>;
};
```

## `ScorerView`
`frontend/src/lib/scorer/scorers.ts:ScorerView`

```ts
type ScorerView = {
  output?: string;
  expectation?: string;
  split?: string | null;
  metric: string;
  judge?: string | null;
  params?: Record<string, unknown>;
};
```

## `ScorerViews`
`frontend/src/lib/scorer/ScorerViews.svelte:ScorerViews`

* `views: ScorerView[] = $bindable()`
* `labels: string[] = $bindable()`
* `judges: JudgeChoice[] = $bindable()`
* `metrics: Schemas["Metric"][]`
* `asked: Choice[]`
* `answered: Choice[]`
* `titles: Record<string, string>`
* `judging: Judging[]`
* `models: Serving[]`
* `me: string`
* `inline?: Snippet<[number]>`
* `below?: Snippet<[ScorerView, number, JudgeChoice | undefined]>`

## `Scoring`
`frontend/src/lib/scorer/scorers.ts:Scoring`

```ts
type Scoring = {
  metrics: Schemas["Metric"][];
  outputs: Output[];
  judges: JudgeChoice[];
  titles: Record<string, string>;
  judging: Judging[];
  models: Serving[];
  me: string;
};
```

## `seedsOf`
`frontend/src/lib/scorer/judging.ts:seedsOf`

* `text: string`
* ∟`number[]`

## `Seg`
`frontend/src/lib/scorer/texts.ts:Seg`

`type Seg = string | Slot | Insert;`

## `segmentsOf`
`frontend/src/lib/scorer/texts.ts:segmentsOf`

* `text: unknown`
* ∟`Seg[]`

## `SelectorPicker`
`frontend/src/lib/scorer/SelectorPicker.svelte:SelectorPicker`

* `choices: Choice[]`
* `value: string`
* `set: (v: string) => void`
* `label: string`

## `Serving`
`frontend/src/lib/scorer/judging.ts:Serving`

`type Serving = { name: string; weights: string };`

## `SLOTS`
`frontend/src/lib/scorer/texts.ts:SLOTS`

`SLOTS: Record<string, string> = {…}`

## `startingParams`
`frontend/src/lib/scorer/judging.ts:startingParams`

* `params: Schema`
* `schema: Schema | null`
* ∟`Record<string, unknown>`

## `textOf`
`frontend/src/lib/scorer/texts.ts:textOf`

* `segs: Seg[]`
* ∟`string | Seg[]`

## `Texts`
`frontend/src/lib/scorer/rewriting.ts:Texts`

```ts
type Texts = {
  configuration: { thread: number; head: number; mine: boolean; name: string } | null;
  recipe: Record<string, unknown>;
  parts: Record<"instructions" | "prompt" | "output", Chunk | null>;
};
```

## `TextSegments`
`frontend/src/lib/scorer/TextSegments.svelte:TextSegments`

* `segs: Seg[]`
* `set: (segs: Seg[]) => void`
* `slots?: string[] = []`
* `inserts?: string[] = []`
* `label: string`
* `quiet?: boolean = false`

## `verdictAt`
`frontend/src/lib/scorer/judging.ts:verdictAt`

* `schema: Schema | null`
* ∟`string[]`

## `WithElementRef` `<T, U extends HTMLElement = HTMLElement>`
`frontend/src/lib/utils.ts:WithElementRef`

`type WithElementRef<T, U extends HTMLElement = HTMLElement> = T & { ref?: U | null };`

## `WithoutChildren` `<T>`
`frontend/src/lib/utils.ts:WithoutChildren`

`type WithoutChildren<T> = T extends { children?: any } ? Omit<T, "children"> : T;`

## `worded`
`frontend/src/lib/kinds.ts:worded`

* `word: string`
* ∟`string`
