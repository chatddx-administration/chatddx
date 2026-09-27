# The chatddx datamodel

This document describes the underlying data structure of ChatDDX.

For using it, see `portal.md` (admin interface), `repl.md` (the shell),
`inventory.md` (the files that seed the database) or
`api.md` (how external tools may connect).

## 1. The classes of data

ChatDDX have two classes of data, both immutable and append-only: Repo and
History. History is the laboratory ledger that logs experimental runs,
conversations and scores. Repo is a collection of 16 versioned controlling factors:
```
case
client
coercion
configuration
instruction
llm
machine
os
output
reasoning
sampling
scorer
serving
stack
tool
toolset
```

Their integrity is assured by fingerprinted Trails (data) and associated Branches (metadata).

A Branch is called "branch" because it behaves like a git branch, with a timeline
attached to its name. So there's a head (canon), and it can be committed to, but it can't
be changed.

## 2. Guiding principles
We want to be able to generate thousands of experiments on whatever inference server we
come by, and find which factors improve their capability in speed and accuracy.
Each experiment reproducible, tomorrow or in five years, so that we can begin to lay the foundation
of knowledge about what an LLM can be trusted with and what it shouldn't.

This is a challenge, in particular grouping controlling factors in such a way that they
represent something meaningful *and* can be reliably applied across models and machines.
Due to the chaotic ecosystem that is LLMs 2026, the path ChatDDX took is a patchwork of
careful compromises to cater to our context specifically: Producing accurate management plans
for emergency healthcare on local, open weight models. This document describes every part
in detail and how they fit together.

## 3. Trails: the data

A **trail** is a factor's content: whatever about a thing could change
what a run comes to, and nothing else. It is named by its
**fingerprint**, a hash of that content:

```
cddx-trail/1:sha256:3f9a1c…
```

that is, the scheme and its version, the hash, and its hex digest. The
short form, `3f9a1c`, is what users see.

- **Identical content is one trail,** whoever writes it. Two owners with
  the same vignette share one case trail, and a configuration two people
  run is one configuration.
- **A trail never changes.** A trigger on every trail table refuses an
  update or a delete, and the fingerprint is computed from the content,
  never given, so the two can't disagree. A change is another trail.
- **A trail names the trails it is made of** by their fingerprints: a
  stack its machine, systems, model and serving; a configuration its
  slices; a toolset its tools, in order. A part left out, such as a
  configuration's toolset, is `null`. So a change anywhere below changes
  everything above it: a reworded output guidance is a new output, and a
  new configuration of each configuration that holds it.

### The canonical form

The fingerprint hashes the content written as JSON in one way only, the
way RFC 8785 (JCS) writes it: no whitespace, the keys of an object sorted
by their UTF-16 code units, numbers as ECMAScript writes them (`1.0` is
`1`), and strings escaped only where JSON must. Nothing but JSON has the
form: a NaN is an error, not a fingerprint.

Sorting makes a fingerprint blind to the order keys were written in.
Where the order is content, it is kept:

- **An answer schema and a tool's parameters keep their written order.**
  The model reads a schema's fields in order, and guided decoding writes
  them in that order, so two fields swapped make another schema. Each
  object in them is hashed as its list of key and value pairs
  (`{"ordered": [[key, value], …]}`), which the sort can't reach.
- **A list keeps its order** everywhere: a toolset's tools are shown to
  the model in order.
- **What is read as a set is written one way.** A serving's arguments and
  environment are read as sets, so their order is nothing, and an
  argument has one spelling: `--max_model_len` and `max-model-len` are one
  argument. An instruction's variables are put in one order too.

So trails are meticulous: a seemingly negligible difference, such as a
reworded description in a schema, makes a different trail, while the
order vLLM's arguments were given in makes none.

### What goes in a trail

Only what could change what a run comes to. What describes a thing, says
where to reach it, or says how to judge its answers is a **detail** of its
branch (§4). Where that line falls is decided factor by factor (§5), and
it is the first of the compromises: a trail that holds too little lets two
experiments pass for one, and a trail that holds too much splits one
experiment in two each time someone edits a description.

## 4. Branches: the metadata

A **branch** is an owner's named timeline of trails. Each version of it
is a row that holds:

- its **owner**, an identity, and its **name**;
- its **trail**;
- its **details**: what describes the trail without being part of it,
  such as a machine's specs, a model's facts, a stack's endpoint, or a
  case's targets;
- when it was committed.

Its **tags** and **collaborators** hang on the version.

### The head and the timeline

The versions under one owner and name are the branch's timeline, and the
newest is its **head**. A commit of a trail and its details to a branch:

- **changes nothing** where the head holds that trail with those details
  (`init-data` says `validated`);
- **makes a new version,** the new head, where either differs (`created`).
  The versions before stay as they were.

A version holds the details it was committed with, and the default of
each it wasn't given: nothing is inherited from the version before. A
detail the factor doesn't have is refused.

Tags and collaborators aren't versioned. A change to them alone is made
on the head, and a new version carries over those it isn't given, so what
is shared stays shared. A tag belongs to one owner and one factor: alice's
case tag `edn` is neither the archive's nor a machine tag of hers.

Details are the owner's: two owners of one trail describe it each their
own way. One vignette can be alice's case, held to her targets, and the
archive's, held to its own.

### Who sees what

An identity sees its own branches, and those shared with it: those whose
collaborators name it. Its own shadows a shared one of the same name. Two
others' branches of one name are told apart by owner, as `bob/plan`.

A portal user is the identity of their user name, and the API speaks as
the signed-in user's identity, or as `guest`.

### The archive

The identity `archive` owns the inventory (§11), what the lab starts
from. `chatddx init-data alice` commits it as the archive's, and makes
alice a collaborator on the head of every branch it committed; with
`--with-giftbag`, alice is also given what is asked, the slices and the
configurations, as her own (§5). The archive's configurations run as they
are; another owner's, shared, runs once it is saved as one's own.

### Closures and copies

A commit gives the owner a branch on every trail the committed one
reaches that they have no branch on, named after the factor and the short
fingerprint, such as `reasoning 3f9a1c`, with default details. So nothing
an owner's branches reach is nameless to them. The factors are committed
in an order where anything a factor refers to comes first (§5), so an
inventory's parts have the names their records gave them before anything
holding them is committed.

Saving a cell's configuration (`save` in the repl) makes it the owner's,
and gives the owner a copy of the archive's branch of each part it
reaches that they have no branch on, name and details included, unless
they already have a branch of that name; such a part is named by its
fingerprint instead.

### Deleting

A case can be **deleted**: taken out of sight, its timeline kept.
Deleting commits a version whose `deleted` detail is true, and committing
the case again brings it back. A deleted case is passed by in lists,
plans and lookups by name, and a shared case of the same name shows again
in its place. It still holds its vignette: its runs keep its name, and
are scored against its targets, unless another of its owner's cases holds
the vignette.

Otherwise rows are removed only where nothing reads them: from the
portal, a case, or a version of one, that no score is held to and none of
its owner's runs or batches read; and with `chatddx wipe-data`, an
identity's own, where no one else's history reads them (§12).

## 5. The factors

The sixteen factors fall in three groups: what answers, what is asked,
and what is asked about and how it is judged. Each is a kind of record:
`machine` is a factor, and `pelle` a machine. They are committed in the
order below, anything a factor refers to before it.

**What answers**

| Factor | Content, in the trail | Details, in the branch |
|---|---|---|
| `machine` | `machine_id` | `unreliable`, `specs` |
| `os` | `toplevel` | `flake_rev`, `specs` |
| `llm` | `snapshot` | `source`, `specs`, `facts` |
| `serving` | `engine`, `args`, `env` | `performance` |
| `client` | `build` | `rev`, `packages` |
| `stack` | its `machine`, `os`, `host_os`, `llm` and `serving` | `endpoint`, `served_name`, `api`, `credential`, `max_jobs` |

Everything below the request: which machine, which system, which model,
started how, and which build of chatddx sent it (§7). Their details
describe them: specs, facts, where to reach them. They are a class of
record apart, which the archive keeps for everyone and no owner is given.

**What is asked**

| Factor | Content, in the trail | Details, in the branch |
|---|---|---|
| `tool` | `name`, `description`, `parameters` | `implementation` |
| `toolset` | its `tools`, `guidance` | |
| `instruction` | `system`, `user`, `variables` | |
| `output` | `answer_schema`, `guidance`, `views` | |
| `coercion` | `mode`, `schema_prompt`, `tool_description` | |
| `reasoning` | `effort`, `budget` | |
| `sampling` | `defaults`, `temperature`, `top_p`, `top_k`, `max_tokens`, `presence_penalty`, `frequency_penalty`, `stop` | |
| `configuration` | its `instruction`, `output`, `coercion`, `reasoning`, `sampling` and `toolset` | |

The request-time slices, and the configuration that picks one variation
of each (§6, §8). They have no details but a tool's implementation: all
they say reaches the request, so all of it is content. A new owner is
given them to start from.

**What is asked about, and how it is judged**

| Factor | Content, in the trail | Details, in the branch |
|---|---|---|
| `case` | `vignette` | `language`, `targets`, `deleted` |
| `scorer` | `function`, `view`, `target_kind`, `args` | `metrics` |

The cases, and the scorers that hold answers to their targets (§9). The
archive's are shared with its users, and an owner adds cases of their
own.

### Content or detail

Whether a field is content comes down to one question: would a run come
out otherwise if it changed? The answers are compromises, each for a
reason:

- **A model is its files.** `snapshot` is the Nix store path of the
  directory vLLM loads (weights, tokenizer, chat template, generation
  config), fetched by hash. A repository name can't be one, since it
  could resolve to any revision; where the files came from, pinned to a
  commit, is the detail `source`.
- **A model's facts are details.** They are claims about the model, which
  resolution reads to turn intents into a request (§6). A changed fact
  changes what is sent, yet the model is the same model: so a run records
  the version whose facts it read, and what it sent, byte for byte (§10).
- **Where and how a stack is reached is a detail:** its endpoint, the
  name the model is served under, its API, its secret's name, and how
  many jobs it takes at once. They say where, how and how often requests
  go, not what comes back, and a run records the version it read.
- **Speed is a detail.** A serving's arguments that change what the model
  reads or the numbers it computes are content; those that change only
  its speed are `performance`.
- **The client is not part of the stack.** chatddx's build changes with
  every deploy, while the servers don't, so a trial pairs a configuration
  with a stack, and each run records the client it was sent from.
- **What a tool runs is a detail.** A tool is what the model sees of it.
  The function behind it can change without the model seeing it, and each
  run records the git blob of the file that ran, which says more than any
  name could.
- **Judging is a detail of what is judged.** A case is what the model
  reads; its targets say how the answer is judged, so a changed target is
  a new version of the same case, and its runs are scored again. A scorer
  is its function, view and target kind; its metrics, how its values are
  summed up, describe it.

## 6. The cell

A run asks one model one case, in one way. The **way** is split into
**slices**, each answering one question someone might want to compare:

| Slice | The question | For example |
|---|---|---|
| stack | which model, on which machine? | `qwen3-8b-awq@pelle`, `gpt-oss-20b@malborg` |
| instruction | what is the model told? | `ddx` |
| output | what should the answer look like? | `management-plan`, `diagnoses`, `free-text` |
| coercion | how is the model held to that shape? | `native`, `tool`, `prompted`, `auto` |
| reasoning | should it think first, and how hard? | `default`, `off`, `on`, `low`, `high` |
| sampling | how does it pick its words? | `recommended`, `generation-config`, `greedy` |
| toolset | which tools may it call? | `web`, or none |

- A **variation** is one answer to a slice's question: a branch of the
  slice's factor.
- A **configuration** is one variation of every slice but the stack, the
  toolset optional. It names no model, so one configuration runs on every
  stack.
- A **cell** is a configuration and a stack, with any variation set in
  place of the configuration's own: `plan+reasoning=off` on
  `qwen3-8b-awq@pelle`. What it runs is a configuration trail all the
  same, whether or not it has a branch; saving the cell gives it one. A
  batch crosses what it varies: reasoning `off` and `on` with sampling
  `recommended` and `greedy` are four cells.
- **A slice owns everything that belongs to it,** wherever it ends up in
  the request. The management plan output carries its schema, the
  sentence that asks for it ("Fill in the management plan for the
  case."), and where the scorers find its parts; a coercion carries the
  words that show the schema, and a toolset those that introduce its
  tools. The instruction places them through **slots**, and names none of
  them, so an output can be paired with any instruction that has its
  slot.

The repl, the API, the portal and its worker put cells together, and run
them, through one internal API, `chatddx.bench`.

### Intents, facts and refusals

A variation says what is wanted, not how to get it: "reasoning off", not
"set `enable_thinking` to false". **Resolution** turns a cell into a
request, reading the model's **facts** (§7) and what its serving
provides, and each intent comes out one of three ways:

- **written** into the request, as the fragment the facts give for it;
- **collapsed** into another intent the facts say it stands for: Qwen3
  has no effort levels, so `low` and `high` are both `on`, and resolution
  says so;
- **refused,** with the reason: gpt-oss can't stop reasoning, so reasoning
  `off` on gpt-oss is refused. An intent the facts don't mention is
  refused too: nothing is guessed.

Every refusal in a cell is given at once, each with its slice, and a
refused cell runs nothing. Only stacks served by vLLM run for now; a
cloud API is refused, for later.

Facts are claims. A run records the version of the model whose facts it
read, and the repl and the API say when the model didn't do as they
promised: no thinking came back though reasoning resolved to on, or some
came back though it resolved to off.

### Resolution

Resolution happens before any case is known, in this order, since each
step needs those before it:

1. **the stack:** where the request goes, and under what name;
2. **reasoning,** translated by the facts, with a thinking budget where
   the facts put one, if the serving provides what it needs;
3. **sampling,** whose `recommended` depends on the reasoning intent, and
   whose `max_tokens` must leave room for a thinking budget;
4. **output and coercion:** the mode (`auto` is the facts' default),
   checked against the facts and the serving: on Qwen3, native and tool
   mode need a reasoning parser, unless reasoning is off;
5. **the toolset,** which needs a tool-call parser;
6. **the instruction,** every slot a slice fills placed.

What it holds to:

- **Each slice writes its own part of the request,** and no two write the
  same field: reasoning writes `chat_template_kwargs`, `reasoning_effort`
  and `thinking_token_budget`, and nothing else.
- **What pydantic-ai adds is turned off.** No words of the library's own
  reach the model. The schema is sent with its references inlined and
  nothing else changed, and the model is shown it only through the
  coercion's `schema_prompt`, or in tool mode as the answer tool's
  parameters.
- **`top_k`, and whatever reasoning writes,** go in `extra_body`, as
  vLLM takes them. The seed goes as `seed`.
- **An answer is an object.** A schema whose top level isn't one is
  refused.
- **A run asks once.** Nothing is retried. A model may call tools for five
  rounds; one still calling after that is stopped, and so is one that
  streams nothing but whitespace for 100 tokens (§10).

The repl's `show` prints what a cell resolves to: each slice's variation
beside what it became, or why it was refused, and the prompt.

## 7. What answers: the stack and its parts

A **stack** is everything below the request: which machine, which system,
which model, started how. Each part holds in its trail only what
identifies it, and describes itself in its details.

**machine**

| Field | | Holds |
|---|---|---|
| `machine_id` | content | a UUID that names the machine |
| `unreliable` | detail | true for a cloud provider's, where nothing below the requests can be checked |
| `specs` | detail | its GPUs (model as `nvidia-smi` names it, memory in MiB, UUID), CPU, RAM in GiB, and location |

**os**

| Field | | Holds |
|---|---|---|
| `toplevel` | content | the system's Nix store path, where `/run/current-system` points |
| `flake_rev` | detail | the flake revision it was built from |
| `specs` | detail | hostname, kernel, NVIDIA driver, nixpkgs revision; a container's has no kernel or driver of its own |

**llm**, the model

| Field | | Holds |
|---|---|---|
| `snapshot` | content | the Nix store path of the model's files, fetched by hash; for a cloud model, the provider's dated name. A repository name is refused. |
| `source` | detail | the Hugging Face repository and commit, `<owner>/<repository>@<40 hex digits>` |
| `specs` | detail | family, size and active size in billions of parameters, quantization, context length, licence |
| `facts` | detail | what resolution reads (below) |

A model's **facts** have four parts:

- **`reasoning`:** for each intent (`off`, `on`, `minimal`, `low`,
  `medium`, `high`, `xhigh`), the fragment to send, the intent it
  collapses into, or `{ refused = "why" }`; `default`, the intent the
  model reasons at of its own; and `budget`, the field a thinking budget
  goes in and what it needs of the serving, or a refusal. A fragment
  writes reasoning's fields and no others, and every collapse ends in a
  fragment or a refusal, never going round.
- **`sampling`:** `recommended`, the vendor's settings for each intent
  that writes a fragment, and `generation_config`, what the server gives
  a setting a request leaves out.
- **`coercion`:** for each of `native`, `tool` and `prompted`, that it
  works, with what it `needs` of the serving and a note, or that it is
  refused; and `default`, the mode `auto` means, which must be one that
  works.
- **`profile`:** settings for pydantic-ai, the library that sends the
  requests, so nothing depends on the name the model is served under.

For example, Qwen3 and gpt-oss, abridged:

```toml
[llm.qwen3-8b-awq.facts.reasoning]
default = "on"
off = { chat_template_kwargs = { enable_thinking = false } }
on = { chat_template_kwargs = { enable_thinking = true } }
low = "on"                       # no effort levels: every effort is "on"
high = "on"
budget = { field = "thinking_token_budget", needs = "reasoning_parser" }

[llm.qwen3-8b-awq.facts.sampling.recommended]
on = { temperature = 0.6, top_p = 0.95, top_k = 20, presence_penalty = 1.5 }
off = { temperature = 0.7, top_p = 0.8, top_k = 20, presence_penalty = 1.5 }

[llm.gpt-oss-20b.facts.reasoning]
default = "medium"
off = { refused = "always reasons: vLLM rejects reasoning_effort = none for harmony" }
on = "medium"
low = { reasoning_effort = "low" }
```

**serving**, how vLLM was started

| Field | | Holds |
|---|---|---|
| `engine` | content | the Nix store path of the vLLM package |
| `args` | content | the start-up arguments that change what the model reads or the numbers it computes, spelled one way |
| `env` | content | environment variables that do the same, such as `VLLM_BATCH_INVARIANT` |
| `performance` | detail | arguments that only change speed, such as memory use or the port |

Each argument has one place. One known to change the output
(`max-model-len`, `reasoning-parser`, `tool-call-parser`, `seed`,
`quantization`, …) is refused in `performance`; one known only to change
speed (`gpu-memory-utilization`, `max-num-seqs`, `port`, …) is refused in
`args`; and `--model`, `--served-model-name` and `--api-key` are refused
in both, since they belong to the model, the stack and a secret. A
serving **provides** a reasoning parser where `reasoning-parser` is set,
and a tool-call parser where both `tool-call-parser` and
`enable-auto-tool-choice` are.

**client**, the chatddx that sends the request

| Field | | Holds |
|---|---|---|
| `build` | content | the Nix store path of the chatddx build; none from a dev shell |
| `rev` | detail | for a dev shell, the checkout's commit, with `-dirty` if it has changes |
| `packages` | detail | the versions of pydantic-ai, openai and inspect-ai |

A run records the client it was sent from as that client finds itself:
its build, and beside it its revision and package versions.

**stack**

| Field | | Holds |
|---|---|---|
| `machine`, `llm` | content | the machine and the model |
| `os`, `serving` | content | the system and the serving; none for a cloud stack |
| `host_os` | content | for a container, its host's system, which holds the kernel and the driver; the container's own is its `os` |
| `endpoint` | detail | the URL requests go to |
| `served_name` | detail | the `model` of a request |
| `api` | detail | `vllm`, or a cloud API: `openai-chat`, `openai-responses`, `anthropic`, `google` |
| `credential` | detail | the name of the identity's secret sent as the API key, never the secret |
| `max_jobs` | detail | how many of the worker's jobs it takes at once, its slots; 1 unless it says more |

## 8. What is asked: the configuration and its slices

Each branch of a slice's factor is a variation of the slice. Tools are
what toolsets are made of, and a configuration picks one variation of
each slice.

**instruction**

| Field | Holds |
|---|---|
| `system` | the template of the system message; empty for none |
| `user` | the template of the user message, usually `{{case}}` |
| `variables` | what the templates place: `case`, and the **slots** other slices fill: `output_guidance`, `schema_prompt`, `tool_guidance` |

The templates are Handlebars, held to a few rules. Every declared
variable is placed, and every placed one declared. The case is placed as
a value, never tested, so a template reads the same for every case. There
are no partials, and no helpers but the blocks `if`, `unless`, `each` and
`with`. A slot no slice fills is empty, and a block leaves out the text
around it:

```
{{#if schema_prompt}}

{{schema_prompt}}{{/if}}
```

**output**

| Field | Holds |
|---|---|
| `answer_schema` | the JSON Schema a structured answer must hold to, as written, key order included; none for free text |
| `guidance` | the words that ask for the answer, for the `output_guidance` slot |
| `views` | where the scorers find each part of the answer |

A **view** is a named reading of an answer. Scorers read views, never the
answer itself, so any output that offers a view can be scored by any
scorer that reads it:

| View | What it reads |
|---|---|
| `text` | the answer as written |
| `differential` | the diagnoses, most likely first |
| `warning` | the red flags, or none |
| `disposition` | where the patient goes |
| `critical` | the diagnoses the answer marks critical |

In a structured output a view is a path into the answer: `$.acute_warning`
is a field, `$.diagnoses[*]` every item of a list,
`$.diagnoses[*].diagnosis` a field of every item, and
`$.diagnoses[?(@.critical)].diagnosis` that field of the items whose
`critical` is true. The path is proved against the schema when the output
is made, so a view always yields text, and a warning text or none. Free
text offers views through a parser instead: `whole` gives `text`, and
`lines` the `differential`, one item a line, list markers stripped.

**coercion**

| Field | Holds |
|---|---|
| `mode` | how the model is held to the schema: `native` (the server constrains the answer), `tool` (the answer is given as a tool call), `prompted` (the model is only asked), or `auto` (the mode the model's facts name) |
| `schema_prompt` | words that show the model the schema, placing `{{schema}}` and nothing else, for the `schema_prompt` slot; none to show nothing. `prompted` needs one. |
| `tool_description` | what the answer tool is said to be; `tool` needs one, and only `tool` and `auto` take one |

With free text there is no schema, and every coercion is the same.

**reasoning**

| Field | Holds |
|---|---|
| `effort` | `default`, `off`, `on`, `minimal`, `low`, `medium`, `high` or `xhigh` |
| `budget` | a number of thinking tokens, or none; `off` takes none |

**sampling**

| Field | Holds |
|---|---|
| `defaults` | what a setting left out means: `generation_config` (the model's own, as the server applies them) or `recommended` (the vendor's, for the reasoning intent resolved) |
| `temperature`, `top_p`, `top_k`, `max_tokens`, `presence_penalty`, `frequency_penalty`, `stop` | settings given outright, which win over the defaults; a `top_k` of -1 turns it off |

The seed is no slice's: it is the trial's (§10).

**toolset** and **tool**

| Field | Holds |
|---|---|
| `toolset.tools` | its tools, in order, at least one, no two of one name |
| `toolset.guidance` | words for the `tool_guidance` slot |
| `tool.name`, `tool.description`, `tool.parameters` | what the model sees: its name, what it does, and the JSON Schema of its arguments, in the order written |
| `tool.implementation` | a detail: the function that runs, `chatddx.runtime.tools.<file>:<function>` |

Only chatddx's own tool files run, loaded fresh. Each call's arguments are
checked against the parameters first, and what fails, or an error the
function raises, goes back to the model as the tool's answer. A run
records the git blob of each tool file that ran, so the exact code can be
got back with `git cat-file blob <id>`.

**configuration**

| Field | Holds |
|---|---|
| `instruction`, `output`, `coercion`, `reasoning`, `sampling` | one variation of each |
| `toolset` | one, or none |

## 9. What is asked about, and how it is judged: cases and scorers

**case**

| Field | | Holds |
|---|---|---|
| `vignette` | content | the case as the model receives it, placed through the instruction's `case` |
| `language` | detail | the vignette's language, `en` or `sv` |
| `targets` | detail | what the case is expected to yield, by kind |
| `deleted` | detail | true once the case is deleted (§4) |

An edited vignette is another case to the runs, since it is what the
model reads: the runs of the old vignette keep the targets they had. An
edited target is a new version of the same case.

A **target** is what is expected of one kind, in two parts, either of
which may be missing:

- **`text`:** what is expected, in plain words, for people;
- **`pattern`:** what the scorers look for in an answer.

A target can also be `false`, meaning none is expected. The kinds:

| Kind | Expected | Can be `false` |
|---|---|---|
| `diagnosis` | the diagnosis the case is known to have | no |
| `warning` | what the answer should warn about | yes: a case that should raise no warning |
| `disposition` | where the patient should go | no |
| `dont_miss` | a condition the differential must include, however unlikely | no |

A **pattern** is words matched against one item of an answer at a time,
one diagnosis or one line:

| Pattern | Finds |
|---|---|
| `pneumonia` | the whole word, in any case: not "pneumonias", and `mi` never inside "anemia" |
| `meningit*` | any word starting so |
| `acute coronary syndrome` | the words side by side |
| `renal & stone*` | both, anywhere in the item |
| `pneumonia \| sepsis` | either |
| `(renal \| kidney) & stone*` | parentheses group, and `&` binds tighter than `\|` |

The data is taken as it is. Nothing is signed off, and a case with
missing targets can be run: the scorers that need what is missing leave
it out, and `show` says `missing`.

**scorer**

| Field | | Holds |
|---|---|---|
| `function` | content | the function that scores, `chatddx.scoring.scorers.<file>:<function>` |
| `view` | content | the view it reads |
| `target_kind` | content | the kind of target it holds that view to, or none |
| `args` | content | further arguments for the function |
| `metrics` | detail | how its values are summed up: `mean`, `stderr`, `std`, `var`; `mean` and `stderr` unless it says |

The archive's scorers:

| Scorer | Reads | Against | Value |
|---|---|---|---|
| `reciprocal_rank` | `differential` | `diagnosis` | 1/rank of the first diagnosis the pattern finds, 0 if none |
| `first_mention` | `text` | `diagnosis` | how many characters come before the pattern is first found; no value if never |
| `warning_mentions` | `warning` | `warning` | 1 if the pattern is found, 0 if not |
| `disposition_mentions` | `disposition` | `disposition` | the same |

When a case expects no warning, `warning_mentions` gives 1 where the
answer names none, and 0 where it names one. No scorer reads `dont_miss`
yet.

A scorer **applies** to a run that completed, whose output offers its
view, and whose case has a pattern for its kind of target, or `false`; a
scorer with no kind of target applies to every completed run whose output
offers its view. What it makes of the run is a score (§10).

## 10. History: trials, runs and scores

History is the ledger of what was run and what came of it. It refers to
the Repo, to trails for what a run was and to branch versions for what
it read, and nothing in the Repo refers to it.

```
score ─┬─> run ─┬─> trial ─┬─> configuration trail
       │        │          ├─> stack trail
       │        │          └─> case trail      (and a seed)
       │        ├─> client trail
       │        ├─> the stack's, the model's and the tools' versions
       │        └─> conversation <── messages
       ├─> scorer trail
       └─> case version
```

### Trials

A **trial** is a cell on a case with a seed, or with none: a
configuration trail, a stack trail, a case trail and the seed. It is
content, like a trail, and belongs to no one: runs of the same
configuration, stack, case and seed are runs of one trial, whoever made
them.

- **A seed makes a draw repeatable,** given the same hardware, server and
  request. Running a seeded trial again checks that it holds, or retries
  one that errored. Why runs are seeded by default, and what it costs, is
  in `research/seeds.md`.
- **Unseeded runs** of a cell on a case all belong to one trial, though
  each is a different draw.
- **Greedy sampling takes no seed.** At temperature 0, or top-k 1, a seed
  changes nothing, so a greedy cell runs unseeded: a seed given it is
  refused, and one drawn for it left out.

### Runs

A **run** is one go at a trial, its owner's alone. It records:

- who ran it, when it started and finished, and whether it **completed**
  (the model answered, even badly, or went on until it was stopped) or
  **errored** (the model or the server failed, or someone stopped it);
- the **client** it was sent from, with its revision and package
  versions;
- the **versions it read:** the stack's, the model's, and each tool's
  with the git blob of its file;
- the **requests and responses,** byte for byte;
- the **answer:** the parsed object for a structured output, the text for
  free text; whether it is **valid** against the schema (none for free
  text); the last response's **finish reason**; and the **error**, if
  any;
- its **conversation**.

How a run came out is in its status, its answer and its error:

| What happened | Status | Answer | Error |
|---|---|---|---|
| the model answered | completed | the answer, marked invalid where it doesn't fit the schema | none |
| the answer doesn't parse | completed | none | `the answer doesn't parse: …` |
| still calling tools after five rounds | completed | none | `stopped: still calling tools after 5 rounds` |
| nothing but whitespace for 100 tokens | completed | what it wrote before, closed where it stops | `stopped: nothing but whitespace for 100 tokens` |
| the model or the server failed | errored | none | the error, by its type |
| someone stopped it | errored | none | `stopped` |

A **conversation** holds the exchange as messages: each request and
response as pydantic-ai writes it, and the error that ended the run, if
one did; each with its role (`system`, `user`, `assistant` or `tool`, and
`unknown` for an error), and the id of the run it belongs to, the one
pydantic-ai ran it under. A conversation has an owner, a description, and
where it was held: `repl`, `api`, `worker` or `chat`. Runs and
conversations can name collaborators, though nothing shares one yet.

### Scores

A **score** is what one scorer made of one run, for whoever scored it. It
keeps the run, who scored, the scorer (its trail, and the name it had),
the case version whose targets were read, the pattern it was held to, the
git blob of the scorer's file, the value, what in the answer it rests on
(the ranked item, the sentence), and a reason, such as `not listed` or
`no answer`.

- **Whoever scores uses their own scorers and the archive's,** and holds
  a run to their own newest version of a case with its vignette, or else
  the archive's; to a deleted one where its owner has no other.
- **Scorer files run like tool files:** only chatddx's own, loaded fresh.
- **A run is waiting to be scored** until it has a score from each scorer
  that applies, as the scorer is now, against the pattern as it is now,
  from the file as it is now. Change any of them and it is waiting again;
  the older scores are kept. The latest from each scorer is the one
  shown.
- **A run with no answer** scores 0 (`no answer`), or no value for
  `first_mention`. An errored run isn't scored. A pattern that doesn't
  parse gets no value from its scorer (`the pattern doesn't parse`), and
  the run's other scorers score it all the same.

The metrics are computed as inspect-ai computes them: a sample deviation,
and a score without a value left out.

## 11. The inventory

The Repo starts from the inventory: TOML files in `src/chatddx/data/`
that `chatddx init-data` commits as the archive's. Nothing reads them
while chatddx runs. `inventory.md` goes through every key; this section
says how the files become the Repo, and what they hold.

### How it is committed

`chatddx init-data alice`:

1. parses `inventory.toml`, and with `--with-giftbag`
   `giftbag-inventory.toml` too, before it writes either, so a mistake in
   one commits nothing of the other;
2. commits the inventory as the archive's, each record a branch of its
   name, factor by factor in the order of §5;
3. makes alice a collaborator on the head of each;
4. with `--with-giftbag`, commits the giftbag as alice's own: the slices
   and the configurations, what is asked.

Run again after an edit, it makes a new version of each record whose
content or details changed, on a new trail where the content did, and
finds the rest as it was (`validated`).

A record is read so:

- It is a table named by its factor and its name:
  `[stack."qwen3-8b-awq@pelle"]`. The name is its key, and its owner
  whoever the inventory is committed for: neither can be set in the
  record.
- It names the records it is made of by their names, as
  `llm = "qwen3-8b-awq"` or `tools = ["web_search"]`, and they are read
  into its trail.
- Each key goes to the trail or to the details, as the factor has it. A
  key the factor doesn't have is refused, with the keys it has.
- `extends` at the top of a file names files it builds on; in a record,
  records it builds on, whose keys it takes unless it sets its own.
  `partial = true` makes a record a template to extend, never a record of
  its own.
- A key ending in `_path` reads its value from a file beside the file it
  is in (`.toml`, `.json` or `.txt`), and a case's vignette is read from
  `cases/<name>.txt` unless it is given.

### What it holds

| File | Holds |
|---|---|
| `inventory/pelle.toml` | pelle, an RTX 3070 serving Qwen3-8B-AWQ, with no reasoning parser: it was dropped for memory |
| `inventory/malborg.toml` | malborg, an RTX 5090 serving gpt-oss-20b, and Qwen3-8B-AWQ from a NixOS container beside it: one model on two cards |
| `inventory/fake.toml` | the fake vLLM, `chatddx fake-vllm`, serving both models with their servings' parsers, on a machine of its own, so that no trial on it passes for one on pelle or malborg |
| `inventory/llms.toml` | `qwen3-8b-awq` and `gpt-oss-20b`, and their facts |
| `inventory/clients.toml` | `chatddx`, the build deployed, and `chatddx-dev`, a dev shell |
| `inventory/slices.toml`, `inventory/schemas/*.json` | every variation of the request-time slices, with the answer schemas and the tools |
| `inventory/configurations.toml` | the clinical configurations (`plan`, `plan-shown`, `plan-prompted`, `plan-web`, `diagnoses`, `diagnoses-tool`, `free-text`), and those the tests run |
| `inventory/scorers.toml` | the four scorers of §9 |
| `cases.toml`, `cases/*.txt` | 99 cases: 30 `dutch-fall`, translated into English, 20 `edn`, in Swedish, and 49 `openxddx`, in English. Each has a pattern for its diagnosis, and patterns for its warning and disposition guessed from its text. |

`# guessed` marks every value not yet read off the machines themselves,
or not yet settled: much of what answers, content included, and the
cases' warnings and dispositions. It is a note for people, and the value
is used as it is. Once the real values are read off the machines, those
of content make new trails, and the runs made before stay with the
guessed ones.

The tests seed the archive from inventories of their own:
`test-inventory.toml`, the same factors on two test cases
(`test-cases.toml`); `test-giftbag-inventory.toml`, the live giftbag; and
`test-later-inventory.toml`, the archive as it stands once its owners
have started (the fake's Qwen on another port, taking more jobs at once,
and a scorer for `dont_miss`), to test what of it reaches an owner seeded
before.

## 12. Storage

- **Three Django apps hold the two classes,** and who owns them. `core`
  holds the identities (`core_identity`, each with its secrets,
  encrypted) and the tags (`core_tag`); `repo` a trail table and a branch
  table for each factor (`repo_case_trail`, `repo_case_branch`), each
  branch table with its tags and collaborators; and `history` the trials,
  runs, conversations, messages and scores (`history_trial`,
  `history_run`, `history_run_tool_branch`, `history_conversation`,
  `history_message`, `history_score`).
- **A trigger** on every trail table refuses an update or a delete. It is
  put in place after every migration.
- **Details** are one JSON column of each branch table. The branch tables
  are indexed by owner, name and time, newest first, which is how a head
  is found.
- **Order-sensitive documents** (an answer schema, a tool's parameters, a
  run's answer) are stored as text, since PostgreSQL's `jsonb` re-sorts
  keys. What is read as a set, such as a serving's arguments, is `jsonb`.
- **A toolset's tools** are an array of tool trail ids, in order, where a
  many-to-many table would lose the order.
- **What is read is kept.** A trail's references to trails, a branch's to
  its trail, and History's to trails and branch versions all refuse the
  deletion of what they refer to. A run's scores, and its rows of the
  tools it ran, go with the run.
- **Beside the two classes** are the tables that change: the worker's
  queue (`worker_job`), each owner's controls on it (`worker_controls`),
  and when the worker was last at it (`worker_state`); and the portal's
  batches (`portal_batch`). They refer to the Repo and History, and
  nothing in either refers to them: no run points at a batch.
- **`chatddx wipe-data alice`** removes alice's jobs, scores, runs and
  conversations with their messages, the trials no one's run is left of,
  and her branches, and unshares what was shared with her: all of it, or
  nothing while anyone else's runs or scores read her branches.
