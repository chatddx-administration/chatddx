# Factors

`chatddx.factors` holds every kind of :Component, factors or not: the rules that keep each one valid, its :Digest and
:Canonical form, how components refer to each other, and the functions that read and combine them, which compile a
recipe, prepare a case, render a request, read a response, select what a view compares and lint. It reads and writes
nothing and imports nothing else of chatddx, and the rest of chatddx builds on it: the store keeps its components
(`src/chatddx/store/store.py:Store`), the catalog names and versions them, the runner sends what it renders, the ledger
writes its records on its `Frozen`, and `chatddx.facts` holds the files the facts are written in and the lints that read
them.

## Components

- A component is a frozen pydantic model whose `kind` has a literal default; a subclass whose `kind` has none, or a kind
  listed twice in `src/chatddx/factors/kinds.py:KINDS`, fails on import.
- Building one validates it whole, so a component that breaks a rule never exists, and `Component.model_copy` with
  changes validates again.
- Equivalent components share a digest, by their canonical form, and a component that can't be stored is refused when it
  is built: one holding U+0000 (`Component._storable`). NaN and infinity aren't refused yet (`docs/backlog.md`, "Values
  the canonical form can't keep").
- A kind's `schema_version` follows the policy at `src/chatddx/factors/base.py:Component.schema_version`, and a bump
  adds to the kind's `upgrades` the step from the version before. `parse_component` brings stored bytes of an older
  version up to the current one step by step, and refuses a version it has no step from
  (`src/chatddx/factors/base.py:upgraded`); a registry keeps what was stored as the component's bytes and digest
  (`src/chatddx/factors/bundle.py:Registry.add_raw`), and a bundle says `bundle.recanonicalized` of it.
- Text cleanup steps, schema ops, fill rules, splits and execution orders are named and versioned, as `strip@1` is, so
  that what names one means the same whatever the code becomes (`src/chatddx/factors/cases.py:CleanupOp`).

### References

A component refers to another by digest, under a type annotated with `RefTo` and the kinds it may refer to
(`SkeletonRef`, `ModelRef` and the rest). `iter_refs` finds each reference as a `RefSite`: its path, its kinds and the
digest. The store writes them as `factor.component_ref` rows, and a kind's JSON Schema names the kinds as `x-kind`,
which the API serves and the portal's fields read.

`Component.cross_check` holds a component to what it references and returns what doesn't hold, as text: a case's
appendices bound to its vignette, a skeleton's tools as its body offers them, a toolset's tools named once, a trial's
and a judge's skeleton of their purpose, a scoring's engines and expectations to its scorer and judges, a compilation's
facts and language to its recipe.

### Registry and bundle

A `Registry` holds components in memory by digest. `Registry.add_raw` reads stored bytes, refuses bytes that don't hash
to their digest, and keeps the bytes as read, so a component keeps its stored digest even where the running code would
write it otherwise. `Registry.closure` follows references; `Registry.check` refuses, in one `StructuralError` that lists
every problem, a reference that is missing or of another kind, and then what each component's cross-check returns. The
store adds and loads closures through a registry.

A :Bundle is a registry's closure from its roots, as canonical text, with the `Code` that wrote it. `Bundle.load` reads
one back and checks it, and notes `bundle.recanonicalized` for a component the running code writes otherwise. Nothing
but the tests writes or reads a bundle yet (`docs/backlog.md`, "Export and publication").

## Requests

### Compiling

`compile_request` turns a :Recipe into a :Skeleton (:Compiling), and `compiled` adds the :Compilation that names the
recipe, the compiler (`src/chatddx/rig.py:rig`), the facts when they were used and the language. In order:

1. `landings` works out the recipe's intents (:Intent) from the facts about its model: the level its reasoning lands on
   (:Land), and the level whose recommended sampling it follows. Facts are needed only for an intent.
2. Each text the recipe's chunks and appendix layout hold (`texts`) goes through one translation: none unless a language
   is asked for, and then every text must have an entry in it (`untranslated`).
3. The guidance is placed, inserted (:Insert) or by the policy in `compile_request`.
4. The messages: the instructions as a system or developer message, the few-shot examples, and the prompt as the user's.
5. The body: the passthrough, then what compiling manages over it: sampling, over the recommended values when it follows
   them; reasoning, as its level lands or as the chunk sets it; the toolset's tools, with `tool_choice` auto; and the
   :Contract, a native contract's `response_format`, a tool contract's :Answer tool offered last, or a text contract
   keeping the schema on itself.

### What a body may hold

The keys a request's body may hold fall into four sets in `src/chatddx/factors/request.py`: `RUNTIME_KEYS`, the rig's
own as it renders and sends; `OUTPUT_KEYS`, the contract's and the tools'; `MANAGED_KEYS`, sampling's and reasoning's;
and `BYPASS_KEYS`, which would go around the other factors (`docs/vllm.md`, "vLLM 0.24 discoveries", item 12). A
passthrough may set none of them; a skeleton's body and a canary's no runtime key.

A skeleton holds itself to what compiling makes, so a hand-written one is held to it too: its slots by its :Purpose,
`max_rounds` exactly when it has tools, its output keys by its contract, and the tools its body offers, each named once,
as its tools name them.

### Sending and reading

- `Skeleton.render` fills its slots (:Slot) and adds the model it is given, the :Served model name, the seed unless the
  skeleton is :Greedy, and `return_token_ids`. `Canary.render` renders a :Canary the same way, without slots.
- `next_request` adds to a request the response's assistant message and a tool message for each tool call, for the next
  :Tool round.
- `src/chatddx/factors/response.py` reads a response: its first choice's message, its reasoning under either key servers
  use, its well-formed tool calls, and its parts, reasoning, content, then tool calls.

## Engines and models

A local engine pins what makes vLLM compute as it does: its :Hardware, its :Runtime, its :Model's files, its chat
template's hash, and its own arguments and environment. A remote engine pins only its model, by provider and name. No
component holds where an engine is, which is its :Endpoint.

`LocalEngine.argv` may not set what the start-up sets or the engine pins (`OWNED_FLAGS`), pull arguments the digest
doesn't pin from a file (`UNPINNED_FLAGS`), abbreviate either, or hold a bare argument (`docs/vllm.md`, "vLLM 0.24
discoveries", items 8 and 11). `check_chat_template` checks a template against its engine where the file is, which today
is the o11n import (`src/chatddx/importers/o11n.py:imported`).

`model_of` gives an engine's model, or a model itself, whose name keys its facts (`LocalModel.name`).

## Facts

`ModelFacts` is a component but not a factor (:Facts), here so that compiling and the lints can read it.
`ReasoningFacts.landing` follows a :Level (reasoning) through its collapses (:Collapse) and nearests (:Nearest) to where
it lands, and facts whose collapses go round, or land on nothing, aren't built. What the facts refuse raises `Refused`,
which `landings` turns into a `StructuralError` naming the model.

## Cases

A :Case names its :Vignette by source, id and :Fingerprint, never by its text, and its appendices (:Appendix) must be
bound to the same vignette. `prepare_case` turns a case and the bytes its caller read from the vignette's source into
the fills of the vignette and appendices slots: it refuses a key other than the one the case was fingerprinted with,
notes `case.drift` when the bytes differ from the case's, refuses bytes that aren't UTF-8, applies the :Text cleanup to
the vignette, and joins the appendices by the :Appendix layout.

## Trials and execution

A :Trial pins one generation skeleton, one engine, its cases once each and in order, its text cleanup and its seeds, a
:Replicate each (`Trial.item_keys`). A :Canary set is a component and an :Instrument. An :Execution isn't a component: a
run records it (`docs/backlog.md`, "Execution settings as a component"). `Execution.schedule` puts a trial's items in
its order, and `Execution.overlaid` takes a start's concurrency and order over an endpoint's.

## Gatherings

A :Gathering binds runs about a :Center, a seed or a component of any kind but a gathering, to the groups it holds: each
run by its id, the trial it ran and the :Seeding it takes in its group, once at most
(`src/chatddx/factors/gathering.py:Gathering`). The seedings are data, each so many seeds, one of which may repeat a
seeding before it on that one's last seeds; `REVIEW` is a review's, three replicates and the third repeated, and
`BASELINE` a baseline's, a replicate and its seed repeated. Its cross-check holds each run's trial to its seeding
(`fits`), a repeat's to the trial it repeats on those seeds, by position when greedy. An item repeats another wherever
the two send the same request, in a gathering or not: the one-item trials they make, `Trial.single`, are one. How a run
is about the center is the source's to say, as a score reaches a scorer and no trial does. It pins its runs by id and
what they ran by digest, and guarantees nothing of how the runs compare: when or where they ran, or that they ran at
all. Nothing stores one yet.

`gather` makes one of runs found, each by its group's key (`src/chatddx/factors/gatherer.py:gather`): each seeding in
turn takes the first run of the group that fits it, so the order found is the preference, and the groups go by their
trials, so the same runs gather alike.

## Scoring

- An :Expectation is data for one case under an :Expectation schema. Building it doesn't check the data against the
  schema; linting does.
- A :Scorer pins the scoring code by entry point and version, and holds its views (:View). A view's selectors
  (:Selector) are parsed when it is built (`src/chatddx/factors/select.py`, whose scope is said there), and `split`
  breaks what it picks from an output into items (:Split). `reaches` tells whether a schema can hold what a selector
  picks, and `View.offered_by` whether an output's can: a view no judge reads isn't offered where its selector reaches
  only objects or arrays, which a pattern would read as JSON (`src/chatddx/factors/select.py:reaches_text`).
- A :Judge pins a judge skeleton without tools, a model, seeds and a :Fill rule. `Judge.fills` writes what a view picks
  into the completion and expectation slots.
- A :Scoring pins the engine each of its scorer's judges is sent to, which must serve the judge's model, and at most one
  expectation per case, under the scorer's expectation schema.

## Lints

`lint` checks components, each kind its own way (`src/chatddx/factors/lint.py`). Its findings, and where it is called,
are in `docs/glossary.md`, "Lints". Its caller gives it what this package can't know: the language of a skeleton or a
case (`languages`), whether an engine's model reasons by default (`reasons`), and the engine each judge is linted on
(`engines`). Its vLLM lints know vLLM 0.24 only; on any other engine, a skeleton's checks against it give
`schema.ref_unverified` alone.

## Errors and findings

- **On import**: a kind without a literal default, or listed twice, is a `TypeError`.
- **Building** a component, or a value inside one, that breaks a rule is pydantic's `ValidationError`, a `ValueError`,
  with the rule's message.
- **`StructuralError`**: components that don't hold together, or can't do what is asked of them: a digest that isn't
  there or is of another kind, bytes that aren't a readable component, a recipe that doesn't compile, a slot without a
  fill, a vignette that can't be read, a tool call without a result.
- **`Refused`**: what a model's facts refuse; compiling makes it a `StructuralError`.
- **Findings** (`Finding`, :Finding): the lints'; `bundle.recanonicalized`; `case.drift`, which the runner keeps in the
  run's finish record; and the chat template's, which the o11n import reports.

## Sensitive content

No component holds a vignette's text: a case names it by source, id and fingerprint. A fingerprint may be keyed
(`Fingerprint.of`), and none is yet (`docs/parts/clearance.md`, "Typed vignettes"). The fills `prepare_case` returns are
sensitive (`docs/chatddx.md`, "Vignettes and anything made from them are sensitive"), and so is what is made from them
here: a request `Skeleton.render` renders with them, the next request `next_request` makes, a response
`src/chatddx/factors/response.py` reads, and the fills `Judge.fills` writes from an answer. This package holds them only
as its caller does, and keeps and sends none of them; where they may go is the gate's
(`src/chatddx/runner/gate.py:bar`).
