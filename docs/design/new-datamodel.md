# The new datamodel

This note gives the entities of the repo registry (`repo/registry.py`) after
the redesign in `research-data-model.md` and `data-generation.md`. Before
the entities, it covers:

- what a slice is, and how its variations are compared one slice at a time
  (§2);
- why slices compose only as intents, and what makes them appear to
  compose (§3);
- how an inspect-ai scorer reads an output that pydantic-ai produced, and
  how chatddx scores runs until inspect does (§4);
- where the combinatorial batch and the compatibility table of
  [PR #68](https://github.com/chatddx-administration/chatddx/pull/68) go
  (§5).

It then maps every current field to its new home or scraps it, and marks
each field as fingerprinted or not. It ends with a proposal for keeping
scorers and targets in the registry (§11), and with where the code still
differs from this note (§12).

For inspect-ai, option C of `data-generation.md` §5 was chosen: chatddx
generates and inspect scores. So the registry keeps what generation needs,
and what only evaluation needs moves to inspect. §11 proposes one change to
that: the scorers and the targets are registered too, since people are to
keep them in the portal, and inspect's model shapes them.

Terms used here:

- **Entity:** a registered kind of record, with a trail table and a branch
  table.
- **Bundle:** the set of schemas and models attached to an entity (`Entity`
  in `repo/registry.py`): trail schema, spec and ref; branch schema and
  spec; details and details patch; trail and branch models. The word means
  nothing else in this note.
- **Trail:** an entity's content, content-addressed and immutable.
- **Branch:** an owner's named version, pointing at a trail.
- **Details:** an entity's non-fingerprinted fields. They form a side schema
  that lives on the branch.
- **Slice:** one dimension of the configuration surface that a batch can
  vary while it holds the others fixed. The slices are the model,
  instruction, output, coercion, reasoning, sampling and toolset. A slice
  is vertical: it owns everything specific to it, wherever that lands in
  the request, in the prompt text or in how the output is read (§2).
  `data-generation.md` first called these bundles. Bundle now keeps only
  the meaning above.
- **Variation:** one value of a slice, such as reasoning `off`, output
  `diagnoses` or the model `qwen3-8b-awq`. A variation of a request-time
  slice is a record of that slice's entity. A variation of the model slice
  is a stack. Where `data-generation.md` says a configuration is one slice
  of each kind, this note says one variation of each slice.
- **Configuration:** one variation of each request-time slice, that is, of
  every slice but the model.
- **Cell:** a configuration and a stack, so one variation of every slice. A
  trial runs one cell on one case, with one seed.
- **Trial and run:** a trial is a cell on a case with a seed, or with none.
  It is content, like a trail, and belongs to no one. A run is one go at a
  trial, and it is the runner's (§6).
- **Replicate:** one of a batch's seeds. Its position among them, from 1,
  is inspect's epoch when the batch is written as a log (§4, §5).
- **Intent and realization:** a variation states what is wanted. Its
  realization on a stack is what it writes into the request: its
  contribution (`data-generation.md` §3.1).
- **Resolution:** turning a cell into a request (§9).
- **View:** a named, typed reading of an output, such as the ranked
  differential. Scorers read views, never outputs (§4).

## 1. Fingerprinted and non-fingerprinted fields

**Decision:** trails stay fingerprint-only. Non-fingerprinted fields go
into the entity's details, a side schema on the branch. Passthroughs
already route an authored record this way; the redesign widens them.

### Why a trail can't hold a non-fingerprinted field

Three properties of a trail row make it the wrong home:

- **It is shared.** `dump_trail` writes with
  `get_or_create(fingerprint=…)`, so every owner of the same content gets
  the same row.
- **The first writer wins.** Once the row exists, every later writer's
  `defaults` are ignored. A later owner's value for a non-fingerprinted
  field would be dropped without a word.
- **It can't be corrected.** A trigger refuses every update: "Records with
  a fingerprint are immutable." A mistyped description could never be
  fixed. Nor could it move to a new row, because it isn't part of the
  fingerprint.

The repo has met this before. `exclude_from_fingerprint` was used exactly
once, on a case's `expects`. 2bf6af7 moved them to the branch because "a
trail field that cannot take part in the fingerprint is not content", and
703c655 removed the flag.

### Where non-fingerprinted fields go

- **The bundle already has a place for them.** Each entity names a details
  schema (`branch_details`, `branch_details_patch`), validated with
  `extra="forbid"`. Details hold the branch's name and owner, its relations
  (collaborators and tags), and descriptive values, such as a machine's
  specs or a stack's endpoint. Most entities have no descriptive values:
  only machine, os, model, serving, client, stack and tool do (§6).
- **Details live on the branch.** That is the layer that already carries
  the owner, the name, collaborators and tags, so details are owned and
  named, per owner.
- **Storage.** Relations stay many-to-many. Plain details go in one JSON
  column on the entity's branch model, validated by its details schema. A
  typed column is added only where something queries it.

### Passthroughs are the router

The inventory parser (`repo/parsers/inventory.py`) treats one authored
record as two:

- A key the trail schema declares is content. Content is looked at first,
  so a tool's `name` is the name the model sees, not its branch's.
- A key the details schema declares passes through to the details.
- `name` and `owner` are refused: a record's name is its key, and its owner
  is whoever parses the inventory.
- Any other key is an error, which names the content and detail keys there
  are.

So an author still writes one record per entity, and the bundle decides
which keys are content and which are description:

```toml
[model.qwen3-8b-awq]
blob = "/nix/store/…-qwen3-8b-awq"      # trail: fingerprinted
source = "Qwen/Qwen3-8B-AWQ@<commit>"    # details: passes through
facts.reasoning.default = "on"           # details: passes through
tags = ["local"]                         # details: passes through
```

The rest of the inventory's rules:

- **A file holds a table per entity, and each holds named records.** An
  entity that isn't registered is an error.
- **`extends` at the top of a file** names the files it builds on. Its own
  records win over theirs, and the first file it names wins over the next.
  A file that extends itself, however far round, is an error.
- **`extends` in a record** names records of the same entity it builds on.
  Its own keys win, and the first record it names wins over the next.
  Records merge key by key and no deeper, so a table a record sets replaces
  the one it would inherit.
- **`partial = true`** makes a record a template to extend. It isn't
  committed, and a relation can't name it.
- **`<key>_path`** reads the key's value from a file next to the file that
  names it: `.toml` and `.json` as data, `.txt` as text. Giving both `<key>`
  and `<key>_path` is an error. Only a record's own keys read files, and
  what they read is data.
- **A relation names a record of the entity it points at:** one name, or a
  list of names for a list. A record written inline would be committed
  without a name, so it isn't accepted.
- **A case with no `payload`** reads it from `cases/<name>.txt` next to its
  file.
- **`init-data` commits the inventory as the archive's** (the identity
  `archive`). The user it is run for becomes a collaborator on every branch
  it committed, and a giftbag inventory, if given, is committed as that
  user's own.

### One change to commit

When only details change, `commit()` edits the canon branch in place:
"What a branch carries besides its content is not fingerprinted, so it can
change while the canon stays put."

- That is fine for tags.
- It is not fine for details that resolution reads, such as a model's facts
  or a stack's served name. A trial must be able to say which version it
  resolved against.
- So a change to details makes a new branch row. That is the "fingerprint
  the commit, not only the tree" item already listed in
  `branch-identity-and-the-repo-registry.md`.
- A run then records the branch rows whose details it read, beside the
  trails it ran (§6).

As built, `commit()` works like this:

- **A version is a trail and its plain details.** A commit whose trail or
  details differ from the canon's makes a new branch row. A commit that
  matches the canon makes no row and answers that nothing changed.
- **Relations change in place.** A commit that names tags or collaborators
  sets them on the row it lands on. One that names none keeps what the
  version before had.
- **The canon is the newest row** of an owner's branch of a name, by
  timestamp and then id. The rows before it are its versions.
- **A commit reaches everything its trail does.** Every trail it reaches,
  such as a stack's machine or a toolset's tools, gets a branch of the
  owner's if the owner has none. The branch is named after its entity and
  short fingerprint (`machine 3f9a1c`), with no tags, no collaborators and
  every detail at its default. Where the owner already has a branch of the
  trail, it isn't touched.
- **Saving copies the archive's branches first.** Before the repl saves a
  configuration as an owner's, each trail it reaches that the owner has no
  branch of gets a copy of the archive's branch of it, under its name and
  with its details, so a tool keeps what it runs. A trail the archive has
  no branch of, or holds under a name the owner already gives another
  trail, is left to the rule above. (`commit_copies` can copy any owner's
  branches; the repl copies the archive's, not the configuration owner's.)
- **Visibility:** an identity can use its own branches and those it
  collaborates on, by name. Its own shadows a shared one of the same name.
  A lookup can be held to one other owner, such as the archive.

### The rule

A field is fingerprinted if and only if it is trail content. Trail content
is:

- for a thing (machine, OS, model, client): its one identifying field;
- for a composition (stack, configuration, toolset): the things it
  combines;
- for a variation of a request-time slice, and for serving: everything
  authored that can change a request, the model's output, or how the
  output is read for scoring.

Names, owners, tags, endpoints, credentials, specs and facts are details,
and are never fingerprinted.

The kinds of hash identify different things:

- Trail fingerprints identify what was authored.
- The request hashes (`data-generation.md` §3) identify what was sent. They
  belong to each run, since a trial can be run on a later client, or after
  a fact changed, and send something else. They aren't computed yet. Until
  they are, a run keeps the exact bodies it sent and got back (§6).
- A model's facts can change a request without moving any trail
  fingerprint. That is by design, since a model is its blob, and the
  request hash catches it.
- An output's views can change its fingerprint without changing a request.
  Two outputs that differ only in their views have equal contributions:
  the same request, read differently (§4).

## 2. Slices and variations

### What a slice is

- **A slice is a question a batch can ask.** Which model? Does reasoning
  help? Should the answer be a management plan or a list? Each question has
  a few answers worth comparing: the slice's variations. A batch compares
  them while every other slice holds one variation (§5).
- **A slice is vertical.** It owns everything specific to it, wherever that
  lands: request fields, prompt text, and the reading of the output.
  - The output slice shows why. A management plan and a list of diagnoses
    differ in their schema. They also differ in what the model is told
    ("Fill in the management plan", "List the plausible diagnoses") and in
    where a scorer finds the differential.
  - Those sentences were agent instructions (the two partial agents in
    `medical-assistant.toml`), each paired with its output type by hand.
    They are the outputs' guidance now (`inventory/slices.toml`).
  - If the instruction kept the sentence, instruction and output could not
    be varied apart: half of any grid would ask for one output and enforce
    another.
- **The model is a slice too.** Its variations are the stacks at hand. Two
  things set it apart:
  - it writes almost nothing into the request: the `model` field, and where
    the request goes;
  - every other slice is resolved against it.

  So it stays out of the configuration. A cell joins a configuration to a
  stack, and one configuration runs on every model.

### Where to cut

A concern is a slice of its own when it passes three tests:

1. **It is varied on its own.** Some batch asks about it while everything
   else stays put.
2. **Its variations make sense against facts alone.** A variation may read
   the model's facts, fill slots, and act on what another slice hands it,
   such as the output's schema. It may not assume which variation of
   another slice it is paired with.
3. **It owns everything specific to it.** No text, request field or reading
   that only makes sense for some of its variations lives anywhere else.

Two concerns that fail the second test against each other are one slice, a
compound (§3). Two that pass it, and vary for different reasons, are two.

**Decision: coercion is a slice, split from output.**

- The output's schema says what is asked for. The mode says how the model
  is held to it.
- They vary for different reasons, and they go with different things: the
  schema with guidance and scorers, the mode with the model's
  capabilities. `compatibility.md` in PR #68 makes the same case.
- Kept together, varying the mode meant copying the schema once per mode
  (`diagnoses tool`, `diagnoses native`, `diagnoses prompted`). Split, a
  batch crosses them.
- Whether the schema is also shown to the model goes with the mode. Tool
  mode shows it anyway, and prompted mode is nothing but showing it.

### The slices

| Slice | A variation is | It writes | Resolved against |
|---|---|---|---|
| model | a stack | the request's `model` field, and where the request goes | nothing: the other slices are resolved against it |
| instruction | system and user templates, with declared slots | the messages | the slots the other slices fill |
| output | a schema (none for free text), its guidance and its views | the `output_guidance` slot, the schema that coercion delivers, and what scorers read | nothing |
| coercion | a mode (native, tool, prompted or auto), a schema prompt, and for tool mode a tool description | `response_format` or a final-result tool, and the `schema_prompt` slot | the model's facts (which modes work, and what `auto` stands for), the serving (a parser a mode needs) and the output's schema |
| reasoning | an effort (default, off, on, minimal, low, medium, high or xhigh) and an optional budget | whatever the model's facts say: `chat_template_kwargs`, `reasoning_effort`, `thinking_token_budget` | the model's facts |
| sampling | explicit values, and what a null means: the model's generation config, or its recommendation for the resolved reasoning mode | temperature, top-p, top-k, penalties, stop and max tokens | the model's facts and the resolved reasoning mode |
| toolset | tool definitions and their guidance | `tools`, and the `tool_guidance` slot | the serving: tools need a tool-call parser |

### Intent and realization

- **A variation states an intent.** Resolution realizes it on one stack as
  a contribution: the part of the request it writes.
- **Each cell comes out one of three ways:**
  - **Realized:** it yields a request.
  - **Collapsed:** it yields the same request as another cell. Equal
    skeleton hashes on the same stack show it (`data-generation.md` §3.1).
    For example, Qwen3 has no effort levels, so reasoning `low` and `high`
    both realize as thinking on. The two cells are one treatment, and a
    batch runs it once. Resolution already names the intent a variation
    collapses into where the facts declare it. The hashes, once computed,
    will show every other collapse.
  - **Refused:** the stack can't honour the intent. For example, gpt-oss
    can't stop reasoning, because vLLM rejects `reasoning_effort = "none"`
    for harmony models. An intent the facts don't mention is refused too,
    for want of a fact: nothing is guessed. Either way the reason is kept.
- **Resolution gathers every refusal in a cell,** each with its slice and
  its reason, so one look shows all that stands in the way. What chatddx
  can't do yet, such as sending to an API other than vLLM, is marked as
  later rather than refused.
- **A name says what was meant; the request says what ran.** Whether two
  cells are one treatment is decided by their requests, never by their
  variations' names.
- **Facts are claims.** A realized cell rests on facts, and only an
  experiment shows whether the model honours them. For example, whether
  gpt-oss honours low, medium and high is still open (`data-generation.md`
  §6). The batch's report and each run record the facts a cell rested on,
  as the branch rows read, so a doubtful fact can be traced to every cell
  that used it. A run in the repl says when the model didn't honour its
  reasoning: no thinking came back though reasoning resolved to a mode that
  thinks, or some came back though it resolved to `off`.

### Example: reasoning, per model

The model's facts translate each intent into one of three things: a
request fragment, another intent it collapses into, or a refusal.

```toml
[model.qwen3-8b-awq.facts.reasoning]
default = "on"
off = { chat_template_kwargs = { enable_thinking = false } }
on = { chat_template_kwargs = { enable_thinking = true } }
minimal = "on"          # no effort levels: every effort is "on"
low = "on"
medium = "on"
high = "on"
xhigh = "on"
budget = { field = "thinking_token_budget", needs = "reasoning_parser" }

[model.qwen3-8b-awq.facts.sampling.recommended]   # the model card, per mode
on = { temperature = 0.6, top_p = 0.95, top_k = 20 }
off = { temperature = 0.7, top_p = 0.8, top_k = 20 }

[model.gpt-oss-20b.facts.reasoning]
default = "medium"
off = { refused = "always reasons: vLLM rejects reasoning_effort = none for harmony" }
on = "medium"
minimal = { refused = "harmony has no minimal effort, only low, medium and high" }
low = { reasoning_effort = "low" }
medium = { reasoning_effort = "medium" }
high = { reasoning_effort = "high" }
xhigh = { refused = "harmony has no xhigh effort, only low, medium and high" }
budget = { refused = "no thinking budget is documented for harmony" }
```

A batch that varies reasoning over `off`, `low`, `medium` and `high` on
both models, with sampling at `recommended`, resolves to:

| Reasoning | qwen3-8b-awq | gpt-oss-20b |
|---|---|---|
| off | `enable_thinking: false`, temperature 0.7, top-p 0.8 | refused: always reasons |
| low | `enable_thinking: true`, temperature 0.6, top-p 0.95 | `reasoning_effort: low` |
| medium | collapsed into low | `reasoning_effort: medium` |
| high | collapsed into low | `reasoning_effort: high` |

The same study today needs a sampling params record per model and
setting: `disable-thinking` for Qwen3 and `low-reasoning` for gpt-oss.
Each is honoured by one model and ignored by the other. And nothing shows
the collapse or the refusal until the runs come back.

### Example: output and coercion

From `inventory/slices.toml`:

```toml
[output.management-plan]
schema_path = "schemas/management_plan_v1.json"
guidance = "Fill in the management plan for the case."
views.differential = "$.diagnoses[*].diagnosis"
views.warning = "$.acute_warning"
views.disposition = "$.management.disposition"

[output.diagnoses]
schema_path = "schemas/diagnoses.json"
guidance = "List the plausible diagnoses, most likely first."
views.differential = "$.diagnoses[*]"

[output.free-text]
guidance = "List the plausible diagnoses, one per line, most likely first."
views.text = "whole"
views.differential = "lines"

[output.raw]                    # no guidance: whatever the model makes of the case
views.text = "whole"

[coercion.native]
mode = "native"                 # on vLLM, guided decoding only: the model never reads the schema

[coercion.native-shown]
mode = "native"
schema_prompt = """
Answer with a JSON object that matches this JSON Schema, and nothing else:

{{schema}}"""                   # chatddx's own text, placed through its slot

[coercion.tool]
mode = "tool"
tool_description = "Give your answer by calling this tool, with the answer as its arguments."

[coercion.prompted]
extends = "native-shown"        # the same text, so the two differ only in what enforces it
mode = "prompted"

[coercion.auto]
mode = "auto"                   # whatever the model's facts name as its default
```

- **The guidance and the view keep one promise.** The `differential` view
  promises a ranked list. The same variation's guidance asks for the
  ranking, and so does the management plan's schema ("ranked by
  probability"). Both ends of the promise live in one record.
- **A schema stays as authored.** `diagnoses` stays the object it is on
  `main`, and its view says where its list is. PR #68 reshaped it into a
  top-level list so that its scorer could read it; a view makes that
  unnecessary.
- **Free text collapses coercion.** With no schema, every coercion variation
  contributes nothing, so a batch that crosses output and coercion reports
  free text × coercion as one cell.

## 3. Composability

### Generic composability is out of reach

Generic composability would mean two things:

- any variation of each slice combines with any variation of every other
  into a coherent request;
- neighbours in a grid then differ only by what the varied slice says.

Three things rule it out. Each can be seen in the code pinned in `uv.lock`
or in vLLM's documentation.

1. **Realization depends on the model.**
   - Qwen3 turns thinking off with a chat-template switch and has no effort
     levels. gpt-oss has effort levels and can't turn reasoning off.
   - Left alone, the libraries hide this. pydantic-ai ignores `thinking =
     False` on a model that always reasons, and it drops `thinking`
     altogether unless the model's profile declares support. vLLM ignores
     `tool_choice = "required"` for gpt-oss (pydantic-ai's vLLM provider
     notes it), so tool mode can't force gpt-oss to answer through its
     tool.
   - So one variation on two models is one intent, not one request.
2. **Slices share resources.**
   - Qwen3's recommended sampling depends on the thinking mode.
   - A thinking budget spends `max_tokens`.
   - Native output on a reasoning model needs a reasoning parser. vLLM's
     grammar engine uses the parser to find where the reasoning ends, and
     it constrains only what follows. vLLM keeps these facts in its own
     table, one row per model family: the parser, and whether structured
     output and tool calling work with reasoning on.
   - Tool-mode coercion puts its final-result tool into the same `tools`
     list as a toolset.
3. **What a scorer can read depends on the output.** A ranked-list scorer
   has nothing to rank in free text until something extracts the list.

**What is within reach, and enough: intents compose.**

- Every cell is either well-formed by construction or refused with a
  reason.
- Every refusal, collapse and translation is visible before anything runs.

The tricks below buy exactly that. Interactions are not a failure of it.
If reasoning helps Qwen3 more than gpt-oss, that is a finding a grid
measures, not a defect of the data model.

### How composability is made to appear

| Trick | What becomes composable | What it costs |
|---|---|---|
| **Slots.** The instruction declares holes (`output_guidance`, `schema_prompt` and `tool_guidance`; later `reasoning_guidance`), and each is filled by exactly one slice. | instruction with output, coercion and toolset, and later with reasoning: an instruction never names an output | The instruction must place every slot that is filled. Nothing checks that the joined text reads well. |
| **Intents plus facts.** A variation states an intent. The model's facts translate it, alias it or refuse it. | reasoning and coercion across models | Facts to write and keep: one row per model and intent, not one per pair of records. |
| **Symbolic values.** Some values are defined by reference: sampling `recommended` (for the resolved reasoning mode), reasoning `default`, coercion `auto` (the mode the model's facts name as its default), and a sampling field left out under `defaults = "model"` (the model's generation config, as its facts give it). | sampling with reasoning and model | The numbers differ per model. Only the request says what was sent. |
| **Disjoint writes.** Each slice declares the request paths and slots it may write. Write sets belong to slices, not to variations, and no two slices share one. | every slice with every other, with no merge rule | It is checked once, over the slices in code, not once per configuration. A concern that needs two slices' paths becomes a coupling. |
| **Couplings.** The few requirements that cross slices are declared in the model's facts, as what a fact needs of the serving (`needs`), and resolution checks them against the serving's arguments. For example, a budget needs a reasoning parser on Qwen3, and a structured mode needs one while the model reasons. Two are resolution's own: a budget must fit in `max_tokens`, and tools need a tool-call parser. | the cells they allow | Each coupling is data someone has to write. Where a symbolic value dissolves a coupling, prefer it. |
| **Views.** Scorers read a named reading of an output, and each output declares its readings (§4). | scorer and output | One view per output and reading. Free text needs a parser. |
| **Collapse detection.** Cells whose requests match on a stack are one treatment. | variations a model can't tell apart | None. This is what the hashes of `data-generation.md` §3 are for. |
| **Compound slices.** Two concerns that can't be separated become one slice. For example, "thinking with its sampling", when a study wants the vendor's pairing rather than a fixed sampling. | an inseparable pair | Their separate effects can't be estimated. |

### What is not worth doing

- **A declared table of pairs.**
  - Pairs of records multiply with every variation anyone makes, and the
    same fact is written again for every pair.
  - Facts are declared once per model or serving, where they are true, and
    the table is derived from them (§5). With m models and r reasoning
    intents, that is m × r rows of facts, however many sampling or output
    variations exist.
- **A general constraint language.** The couplings are few and local.
  Resolution code states them more plainly than a rule engine would, and a
  new one is a small change.
- **Filling every cell.** Faking "reasoning off" on gpt-oss with an
  instruction to be brief would make `off` mean different things on
  different models. That is a different variation, and it should be named
  as one.
- **Raw provider parameters in a variation.** A bag of provider
  parameters, like today's `provider_params`, is valid on one model only.
  It fails the second test of §2, so it can't be a variation of any slice.

## 4. Outputs and scorers

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
    It is appended to any text the model wrote beside the call, or stands
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
  - `Score.reason` separates failures of the model under test
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
  (§1). A batch that varies only views generates once, and reads the same
  trials each way.
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
  output is the answer as the model gave it.
- **The schema a request carries is chatddx's to say.** Resolution inlines
  its references and drops `$defs`, so pydantic-ai is left with nothing to
  make of it but a sort of its keywords; the properties keep the order they
  were written in. A schema that refers to itself can't be sent, and is
  refused.
- `template` is always `False`. The schema prompt, when there is one,
  reaches the model through the `schema_prompt` slot, never through
  pydantic-ai's default text. It shows the schema as written, not inlined.
- `auto` is resolved to one of the three from the model's facts before the
  spec is built. Left to pydantic-ai, it would also bring the profile's
  default template along on vLLM.
- **No words of pydantic-ai's own reach the model.** The profile is
  pydantic-ai's default, then its vLLM provider's, then the model's facts,
  then chatddx's own on top: no JSON schema transformer, no schema added to
  the instructions, no JSON object mode, and no OpenAI reasoning field. The
  model's facts give the profile instead of the served name.
- **A trial asks once.** Nothing is retried: an answer that doesn't hold is
  recorded, not asked for again. A model may call tools for five rounds,
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

### What a trial records, and what the log carries

- **A trial's run records the value, not only the transcript.** `output`
  is `result.output`, the same whichever mode carried it (PR #68's
  `RunModel.output`): an object for a structured output, the text for free
  text. `valid` says whether it holds to the output's schema. It is null
  for free text. It is false where no answer that parses came, and then
  there is no output, and where one parsed but doesn't hold, and then the
  output is kept.
- **Until inspect scores runs, chatddx does,** with scorers of its own and
  rules of their own (below, How chatddx scores).
- **chatddx writes one inspect sample per trial** (`data-generation.md` §5,
  option C):

  | Sample field | Holds |
  |---|---|
  | `id`, `epoch` | the case, and the replicate: the position of the trial's seed among the batch's seeds, from 1 |
  | `input` | the case, as the model received it |
  | `output.completion` | the answer as text: where inspect expects an answer, and where `react()` puts a submitted one. It is the `text` view where the output offers one, and a structured answer's JSON otherwise |
  | `messages`, and a `ModelEvent` | the exchange as it happened, tool call or `response_format` included, with the raw request and response |
  | `target` | the case's target for what the batch's scorers expect; for `diagnosis`, read by `reciprocal_rank` and `first_mention`, one pattern |
  | `metadata` | one key per slice, naming the cell's variation; the identities and hashes; the output's fingerprint and its views |

- **A batch writes one log per cell.**
  - An inspect log is one task on one model, and a sample id appears once
    per epoch. So a cell, one configuration on one stack, is the natural
    unit.
  - `data-generation.md` wrote one log per batch, when a batch held one
    configuration.
  - A batch is then an inspect eval set in all but name.
- **Analysis needs no join.** `samples_df` over a batch's logs gives one
  row per trial, with its variation per slice as `metadata_*` columns and
  its scores as `score_*` columns. That is the factor vector of
  `research-data-model.md`, as a table.

### When an output can't be read

These are the rules for when inspect scores. chatddx's own scorers keep
theirs until then (below).

- **Refused before running.** A cell whose output lacks a view that a
  scorer reads is refused for that scorer when the batch is planned (§5).
  If no scorer is left, the cell isn't generated.
- **Unreadable at scoring.**
  - An output that isn't valid, or whose view yields a value that fails
    the view's schema, scores 0 with `reason = "invalid_response_format"`.
    That is the model's failure, and it counts as a miss.
  - A reply cut off at `max_tokens` scores 0 with `reason = "truncated"`
    instead. `data-generation.md` §4 keeps a truncated answer apart from a
    wrong one.
  - `Score.unscored()` would drop these from the mean, which flatters a
    configuration that often fails. The reason keeps the rate countable.
- **The instrument's fault.** A target the scorer can't parse is
  `unscored`, with `reason = "scoring_failed"`.

### How chatddx scores, until inspect does

`chatddx.scoring` holds runs to scorers of chatddx's own. It is a stand-in
to establish a reference, and its rules differ from inspect's above.

- **A scorer is a function, the view it reads, and the kind of target it
  holds that to.** The four are a table in code (`SCORERS` in
  `scoring/score.py`):

  | Scorer | Function | View | Target | Value |
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
  the view's items, or none where the run came to no answer, and the
  target, and returns a value, an answer and a reason.
- **A target is a pattern of words.** A word is found whole and in any
  case: `pneumonia` isn't found in "pneumonias", nor `mi` in "anemia". A
  trailing `*` takes any word that starts so (`meningit*`). Words side by
  side are a phrase, found side by side. `&` needs both sides and `|`
  either, `&` binds tighter than `|`, and parentheses group:
  `(renal | kidney) & stone*`. A pattern is held to one item at a time, a
  diagnosis, a sentence or a field, never to two at once. `first_mention`
  splits text into sentences and lines, at line breaks and after `.`, `!`
  or `?`.
- **Targets are read from `targets.toml`,** keyed by the case's name and
  then by the kind of target: `diagnosis`, `warning` and `disposition`. A
  run's case is found by its trail among the archive's case branches, so a
  case is known by its inventory name. Tests read `test-targets.toml`
  instead.
- **A scorer applies to a run** that completed, whose output offers its
  view, and whose case has its kind of target.
- **A run is outstanding for a scorer** until it has a score from that
  scorer with the view, the target and the file's blob as they are now. An
  edit to the file or to the target makes it outstanding again, and the
  scores before stay. The latest score from each scorer is the one shown.
- **Its rules for what can't be read:**
  - A view reads whatever output the run kept, valid or not.
  - A run with no output scores 0 with the reason `no answer`, or no value
    for `first_mention`.
  - A reply cut off at `max_tokens` isn't told apart, though the run keeps
    its finish reason.
  - A target that doesn't parse is an error, and nothing is scored. A test
    holds every target in `targets.toml` to parse.
  - An errored run is never scored.
- **When:** a run in the repl is scored as soon as it is recorded. `score`
  scores every outstanding run of the identity's, oldest first, and ends
  with each scorer's mean. `score RUN` scores one. `scorers` lists the
  scorers, and whether the cell's output offers each one's view.
- **What is kept:** a score row per run and scorer (§6).

## 5. The batch and the compatibility table

PR #68 prepared for a combinatorial batch, which built an agent for every
combination of chosen components. It also prepared for a table saying which
components go together. This section is the new home for both.

### The batch

A batch names:

- a base;
- the slices it varies, with their variations;
- cases;
- scorers;
- replicates.

It stays an order in history, not a registry entity, and today's split
between `plan` and `generate` stays.

| Field | Holds |
|---|---|
| `base` | a configuration and a stack: the variation every slice keeps unless it is varied |
| `varied` | groups of slices, each slice with its variations, such as `[{model: [qwen3-8b, gpt-oss-20b], reasoning: [off, low, high]}, {output: [management-plan, diagnoses, free-text]}]` |
| `case_tags` | as today; the cases are resolved when the batch generates |
| `scorers` | inspect scorers with their arguments, which include the view each reads; as §11 proposes, the registry's scorers, by their trails |
| `replicates` | its seeds, one per replicate. A replicate's position among them, from 1, is its epoch in the cell's inspect log. Each seed makes a trial of every cell on every case. |

- **Cells.** The slices within a group are crossed, and the groups are
  varied one at a time, with every other slice at the base.
  - Groups of one slice each give a one-slice-at-a-time design: every cell
    differs from the base in exactly one slice.
  - One group holding every varied slice is a full cross.
  - The example above does both. It crosses model with reasoning, which
    gives the table of §2, and varies output on its own.
  - A batch with nothing varied is today's batch: one configuration.
- **A cell is content, not a name.**
  - Its configuration is a trail, deduplicated by fingerprint. The base
    cell appears once, however many groups reach it.
  - It needs no branch. A trial points at trails, and the worker never
    looks for a branch to run it (`research-data-model.md`, item 19).
  - Within its batch, a cell is labelled by its varied slices
    (`model=gpt-oss-20b reasoning=low`), for people only.
  - To keep a cell is to commit its configuration, under a name the
    committer chooses.

### The compatibility table is the batch's resolution report

**Decision:** there is no authored compatibility table. Planning a batch
resolves every cell against its stack, as a dry run (`data-generation.md`
§2.4). The report of that run is the table.

- **Its inputs are all in the model already:**
  - the variations' content;
  - model facts and serving settings, each declared once per model or
    serving, where it is true;
  - the scorers' views and the outputs' views;
  - the cases' targets, which inspect keeps, keyed by the case (§7); §11
    proposes keeping them in the cases' details.
- **Per cell,** the report gives realized, collapsed into another cell, or
  refused, with the reason and the facts it rested on (the branch rows it
  read).
- **Per cell and scorer,** it says whether the output offers the scorer's
  view.
- **Per scorer and case,** it says whether the case has a target the scorer
  reads. A case without one is left out for that scorer, as `plan` does
  today.
- **Pairwise tables are views of the report.** Model × reasoning (§2) is
  the report projected onto two slices.
- **Collapsed cells are shown and not run.** Refused cells are shown and
  not run either, so a sweep whose base variation some model can't honour
  says so before generating. For example, a base with reasoning `off`
  swept across models refuses the gpt-oss cell.
- **The batch keeps its report,** so a missing cell can still be explained
  after generation.

### PR #68's pairs, in the new model

`compatibility.md` in PR #68 listed the pairs a table would hold. Each one
has a home now:

| Pair in PR #68 | Now | Kind |
|---|---|---|
| scorer × output type | the scorer's view is among the output's views; each view is proved once, at commit | derived |
| output type × connection (coercion) | the coercion's mode against the model's capabilities, with `auto` resolved from the model's facts | derived from facts |
| sampling params × connection (the provider settings a model honours) | reasoning × model: reasoning is an intent that the model's facts translate, and `provider_params` is dissolved | derived from facts |
| sampling params × connection (settings never sent: `top_k`, `n`) | gone: `top_k` goes out in `extra_body`, and `n` is scrapped | none |
| instruction × output type | the output's guidance fills the instruction's slot, and resolution checks that the slot is placed | derived |
| scorer × expectation | scorer × case: does the case have a target the scorer reads, and does it parse? Both are checked when the batch is planned, not when the run is scored. | derived |

### What goes away

- **Names built from components.** PR #68 found that such names "must be
  injective over the product". Cells have labels, not names.
- **Agents held only by the archive,** and runs under a shared branch.
  Nothing needs a branch to run.
- **One agent per batch** (`BatchModel.agent`). A batch has cells.
- **One copy of an output type per mode.** Coercion is its own slice.
- **Reshaping a schema to suit a scorer.** Views replace it.
- **Merged sampling params** (`sampling_params = ["seed-locked",
  "low-reasoning"]`) and the anonymous records they commit. The seed
  belongs to the trial, and reasoning is a slice.

## 6. The entities

Every entity keeps the branch fields it has today: `name`, `owner`,
`timestamp`, `target`, `collaborators` and `tags`, and gains `details`, the
JSON column of its plain details (§1). None of them is fingerprinted.

The notes say what each field holds, and the rules a record is held to when
it is committed. A record that breaks one is refused, with the reason.

### Below the request

**machine**: a thing. Any change to its hardware makes a new machine.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `machine_id` | trail | yes | a UUID assigned at registration, and the only identifying field |
| `unreliable` | details | no | true for a cloud provider, where nothing below its requests can be checked; false by default |
| `specs` | details | no | GPUs (the model as `nvidia-smi` names it, memory in MiB, the UUID as `GPU-…`), CPU, RAM in GiB, location. The GPU UUIDs back the check in `data-generation.md` §1. |

**os**: a thing.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `toplevel` | trail | yes | the system's store path, the target of `/run/current-system` |
| `flake_rev` | details | no | |
| `specs` | details | no | hostname, kernel, NVIDIA driver, nixpkgs revision. A container has no kernel or driver of its own: they are its host's. |

A store path is `/nix/store/<32 characters of Nix's base32>-<name>`,
wherever one is asked for.

**model**: a thing.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `blob` | trail | yes | a hash of the directory vLLM loads: the store path of a fixed-output derivation. For a cloud model, the provider's dated model name stands in, unverified. A value that starts with `/` must be a store path. Any other value with a `/` in it is refused as a repository name, which vLLM would resolve to whatever revision it finds when it starts. |
| `source` | details | no | the Hugging Face repository and commit, pinned: `<owner>/<repository>@<40 hex digits>` |
| `specs` | details | no | family, parameter count, active parameter count for a mixture of experts, quantization, context length, licence |
| `facts` | details | no | what resolution reads (§2), below |

A model's facts have four parts:

- **`reasoning`** translates each intent: `off`, `on`, `minimal`, `low`,
  `medium`, `high` and `xhigh`. A fact is a request fragment, the name of
  another intent it collapses into, or `{ refused = "why" }`, and an intent
  with none is refused for want of one. `default` names the model's own
  intent.
  - A fragment writes only reasoning's fields: `chat_template_kwargs`,
    `reasoning_effort` and `thinking_token_budget`.
  - A collapse must end in a fragment or a refusal, and collapses can't go
    round.
  - `budget` says which field a token budget goes in and what it needs of
    the serving (`{ field = …, needs = … }`), or refuses budgets.
- **`sampling`** gives `recommended`, the vendor's values per reasoning
  mode, and `generation_config`, what vLLM gives a field a request leaves
  out. A mode is an intent with a fragment of its own, and only a mode can
  have sampling recommended for it.
- **`coercion`** says which modes work: each is `{ needs = …, note = … }`
  or a refusal. `default` names the mode `auto` resolves to, and it must be
  one that works. The note is what a report says about the mode on this
  model.
- **`profile`** overrides pydantic-ai's profile, so that nothing hangs on
  the served name.

What a fact can need of the serving is a reasoning parser or a tool-call
parser.

**serving**: the start-up settings. vLLM only.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `engine` | trail | yes | the store path of the vLLM package |
| `args` | trail | yes | arguments that change what the model reads or the numbers, in canonical form (the table in `data-generation.md` §1). Resolution reads them for couplings, such as whether a reasoning parser is set. |
| `env` | trail | yes | environment variables that do the same, such as `VLLM_BATCH_INVARIANT` and `VLLM_SYSTEM_START_DATE` |
| `performance` | details | no | arguments that only change speed, recorded for latency comparisons |

- **Canonical form:** an argument is its long name without its dashes,
  with `_` spelled `-`, so two spellings of one argument are one. An
  argument given twice is an error, and the arguments are kept sorted.
- **Each argument has one home.** Code lists the arguments that change the
  output and those that only change speed, and one in the other's place is
  refused. `--model` is refused as the model's blob, `--served-model-name`
  as the stack's served name, and `--api-key` as a secret the stack names.
- **What a serving provides:** a reasoning parser where `reasoning-parser`
  is set, and a tool-call parser where `tool-call-parser` and
  `enable-auto-tool-choice` both are.

**client**: a thing.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `build` | trail | yes | the store path of the chatddx build. A run from a dev shell has none, and is recorded as such. |
| `rev` | details | no | for a dev shell, the checkout's commit, with `-dirty` where it has changes |
| `packages` | details | no | the versions of `pydantic-ai-slim`, `openai` and `inspect-ai`, by distribution |

A run records the client it ran on itself: the build's trail, and the
revision and versions where it ran. It reads no client branch.

**stack**: a composition, and a variation of the model slice. It replaces
`connection`.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `machine` | trail | yes | |
| `os` | trail | yes | null for cloud |
| `host_os` | trail | yes | for a NixOS container, the host's OS, which holds the kernel and the NVIDIA driver; null otherwise. It needs the container's OS beside it, and must differ from it. |
| `model` | trail | yes | |
| `serving` | trail | yes | null for cloud |
| `endpoint` | details | no | where requests go: a URL |
| `served_name` | details | no | the `model` field of the request |
| `api` | details | no | `vllm`, or the cloud API a cloud stack names: `openai-chat`, `openai-responses`, `anthropic` or `google` |
| `credential` | details | no | the name of a secret, never the secret |

Resolution needs a stack's API, endpoint and served name. It sends to vLLM
only, for now: another API is refused as later.

`data-generation.md` counted the client as part of the stack. As an entity
it stands apart: it changes with every chatddx deploy while the server
doesn't, and a run joins the two.

### Request-time slices

Each entity below is one slice, and each of its records is a variation.

**instruction**

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `system` | trail | yes | the template for the system message (Handlebars, via `TemplateStr`); empty for none |
| `user` | trail | yes | the template for the user message; `{{case}}` reproduces today's behaviour |
| `variables` | trail | yes | the variables the templates place, from a fixed list: `case`, and the slots other slices fill, `output_guidance`, `schema_prompt` and `tool_guidance` |

- Every declared variable is placed as a value, and every variable placed
  is declared. `case` is always declared.
- The case is a value, never a condition: a template places it and never
  branches on it, so equal request skeletons mean equal requests for every
  case (`data-generation.md` §3.1). A slot may be a condition as well, so a
  template can leave out the text around a slot no slice fills.
- A declared slot no slice fills renders as nothing.
- A variable declared twice is an error. Declarations are kept in the fixed
  list's order, so the same set is the same content.

**output**

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `schema` | trail | yes | a valid JSON Schema (draft 2020-12 unless it names its own), kept as written, key order included; null for free text |
| `guidance` | trail | yes | the text for the `output_guidance` slot: what to produce, and in what order; null for none |
| `views` | trail | yes | the readings it offers scorers (§4). Each maps a view name to a path into the schema or, for free text, to a parser. Views are not part of the contribution. |

**coercion**: new, split from output.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `mode` | trail | yes | native, tool, prompted or auto (resolved from the model's facts) |
| `schema_prompt` | trail | yes | the template that shows the schema to the model, for the `schema_prompt` slot. It places `{{schema}}`, the output's schema as indented JSON, and nothing else. Null means the schema isn't shown. Prompted mode requires one. |
| `tool_description` | trail | yes | what the tool the answer is given through is said to be, in tool mode: text the model reads, placing nothing. Tool mode requires one, and so does `auto` where it resolves to tool. Native and prompted modes refuse one. |

**reasoning**: new.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `effort` | trail | yes | default, off, on, minimal, low, medium, high or xhigh: pydantic-ai's `ThinkingLevel`, plus `default` for the model's own, which resolution looks up and writes out |
| `budget` | trail | yes | a positive number of tokens, or null. `off` refuses one. |

**sampling**

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `defaults` | trail | yes | what a field left out means: `model` for the model's generation config, or `recommended` for what the model's facts recommend in the resolved reasoning mode. A cell whose model's facts don't give the one asked for is refused. |
| `temperature`, `top_p`, `top_k`, `max_tokens`, `presence_penalty`, `frequency_penalty`, `stop` | trail | yes | an explicit value overrides the defaults; resolution writes every value it used into the request. Temperature is 0 to 2, top-p above 0 and up to 1, top-k −1 (off) or more, the penalties −2 to 2, and max tokens positive. |

**toolset**: it replaces `tool_group`.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `tools` | trail | yes | ordered; at least one, and no two of one name, which would be one tool to the model |
| `guidance` | trail | yes | the text for the `tool_guidance` slot; null for none |

Tools need a tool-call parser on the serving: resolution refuses a toolset
on a serving without one.

**tool**: part of a toolset, not a slice.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `name` | trail | yes | the name the model sees, as the OpenAI API takes it: letters, digits, `_` and `-`, at most 64 |
| `description` | trail | yes | empty by default |
| `parameters` | trail | yes | a JSON Schema, kept as written, key order included; an object with no properties by default |
| `implementation` | details | no | an entry point into one of chatddx's own tool files, `chatddx.runtime.tools.<file>:<function>`; each run records the git blob of the file that ran |

- **Only chatddx's own tool files run,** whoever's branch names them: an
  entry point outside `chatddx.runtime.tools` is refused. A file is loaded
  afresh from its bytes each time, and the run records those bytes' git
  blob id: `git cat-file blob <id>` gets them back. A tool file imports
  nothing else of chatddx's, so the file is all of chatddx that ran.
- **A call's arguments are held to the parameters first.** What doesn't
  hold goes back to the model as the tool's answer, and so does an error
  the function raises.
- **A request carries a tool's parameters inlined,** as it does an
  answer's schema (§4).
- A test holds each tool file's function to its parameters: the same
  names in the same order, required exactly where there is no default, and
  the same defaults and types.

### The configuration and the case

**configuration**: a composition. It replaces `agent`.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `instruction`, `output`, `coercion`, `reasoning`, `sampling` | trail | yes | one variation of each request-time slice |
| `toolset` | trail | yes | optional |

**case**

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `payload` | trail | yes | unchanged: the case as the model receives it, through the instruction's `case` variable |

### Trials and runs

A trial is history, not part of the registry. It is content, like a trail:
the configuration, the stack and the case it points at, by their trails,
and its seed, or none. Runs of the same four are runs of one trial,
whoever made them: a trial belongs to no one, and each run to whoever made
it. (The code still keys a trial by its owner too, §12.) A trial can be run
more than once, to see its seed hold, to retry one that errored, or on the
client of a later deploy. A trial with no seed is a trial too, and its runs
are draws that can't be repeated.

Each run records:

- who ran it, when it started and finished, and whether it completed or
  errored. It completes when the model answered, even with an answer that
  doesn't parse or hold, or with none after five rounds of tools. It errors
  when the model or the server failed, or when it was stopped;
- the client it ran on: its build's trail, and the revision and package
  versions it ran with;
- the branch rows whose details resolution read, the stack's and the
  model's, and each tool's, with the git blob of the file that ran for it;
- the requests and responses themselves, byte for byte
  (`data-generation.md` §4);
- the output value, whether it is valid, the last response's finish
  reason, and the error, if any (§4);
- its session: the exchange as pydantic-ai's messages, with a message for
  the error where there was one. A later run could continue a session, as
  a chat would, though no run does yet;
- its scores (§4): per scorer, the value, what in the answer it rests on or
  why there is none, and what it was made with: the view, the target, and
  the git blob of the scorer's file. A run scored again keeps every score.

A batch is history too (§5).

## 7. Current fields, mapped

**Every trail**

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `id` | kept | no |
| `fingerprint` | kept. Its format gains a scheme and version, for example `cddx-trail/1:sha256:…`, and canonicalization keeps order wherever the model reads it (`data-generation.md` §3). | it is the fingerprint |
| `timestamp` | kept, as the time the content was first seen | no |

**Every branch**

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `id`, `name`, `owner`, `timestamp`, `target`, `collaborators`, `tags` | kept | no |
| `version_count` (an annotation) | kept | no |

**instruction**

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `definition` | `instruction.system`. Text that asks for one output ("fill in the management plan based on the case") moves to that output's `guidance`. | yes |

**connection** (removed)

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `provider` | `stack.api` (details) | no |
| `model` | `stack.served_name` (the request's `model` field) and `model.source` (details); identity moves to the new `model.blob` | no |
| `endpoint` | `stack.endpoint` (details) | no |
| `profile` | `model.facts` (details) | no |

**sampling_params** (removed; split into sampling and reasoning)

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `temperature`, `top_p`, `max_tokens`, `presence_penalty`, `frequency_penalty` | `sampling`, same names | yes |
| `top_k` | `sampling.top_k`, and now actually sent (via `extra_body`) | yes |
| `stop_sequences` | `sampling.stop` | yes |
| `seed` | scrapped from the registry; it becomes the trial's, one per replicate of a batch | no |
| `n` | scrapped | no |
| `logit_bias` | scrapped: its keys are token ids, so a variation carrying them would fit only one tokenizer | no |
| `provider_params` | dissolved. The reasoning switches it carried (`chat_template_kwargs.enable_thinking`, `openai_reasoning_effort`) become `reasoning.effort`, which the model's facts translate. Anything else needed later becomes a typed field of the slice it belongs to. | yes, as those fields |

**output_type** (split into output and coercion)

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `definition` | `output.schema` | yes |
| `coercion_strategy` | `coercion.mode`; PR #68's `auto` is kept as a mode | yes |
| `validation_strategy` | scrapped: research trials record validity instead | no |
| `output_retries` | scrapped with it | no |

**tool**

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `command` | split into `tool.name` (what the model sees) and `tool.implementation` (what runs) | yes and no, respectively |
| `type` | scrapped: only `function` tools were ever built | no |
| `description` | `tool.description` | yes |
| `parameters` | `tool.parameters` | yes |

**tool_group** (renamed toolset)

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `instructions` | `toolset.guidance` | yes |
| `tools` | `toolset.tools` | yes |

**agent** (renamed configuration)

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `instruction` | `configuration.instruction` | yes |
| `connection` | removed: the stack is chosen per trial, so one configuration can run on any model | no |
| `sampling_params` | `configuration.sampling` and `configuration.reasoning` | yes |
| `output_type` | `configuration.output` and `configuration.coercion` | yes |
| `tool_group` | `configuration.toolset` | yes |

**case**

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `payload` | `case.payload` | yes |
| `expects` (details) | removed: targets move to inspect. §11 proposes bringing them back as the case's `targets`, by kind. | no |

**expect** (removed)

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `payload` | inspect: a sample's `target`, keyed by the case; for now `targets.toml`, and as proposed in §11, the case's `targets` | no |
| `scorer` | inspect: one of the batch's scorers | no |

**scorer** (removed)

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `command` | inspect scorers that read views: `regex_match` becomes `reciprocal_rank` over `differential` (as in PR #68), and `exact_match` reads `text`. §11 proposes a new `scorer` entity: a function, the view it reads and the kind of target it holds that to. | no |

**Views.** `super_agent`'s flat form becomes the configuration's, and every
other view follows its entity. Form data isn't identity.

**batch** (history, not registry)

| Current field | Becomes |
|---|---|
| `agent` | `base`: a configuration and a stack |
| `case_tags` | kept |
| `scorers` | inspect scorers, each with the view it reads; as §11 proposes, the registry's scorers |
| (new) | `varied`, `replicates` |

An experiment becomes a trial, which `data-generation.md` §4 describes,
and a run stays: one go at a trial, one pydantic-ai agent run. PR #68's
`RunModel.output` stays the run's `output`.

## 8. New fields, and what was left out

Only the fields the redesign cannot work without were added:

- **`machine.machine_id`, `os.toplevel`, `model.blob`, `client.build`:**
  the single identifying fields of the things below a request.
- **`machine.unreliable`:** marks what can't be checked.
- **`serving.engine`, `serving.args`, `serving.env`:** the start-up
  settings, identified separately from the OS.
- **`stack` and its relations:** which things answered a request.
- **`model.facts`:** what resolution reads to realize variations on each
  model, structured as in §2.
- **`instruction.user`, `instruction.variables`:** templating instead of a
  text blob, with its slots declared.
- **`output.guidance`, `coercion.schema_prompt`, `coercion.tool_description`,
  `toolset.guidance`:** the text a slice brings with it, and whether the
  model sees the schema.
- **`output.views`:** where scorers read an output.
- **`coercion.mode`:** the mode, as a slice of its own.
- **`reasoning.effort`, `reasoning.budget`:** reasoning as a slice of its
  own, with `default` as a variation.
- **`sampling.defaults`:** what a null means, so that one sampling
  variation fits every reasoning variation.
- **`batch.varied`, `batch.replicates`:** a batch compares variations.

Left out on purpose, to be added when a study needs them:

- `min_p`, `repetition_penalty` and the other vLLM-only sampling settings;
- a reasoning slot in the instruction;
- `tool_choice`;
- few-shot examples;
- a case's language, source and stage (tags cover dataset membership for
  now);
- pricing;
- a model-graded extractor for free text, which would be a pinned judge
  configuration like any other;
- the `plan` view, and rubric scoring;
- fractional designs.

Left out for good: an authored table of compatible pairs (§3).

## 9. Resolution

- **A configuration only names variations, one per request-time slice.**
  Resolution turns a cell into one coherent request. It:
  - translates each intent with the model's facts;
  - looks up defaults;
  - fills the instruction's slots;
  - checks couplings.

  Write sets are disjoint by construction, so no two slices ever write one
  field. Resolution is `runtime/resolution.py`.
- **A cell is resolved once, without its case.** Each trial renders the
  messages with a case of its own.
- **Its order follows what each slice is resolved against:**
  1. the model;
  2. reasoning, translated by the facts;
  3. sampling, whose defaults need the resolved reasoning mode;
  4. output and coercion, the mode checked against the model's facts and
     the serving;
  5. the toolset, which fills the `tool_guidance` slot;
  6. the instruction, with every filled slot placed.

  Reasoning and sampling are resolved together, since a budget has to fit
  in the `max_tokens` sampling resolves to.
- **Its outcomes** are realized, collapsed and refused (§2). Every refusal
  in a cell is gathered, each with its slice and reason.
- **What the data model owes it:**
  - slot names, fixed by convention for each slice: `output_guidance`,
    `schema_prompt` and `tool_guidance`, and later `reasoning_guidance`;
  - the instruction's declared variables;
  - the model's facts, structured as in §2;
  - the serving's arguments, for couplings such as a reasoning parser;
  - each slice's write set, declared in code, once per slice;
  - couplings, as what the model's facts need of the serving.
- **Where its result goes:** into the requests a run sends, which the run
  keeps with the branch rows resolution read (§6), and for a batch into its
  report (§5).

## 10. Order and storage

- **Commit order.** `EntityName` keeps its rule that anything an entity
  references is committed first. The order becomes: machine, os, model,
  serving, client, stack, tool, toolset, instruction, output, coercion,
  reasoning, sampling, configuration, case.
- **Schema storage.** `output.schema` is stored as text, not `jsonb`,
  because `jsonb` re-sorts keys. So are a tool's `parameters` and a run's
  `output`.
- **Fingerprint column.** A versioned fingerprint no longer fits
  `TrailModel.fingerprint` (`max_length=64`), so the column grows. Short
  forms such as `short_fingerprint` read the hex part.

## 11. Scorers and targets in the registry (proposed)

Today the targets are read from `targets.toml` when a run is scored, and
the scorers are a table in code (§4). The inventory is the source of truth
for now, but everything in it is to be kept in the portal. Once people work
there, the database is the source of truth, and the TOML files only seed
it. So scoring has to read scorers and targets from the registry, and
nothing but a scorer's function stays in code. This section proposes how.

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

### The proposal

- **A scorer is an entity:**

  | Field | In | Fingerprinted | Notes |
  |---|---|---|---|
  | `function` | trail | yes | an entry point into one of chatddx's own scorer files, `chatddx.scoring.scorers.<file>:<function>` |
  | `view` | trail | yes | the view it reads (§4) |
  | `target` | trail | yes | the kind of target it holds the view to, or null for a scorer that needs none |
  | `args` | trail | yes | further keyword arguments to the function; empty by default |
  | `metrics` | details | no | how its values are summed up, by name: `mean`, `stderr`, `accuracy` and the like, computed with inspect's own metrics |

  - It is inspect's `ScorerSpec`: the function is the name, the view, the
    target and the arguments are the options, and the metrics are the
    metrics.
  - What can change a score is content, so a score can cite exactly what
    made it. Metrics change no score, so they are details, and a change to
    them leaves every run scored.
  - Unlike inspect, the view and the kind of target are fields of their
    own rather than arguments, because pairing a scorer with a run reads
    them: set membership, as in §4.
  - The function runs as a tool does: from an allowlisted package, loaded
    afresh, with its file's git blob recorded on each score. Where inspect
    names a commit, and can only say that the tree was dirty, the blob
    names the code that scored.
  - A scorer is named per owner, like every entity. The archive's four are
    seeded from `inventory/scorers.toml`:

    ```toml
    [scorer.reciprocal_rank]
    function = "chatddx.scoring.scorers.patterns:reciprocal_rank"
    view = "differential"
    target = "diagnosis"
    metrics = ["mean", "stderr"]
    ```

- **A case's targets are its details:**

  | Field | In | Fingerprinted | Notes |
  |---|---|---|---|
  | `targets` | details | no | what the case is expected to yield, by kind: `diagnosis`, `warning` and `disposition`. Each is text its scorers read: for the pattern scorers, a pattern (§4). |

  - inspect keeps the target with the sample, and a case is chatddx's
    sample. The kinds are chatddx's own: inspect has one target per sample,
    and each of chatddx's scorers reads the kind it names.
  - Details, not content: a target changes nothing the model reads, and a
    case's fingerprint names what it reads. Like a model's facts, targets
    are versioned by branch row: a changed target makes a new row, and a
    score records the row it read.
  - The kinds are a vocabulary kept in code, as the views are.
  - The archive's targets are seeded from `cases.toml`, as `targets.*` in
    each case's record, and `targets.toml` goes. It can't stay a file of
    its own: an inventory that extends another replaces its records whole,
    and doesn't merge them.
  - A run is held to the targets of the scoring identity's own branch of
    the run's case, or else the archive's: the newest row that holds the
    run's case trail. So a fixed target reaches earlier runs of the same
    payload, and a new payload comes with targets of its own.
  - This brings back what `2bf6af7` made of a case's `expects`: details on
    the case's branch.
- **Which scorers apply to a run:** every scorer the scoring identity can
  see, its own and those shared with it, whose view the run's output
  offers, and whose kind of target the run's case has, if it needs one. A
  batch will name its scorers instead (§5).
- **A score** points at its scorer's trail instead of naming it, and at
  the case branch row whose targets it read. It keeps the target it held
  the view to, the blob, the value, the answer and the reason, and who
  scored. The view is the scorer's.
  - A run is outstanding for a scorer, for the identity that scores it,
    until it has a score from that scorer's trail with the target and the
    blob as they are now.
  - The fields are inspect's `Score`: a null value is inspect's unscored.
    `explanation` and `metadata` can join when a scorer needs them.
- **Parsing needs nothing new.** `scorer` is one more entity, and a case's
  `targets` pass through as details. At commit, a scorer's function must
  have an entry point's shape, its view and kind must be in their
  vocabularies, its arguments must be an object, and its metrics must be
  known. The package is held at load, as a tool's is. Whether a target
  parses is for the scorers that read it to say: a test checks the
  archive's, and scoring checks the rest (§4).
- **In the portal,** a scorer is shown like a tool, and a case's form gains
  its targets. An edit there makes a new version, and that makes runs
  outstanding again.
- **Later, from inspect:** people's edits to scores, as rows beside a
  score, each with its author, time and reason, when clinicians adjudicate
  in the portal; reducers over a batch's replicates; and a log per cell,
  each scorer as an `EvalScorer` and the case's targets in the sample's
  metadata.

### Steps

1. **Registry:** the `scorer` entity (schemas, models and bundle; it
   refers to nothing, so it can come last in commit order), the target
   kinds, and the case's `targets` detail.
2. **Inventory:** `inventory/scorers.toml` with the four scorers.
   `cases.toml` takes the targets from `targets.toml`, their `# guessed`
   marks kept, and the test inventory takes its own. `targets.toml`,
   `test-targets.toml` and `settings.TARGETS_PATH` go.
3. **History:** a score's `scorer` becomes a reference to the scorer's
   trail, and it gains the case branch row it read and who scored. Its
   `view` column goes. Migrations are reset, as this branch has done
   before.
4. **Scoring:** the scorers and targets come from the registry. The table
   in code goes, and summaries use each scorer's metrics.
5. **Repl:** `scorers` lists the scorers the identity can see, with their
   owners and metrics. `score` stays as it is.
6. **Tests:** the parser and `init-data` with scorers and targets. Scoring
   with targets committed, so a changed target is a new version of the
   case. The archive's scorers' arguments held to their functions'
   signatures, as tools' parameters are, and the archive's targets held to
   parse.
7. **This note:** §11 and the passages that point to it lose
   "proposed", and §4 describes scoring as it then is.

### Open

- **A case that should raise no warning.** A plan that rightly leaves
  `acute_warning` null reads as no warning, and `warning_mentions` scores
  it 0. A target could say that no warning is expected, and score such a
  plan 1.

## 12. Where the code lags

Where this note and the code differ, the note is what was decided:

- **Trials:** a trial is its configuration, stack, case and seed (§6), but
  the code keys it by its owner as well. `TrialModel` is to lose its owner
  and collaborators and gain a unique constraint over the four, with nulls
  not distinct. `wipe-data` is to remove a user's runs, and then any trial
  left without a run.
- **Docstrings:** the toolset's still calls it deferred, and the output's
  still says every output offers `text`.
- **Run status:** the model keeps statuses from the worker before the
  redesign: stored, queued, running and scored. Only completed and errored
  are set.
- **Request hashes** (`data-generation.md` §3) aren't computed yet.

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
