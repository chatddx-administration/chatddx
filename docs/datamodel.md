# The chatddx datamodel

chatddx asks language models clinical questions and scores their answers.
This note describes what it keeps to do that: what a model is asked and how,
which model on which machine answered, the cases, what came back, and what
the scorers made of it. It describes chatddx as it is.

For using it, see `repl.md` (the shell) and `inventory.md` (the files that
seed the database).

## 1. Content and versions

Everything chatddx keeps about the things it works with has two layers.

### Content: trails

A **trail** is a piece of content that can't change: a vignette, a JSON
schema, a sampling setting, a model's snapshot. Each trail is named by a
**fingerprint**, a hash of its content, such as
`cddx-trail/1:sha256:3f9a1c…`. The first part names the scheme and its
version, so a new way of hashing can be added without breaking old
fingerprints. The short form, `3f9a1c`, is what the shell shows.

- **The same content is one trail,** whoever writes it. Two people who
  write the same sampling setting share one row.
- **A trail can't be edited or deleted.** The database refuses it. A
  change is a new trail.
- **Order is kept where a model reads it.** A JSON schema's properties are
  hashed and stored in the order they were written, since a constrained
  decoder emits them in that order.
- **A trail holds only what changes a request, what the model reads, or how
  an answer is read for scoring.** Everything else goes in the branch.

### Names and descriptions: branches

A **branch** is someone's named version of a trail: alice's
`management-plan`, the archive's `qwen3-8b-awq`. A branch has:

- an **owner** and a **name**;
- the **trail** it points at;
- its **details**: what describes the content without being part of it,
  such as a machine's specs, a model's facts, a stack's address, or a
  case's targets;
- **tags** and **collaborators**.

How versions work:

- **A change to the trail or the details makes a new version:** a new
  branch row under the same owner and name. The newest row is the current
  one, and the older rows are its history. A run records the rows it read,
  so it can always say which version it ran with.
- **A change to tags or collaborators doesn't make a new version.** They
  are set on the current row.
- **Committing what is already current changes nothing.**
- **A composition brings its parts along.** Committing a stack or a
  configuration gives the owner a branch of every part it reaches that
  they have none of, named after the kind and short fingerprint
  (`machine 3f9a1c`). When the shell saves a configuration (`save`), those
  parts are copies of the archive's branches instead, names and details
  included, where the archive has them.

Who can see what:

- **Everyone sees their own branches, and those they collaborate on.** A
  branch of one's own shadows a shared one of the same name.
- **The archive** is the identity that owns the curated inventory.
  `chatddx init-data USER` commits the inventory as the archive's, and
  makes USER a collaborator on everything it committed.

### Kinds of record

The kinds, in the order they are committed (anything a kind refers to comes
before it):

| Group | Kinds |
|---|---|
| What answers (§3) | machine, os, llm, serving, client, stack |
| What is asked (§4) | tool, toolset, instruction, output, coercion, reasoning, sampling, configuration |
| What is asked about, and how it is judged (§6, §7) | case, scorer |

## 2. The cell

A run asks one model one case, in one way. The **way** is split into
**slices**, each answering one question someone might want to compare:

| Slice | The question | Example variations |
|---|---|---|
| stack | which model, on which machine? | `qwen3-8b-awq@pelle`, `gpt-oss-20b@malborg` |
| instruction | what is the model told? | `ddx` |
| output | what should the answer look like? | `management-plan`, `diagnoses`, `free-text` |
| coercion | how is the model held to that shape? | `native`, `tool`, `prompted`, `auto` |
| reasoning | should it think first, and how hard? | `default`, `off`, `on`, `low`, `high` |
| sampling | how does it pick its words? | `recommended`, `generation-config` |
| toolset | which tools may it call? | `web`, or none |

- A **variation** is one answer to a slice's question: a record of that
  slice's kind.
- A **configuration** is one variation of every slice but the stack. It
  names no model, so the same configuration can run on any stack.
- A **cell** is a configuration and a stack: one variation of every slice.
- **A slice owns everything that belongs to it,** wherever it ends up. The
  management plan output carries its schema, the sentence that asks for it
  ("Fill in the management plan for the case."), and where scorers find
  its parts. So any output can be paired with any instruction.

### Intents, facts and refusals

A variation says what is wanted, not how to get it: "reasoning off", not
"set `enable_thinking` to false". Turning it into a request is
**resolution** (§5), and it reads the model's **facts** (§3) to do it.

Each cell comes out one of two ways:

- **Resolved:** it makes a request. Where a model's facts say one intent
  stands for another (Qwen3 has no effort levels, so `low` and `high` are
  both just thinking on), resolution says so.
- **Refused:** the model can't do what is asked. gpt-oss can't stop
  reasoning, so reasoning `off` on gpt-oss is refused, with the reason. An
  intent the facts don't mention is refused too: nothing is guessed. Every
  refusal in a cell is given at once, each with its slice.

Facts are claims. A run records the branch rows whose facts it read, and
the shell says after a run when a model didn't do what its facts promised
(no thinking came back when reasoning was on, or some came back when it
was off).

## 3. What answers: the stack and its parts

A **stack** is everything below the request: which machine, which system,
which model, started how. Each part is a thing with one identifying field,
its trail, and details that describe it.

**machine**

| Field | Kind | Holds |
|---|---|---|
| `machine_id` | content | a UUID given when the machine is registered |
| `unreliable` | detail | true for a cloud provider, where nothing below the requests can be checked |
| `specs` | detail | GPUs (model, memory in MiB, UUID), CPU, RAM in GiB, location |

**os**

| Field | Kind | Holds |
|---|---|---|
| `toplevel` | content | the system's Nix store path (the target of `/run/current-system`) |
| `flake_rev` | detail | the flake revision it was built from |
| `specs` | detail | hostname, kernel, NVIDIA driver, nixpkgs revision |

**llm**, the model

| Field | Kind | Holds |
|---|---|---|
| `snapshot` | content | the Nix store path of the model's files, fetched by hash; for a cloud model, the provider's dated name. A repository name is refused, since it could resolve to any revision. |
| `source` | detail | the Hugging Face repository and pinned commit, `<owner>/<repository>@<40 hex digits>` |
| `specs` | detail | family, size, active size for a mixture of experts, quantization, context length, licence |
| `facts` | detail | what resolution reads (below) |

A model's **facts** have four parts:

- **`reasoning`:** for each intent (`off`, `on`, `minimal`, `low`,
  `medium`, `high`, `xhigh`), what to send, the intent it stands for, or
  `{ refused = "why" }`. `default` names the model's own. `budget` says
  where a thinking budget goes, and what it needs of the serving.
- **`sampling`:** `recommended`, the vendor's settings for each reasoning
  mode, and `generation_config`, what the server uses for a setting a
  request leaves out.
- **`coercion`:** which ways of holding the model to a schema work, what
  each needs of the serving, and which one `auto` means.
- **`profile`:** settings for pydantic-ai, the library that sends the
  requests, so nothing depends on the name the model is served under.

For example, Qwen3 (abridged):

```toml
[llm.qwen3-8b-awq.facts.reasoning]
default = "on"
off = { chat_template_kwargs = { enable_thinking = false } }
on = { chat_template_kwargs = { enable_thinking = true } }
low = "on"                       # no effort levels: every effort is "on"
high = "on"
budget = { field = "thinking_token_budget", needs = "reasoning_parser" }

[llm.qwen3-8b-awq.facts.sampling.recommended]
on = { temperature = 0.6, top_p = 0.95, top_k = 20 }
off = { temperature = 0.7, top_p = 0.8, top_k = 20 }
```

**serving**, how vLLM was started

| Field | Kind | Holds |
|---|---|---|
| `engine` | content | the Nix store path of the vLLM package |
| `args` | content | the start-up arguments that change what the model reads or the numbers it computes, spelled one way and sorted |
| `env` | content | environment variables that do the same, such as `VLLM_BATCH_INVARIANT` |
| `performance` | detail | arguments that only change speed |

Each argument has one place: one in the wrong place is refused, and so are
`--model`, `--served-model-name` and `--api-key`, which belong to the
model, the stack and a secret. A serving provides a reasoning parser where
`reasoning-parser` is set, and a tool-call parser where both
`tool-call-parser` and `enable-auto-tool-choice` are.

**client**, the chatddx that sent the request

| Field | Kind | Holds |
|---|---|---|
| `build` | content | the Nix store path of the chatddx build; none from a dev shell |
| `rev` | detail | for a dev shell, the checkout's commit, with `-dirty` if it has changes |
| `packages` | detail | the versions of pydantic-ai, openai and inspect-ai |

A run records the client it ran on itself.

**stack**

| Field | Kind | Holds |
|---|---|---|
| `machine`, `llm` | content | the machine and the model |
| `os`, `serving` | content | the system and the serving; none for a cloud stack |
| `host_os` | content | for a container, its host's system, which holds the kernel and driver |
| `endpoint` | detail | the URL requests go to |
| `served_name` | detail | the `model` field of a request |
| `api` | detail | `vllm`, or a cloud API: `openai-chat`, `openai-responses`, `anthropic`, `google` |
| `credential` | detail | the name of a secret, never the secret |

Only `vllm` stacks can be run; the others are refused.

## 4. What is asked: the request-time slices

Each kind below is one slice, and each of its records is a variation.

**instruction**

| Field | Holds |
|---|---|
| `system` | the template for the system message; empty for none |
| `user` | the template for the user message, usually `{{case}}` |
| `variables` | the variables the templates place: `case`, and the **slots** other slices fill: `output_guidance`, `schema_prompt`, `tool_guidance` |

Every declared variable is placed, and every placed variable declared. The
case is placed as a value, never tested, so a template reads the same for
every case. A slot no slice fills is empty, and a template can leave out
the text around it:

```
{{#if schema_prompt}}

{{schema_prompt}}{{/if}}
```

**output**

| Field | Holds |
|---|---|
| `answer_schema` | the shape a structured answer must have, as written, key order included; none for free text |
| `guidance` | the words that ask for the answer, placed in the `output_guidance` slot |
| `views` | where scorers find each part of the answer |

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
is a field, `$.diagnoses[*].diagnosis` a field of every item of a list, and
`$.diagnoses[?(@.critical)].diagnosis` that field of the items whose
`critical` is true. The path is checked against the schema when the output
is committed, so a view always yields what it promises. Free text offers
views through a parser instead: `whole` gives `text`, and `lines` gives the
`differential`, one item per line.

**coercion**

| Field | Holds |
|---|---|
| `mode` | how the model is held to the schema: `native` (the server constrains the answer), `tool` (the answer is given as a tool call), `prompted` (the model is only asked), or `auto` (what the model's facts name) |
| `schema_prompt` | words that show the model the schema, placing `{{schema}}`, for the `schema_prompt` slot; none to show nothing. `prompted` needs one. |
| `tool_description` | what the answer tool is said to be; `tool` needs one |

With free text there is no schema, and every coercion is the same.

**reasoning**

| Field | Holds |
|---|---|
| `effort` | `default`, `off`, `on`, `minimal`, `low`, `medium`, `high` or `xhigh` |
| `budget` | a number of thinking tokens, or none; `off` takes none |

**sampling**

| Field | Holds |
|---|---|
| `defaults` | what a setting left out means: `generation_config` (the server's default) or `recommended` (the vendor's, for the reasoning mode resolved) |
| `temperature`, `top_p`, `top_k`, `max_tokens`, `presence_penalty`, `frequency_penalty`, `stop` | settings given outright, which win over the defaults |

**toolset** and **tool**

| Field | Holds |
|---|---|
| `toolset.tools` | its tools, in order, at least one, no two of one name |
| `toolset.guidance` | words for the `tool_guidance` slot |
| `tool.name`, `tool.description`, `tool.parameters` | what the model sees: its name, what it does, and a JSON Schema of its arguments |
| `tool.implementation` | a detail: the function that runs, `chatddx.runtime.tools.<file>:<function>` |

Only chatddx's own tool files run. Each call's arguments are checked
against the parameters first, and what fails, or an error the function
raises, goes back to the model as the tool's answer. A run records the git
blob of each tool file that ran, so the exact code can be got back with
`git cat-file blob <id>`.

**configuration**

| Field | Holds |
|---|---|
| `instruction`, `output`, `coercion`, `reasoning`, `sampling` | one variation of each |
| `toolset` | one, or none |

## 5. Resolution

Resolution turns a cell into a request, before any case is known. It goes
in this order, since each step needs the ones before:

1. **the stack:** where the request goes, and under what name;
2. **reasoning,** translated by the model's facts;
3. **sampling,** whose `recommended` depends on the reasoning mode, and
   whose `max_tokens` must leave room for a thinking budget;
4. **output and coercion,** the mode checked against the model's facts and
   the serving (constrained output on a reasoning model needs a reasoning
   parser);
5. **the toolset,** which needs a tool-call parser on the serving;
6. **the instruction,** every filled slot placed.

What it holds to:

- **Each slice writes its own parts of the request,** and no two write the
  same field.
- **What pydantic-ai adds is turned off.** No words of the library's own
  reach the model. The schema is sent with its references inlined and
  nothing else changed, and the model is shown it only through the
  coercion's `schema_prompt`.
- **Settings the OpenAI API doesn't have** (`top_k`, and whatever the
  reasoning facts write) go in `extra_body`. The seed goes as `seed`.
- **An answer is always an object.** A schema whose top level isn't one is
  refused.
- **A run asks once.** Nothing is retried. A model may call tools for five
  rounds; one still calling after that stops with no answer.

The shell's `show` prints the result: each slice's variation beside what
it became, or why it was refused, and the prompt text. §6 covers what it
says of targets.

## 6. Cases and targets

**case**

| Field | Kind | Holds |
|---|---|---|
| `vignette` | content | the case as the model receives it, placed through the instruction's `case` variable |
| `language` | detail | the vignette's language, `en` or `sv` |
| `targets` | detail | what the case is expected to yield, by kind |

An edited vignette is a new case, since it is what the model reads. An
edited target is a new version of the same case.

A **target** is what is expected of one kind, in two parts:

- **`text`:** what is expected, in plain words, for people;
- **`pattern`:** what the scorers look for in an answer.

Either may be missing. A target can also be `false`, meaning none is
expected. The kinds:

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

The data is taken as it is. Nothing is signed off, and a case with missing
targets can be run: the scorers that need what is missing leave it out,
and `show` says `missing`. `show` of the cell counts, per scorer, the cases
that have its target and names those that don't; `show tag TAG...` counts
only the cases with those tags.

## 7. Scorers and scores

**scorer**

| Field | Kind | Holds |
|---|---|---|
| `function` | content | the function that scores, `chatddx.scoring.scorers.<file>:<function>` |
| `view` | content | the view it reads |
| `target_kind` | content | the kind of target it compares that to, or none |
| `args` | content | further arguments for the function |
| `metrics` | detail | how its values are summed up: `mean`, `stderr`, `std`, `var` |

The archive's scorers:

| Scorer | Reads | Against | Value |
|---|---|---|---|
| `reciprocal_rank` | `differential` | `diagnosis` | 1/rank of the first diagnosis the pattern finds, 0 if none |
| `first_mention` | `text` | `diagnosis` | how many characters come before the pattern is first found; no value if never |
| `warning_mentions` | `warning` | `warning` | 1 if the pattern is found, 0 if not |
| `disposition_mentions` | `disposition` | `disposition` | the same |

When a case expects no warning (`false`), `warning_mentions` gives 1 when
the answer names none, and 0 when it names one. No scorer reads
`dont_miss` yet.

How scoring works:

- **A scorer applies to a run** that completed, whose output offers its
  view, and whose case has a pattern for its kind (or `false`).
- **Whoever scores uses their own scorers and the archive's,** and their
  own version of the case's targets, or else the archive's.
- **Scorer files run like tool files:** only chatddx's own, loaded fresh,
  and each score records the file's git blob.
- **A run is waiting to be scored** until it has a score from the scorer as
  it is now, against the target as it is now, from the file as it is now.
  Change any of them and it is waiting again; the older scores are kept.
  The latest score from each scorer is the one shown.
- **A run with no answer** scores 0 (`no answer`), or no value for
  `first_mention`. An errored run isn't scored. A pattern that doesn't
  parse is an error, and nothing is scored with it.

A **score** keeps: the run, who scored, the scorer (its trail, and the name
it had), the case branch whose targets were read, the pattern it was held
to, the blob, the value, what in the answer it rests on (the ranked item,
the sentence), and the reason where there is no value.

The metrics are computed as inspect-ai computes them: a sample deviation,
and a score without a value left out.

## 8. Trials, runs and conversations

A **trial** is a cell on a case with a seed, or with none. It is content,
like a trail, and belongs to no one: runs of the same configuration, stack,
case and seed are runs of one trial, whoever made them.

- **A seed makes a draw repeatable,** given the same hardware, server and
  request. Running a seeded trial again checks that it holds, or retries
  one that errored. Why runs are seeded by default, and what it costs, is
  in `research/seeds.md`.
- **Unseeded runs** of a cell on a case all belong to one trial, though
  each is a different draw.
- **The shell holds a seed** and sends it with every run (`repl.md`). With
  greedy sampling (temperature 0, or top-k 1) the seed changes nothing, so
  the shell refuses to send one.

A **run** is one go at a trial. It records:

- who ran it, when it started and finished, and whether it **completed**
  (the model answered, even badly) or **errored** (the model or the server
  failed, or it was stopped);
- the **client** it ran on, and that client's revision and package
  versions;
- the **branch rows** whose details it read: the stack's, the model's, and
  each tool's with the blob of its file;
- the **requests and responses,** byte for byte;
- the **answer:** the parsed object for a structured output, the text for
  free text; whether it is **valid** against the schema (none for free
  text); the last response's **finish reason**; and the **error**, if any.
  An answer that parsed but doesn't fit the schema is kept, marked invalid;
- its **conversation.**

A **conversation** holds the exchange as messages: each request, response
and error, with its role. It has an owner, collaborators, a description,
and where it was held (`repl`, `chat` or `worker`).

## 9. Storage

- **Three Django apps** hold the tables: `core` the identities and tags,
  `repo` each kind's trails and branches (`repo_case_trail`,
  `repo_case_branch`), and `history` the trials, runs, conversations,
  messages and scores (`history_trial`, `history_run`).
- **A trigger** keeps every trail table from being updated or deleted.
- **Details** are one JSON column on each branch table.
- **Order-sensitive documents** (a JSON schema, a tool's parameters, a
  run's answer) are stored as text, since PostgreSQL's `jsonb` re-sorts
  keys.
