# Compatibility is decided by fields, not by entities

Why `regex_match` became `reciprocal_rank` over a list, what that does to
which parts of an agent go together, and what was changed so that a
compatibility table and a combinatorial batch have something to stand on.
Neither is built here.

## The question

A combinatorial batch builds an agent for every combination of the output
types, sampling params, instructions and connections chosen, each owned by
the archive and named by its parts. Not every combination is worth building,
and not every agent is worth scoring by every expectation. A compatibility
table is where that is said. Two pairs make the point:

- **A scorer assumes an output.** `reciprocal_rank` reads a ranked list of
  answers. It cannot read free text, and before this change there was no
  way to know that except by running it.
- **A sampling param assumes a model.** `low-reasoning`
  (`provider_params.openai_reasoning_effort`) is honoured by gpt-oss and
  ignored by qwen3, whose switch is
  `extra_body.chat_template_kwargs.enable_thinking` (`disable-thinking`).
  Ignored, not refused: the run succeeds and is labelled with a setting it
  never had.

## One rule

> Whether two things go together is a property of the fields that decide
> it, never of the entities that happen to carry those fields.

Everything below follows from it.

- Where the deciding fields are content, the verdict is **derived**: code
  computes it, nobody enters it. Whether a scorer can read an output type
  is a question about the output type's `definition`, and three output types
  that differ only in coercion strategy get one answer.
- Where they are knowledge about the world (what a model's chat template
  honours), the verdict has to be **declared**. It should be declared once,
  at the level where it is true: `openai/gpt-oss-20b` honours
  `openai_reasoning_effort`. Declared per pair of entities, the same fact
  is written again for every sampling params that carries the setting and
  every connection that reaches the model, and the table grows with every
  variant anyone makes.
- A verdict has three values: yes, no, unknown. A derived one can be
  unknown (a scorer whose command no code implements, or a schema the
  checker cannot read) and a declared one can be missing. The table should
  show unknown as unknown, and anything that prunes by it, such as a batch
  plan, should rule out only a no.

| Pair | Decided by | Kind | Here |
|---|---|---|---|
| scorer × output type | the scorer's contract against `output_schema(definition)` | derived | `Scorer.reads`: batch plan, experiment form |
| output type × connection | the pinned coercion strategy against the connection's resolved profile | derived | not built; `auto` takes the axis away for output types that pin nothing |
| sampling params × connection | the provider settings the params set, against what the model honours | declared, per (model, setting) | not built |
| sampling params × connection | whether pydantic-ai's model class sends a setting at all | derived | not built; see `top_k` and `n` below |
| instruction × output type | what the instruction asks for, against the definition | declared | not built |
| scorer × expectation | whether the scorer can parse the expectation's payload | derived | only when the run is scored |

## What stood in the way, and what was done

### A scorer read the transcript, and the transcript depends on coercion

Scorers read the text of the session's last assistant message. When an
output type coerces by `tool`, the structured reply arrives as a tool call,
so there is no text, and every such run scored 0 without an error. Under
`native` and `prompted` the text is JSON, and for anything that is not an
object it is wrapped (see below). So scoring was coupled to the coercion
strategy through the transcript.

Now the worker records what the agent returned, `result.output`, on the run
(`RunModel.output`, migration 0017). That value is the same whichever
strategy carried it. A scorer is a plain `(output, expected)` function and
no longer touches the ORM.

### A scorer's assumption lived only in its code

What a scorer can read is now registered next to it: `Scorer.accepts`, a
JSON Schema (`chatddx.eval.scorers`). Two things come from it.

- `Scorer.reads(definition)` decides whether the scorer can judge an output
  type, from the definition alone, before anything runs. It is
  `chatddx.core.json_schema.satisfies`, a conservative subsumption check:
  every value the definition admits has to be one the contract admits. It
  says yes only where it can prove it, for the keywords definitions and
  contracts here are written with (`type`, `items`, `properties`,
  `required`, `enum`/`const`, combinators, local `$ref`), and no
  everywhere else. A pairing it misses has to be made by hand. One it
  wrongly claimed would be a batch of runs that fail at scoring, so it errs
  the first way.
- `Scorer.check(output)` applies the same contract to a value before the
  output is judged. An output its scorer cannot read errors the run, with a
  message naming the scorer, where it used to score 0.

Both places that make experiments now ask. The batch plan leaves out
expectations whose scorer cannot read the agent's output and names those
scorers on the confirmation page. The experiment form refuses such an
expectation. A scorer whose command no code implements is unknown, so both
leave it in, and its runs fail at scoring with `unknown scorer`.

`reciprocal_rank(output, expected)`: `expected` is one pattern, in the same
`&`/`|`/parentheses grammar as before, and the first item of the list that
matches it decides the score, 100/rank, or 0 if none does. An expectation
used to have several rows, one acceptable answer per row with the best
first. Ranking is now the output's job, and a second line would otherwise
be read as more words of the first phrase, so a pattern of several lines is
rejected.

### The definition did not decide what a run returned

`build_output_type` turned `"array"` into a bare `list`. The items schema
never reached the model and the output was never validated. It matched
`"bool"`, which is not a JSON Schema type, and rejected `"string"`. So an
output type that is a list proper could not be asked for reliably, and a
compatibility derived from its definition would have been a claim about a
schema the runtime did not follow.

Now the definition decides:

- `output_schema(definition)` (`chatddx.repo.entities.output_type`) is the
  one place that says what a definition means: a definition with no type
  stands for free text.
- `build_output_type` builds from it: text as `str`, an object through
  `StructuredDict`, and anything else through `structured_value`, a type
  whose JSON Schema is the definition as written. pydantic-ai sends the
  model any non-object output as the single field of an object,
  `{"response": ...}`, because tool arguments and most structured output
  APIs accept only objects, and unwraps it on the way back.
  `Message.typed_content` unwraps it the same way (`builder.unwrap`).
- `validate_output` validates every structured output against its
  definition, not only dicts.
- The `diagnoses` output type is now a top-level ranked list of names, so
  the agents that use it can be scored by `reciprocal_rank`.

### Is it a mistake to couple coercion strategy with the definition?

Yes, as long as every output type has to carry one. The two fields vary with
different things and go together with different things:

- The **definition** is the contract. Scorers, instructions and anything
  that renders an output depend on it.
- The **coercion strategy** is a mechanism, and whether it works depends on
  the connection: `native` needs `supports_json_schema_output`, `tool` needs
  `supports_tools`, and `prompted` works everywhere. pydantic-ai keeps the
  default on the model profile (`default_structured_output_mode`), next to
  exactly those capabilities.

The coupling shows up in three ways:

- To vary coercion, a schema has to be copied three times
  (`diagnoses tool|native|prompted`). Every declared compatibility of the
  schema, such as instruction × output type, then has to be declared once
  per copy.
- A connection cannot say how it wants to be driven. The output type's
  field is never empty (it defaults to `native`), so it always overrides
  the profile's `default_structured_output_mode`. On a connection that
  cannot do native output, every structured run of an output type that
  never asked for anything fails.
- Free text carries a coercion strategy that means nothing.

It does no harm to derived compatibility as long as each check reads only
the field that decides it: scorer × output type reads the definition, and
output type × connection reads the strategy.

What was done: `CoercionChoices.AUTO`, which is pydantic-ai's own word for
it. An output type set to `auto` pins no strategy and leaves it to the
connection's profile. `build_model` already deferred to the profile for any
strategy that is not a pydantic-ai structured output mode; nothing could
ask it to until now. The default is still `native`, so no fingerprint that
exists today changes.

Two larger changes were considered and not made:

- **Moving coercion to the connection.** This recreates the problem on the
  other axis: every declared sampling params × connection verdict would be
  needed once per coercion variant of each connection. It is also a lossy
  migration. Output types that differ only by coercion would fingerprint
  alike and have to merge, with agents and experiments pointing at each of
  them.
- **Splitting the definition into an entity of its own.** That would give
  the schema a name. But a derived verdict needs the schema's content, not
  its name, and `output_schema(definition)` already provides the content.

The next step is to make `auto` the default and give each connection its
`default_structured_output_mode`. That changes the fingerprint of every
output type whose inventory entry names no strategy, and of the output type
`AgentTrailSchema` falls back to. It should be decided with the data in
view, not arrive as a side effect.

### Sampling params mix what every model honours with what one model does

- `seed-locked` (`seed`) works with any model. `low-reasoning` and
  `disable-thinking` are provider settings, and those are the only part of
  a sampling params with a compatibility partner. What a sampling params
  requires can be read from its content: the keys `build_config` puts in
  `ModelSettings`, and the paths inside `extra_body`. What a model honours
  cannot be read from anything and has to be declared, once per (model,
  setting).
- The two examples are the same control, how much the model thinks,
  written in two provider-specific forms. pydantic-ai has a portable form,
  `ModelSettings.thinking`, which it forwards where the profile says
  `supports_thinking`. For an OpenAI-compatible endpoint it becomes
  `reasoning_effort`, which qwen3's template ignores. A portable `thinking`
  setting, translated per connection, would remove this pair instead of
  tabulating it. Not done here, because it adds a sampling params field and
  so changes every sampling params' fingerprint.
- Some settings are dropped without a word. Every connection is driven
  through `OpenAIChatModel` whatever its `provider` says. That class does
  not send `top_k` (pydantic-ai lists Anthropic, Google, Cohere and
  Bedrock), and `n` is not a model setting at all. A sampling params that
  sets either is effectively compatible with no connection here, and
  nothing reports it.

### For the combinatorial batch

- **Agents owned by the archive.** A session names its agent by a branch
  (`SessionModel.default_agent`), and the worker looked only for the run
  owner's own, so an agent held by the archive could never run. It now
  takes the owner's branch, or failing that one shared with them
  (`qs_canon_col`), the way `init-data` shares the archive's branches.
- **Names built from components** must be injective over the product.
  `commit()` treats a new trail under an existing name as a new version of
  that branch, so two agents given the same name silently become two
  versions of one agent. Joining component names with spaces is not
  injective: `"a b" + "c"` and `"a" + "b c"` collide, and
  `seed-locked low-reasoning` already contains a space. The name needs a
  separator that names cannot contain, or the trail's short fingerprint as
  a suffix. The components also need names: a sampling params merged in an
  inventory (`sampling_params = ["seed-locked", "low-reasoning"]`) is
  committed by `commit_closure` as `sampling_params a1b2c3`.
- **A batch holds one agent** (`BatchModel.agent`). `plan()` now takes the
  agent, and its readability check (`_Reads`) is per agent, so a plan over
  many agents is a loop that yields (agent, case, expect) triples in place
  of pairs.

## Known, not fixed

- **Expectations that still name `regex_match`** no longer resolve. A run
  of one errors at scoring with `unknown scorer 'regex_match'`.
  Re-importing the cases (`init-data`) points each case at a
  `…|reciprocal_rank` expectation in place of its old one, and experiments
  already made keep the expectation they were made with. Runs already
  scored keep their results. There is no alias, on purpose: the old scorer
  read free text and ranked the rows of its expectation, and nothing reads
  that way any more.
- **`inform` has nowhere to put `__error__`** on a list or a bare value. The
  failure is logged and the output passes on unmarked. A scorer's check
  catches whatever its contract covers.
- **An expectation's payload is parsed only when it is scored.** A
  malformed pattern, or one in the old several-line format, errors its runs
  instead of the commit that introduced it.
- **`Message.typed_content` still raises** on a reply that does not validate
  against its definition. This predates the present change.

## Next

- The table. The derived axes come from `Scorer.reads` and from a coercion
  check still to be written against the connection's resolved profile
  (`build_model(...).profile`, so the check and the runtime cannot
  disagree). The declared axes should be keyed at the level the fact is
  true, (model, setting) and (instruction, definition), not per entity
  pair.
- Make coercion `auto` by default and have connections declare their mode.
- A portable `thinking` setting, translated per connection.
- Check an expectation's payload against its scorer when it is committed.
- Have the batch plan loop over agents, and name generated agents
  injectively.
