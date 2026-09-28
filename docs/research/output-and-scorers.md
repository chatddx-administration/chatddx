# Outputs and scorers

Research behind how chatddx reads an output and scores it: what inspect-ai
and pydantic-ai do, why scorers read views, how chatddx's own scoring
relates to inspect's, a judge for the diagnosis, and why scorers and
targets are kept in the registry. What is built is described in
`datamodel.md`; this note keeps the reasoning, the comparisons with the
libraries, and what is still open for judges and scoring. How runs become
inspect logs is in `backlog/export.md`.

## 1. Outputs and scorers

The concrete question: how does an inspect-ai scorer relate to a
pydantic-ai output type? This section first sets out what each library
does, then gives the answer.

### What inspect-ai does with an output

Read from inspect-ai 0.3.263:

- **A scorer is a function of the task state and a target.** `Scorer` is
  `async (state: TaskState, target: Target) -> Score`, and `Target` is one
  or more strings. Nothing declares what kind of output a scorer can read.
- **The answer is text, in one place.**
  - The built-in scorers that judge an answer read
    `state.output.completion`: `match`, `includes`, `pattern`, `answer`,
    `exact`, `f1`, `math`, `model_graded_qa` and `model_graded_fact`.
  - The exceptions are `choice`, which reads `state.choices`, and the
    perplexity scorers, which read log-probabilities.
  - The completion defaults to the text of the reply
    (`choices[0].message.text`), so a reply that is only a tool call has an
    empty completion. That is the trap PR #68 found in chatddx's own
    scorers, which read the last message's text.
- **Structured output is only a request option.**
  `GenerateConfig.response_schema` asks for JSON, and nothing parses the
  reply. A scorer gets the JSON as text.
- **An answer delivered another way is moved into the completion.**
  - inspect's own `react()` agent writes the `submit()` tool's argument into
    `state.output.completion` ("set the output to the answer for scoring").
    It is appended to any text the LLM wrote beside the call, or stands
    alone with `answer_only`.
  - By default the submit call is also removed from the messages.
  - So the mechanism that carried the answer never reaches the scorer.
- **A producer and its scorer are paired by convention.**
  - `multiple_choice()` writes the format instruction ("ANSWER: $LETTER"),
    parses the reply and marks `state.choices`.
  - `choice()` reads `state.choices`, and its docstring calls it "required
    by the `multiple_choice` solver".
  - Nothing checks the pairing: `choice()` scores a sample with no choices
    as incorrect.
  - This is the vertical slice again. Instruction, parsing and scoring form
    one unit, held together by name.
- **Typed data travels beside the text.**
  - `state.metadata_as(Model)` reads sample metadata into a frozen pydantic
    model, and `store_as` does the same for the store.
  - Re-scoring (`inspect score`, `score_async`) rebuilds the state from the
    logged sample's output, messages, metadata and store.
- **Scorers take arguments.** A scorer is a factory. Its arguments are
  recorded in the log header (`EvalScorer.options`) and on each score event
  (`scorer_args`).
- **Failures are attributed.**
  - `Score.reason` separates failures of the LLM under test
    (`invalid_response_format`, `refusal`, `no_response`) from failures of
    the instrument (`grader_failed`, `scoring_failed`).
  - `Score.unscored()` records a NaN that metrics and reducers skip.
- **Analysis reads metadata as columns.** `samples_df` flattens sample
  metadata into `metadata_*` columns beside the `score_*` columns.

In short, inspect has no output types. It has one text channel and typed
side channels, and it pairs what writes an answer with what reads it by
convention.

### What pydantic-ai does

Read from pydantic-ai 2.41.0:

- **The output type decides the value; the mode decides the transport.**
  - `NativeOutput`, `ToolOutput` and `PromptedOutput` wrap the same type.
  - `auto` takes the profile's `default_structured_output_mode`.
  - `result.output` is the same value whichever mode carried it.
- **A value that isn't an object travels in an envelope.** pydantic-ai asks
  for `{"response": …}` and unwraps it (`outer_typed_dict_key`), since tool
  arguments and most structured output APIs take only objects. chatddx
  holds every answer to an object instead (below).
- **Whether the schema is shown belongs to the mode.**
  - `NativeOutput` and `PromptedOutput` take a `template`, and `False`
    shows nothing.
  - On vLLM, the provider's profile sets
    `native_output_requires_schema_in_instructions`, because guided
    decoding "is pure token masking, so the model only sees the schema if
    it is also injected into the instructions".
- **Free text can be read into a value.** `TextOutput(fn)` passes the
  reply's text through a function. Its example splits the text into a
  list.

### The answer: scorers read views

**Decision:** a scorer never sees an output type, a mode or a transcript.
It reads a **view**: a named, typed reading of the output, declared by the
output variation.

- **Views are a small vocabulary kept in code** (`View` in
  `repo/entities/output/pydantic.py`). A view yields items, and each view
  names the JSON type of its items and whether a null may stand in for
  one:

  | View | Items | Read by |
  |---|---|---|
  | `text` | a string: an answer as written | `first_mention`; later, a model-graded judge |
  | `differential` | strings, most likely first | `reciprocal_rank` |
  | `warning` | a string, or null: a plan's red flags | `warning_mentions` |
  | `disposition` | a string: where a plan sends the patient | `disposition_mentions` |
  | `plan` (later) | workup, treatment and disposition | rubric scoring of management plans |

  The order of the vocabulary is fixed in code, since a `jsonb` column
  doesn't keep the order an output's views were written in.

- **An output variation declares the views it offers.**
  - A structured output gives each view as a path into its schema, in a
    subset of JSONPath: names and `[*]`.
  - Free text gives a named parser instead: `lines` for its
    `differential`, `whole` for its `text`.
  - An output offers only what it declares, `text` included: a structured
    output offers `text` only where a path proves a string.

  | Output | Its views |
  |---|---|
  | management plan | `differential` at `$.diagnoses[*].diagnosis`, `warning` at `$.acute_warning`, `disposition` at `$.management.disposition` |
  | diagnoses | `differential` at `$.diagnoses[*]` |
  | free text | `text` by `whole`; `differential` by `lines` |
  | raw | `text` by `whole` |
  | type check | none: it tests coercion, and has no clinical reading |

- **Reading a view.**
  - A path yields every value it reaches, in the document's order. A null
    is nothing reached, so a plan whose `acute_warning` is null yields no
    warning.
  - `lines` yields an item per non-empty line, with a leading list marker
    (`-`, `*`, `•`, `1.` or `1)`) stripped.
  - `whole` yields the answer as written, or nothing if it is blank.
  - A scorer gets each item as a string.

- **A path is proved when the output is committed.**
  - Walking the schema along the path gives the type of what the path
    yields, and that type must be the view's item type.
  - A name steps into a property an object declares under `properties`,
    and `[*]` steps into an array's `items`. A reference within the
    document is followed.
  - The check is conservative: a union, a nullable step or a reference
    outside the document is refused. A string is `type: string`, or an
    `enum` or `const` whose values are all strings. Only `warning` may end
    in `["string", "null"]`.
  - This is PR #68's conservative subsumption check (`core/json_schema.py`
    there), cut down to what views need. It runs once per output and view,
    instead of once per scorer and output type. What PR #68 registered with
    each scorer as `accepts` is registered with each view instead.
  - A path the check can't prove is refused at commit, and so is a free
    text view whose parser gives another view.
- **A scorer names its view as an argument:**
  `reciprocal_rank(view="differential")`. inspect records the argument with
  every score.
- **So scorer × output is set membership:** does the output offer the view?
  Pairing needs no schema reasoning, and a new output variation needs no
  new scorer.
- **Views are fingerprinted.** They change no request, but they decide
  what is measured, so a score can cite exactly which reading it applied
  (`datamodel.md`).
- **A parser is a view, not an output mode.** pydantic-ai's `TextOutput`
  would parse at generation time and keep only the parsed value. chatddx
  keeps the text and parses when scoring, so a parser can be fixed without
  generating again.

On the pydantic-ai side, the output and coercion variations together build
the output spec:

| Coercion mode | Output with a schema | Free text |
|---|---|---|
| native | `NativeOutput(T, template=False)` | `str` |
| tool | `ToolOutput(T, name="final_result", description=…)`, the description being the coercion's `tool_description` | `str` |
| prompted | `PromptedOutput(T, template=False)` | `str` |

- **An answer is held to an object.** `T` is `StructuredDict` of the
  schema. A schema whose top level isn't an object is refused at
  resolution, so no answer travels in pydantic-ai's envelope, and a run's
  `answer` is the answer as the LLM gave it.
- **The schema a request carries is chatddx's to say.** Resolution inlines
  its references and drops `$defs`, so pydantic-ai is left with nothing to
  make of it but a sort of its keywords; the properties keep the order they
  were written in. A schema that refers to itself can't be sent, and is
  refused.
- `template` is always `False`. The schema prompt, when there is one,
  reaches the LLM through the `schema_prompt` slot, never through
  pydantic-ai's default text. It shows the schema as written, not inlined.
- `auto` is resolved to one of the three from the LLM's facts before the
  spec is built. Left to pydantic-ai, it would also bring the profile's
  default template along on vLLM.
- **No words of pydantic-ai's own reach the LLM.** The profile is
  pydantic-ai's default, then its vLLM provider's, then the LLM's facts,
  then chatddx's own on top: no JSON schema transformer, no schema added to
  the instructions, no JSON object mode, and no OpenAI reasoning field. The
  LLM's facts give the profile instead of the served name.
- **A run asks once.** Nothing is retried: an answer that doesn't hold is
  recorded, not asked for again. An LLM may call tools for five rounds,
  and a run still calling them after that stops with no answer.
- **What isn't an OpenAI field goes in `extra_body`:** `top_k`, and
  whatever the reasoning facts write (`chat_template_kwargs`,
  `reasoning_effort`, `thinking_token_budget`). The trial's seed goes out
  as `seed`.

On the inspect side, a scorer reads its view from the sample:

```python
@scorer(metrics=[mean(), stderr()])
def reciprocal_rank(view: str = "differential") -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        # the output's views travel in the sample's metadata
        ranked = state.metadata_as(Trial).read(view, state.output.completion)
        if ranked is None:
            return Score(value=0, reason="invalid_response_format")
        rank = first_rank(ranked, pattern=target.text)
        return Score(
            value=1 / rank if rank else 0,
            answer=ranked[rank - 1] if rank else None,
        )

    return score
```

### What a run records, and what the log carries

- **A run records the value, not only the transcript.** `answer` is
  `result.output`, the same whichever mode carried it (PR #68's
  `RunModel.output`): an object for a structured output, the text for free
  text. `valid` says whether it holds to the output's schema. It is null
  for free text. It is false where no answer that parses came, and then
  there is no answer, and where one parsed but doesn't hold, and then the
  answer is kept.
- **chatddx scores its runs, and inspect scores logs of them the same
  way.** chatddx holds each run to the registry's scorers in its database
  (below, How chatddx scores). A log of the runs is scored by inspect with
  the same functions, to the same values (below, inspect scores the log).
### When an output can't be read

These are the rules for when inspect scores with scorers of its own.
chatddx's scorers keep theirs until then (below), in a log too.

- **Refused before running.** A cell whose output lacks a view that a
  scorer reads is refused for that scorer when the cell is resolved.
  If no scorer is left, the cell isn't generated.
- **Unreadable at scoring.**
  - An output that isn't valid, or whose view yields a value that fails
    the view's schema, scores 0 with `reason = "invalid_response_format"`.
    That is the LLM's failure, and it counts as a miss.
  - A reply cut off at `max_tokens` scores 0 with `reason = "truncated"`
    instead. `data-generation.md` §4 keeps a truncated answer apart from a
    wrong one.
  - `Score.unscored()` would drop these from the mean, which flatters a
    configuration that often fails. The reason keeps the rate countable.
- **The instrument's fault.** A target the scorer can't parse is
  `unscored`, with `reason = "scoring_failed"`.

### How chatddx scores, until inspect does

`chatddx.scoring` holds runs to scorers of chatddx's own, kept in the
registry (§2). It is a stand-in to establish a reference, and its rules
differ from inspect's above.

- **A scorer is a function, the view it reads, and the kind of target it
  holds that to.** The archive's four are seeded from
  `inventory/scorers.toml`:

  | Scorer | Function | View | Target kind | Value |
  |---|---|---|---|---|
  | `reciprocal_rank` | `reciprocal_rank` | `differential` | `diagnosis` | 1/rank of the first item the target is found in, and 0 where it isn't (`not listed`) |
  | `first_mention` | `first_mention` | `text` | `diagnosis` | the characters before the target is first named, and none where it isn't (`never named`) |
  | `warning_mentions` | `mentions` | `warning` | `warning` | 1 where the target is found, and 0 where it isn't (`not named`) |
  | `disposition_mentions` | `mentions` | `disposition` | `disposition` | the same |

  Each score says what in the answer it rests on: the ranked item, the
  sentence or line the target was named in, or the item it was found in.
- **The functions are chatddx's own code,** in
  `chatddx.scoring.scorers.patterns`. They are loaded as tools are, from an
  allowlisted package and afresh from the file's bytes, and the file's git
  blob id names the version that scored. A scorer file imports nothing else
  of chatddx's, so the file is all of chatddx that scored. A function takes
  the view's items, or none where the run came to no answer, the target,
  and the scorer's arguments, and returns a value, an answer and a reason.
- **A target is a pattern of words.** A word is found whole and in any
  case: `pneumonia` isn't found in "pneumonias", nor `mi` in "anemia". A
  trailing `*` takes any word that starts so (`meningit*`). Words side by
  side are a phrase, found side by side. `&` needs both sides and `|`
  either, `&` binds tighter than `|`, and parentheses group:
  `(renal | kidney) & stone*`. A pattern is held to one item at a time, a
  diagnosis, a sentence or a field, never to two at once. `first_mention`
  splits text into sentences and lines, at line breaks and after `.`, `!`
  or `?`.
- **A case that expects no warning** has `warning = false`. `mentions` is
  then given no target: 1 where the view read nothing (`none named, as
  expected`), and 0 where it read something (`none expected`, resting on
  what was named).
- **Who scores decides what with.** Whoever scores holds runs to their own
  scorers and the archive's, and to the targets of the case branch that
  holds the run's case: the newest row of their own, or else of the
  archive's that they can see (§2).
- **A scorer applies to a run** that completed, whose output offers its
  view, and whose case has its kind of target, if it needs one.
- **A run is outstanding for a scorer,** for whoever scores, until it has a
  score of theirs from that scorer's trail with the target and the file's
  blob as they are now. An edit to the scorer, to the target or to the file
  makes it outstanding again, and the scores before stay. The latest score
  from each scorer, by its name, is the one shown.
- **Its rules for what can't be read:**
  - A view reads whatever answer the run kept, valid or not.
  - A run with no answer scores 0 with the reason `no answer`, or no value
    for `first_mention`.
  - A reply cut off at `max_tokens` isn't told apart, though the run keeps
    its finish reason.
  - A target that doesn't parse is an error, and nothing is scored. A test
    holds every target of the inventories to parse.
  - An errored run is never scored.
- **When:** a run in the repl is scored as soon as it is recorded. `score`
  scores every outstanding run of the identity's, oldest first, and ends
  with each scorer's metrics. `score RUN` scores one. `scorers` lists the
  scorers the identity can see, their metrics and owners, and whether the
  cell's output offers each one's view.
- **What is kept:** a score row per run and scorer (`datamodel.md`).

### inspect scores the log

- **The registry's scorers run in inspect** (`chatddx.logs.scorers`): each
  runs its function, loaded as chatddx loads it, on the view it names and
  the case's target of its kind, both read from the sample's metadata. It
  keeps its registry name, and its function, view, target kind and
  arguments are its options, so the log says what scored it. A score keeps
  the target it was held to and the blob, as a score row does.
- **Where chatddx makes no score, inspect's is unscored,** which inspect's
  metrics and reducers leave out: for an errored run, or a case without
  the scorer's kind of target. A value chatddx leaves empty, as
  `first_mention`'s where the target is never named, is unscored too, with
  the same reason.
- **A test holds inspect to chatddx** (`logs/tests/test_scorers.py`): each
  sample's value, answer, reason, target and blob are its run's, for every
  scorer, and a scorer's metrics are chatddx's over the same values.
- **The scorers a log is scored with** are those the exporter sees whose
  view the output offers. They go in the order of the views they read, the
  differential first, so that the log's headline in inspect's viewer is
  the diagnosis's rank where the output offers a differential.
- **A case's epochs are folded first.** inspect takes the mean of a case's
  epochs, then a metric over the cases. chatddx's summary takes it over
  runs, so the two agree where each case has one epoch.
- **A log is scored as it is written** (`backlog/export.md`). It can be scored again
  without generating, by any scorer, with `inspect score`.

### A judge for the diagnosis

- **What it reads** (`chatddx.logs.judge`): a grader model is given the
  differential and the case's diagnosis target, and says which item, if
  any, is the first to name that diagnosis, allowing what a clinician
  would and a pattern can't: a synonym, an abbreviation, another spelling,
  a more specific form, or the other language. A related diagnosis, a
  complication or a symptom doesn't count.
- **Its value is `reciprocal_rank`'s:** 1/rank, and 0 where no item names
  the target. So the judge and the pattern can be held to each other, and
  both to clinicians.
- **It reads today's target, a pattern,** which its prompt explains. A
  target in plain words would suit it better.
- **The grader** is the model given, or else the model bound to the
  `grader` role, which one must be. The file imports nothing of chatddx's,
  so inspect loads it on its own:
  `inspect score LOG --scorer src/chatddx/logs/judge.py@diagnosis_judge
  --model-role grader=MODEL --action append`.
- **A score keeps the grader's reasoning** as its explanation. A verdict
  that can't be read leaves the sample unscored (`grader_failed`). The last
  verdict counts, so that one quoted from an answer can't.
- **It is an instrument, and has to be validated.** `chatddx agreement
  FIRST SECOND LOG...` says how two scorers read the same samples: how
  often both found the target, neither did, or one alone; Cohen's kappa on
  found; and the samples whose values differ, which are what clinicians
  should settle first.
- **Open:** which model grades, one chatddx serves or a hosted one; a
  target in plain words for it; how clinicians label a subset, blind to
  both scorers, and what kappa is good enough.


## 2. Scorers and targets in the registry

The inventory is the source of truth for now, but everything in it is to be
kept in the portal. Once people work there, the database is the source of
truth, and the TOML files only seed it. So scoring reads its scorers and
targets from the registry, and nothing but a scorer's function stays in
code.

### What inspect does

Read from inspect-ai 0.3.263:

- **A scorer is a registered function made with arguments.** `@scorer`
  registers a factory by name, and a log records each scorer a task used
  as `EvalScorer`: its name, its arguments (`options`) and its metrics.
  `ScorerSpec` is the same triple, and is what re-creates a scorer.
- **Metrics belong to the scorer.** A scorer declares how its values are
  summed up over samples (`mean`, `stderr`, `accuracy` and the like). A
  task can override them. Reducers (`mean`, `median`, `mode`, `max`,
  `at_least`, `pass_at`) fold a sample's epochs into one score first.
- **The target belongs to the sample.** A sample is its input and its
  target, one or more strings (`Target`), and every scorer of the task
  reads the same one. A scorer that needs more reads the sample's metadata.
- **A score is its value, answer, explanation, reason and metadata.** The
  reason is for an abnormal score, from a short list or any string.
  `Score.unscored()` is a NaN that metrics and reducers skip.
- **People can edit a score.** Each edit (`ScoreEdit`) keeps who made it,
  when and why (`ProvenanceData`), and `Score.history` keeps the states
  before it.
- **A scorer's code is versioned with everything else.** The log's header
  names the packages, and the git commit the eval ran from, with whether
  the tree was dirty. Nothing names a scorer's own code.

### Scorers

A scorer is an entity:

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `function` | trail | yes | an entry point into one of chatddx's own scorer files, `chatddx.scoring.scorers.<file>:<function>` |
| `view` | trail | yes | the view it reads (§1) |
| `target_kind` | trail | yes | the kind of target it holds the view to, or null for a scorer that needs none |
| `args` | trail | yes | keyword arguments the function takes beside the view's items and the target; empty by default |
| `metrics` | details | no | how its values are summed up: `mean`, `stderr`, `std` or `var`; `mean` and `stderr` by default |

- **In a log it is an inspect scorer** (§1, inspect scores the log): it
  keeps its name, its function, view, target kind and arguments are its
  options, and its metrics are its metrics.
- **What can change a score is content,** so a score can cite exactly what
  made it. Metrics change no score, so they are details, and a change to
  them leaves every run scored.
- **The view and the target kind are fields of their own,** unlike
  inspect's options, because pairing a scorer with a run reads them: set
  membership, as in §1. The field is `target_kind` rather than `target`:
  the target is the case's, and a scorer names only the kind it reads.
- **The function runs as a tool's does:** from an allowlisted package,
  loaded afresh, with its file's git blob recorded on each score. Where
  inspect names a commit, and can only say that the tree was dirty, the
  blob names the code that scored.
- **The metrics are inspect's, by name and formula,** and chatddx computes
  them itself (`scoring/metrics.py`) rather than load inspect, which takes
  seconds. A deviation is a sample's (`ddof=1`), and a formula with too few
  values gives 0, as inspect's do. A score without a value is left out, as
  inspect leaves out an unscored one.
- **A scorer is named per owner,** like every entity. It comes last in
  commit order, since it refers to nothing. The archive's four are seeded
  from `inventory/scorers.toml`:

  ```toml
  [scorer.reciprocal_rank]
  function = "chatddx.scoring.scorers.patterns:reciprocal_rank"
  view = "differential"
  target_kind = "diagnosis"
  metrics = ["mean", "stderr"]
  ```

### Targets

A case's targets are its details:

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `targets` | details | no | what the case is expected to yield, by kind: `diagnosis`, `warning`, `disposition` and `dont_miss`. Each is its plain words (`text`) and its pattern (`pattern`), either of which may be missing, or `false` where the case expects none. The pattern scorers read the pattern (§1). |

- **inspect keeps the target with the sample, and a case is chatddx's
  sample.** The kinds are chatddx's own: inspect has one target per sample,
  and each of chatddx's scorers reads the kind it names.
- **Details, not content:** a target changes nothing the LLM reads, and a
  case's fingerprint names what it reads. Like an LLM's facts, targets are
  versioned by branch row: a changed target makes a new row, and a score
  records the row it read.
- **The kinds are a vocabulary kept in code,** as the views are. Only
  `warning` can be `false`: a plan that rightly raises no warning is held
  to none (§1). A kind that must be named can't be `false`.
- **This brings back what `2bf6af7` made of a case's `expects`:** they hang
  off the case's branch, per owner and per version, not off its shared
  trail. They are plain details now rather than a relation to an `expect`
  entity, since a target is its words and a pattern, not a record of its
  own.
- **The archive's targets are seeded from `cases.toml`,** as `targets.*` in
  each case's record. They can't be a file of their own: an inventory that
  extends another replaces its records whole, and doesn't merge them.
- **Which targets a run is held to:** those of the scoring identity's own
  branch of the run's case, or else the archive's, where the identity can
  see it: the newest row that holds the run's case trail. So a fixed target
  reaches earlier runs of the same vignette, and a new vignette comes with
  targets of its own.
- **A target is its plain words and its pattern** (`clinical-input.md`
  §3). The pattern is what the pattern scorers read; the words are what
  people see, and what the judge is to read (`clinical-input.md` §5.1). A
  kind left out, or a target without a pattern, is missing, and the
  pattern scorers of that kind leave the case out.
- **`dont_miss` has no scorer yet.** The management plan offers the view
  it would read, `critical`: the differential's items the answer marks
  critical. What it measures waits on clinicians (`clinical-input.md` §3).

### Scores

- **Whoever scores holds runs to their own scorers and the archive's,** and
  to their own targets or the archive's. Their own shadows the archive's of
  a name, as everywhere in the registry.
- **A score points at its scorer's trail,** and keeps the name the scorer
  had for whoever scored, the case branch row whose targets it read (none
  for a scorer that needs no target), the target it held the view to (none
  where the case expects none, or the scorer needs none), the blob, the
  value, the answer and the reason, and who scored.
- **A run is outstanding for a scorer, for the identity that scores it,**
  until it has a score of theirs from that scorer's trail with the target
  and the blob as they are now. The latest score from each scorer, by name,
  is the one shown.
- **The fields are inspect's `Score`:** a null value is inspect's unscored.
  `explanation` and `metadata` can join when a scorer needs them.

### Parsing and committing

- **Parsing needs nothing new.** `scorer` is one more entity, and a case's
  `targets` pass through as details.
- **At commit,** a scorer's function must have an entry point's shape, its
  view and target kind must be in their vocabularies, its arguments must be
  an object, and its metrics must be known, and named once. A target must
  be text, or `false` where its kind allows it.
- **The package is held at load,** as a tool's is. Whether a target parses
  is for the scorers that read it to say: a test holds the inventories'
  targets to parse, and scoring checks the rest (§1).
- **A test holds each scorer to its function,** as tools are held to their
  parameters: the function takes the view's items, a target, and the
  scorer's arguments.

### In the portal

The portal's case page predates this note, and its registration is off. It
ports with little change:

- **What carries over as is:** `CaseAdmin` and `SharedCaseAdmin` list a
  case's name, versions, vignette (their `payload`), tags and
  collaborators, step through its versions, and offer templates to start
  from. `CaseForm` edits the name, the vignette and the tags. A case is
  still its vignette, and its branch still carries its tags and
  collaborators.
- **Expects become three fields.** `ExpectInline` was a formset whose rows
  each paired an expected payload with a scorer, committed as an `expect`
  entity named `<case>|<scorer>` and linked to the case's branch. Targets
  make that simpler: one field per kind on the case's form, the warning's
  with a way to say that none is expected, and no entity, formset or link.
  A changed target is a new version of the case, as a changed vignette is.
- **Two changes are generic, and needed by every entity with details.**
  `BranchModelAdmin.save_model` commits the name and the owner alone, so it
  would commit every detail at its default: a saved case would lose its
  targets, and a tool what it runs. It has to commit the entity's details
  from the form (`entity.branch_details`). And `load_form_data` leaves the
  details out of a form's data, where the registry's own `form_data_out`
  puts them beside the trail's fields.
- **A form can check a target as it is written,** since the file of the
  pattern language imports nothing else of chatddx's.
- **A scorer's page is a tool's:** its function, view, target kind,
  arguments and metrics.

### Later, from inspect

- people's edits to scores, as rows beside a score, each with its author,
  time and reason, when clinicians adjudicate in the portal (inspect's
  `ScoreEdit` and `ProvenanceData`);
- inspect's reasons for what can't be read, when inspect scores with
  scorers of its own (§1).


### Scoring not built

- **Rubric scoring of management plans,** which would read a `plan` view
  (workup, treatment and disposition) that no output offers
  (`post-endgame.md`).
- **A model-graded extractor for free text,** which would read a
  differential out of free text as a pinned judge configuration like any
  other, where the `lines` parser can't.
- **A scorer for `dont_miss`,** above.

## Sources

- inspect-ai 0.3.263: `scorer/_scorer.py`, `scorer/_target.py`,
  `scorer/_metric.py`, `scorer/_metrics/`, `scorer/_reducer/reducer.py`,
  `scorer/_common.py`, `scorer/_choice.py`,
  `scorer/_classification.py`, `scorer/_pattern.py`, `scorer/_model.py`,
  `solver/_multiple_choice.py`, `solver/_task_state.py`,
  `model/_model_output.py`, `model/_generate_config.py`,
  `agent/_react.py`, `agent/_types.py`, `_eval/score.py`,
  `_eval/task/epochs.py`, `_eval/task/run.py`, `_eval/task/log.py`,
  `log/_log.py`, `log/_edit.py`, `_util/metadata.py`,
  `util/_store_model.py`, `analysis/_dataframe/samples/columns.py`
- pydantic-ai 2.41.0: `output.py`, `_output.py`, `profiles/__init__.py`,
  `providers/vllm.py`, `settings.py`
- vLLM, main branch at the time of writing:
  `docs/features/structured_outputs.md`,
  `docs/features/reasoning_outputs.md`
  (https://github.com/vllm-project/vllm)
- PR #68, `docs/design/compatibility.md` on `claude/fervent-newton-8eqiy1`:
  https://github.com/chatddx-administration/chatddx/pull/68

