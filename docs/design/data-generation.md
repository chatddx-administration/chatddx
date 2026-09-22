# Addendum: how a request is generated and recorded

This narrows `research-data-model.md` to one question: how chatddx turns a
configuration and a case into a request to a model, and what it records
about that request. Evaluation is out of scope. inspect-ai will do it, and
it appears here only where its needs shape what generation records. Where
this note and the original disagree, this note wins; §7 lists what it
replaces.

Terms used below:

- **Stack**: machine, OS, model, serving settings and client.
- **Configuration**: the request-time bundles.
- **Trial**: one request made and recorded.

What was read: pydantic-ai 2.41.0, inspect-ai 0.3.263 and openai 3.10.0
(the versions pinned in `uv.lock`), and vLLM's main branch at the time of
writing. Anything said about vLLM needs checking against the version the
NixOS configuration actually ships (§6).

## 1. The stack under a request

A machine, an operating system and a model are things, not settings. Each
has exactly one identifying field. Everything else about it is description:
kept for people, never hashed. Change anything real about one of them and
it becomes a new one.

### Machine

- **Identity:** an `id`, assigned when a physical machine is registered.
- **Description:** GPUs (model, memory, UUIDs), CPU, RAM, and where the
  machine is.
- **Change:** any change to the hardware makes a new machine.
- **A check, not an identity:** the host reports its GPU UUIDs
  (`nvidia-smi -L`), and a run on a machine whose UUIDs don't match its
  registration is flagged. This catches an unregistered hardware swap
  without making the UUIDs part of the identity.
- **Cloud:** a cloud provider is a machine with `unreliable = true`.
  Everything under its requests is the provider's claim rather than
  something chatddx can check. Its OS is unknown, and its model is the
  provider's dated model name.

### Operating system

- **Identity:** the system's top-level store path, which is what
  `/run/current-system` points to (`/nix/store/<hash>-nixos-system-<host>-…`).
  This is recommended over the flake revision for three reasons:
  - A revision identifies source, not a system. One flake usually builds
    several hosts, so a commit that only touches another host, or only the
    README, gives this host a new revision while its system stays the same.
  - A dirty tree has no revision. `system.configurationRevision` is null
    unless the flake sets it (`self.rev or "dirty"`), and
    `nixos-version --json` has been known to leave it out (nixpkgs #303945).
  - The store path is exactly the closure that runs: every package, unit
    file and environment variable, the vLLM service included.

  The flake revision is kept as description. If the revision is kept as the
  identity instead, dirty deploys must be refused, and unrelated commits
  will split identities.
- **Containers:** a NixOS container has its own top-level path, but the
  kernel and the NVIDIA kernel module belong to the host. Register the
  host's system as an OS too, and let a run point at both. Each still has a
  single identifying field.

### Model

- **Identity:** a hash of the directory vLLM loads. That directory holds the
  weights, `config.json`, the tokenizer, the chat template and
  `generation_config.json`. All of it changes behaviour: the chat template
  shapes the prompt, and `generation_config.json` decides what an unset
  sampling parameter means.
- **Getting the hash:** fetch the model as a Nix fixed-output derivation.
  - Tools such as nix-hug fetch each file by its Hugging Face LFS SHA-256.
    The store path is then derived from the content.
  - Start vLLM with `--model /nix/store/<hash>-<name>`. `GET /v1/models`
    then reports that path back as `root` (vLLM's `ModelCard.root` is the
    model path), so a model's identity can be read off the running server.
- **Never let vLLM download by repository name at start-up.** That resolves
  a floating revision at run time.
- **Variants:** a quantized variant (AWQ, FP8) is a different blob, and so a
  different model.
- **Description:** family, Hugging Face repository and commit, quantization,
  parameter count, context length and licence. It also holds **capability
  facts**, which the compile step (§2.4) reads:
  - how reasoning is switched and graded;
  - the vendor's recommended sampling for each mode;
  - whether the chat template renders tool definitions.

  These are facts about the blob, so they don't touch its identity.

### Serving: start-up settings

vLLM only. Its settings are declared in NixOS, so the OS identity already
pins them. They are still recorded separately, as **Serving**: the vLLM
package plus the arguments and environment variables that change output,
hashed on their own. The `--model` path is left out, because that is the
model's identity. Keeping Serving separate buys two things:

- It tells "the same serving on a patched OS" apart from "different
  serving".
- If run-time reloading is ever introduced, Serving becomes a record in its
  own right, and nothing that points at it has to change.

| Kind | vLLM arguments and environment | In the serving hash |
|---|---|---|
| Changes what the model reads or how output is shaped | `--chat-template`; `--default-chat-template-kwargs` (e.g. a server-wide `enable_thinking`, which a request can override); `--generation-config` and `--override-generation-config` (what unset sampling parameters become); `--reasoning-parser` and `--reasoning-config` (the text forced when a thinking budget runs out, which the model then continues from); `--tool-call-parser` and `--enable-auto-tool-choice`; `--structured-outputs-config` (the default backend `auto` chooses per request; `disable_any_whitespace`, `disable_additional_properties`, `enable_in_reasoning`); `--max-model-len`; `--seed` (default 0); `--logits-processors`; `VLLM_SYSTEM_START_DATE` and `VLLM_GPT_OSS_HARMONY_SYSTEM_INSTRUCTIONS` (see below) | yes |
| Changes numerics, not the prompt | `--dtype`, `--quantization`, `--kv-cache-dtype`, `--tensor-parallel-size`, `--enforce-eager`, the attention backend, speculative decoding, `VLLM_BATCH_INVARIANT` | yes |
| Performance only | `--gpu-memory-utilization`, `--max-num-seqs`, `--max-num-batched-tokens`, `--enable-prefix-caching`, host, port, API key | no, but recorded |

Some of these settings need explaining:

- **gpt-oss prompts contain today's date.** For gpt-oss, vLLM writes the
  current date into the system message. Its own source says: "This brings
  non-determinism in vLLM. Set VLLM_SYSTEM_START_DATE to pin it." Whether
  gpt-oss's instructions land in the system or the developer message is an
  environment switch too.
- **`--served-model-name` is not cosmetic.** pydantic-ai chooses a model
  profile by the prefix of the model's name. Either the served name starts
  with the family (`qwen3-…`, `gpt-oss-…`), or, better, the compile step
  passes the profile explicitly from the model's description.
- **"Performance only" holds only under batch invariance.** Without it,
  anything that changes batching changes the numbers.
- **Determinism:**
  - vLLM's documentation says results are not reproducible by default.
  - For online serving the only route is batch invariance
    (`VLLM_BATCH_INVARIANT=1`). It is in beta and needs NVIDIA compute
    capability 8.0 or higher, which both the 3090 and the 5090 have. It has
    been validated on Qwen3-8B-AWQ and gpt-oss-20b.
  - Even then, reproducibility holds "only when it runs on the same hardware
    and the same vLLM version". That sentence is the case for machine and OS
    as identities.
  - Research servers should run with batch invariance on, with its
    throughput cost measured.
- **Where chatddx learns these settings:**
  - vLLM's API exposes `/version` and `/v1/models` (`root`,
    `max_model_len`), but not its arguments.
  - So the NixOS module that writes the `vllm serve` unit should also write
    a manifest from the same Nix values: model path, vLLM package,
    arguments and environment.
  - A small internal endpoint serves that manifest, together with
    `/run/current-system` and the GPU UUIDs.
  - The worker reads it before each batch and cross-checks `root` and
    `/version`. A mismatch stops the batch.

### Client

The chatddx build decides how a configuration becomes a request. Its store
path pins pydantic-ai, openai and inspect-ai, and pydantic-ai's model
profiles, schema transformers and default prompt text all live in library
code. (For example, Qwen's profile inlines `$defs`, and the OpenAI fallback
rewrites schemas for OpenAI's strict mode and drops `title`.) So the client
follows the same pattern: one identifying field, its store path, recorded
with every trial.

Two things keep a library upgrade from changing requests without anyone
noticing:

- chatddx owns every string the model reads (§2.2);
- the recorded request (§3) catches whatever that misses.

## 2. Request-time settings

### 2.1 What a request is made of

| Layer | Contents | pydantic-ai | vLLM-only, via `extra_body` |
|---|---|---|---|
| Messages | system text, the case, earlier turns | instructions, message history | none |
| Output | `response_format` (native), a final-result tool (tool), or the schema as text in the instructions (prompted) | `NativeOutput`, `ToolOutput`, `PromptedOutput` | `structured_outputs` (regex, choice, grammar) |
| Reasoning | on, off, effort, budget | unified `thinking`, `openai_reasoning_effort` | `chat_template_kwargs`, `thinking_token_budget`, `include_reasoning` |
| Sampling | temperature, top-p, penalties, stop, max tokens, seed | typed `ModelSettings` | `top_k`, `min_p`, `repetition_penalty`, `min_tokens` |
| Tools | definitions, `tool_choice`, `parallel_tool_calls` | toolsets | none |
| Transport | timeouts, retries, streaming, headers | `timeout`, the HTTP client | `priority`, `request_id` |

pydantic-ai's OpenAI chat model sends only OpenAI's standard fields, plus
`extra_body`, whose keys the openai SDK merges into the top level of the
JSON body. A `top_k` in `ModelSettings` is dropped without a warning, so
the `top_k` chatddx stores today has never reached vLLM.

### 2.2 Bundles

A bundle owns one concern, may write into several layers, and declares
everything it writes. There are four bundles now and a fifth later.

**Instruction.**
- **Templates:** the system and user messages are templates. They are
  Handlebars, via pydantic-ai's `TemplateStr`, and are checked at compile
  time against a declared variable schema (`deps_schema`). Today's Jinja
  instead renders a missing variable as blank without complaint.
- **Variables:** `case`, plus named **slots** that other bundles fill:
  `output_guidance`, `reasoning_guidance` and, later, `tool_guidance`.
  This generalizes today's `{{ tool_group_instructions }}`.
- **The case is a value, never a condition.** The template places the case
  but never branches on it. The request fingerprint in §3 depends on that.

**Output.**
- **Holds:**
  - the schema, with its key order kept;
  - the mode: native, tool or prompted;
  - the text that fills `output_guidance`;
  - whether the schema is also shown to the model, and the template that
    shows it.
- **Whether the model reads the schema is a factor of its own.**
  - pydantic-ai's vLLM provider explains why: native output on vLLM "is pure
    token masking, so the model only sees the schema if it is also injected
    into the instructions".
  - That provider injects it. chatddx today uses `OpenAIProvider` with a
    hand-made profile, which does not. So today's native runs force the
    output into the management-plan schema without the model ever reading
    the schema's field descriptions ("Include critical rules even if low
    probability").
  - For gpt-oss, vLLM's harmony renderer puts instructions and function
    tools into the prompt, but not `response_format`.
  - In tool mode, the schema does reach the model, as a tool definition.
  - So the Output bundle states whether the schema is shown, using its own
    template rather than pydantic-ai's default text ("Always respond with a
    JSON object that's compatible with this schema: …").
- **The schema is the contract inspect's scorers read.** The bundle's other
  fields are how the model is made to meet it.
- **Validation leaves the research path:**
  - Retrying on invalid output re-samples with an error message. The trial
    becomes a conversation, and its accuracy measures the model plus a
    repair loop.
  - `inform` writes `__error__` into the output itself.
  - A research trial records the raw output and whether it validates. The
    product can keep its retries.
  - If repair is ever studied, it becomes a bundle of its own, with its own
    message text.

**Reasoning.**

Reasoning gets a bundle of its own because it is the biggest lever, and
each model family takes it differently. The bundle states an intent (off,
on, an effort level, or a token budget) plus optional guidance. The compile
step translates the intent using the model's description:

| Family on vLLM | Off | On | Effort levels | Budget |
|---|---|---|---|---|
| Qwen3 | `chat_template_kwargs.enable_thinking = false` | `true`, the default | none; low and high both mean "on" | `thinking_token_budget`, which needs `--reasoning-parser` (`--reasoning-config` sets the forced end text) |
| gpt-oss | impossible: vLLM rejects `reasoning_effort = "none"` for harmony | `medium` | `reasoning_effort` low, medium or high | not documented |

- **A pydantic-ai trap.** Its unified `thinking` setting is dropped silently
  unless the model profile declares thinking support. Its vLLM provider
  declares that for Qwen3 but not for gpt-oss. So chatddx supplies profiles
  from the model's description instead of relying on name matching.
- **The hash is taken after translation.**
  - Low and high on Qwen3 are one configuration, not two.
  - An intent the model can't honour is an error, not a field that is
    silently ignored.
- **Reasoning and sampling are coupled.**
  - Qwen3's model card recommends different sampling for each mode:

    | Mode | temperature | top-p | top-k | min-p |
    |---|---|---|---|---|
    | Thinking (never greedy decoding) | 0.6 | 0.95 | 20 | 0 |
    | Non-thinking | 0.7 | 0.8 | 20 | 0 |

  - The card gives the thinking values as the defaults in
    `generation_config.json`.
  - Today's `disable-thinking` agents set no sampling. Unless the server was
    started with `--generation-config vllm`, they ran non-thinking mode on
    thinking-mode defaults. Setting `top_k` would not have helped, since it
    never reaches vLLM (§2.1).
  - So a reasoning bundle may require a sampling bundle tuned for its mode,
    and the compile step checks it.
  - A thinking budget is coupled to `max_tokens` in the same way.

**Sampling.**
- **Holds:** temperature, top-p, top-k, min-p, the repetition, presence and
  frequency penalties, stop sequences and `max_tokens`.
- **Typed:** the fields are typed in chatddx, and the vLLM-only ones compile
  into `extra_body`.
- **"Use the model's default" is a legitimate value.** The compile step
  resolves it from the model's `generation_config.json` and the serving
  settings, then writes it into the request, so the request states what it
  asked for.
- **Not part of this bundle:** the seed, which belongs to the trial (§4).
  `n` is gone.

**Tools (later).**
- The definitions the model reads (name, description and parameter schema)
  are part of the request and are hashed.
- Implementations are referenced by git revision. They belong to the trial,
  because they change the tool's results, not the request.
- Their guidance fills `tool_guidance`.

### 2.3 Composition

- **One of each:** a configuration is one Instruction, one Output, one
  Reasoning and one Sampling bundle, and later zero or one Tools bundle.
- **Nothing is written twice.**
  - Each bundle declares what it writes: request fields, including nested
    `extra_body` paths, and slots.
  - Composition takes their union. A field or slot written twice is an
    error.
  - Contrast pydantic-ai's own merge, where the later value wins
    (`merge_model_settings` merges shallowly). chatddx's inventory merge is
    shallow too, so two sampling records' `provider_params` replace each
    other instead of combining.
- **Requirements are checked.** Each bundle declares what it needs from the
  other bundles, from the model's description and from the serving
  settings, and composition checks all of it. For example:
  - a reasoning budget needs a reasoning parser;
  - native output needs structured outputs;
  - a sampling bundle tuned for non-thinking mode needs reasoning off.
- **How this maps onto pydantic-ai:**
  - Each bundle maps naturally onto a pydantic-ai capability
    (`get_instructions`, `get_model_settings`, `get_toolset`).
  - pydantic-ai's `AgentSpec`, which loads from YAML or JSON, is close to a
    serialized configuration: it has templated instructions,
    `deps_schema`, `output_schema`, `model_settings` and capabilities.
  - It has two gaps. It cannot state the output mode: it turns
    `output_schema` into a `StructuredDict` and leaves the mode to the
    profile. And when two capabilities set the same thing, the later one
    wins.
  - So chatddx keeps a thin spec of its own on top: bundles go in; an
    `AgentSpec`, plus an explicit output type and profile, come out.
  - `TemplateStr` needs the `pydantic-ai-slim[spec]` extra.

### 2.4 Compile

`compile(configuration, case, stack facts, seed)` produces the exact HTTP
request, in five steps:

1. Check the composition and every requirement.
2. Resolve defaults from the model's description and the serving manifest,
   and translate the reasoning intent.
3. Render the templates.
4. Build the pydantic-ai agent on `VLLMProvider`, with a profile taken from
   the model's description.
5. Send the request through an httpx client (pydantic-ai's providers accept
   one) whose event hook captures the exact request and response bytes.

A **dry run** follows the same path against an `httpx.MockTransport` that
records the body and returns a stub completion. It yields the request
without touching a GPU. The first thing to test is whether dry-run bodies
are byte-identical to real ones.

### 2.5 Example

Today's `qwen3-8b management_plan_v1 seed-locked disable-thinking`, stated
as bundles:

```yaml
instruction: ddx-plan            # system and user templates; slots output_guidance, reasoning_guidance
output:
  schema: management_plan_v1     # key order kept
  mode: native
  show_schema: true              # a factor; the template is the bundle's own
reasoning: off
sampling: qwen3-non-thinking     # temperature 0.7, top_p 0.8, top_k 20, min_p 0, max_tokens 4096
```

Compiled for Qwen3-8B-AWQ, abbreviated:

```json
{
  "model": "qwen3-8b-awq",
  "messages": [
    {"role": "system", "content": "…instructions, output guidance, schema text…"},
    {"role": "user", "content": "…the case…"}
  ],
  "response_format": {"type": "json_schema", "json_schema": {"name": "management_plan_v1", "schema": "…authored key order, $defs inlined by Qwen's profile…"}},
  "temperature": 0.7,
  "top_p": 0.8,
  "max_completion_tokens": 4096,
  "seed": 1,
  "top_k": 20,
  "min_p": 0.0,
  "chat_template_kwargs": {"enable_thinking": false}
}
```

The Reasoning bundle's contribution to that request is
`{"chat_template_kwargs": {"enable_thinking": false}}`. The Sampling
bundle's is the six sampling fields.

## 3. Fingerprints

### 3.1 What is hashed

| Level | Covers | Used for |
|---|---|---|
| Stack | machine id, OS id(s), model hash, serving hash, client id | which hardware, system, model, serving and client produced a trial |
| Bundle | each bundle's declared content, in canonical form | authoring: reuse, naming, the branch layer |
| Contribution | each bundle's effect on the request once compiled for a given stack | comparing configurations |
| Request | the request with the case left as a placeholder (the skeleton), and each trial's exact body | proving what was asked, and of which configuration |

**Contributions are the tool for comparison:**

- Two configurations whose contribution vectors differ in one position give
  a clean single-factor contrast.
- A position that collapses, as Qwen3's low and high do, shows as equal.
- Equal skeletons on the same stack mean identical requests for every case.
  That works because the case reaches the request only through the
  template's `case` variable. A template that branched on the case would
  break it, which is why §2.2 forbids that.

### 3.2 Canonical form

- **JSON Canonicalization Scheme (RFC 8785), with one exception.** RFC 8785
  sorts keys and fixes number formatting. The exception is anything whose
  order carries meaning: JSON Schema `properties`, because constrained
  decoders emit keys in that order.
  - Such objects are encoded as ordered pairs before canonicalizing, so the
    sort can't reach them.
  - Today both `generate_fingerprint` and Postgres `jsonb` sort them (see
    the original note).
  - Documents whose order matters are stored as `json` or text, not
    `jsonb`.
- **Resolved values, not blanks.** The compile step writes down the values
  it relied on.
- **Left out:** transport (timeouts, retries, streaming, headers, request
  ids, API keys), the seed (it is the trial's), and names, owners and tags.
  - inspect-ai makes the same cut for its cache key and task identifier,
    dropping `max_retries`, `timeout`, `max_connections` and the like. That
    is a useful precedent.
  - But inspect's identities are name-based (`vllm/Qwen/Qwen3-8B-AWQ`), not
    content-addressed, so they cannot stand in for these.
- **Two hashes per trial:**
  - the hash of the exact bytes: the audit, which proves what was sent;
  - the canonical hash: the comparison across client versions, where the
    SDK may serialize the same request differently.

### 3.3 Securable later

Nothing here is enforced yet. Four rules keep enforcement possible later:

1. **Every hash names its scheme and version**, for example
   `cddx-request/1:sha256:…`. Changing the scheme then adds a version
   instead of silently breaking old hashes. inspect's
   `TASK_IDENTIFIER_VERSION` is the same idea.
2. **Every hash is stored next to its canonical input**, so it can be
   recomputed.
3. **Every trial keeps its raw request and response bytes.**
4. **Identities are single, write-once fields.** The existing trail triggers
   show the pattern.

Later, these allow hosts to sign their manifests, trials to be chained or
signed, and stored inputs to be re-verified in bulk.

## 4. A trial

- **Scope:** one configuration × one case × one stack × one replicate.
  Today that means one request; it becomes more once tools or repair exist.
- **It records:**
  - the stack identities;
  - the bundle, contribution and skeleton hashes;
  - the exact request and response bytes, with their hashes;
  - the parsed output, and whether it validates against the Output schema;
  - `finish_reason` (a truncated answer is not a wrong one);
  - usage, including reasoning tokens where vLLM reports them;
  - latency;
  - the served name and vLLM version;
  - the replicate index and seed.
- **Concurrency:** with batch invariance on, concurrency doesn't change
  outputs, so the worker can send requests in parallel. Latency is then
  recorded together with the concurrency it ran under.
- **No targets:** nothing about the expected answer belongs to a trial. That
  is inspect's.

## 5. inspect-ai

inspect-ai evaluates. The question is how much of generation it can take
over as well.

| Option | How | Verdict |
|---|---|---|
| A. inspect generates | tasks, solvers and `GenerateConfig`, through inspect's vLLM provider | Loses control of the request. `top_k` is not sent to vLLM (inspect sends it only for a few providers such as Anthropic, Google, Bedrock and Hugging Face). `reasoning_tokens` is Anthropic-only. The response schema passes through inspect's `JSONSchema` model, which has no `$defs`, `$ref` or `title`, and its OpenAI-compatible path strips `pattern`, `minLength`, `maxLength`, `minimum`, `maximum` and `examples`. Structured output exists only as `response_format`. Everything else has to ride in `extra_body`, and the product would run a different client from the one evaluated. |
| B. pydantic-ai inside inspect, through its agent bridge | inspect intercepts pydantic-ai's OpenAI calls and re-issues them through its own model API | Unusable for research. The bridge rebuilds `GenerateConfig` from the OpenAI fields it knows, so `extra_body` is dropped: Qwen3's thinking switch, `top_k`, `thinking_token_budget`. Generation parameters are dropped unless `forward_generation_config=True`. And by inspect's own account, "a dropped `$ref` leaves the property an empty schema (`{}`) while it stays `required`". The request vLLM receives is not the one composed. |
| C. chatddx generates, inspect scores | pydantic-ai compiles and sends (§2.4). chatddx writes each batch as an inspect `EvalLog` (`write_eval_log`), one sample per trial, holding the input, messages, output, `epoch` (the replicate), `metadata` (identities and hashes) and a `ModelEvent` whose `call` carries the raw request and response. inspect scores it with `inspect_ai.score(log, scorers)` or `inspect score`, and can re-score without generating again. | **Recommended now.** The request is exactly the one composed, research and product use one client, and the existing worker is reused. The cost is an adapter from pydantic-ai's messages to inspect's log types. |
| D. inspect orchestrates, pydantic-ai builds requests | a custom inspect provider (`@modelapi("chatddx")`) whose `generate()` calls pydantic-ai's `direct.model_request` with the compiled settings | The upgrade path, if inspect's orchestration (epochs, eval sets, retries, concurrency) comes to be worth more than the worker. A larger integration surface. |

Whichever option is chosen, it shapes generation the same way:

- Trials map one-to-one onto inspect samples: the case is the sample id and
  the replicate is the epoch.
- Identities and hashes travel in sample metadata.
- Raw requests travel as `ModelEvent` calls, so inspect's viewer shows
  exactly what was sent.
- Targets stay out of generation.

## 6. Open questions to settle by experiment

1. Which vLLM version does the NixOS configuration ship, and does it have
   the following? The documentation cited here describes vLLM's main branch.
   - `reasoning_effort` setting `enable_thinking` automatically;
   - `thinking_token_budget`;
   - batch invariance;
   - `--structured-outputs-config`.

   nixpkgs has also had trouble serving on the RTX 5090 (#406675).
2. Does gpt-oss on vLLM honour low, medium and high? Compare reasoning-token
   counts.
3. Does vLLM report reasoning tokens in `usage`? If not, count them with the
   model's tokenizer.
4. Is a dry-run request byte-identical to a real one?
5. What does batch invariance cost in throughput, on the 3090 and on the
   5090?
6. Where does the manifest endpoint live, and who may read it?
7. Does showing the schema to the model change accuracy in native mode? That
   is a study rather than a question for this note, but it can now be asked.

## 7. What this replaces in `research-data-model.md`

| Original | Now |
|---|---|
| Deployment, with pricing, `honours` and credentials | Machine, OS, Model, Serving and Client, one identifying field each. `honours` becomes facts in the model's description and the serving manifest, read at compile time. |
| Model, with revision and quantization in its identity | Identified by its blob hash alone; the rest is description. |
| Inference | Reasoning and Sampling bundles. `overrides` become typed vLLM fields. `n` is dropped. |
| Prompt | The Instruction bundle: `TemplateStr` with declared slots. Examples are deferred. |
| OutputContract and ResponseFormat | The Output bundle. `on_invalid` and retries leave the research path. |
| Toolset | Tools, deferred, referenced by git revision |
| Strategy | Deferred: one request per trial |
| Case, Reference, Dataset, Grader, Score, and the derived views | inspect-ai; out of scope here |
| Identity (compile, spec and effective fingerprints) | §3 of this note |
| Study, Arm, Trial | The trial as described in §4. Study design is not covered here. |

## Sources

- vLLM: `docs/features/reasoning_outputs.md`, `docs/features/batch_invariance.md`,
  `docs/usage/reproducibility.md`, `docs/features/structured_outputs.md`,
  `vllm/config/model.py`, `vllm/config/structured_outputs.py`,
  `vllm/entrypoints/openai/chat_completion/protocol.py`,
  `vllm/entrypoints/openai/parser/harmony_utils.py`,
  `vllm/entrypoints/openai/models/serving.py`
  (https://github.com/vllm-project/vllm)
- pydantic-ai 2.41.0: `providers/vllm.py`, `models/__init__.py`,
  `models/openai.py`, `profiles/`, `agent/spec.py`, `template.py`,
  `capabilities/`, `settings.py`
- inspect-ai 0.3.263: `model/_providers/vllm.py`, `model/_openai.py`,
  `model/_generate_config.py`, `util/_json.py`, `model/_cache.py`,
  `_eval/evalset.py`, `agent/_bridge/`, `event/_model.py`
- Qwen3 model card, sampling recommendations:
  https://huggingface.co/Qwen/Qwen3-8B
- nixpkgs issues: https://github.com/NixOS/nixpkgs/issues/303945 and
  https://github.com/NixOS/nixpkgs/issues/406675
- nix-hug, Hugging Face models as fixed-output derivations:
  https://github.com/marksisson/nix-hug
