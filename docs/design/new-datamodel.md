# The new datamodel

This note gives the entities of the repo registry (`repo/registry.py`) after
the redesign in `research-data-model.md` and `data-generation.md`. It maps
every current field to its new home or scraps it, and marks each field as
fingerprinted or not.

For inspect-ai, option C of `data-generation.md` §5 was chosen: chatddx
generates and inspect scores. So the registry keeps what generation needs,
and what only evaluation needs moves to inspect.

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
- **Slice:** a vertical collection of request-time settings that belong
  together. A slice may write into several parts of a request.
  `data-generation.md` first called these bundles; it now says slice too,
  and bundle keeps only the meaning above.
- **Configuration:** one slice of each kind.
- **Resolution:** turning a configuration into a request (§5).

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
  `extra="forbid"`. Today details hold the branch's name and owner and its
  relations (collaborators, tags, and a case's expects). The redesign adds
  descriptive values, such as a machine's specs or a stack's endpoint.
- **Details live on the branch.** That is the layer that already carries
  the owner, the name, collaborators and tags, so details are owned and
  named, per owner.
- **Storage.** Relations stay many-to-many. Plain details go in one JSON
  column on the entity's branch model, validated by its details schema. A
  typed column is added only where something queries it.

### Passthroughs are the router

The inventory parser already treats one authored record as two:

- In `parse_entity`, the keys the details schema declares (passthroughs)
  skip trail parsing.
- The trail schema ignores them, and `parse` validates them into the
  details.
- A key that is neither trail content nor a declared detail is an error.

So an author still writes one record per entity, and the bundle decides
which keys are content and which are description:

```toml
[model.qwen3-8b-awq]
blob = "/nix/store/…-qwen3-8b-awq"      # trail: fingerprinted
source = "Qwen/Qwen3-8B-AWQ@<commit>"    # details: passes through
facts.reasoning = "toggle"               # details: passes through
tags = ["local"]                         # details: passes through
```

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
- A trial then records the branch rows whose details it read, beside the
  trails it ran.

### The rule

A field is fingerprinted if and only if it is trail content. Trail content
is:

- for a thing (machine, OS, model, client): its one identifying field;
- for a composition (stack, configuration, toolset): the things it
  combines;
- for a slice, and for serving: everything authored that can change a
  request or the model's output.

Names, owners, tags, endpoints, credentials, specs and facts are details,
and are never fingerprinted.

The two kinds of hash identify different things:

- Trail fingerprints identify what was authored.
- The request hashes on a trial (`data-generation.md` §3) identify what was
  sent.
- A model's facts can change a request without moving any trail
  fingerprint. That is by design, since a model is its blob, and the
  request hash catches it.

## 2. The entities

Every entity keeps the branch fields it has today: `name`, `owner`,
`timestamp`, `target`, `collaborators` and `tags`. None of them is
fingerprinted.

### Below the request

**machine**: a thing.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `machine_id` | trail | yes | a UUID assigned at registration, and the only identifying field |
| `unreliable` | details | no | true for a cloud provider, where nothing below its requests can be checked |
| `specs` | details | no | GPUs (model, memory, UUID), CPU, RAM, location. The GPU UUIDs back the check in `data-generation.md` §1. |

**os**: a thing.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `toplevel` | trail | yes | the system's store path, the target of `/run/current-system` |
| `flake_rev` | details | no | |
| `specs` | details | no | hostname, kernel, NVIDIA driver, nixpkgs revision |

**model**: a thing.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `blob` | trail | yes | a hash of the directory vLLM loads: the store path of a fixed-output derivation. For a cloud model, the provider's dated model name stands in, unverified. |
| `source` | details | no | Hugging Face repository and commit |
| `specs` | details | no | family, parameter count, quantization, context length, licence |
| `facts` | details | no | read by resolution: how reasoning is controlled, the recommended sampling per mode, and pydantic-ai profile overrides |

**serving**: the start-up settings.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `engine` | trail | yes | the store path of the vLLM package |
| `args` | trail | yes | arguments that change what the model reads or the numbers, in canonical form (the table in `data-generation.md` §1) |
| `env` | trail | yes | environment variables that do the same, such as `VLLM_BATCH_INVARIANT` and `VLLM_SYSTEM_START_DATE` |
| `performance` | details | no | arguments that only change speed, recorded for latency comparisons |

**client**: a thing.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `build` | trail | yes | the store path of the chatddx build. A run from a dev shell has none, and is recorded as such. |
| `rev` | details | no | |
| `packages` | details | no | the pydantic-ai, openai and inspect-ai versions |

**stack**: a composition. It replaces `connection`.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `machine` | trail | yes | |
| `os` | trail | yes | null for cloud |
| `host_os` | trail | yes | for a NixOS container, the host's OS, which holds the kernel and the NVIDIA driver; null otherwise |
| `model` | trail | yes | |
| `serving` | trail | yes | null for cloud |
| `endpoint` | details | no | where requests go |
| `served_name` | details | no | the `model` field of the request |
| `api` | details | no | `vllm`; a cloud stack names its API |
| `credential` | details | no | the name of a secret, never the secret |

`data-generation.md` counted the client as part of the stack. As an entity
it stands apart: it changes with every chatddx deploy while the server
doesn't, and a trial joins the two.

### Slices

**instruction**

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `system` | trail | yes | the template for the system message (Handlebars, via `TemplateStr`) |
| `user` | trail | yes | the template for the user message; `{{case}}` reproduces today's behaviour |
| `variables` | trail | yes | the declared variable schema (`deps_schema`): `case`, plus the slots other slices fill |

**output**

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `schema` | trail | yes | JSON Schema, with key order kept |
| `mode` | trail | yes | native, tool or prompted |
| `guidance` | trail | yes | the text for the `output_guidance` slot |
| `schema_prompt` | trail | yes | the template that shows the schema to the model; null means it isn't shown |

**reasoning**: new.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `effort` | trail | yes | off, on, minimal, low, medium, high or xhigh (pydantic-ai's `ThinkingLevel`) |
| `budget` | trail | yes | a token budget, or null |

**sampling**

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `temperature`, `top_p`, `top_k`, `max_tokens`, `presence_penalty`, `frequency_penalty`, `stop` | trail | yes | null means the model's default, which resolution looks up and writes into the request |

**toolset**: deferred. It replaces `tool_group`.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `tools` | trail | yes | ordered |
| `guidance` | trail | yes | the text for the `tool_guidance` slot |

**tool**: deferred. It is part of a toolset, not a slice.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `name` | trail | yes | the name the model sees |
| `description` | trail | yes | |
| `parameters` | trail | yes | |
| `implementation` | details | no | a git revision and entry point; the trial records the revision it ran |

### The configuration and the case

**configuration**: a composition. It replaces `agent`.

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `instruction`, `output`, `reasoning`, `sampling` | trail | yes | one slice of each kind |
| `toolset` | trail | yes | optional |

**case**

| Field | In | Fingerprinted | Notes |
|---|---|---|---|
| `payload` | trail | yes | unchanged |

A trial is history, not part of the registry. It points at trails: the
configuration, the case, the stack and the client. It also records the
seed and replicate, the branch rows whose details resolution read, and the
request itself (`data-generation.md` §4).

## 3. Current fields, mapped

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
| `definition` | `instruction.system` | yes |

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
| `seed` | scrapped from the registry; it becomes a per-replicate value on the trial | no |
| `n` | scrapped | no |
| `logit_bias` | scrapped: its keys are token ids, so a slice carrying them would fit only one tokenizer | no |
| `provider_params` | dissolved. The reasoning switches it carried (`chat_template_kwargs.enable_thinking`, `openai_reasoning_effort`) become `reasoning.effort`. Anything else needed later becomes a typed field of the slice it belongs to. | yes, as those fields |

**output_type** (renamed output)

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `definition` | `output.schema` | yes |
| `coercion_strategy` | `output.mode` | yes |
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
| `sampling_params` | `configuration.sampling` | yes |
| `output_type` | `configuration.output` | yes |
| `tool_group` | `configuration.toolset` | yes |

**case**

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `payload` | `case.payload` | yes |
| `expects` (details) | removed: targets move to inspect | no |

**expect** (removed)

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `payload` | inspect: a sample's `target`, keyed by the case | no |
| `scorer` | inspect: the task's scorer | no |

**scorer** (removed)

| Current field | Becomes | Fingerprinted |
|---|---|---|
| `command` | inspect: `exact_match` and `regex_match` become inspect scorers | no |

**Views.** `super_agent`'s flat form becomes the configuration's, and every
other view follows its entity. Form data isn't identity.

## 4. New fields, and what was left out

Only the fields the redesign cannot work without were added:

- **`machine.machine_id`, `os.toplevel`, `model.blob`, `client.build`:**
  the single identifying fields of the things below a request.
- **`machine.unreliable`:** marks what can't be checked.
- **`serving.engine`, `serving.args`, `serving.env`:** the start-up
  settings, identified separately from the OS.
- **`stack` and its relations:** which things answered a request.
- **`model.facts`:** what resolution reads to translate slices for each
  model.
- **`instruction.user`, `instruction.variables`:** templating instead of a
  text blob, with its slots declared.
- **`output.guidance`, `output.schema_prompt`, `toolset.guidance`:** the
  text a slice brings with it, and whether the model sees the schema.
- **`reasoning.effort`, `reasoning.budget`:** reasoning as a slice of its
  own.

Left out on purpose, to be added when a study needs them:

- `min_p`, `repetition_penalty` and the other vLLM-only sampling settings;
- a reasoning slot in the instruction;
- `tool_choice`;
- few-shot examples;
- a case's language, source and stage (tags cover dataset membership for
  now);
- pricing.

## 5. Slices and resolution

- **A configuration only names slices, one of each kind.** Turning them
  into one coherent request is resolution. Resolution fills the
  instruction's slots, refuses a request field that two slices both write,
  checks what slices require of each other and of the stack, translates
  reasoning for the model, and looks up defaults.
- **Resolution is a task of its own**, and this note doesn't specify it.
- **What the data model owes it:**
  - slot names, fixed by convention for each slice kind (`output_guidance`,
    `tool_guidance`);
  - the instruction's declared variables;
  - the model's facts.
- **Where its result goes:** resolution's output is recorded on the trial,
  with its hashes. If requirements between slices ever need declaring as
  data, they become fields on the slices that hold them.

## 6. Order and storage

- **Commit order.** `EntityName` keeps its rule that anything an entity
  references is committed first. The order becomes: machine, os, model,
  serving, client, stack, tool, toolset, instruction, output, reasoning,
  sampling, configuration, case.
- **Schema storage.** `output.schema` is stored as `json` or text, not
  `jsonb`, because `jsonb` re-sorts keys.
- **Fingerprint column.** A versioned fingerprint no longer fits
  `TrailModel.fingerprint` (`max_length=64`), so the column grows. Short
  forms such as `short_fingerprint` read the hex part.
