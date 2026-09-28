# The chatddx initial data inventory

The inventory is an initial set of configurations and cases that is used to
bootstrap new users and testing the code.

The files live in `src/chatddx/data/`:

| File | Holds |
|---|---|
| `inventory.toml` | the whole inventory: it names the others |
| `cases.toml`, and `cases/*.txt` | the cases, their targets, and their vignettes |
| `inventory/scorers.toml` | the scorers |
| `inventory/slices.toml`, and `inventory/schemas/*.json` | what the model is asked, and the shape of the answer |
| `inventory/configurations.toml` | named combinations of the above |
| `inventory/llms.toml` | the models, and what each can do |
| `inventory/pelle.toml`, `malborg.toml`, `fake.toml` | the machines, and the models they serve |
| `inventory/clients.toml` | the builds of chatddx that send the requests |

## How it is used

Load into database with:

```
chatddx init-data alice
```

This will setup the archive if it doesn't exist already and share full inventory
with alice but not add anything. Useful to update shared resources without
interfering with existing owned data.

To bootstrap a user, a `--with-giftbag` also gives alice everything in
`giftbag-inventory.toml`.

A comment `# guessed` after a value is a note to people that the value has been
guessed by an llm.

## Writing a record

A record is a table named by its kind and its name:

```toml
[case.DutchFall10w]
tags = ["dutch-fall"]
```

* A name with dots or `@` in it is quoted: `[stack."qwen3-8b-awq@pelle"]`.
* A record names other records by their names: `llm = "qwen3-8b-awq"`.

Every record can also have:

- `tags`: labels, for grouping and finding. Case tags are what `batch`
  selects by in the shell.
- `collaborators`: other identities the record is shared with.

A few keys shape how records are written, and change nothing they mean:

- `extends` at the top of a file names files it builds on; inside a record,
  records it builds on, whose keys it takes unless it sets its own.
- `partial = true` makes a record a template for others to extend, never a
  record of its own.
- A key ending in `_path` reads its value from a file next to the file it
  is in: `answer_schema_path = "schemas/diagnoses.json"`.

## Cases

A case is a clinical vignette and what the model is expected to make of it.

```toml
[case.Dutchfall14w]
tags = ["dutch-fall"]
language = "en"
targets.diagnosis.text = "Acute exacerbation of COPD"
targets.diagnosis.pattern = "copd | (exacerbation | obstructive) & pulmonary"
targets.warning.pattern = "hypoxi* | hypercapni* | respiratory & failure | pulmonary & embolism"  # guessed
targets.disposition.pattern = "admit* | admission | hospital*"  # guessed
```

- **The vignette** is the text of `cases/<name>.txt`, sent to the model as it is.
- **`tags`:** the set the case comes from: `dutch-fall`, `edn` or `openxddx`.
- **`language`:** the language the vignette is written in, `en` or `sv`.
- **`targets`:**
  - `text`: what is expected, in plain words, for people (or possibly llm judges) to read.
  - `pattern`: what the scorers look for in an answer (below).

  A case may leave a kind out, or give a target no pattern. The scorers of
  that kind then skip the case, and the shell's `show` says `missing`.
  The kinds:
  - `diagnosis`: the diagnosis the case is known to have.
  - `warning`: what the answer should warn about. `targets.warning = false`
    says the case should raise no warning at all.
  - `disposition`: where the patient should go: home, admission, intensive
    care, theatre.
  - `dont_miss`: a condition the differential must include, however
    unlikely. No scorer reads it yet.

### How a target is written

A target's pattern is what the answer's words are matched against, one
item at a time: one diagnosis of the differential, one warning.

| Write | Matches |
|---|---|
| `pneumonia` | the whole word, in any case: not "pneumonias", and `mi` is never found inside "anemia" |
| `meningit*` | any word starting so: meningitis, meningitic |
| `acute coronary syndrome` | the words side by side, in this order |
| `renal & stone*` | both, anywhere in the item |
| `pneumonia \| sepsis` | either |
| `(renal \| kidney) & stone*` | parentheses group; `&` binds tighter than `\|` |

For a Swedish case, name the words in both languages
(`myocardial & infarction | hjärtinfarkt`): the model may answer in
either.

## Scorers

A scorer judges one part of an answer against one kind of target.

```toml
[scorer.reciprocal_rank]
function = "chatddx.scoring.scorers.patterns:reciprocal_rank"
view = "differential"
target_kind = "diagnosis"
metrics = ["mean", "stderr"]
```

- **`function`:** a hard-coded function that scores, which needs to be predefined in the code itself.
  The current functions are preliminary and awaits clinical input.
  - `reciprocal_rank`: 1 if the diagnosis is first in the differential,
    1/2 if second, and so on; 0 if it isn't there.
  - `first_mention`: in the first sentence or line of the answer that
    names the diagnosis, how many characters come before it.
  - `mentions`: 1 if the part read names the target, 0 if not; with
    `warning = false`, 1 if the answer warns about nothing.
- **`view`:** the part of the answer it reads (see Outputs).
- **`target_kind`:** the kind of target it compares that to.
- **`args`:** anything more the function takes; none of the inventory's
  take any.
- **`metrics`:** how its scores are summed up over runs: `mean`, `stderr`,
  `std`, `var`. These describe the scorer; the others make it what it is.

## The components of a configuration

### Outputs

What is asked for, and how the answer is read.

```toml
[output.management-plan]
answer_schema_path = "schemas/management_plan_v1.json"
guidance = "Fill in the management plan for the case."
views.differential = "$.diagnoses[*].diagnosis"
views.warning = "$.acute_warning"
views.disposition = "$.management.disposition"
views.critical = "$.diagnoses[?(@.critical)].diagnosis"
```

- **`guidance`:** Are inserted into the main instruction (sometimes called system prompt)
- **`answer_schema`** (or `answer_schema_path`): the shape a structured answer
  must have. Each field's `description` in the schema is read by the
  model, so its wording is part of what the model is asked. Leave it out
  for a free-text answer.
- **`views`:** tells the scorer where in the response the answer is expected.
  In a structured answer a view is a path into it: `$.acute_warning` is a
  field, `$.diagnoses[*]` every item of a list, `$.diagnoses[*].diagnosis`
  a field of every item, and `$.diagnoses[?(@.critical)].diagnosis` that
  field of the items whose `critical` is true. In free text, `whole` reads the whole answer as
  `text`, and `lines` reads each non-empty line as an item of the
  `differential`, list markers stripped.

### Instructions

The prompt's template.

```toml
[instruction.ddx]
system = """
{{output_guidance}}{{#if tool_guidance}}

{{tool_guidance}}{{/if}}{{#if schema_prompt}}

{{schema_prompt}}{{/if}}"""
user = "{{case}}"
variables = ["case", "output_guidance", "schema_prompt", "tool_guidance"]
```

- **`system`:** the system message; empty for none.
- **`user`:** the user message.
- **`variables`:** the slots the texts use, filled in when the request is
  made: `case` (the vignette), `output_guidance` (the output's guidance),
  `schema_prompt` (the coercion's, below) and `tool_guidance` (the
  toolset's). `{{#if x}}…{{/if}}` includes text only when the slot is
  filled.

### Coercions

How tells what mechanism is used to tell the LLM the expected output's shape.
With free text, none of this applies.

- **`mode`:**
  - `native`: the server itself only lets the model write text that fits
    the shape; the model doesn't read the shape unless shown it.
  - `tool`: the model answers by calling a tool whose arguments are the
    shape.
  - `prompted`: the model is shown the shape and asked to follow it;
    nothing enforces it.
  - `auto`: whichever of these the model's facts name as its default.
- **`schema_prompt`:** words that show the model the shape, with
  `{{schema}}` where the schema goes.
- **`tool_description`:** in `tool` mode, what the answer tool says it is
  for.

### Reasoning

Whether, and how hard, the model thinks before answering.

- **`effort`:** `default` (whatever the model does by default), `off`, `on`,
  or a level: `minimal`, `low`, `medium`, `high`, `xhigh`. Each model's
  facts say what each becomes for it, and which it can't do.
- **`budget`:** the most tokens the model may think for, where the model
  and its server allow a budget.

### Sampling

How the model picks its words.

- **`defaults`:** where every value left out comes from:
  `generation_config`, the model's own defaults, or `recommended`, what
  the model's makers recommend for its reasoning mode.
- **`temperature`:** 0 always picks the most likely word (greedy); higher is
  more varied.
- **`top_p`, `top_k`:** how many of the likeliest words are considered.
- **`max_tokens`:** the longest answer, thinking included.
- **`presence_penalty`, `frequency_penalty`:** discourage repeating words.
- **`stop`:** text that ends the answer when it appears.

The seed is not set here: it belongs to each run, and the shell sets it.

### Toolsets and tools

Tools the model may call while it answers, such as a web search.

```toml
[toolset.web]
tools = ["web_search"]
guidance = "You have access to a web_search tool. ..."

[tool.web_search]
name = "web_search"
description = "Search the web for up-to-date information"
implementation.function = "chatddx.runtime.tools.web_search:web_search"
parameters = { type = "object", properties.query = { type = "string" }, required = ["query"] }
```

- **Toolset:** `tools`, in order, and `guidance`, the words that tell the
  model about them.
- **Tool:** the `name`, `description` and `parameters` the model sees, and
  `implementation.function`, the code that runs, one of chatddx's own.

## Configurations

Configuration combines all components into a complete ask.

```toml
[configuration.plan]
instruction = "ddx"
output = "management-plan"
coercion = "native"
reasoning = "default"
sampling = "recommended"
tags = ["ddx"]

[configuration.plan-web]
extends = "plan"
toolset = "web"
```

`instruction`, `output`, `coercion`, `reasoning` and `sampling` are
required; `toolset` is optional. A configuration names no model: it runs
on whichever stack it is paired with.

## Models and machines

### Stacks

```toml
[stack."qwen3-8b-awq@pelle"]
machine = "pelle"
os = "pelle"
llm = "qwen3-8b-awq"
serving = "qwen3-8b-awq@pelle"
endpoint = "http://pelle.km:12009/v1/"
served_name = "Qwen/Qwen3-8B-AWQ"
api = "vllm"
```

- **`machine`, `os`, `llm`, `serving`:** its parts, by name. These make the
  stack what it is. A model served from a container names the container's
  system as `os` and the machine's as `host_os`.
- **`endpoint`:** the address requests go to.
- **`served_name`:** the name the server knows the model by.
- **`api`:** how to talk to it; `vllm` is the one the shell uses.
- **`credential`:** the name of the identity's secret that holds the API
  key, where the server wants one.
- **`max_jobs`:** how many of the worker's jobs run on it at once, its
  slots: 1 unless it says more. A detail, like the rest of these, so it
  changes no trial.

### Models (`llm`)

- **`snapshot`:** the exact files loaded, by their store path.
- **`source`:** where they came from: repository and revision.
- **`specs`:** family, size, quantization, context length, licence.
- **`facts`:** Details from the model's specification (called "model card").
  It comes from the manufacturer and is needed in order to know in advance
  what the model will do with a configuration:
  - `facts.reasoning`: for each effort, what to send, another effort it
    becomes (`minimal = "on"`), or `{ refused = "why" }`; `default` names
    the effort it thinks at by default; `budget` says where a thinking
    budget goes and what the server needs for it.
  - `facts.sampling.recommended`: the makers' sampling values per
    reasoning mode. `facts.sampling.generation_config`: the model's own
    defaults.
  - `facts.coercion`: which modes work (`needs` names a server feature they
    depend on, such as a reasoning parser), and `default`, what `auto`
    becomes.
  - `facts.profile`: technical settings for the client library.

### Servings

How the server runs the model.

- **`engine`:** the vLLM build, by store path.
- **`args`:** server options that change what the model reads or writes,
  such as the context length or the tool-call parser.
- **`env`:** environment settings of the same kind.
- **`performance`:** options that only change speed, such as memory use or
  the port; these describe the serving.

### Machines and operating systems

- **Machine:** `machine_id`, which makes it what it is; `specs` (GPUs, CPU,
  RAM, location) and `unreliable`, for a machine nothing below the
  requests can be checked on, such as a cloud provider.
- **Operating system:** `toplevel`, the system's store path, which makes it
  what it is; `flake_rev`, and `specs` (hostname, kernel, NVIDIA driver,
  nixpkgs revision).

### Clients

The builds of chatddx that send requests: `build`, the store path of a
deployed build (none for a developer's shell), `rev`, the git revision, and
`packages`, the versions of the libraries that shape a request.
