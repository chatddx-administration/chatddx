# A data model that can say which parameter mattered

ChatDDX exists to answer one question: **which configuration choices make a
generated management plan more or less accurate, and what does each choice
cost in time and compute?** This note sets out the data model that question
needs, and compares the current model against it. It does not propose a
migration.

## The question, as data

To answer the question, the model needs three things:

1. **Settings that can be varied one at a time and compared across
   models.** A study changes one setting and holds the rest fixed. That only
   works if each setting lives in one place and means the same thing
   whatever it is paired with.
2. **A valid measure of how accurate a plan is.** That covers the
   differential, the workup, the treatment, the disposition and harm, scored
   against a clinical reference by a grader that stays fixed while the
   configurations vary.
3. **Time and compute measured for every observation.** That means latency,
   tokens, calls and cost, together with what the model ran on.

Today an agent is `instruction + connection + sampling_params + output_type +
tool_group`, and its fingerprint is a hash of its components' hashes. The
fields were grouped by implementation, following which pydantic-ai argument
each one feeds, rather than by the questions a study asks. So:

- components don't transfer between models;
- some fingerprinted fields never reach the model, while some things that do
  reach it are not fingerprinted;
- nothing scores the management plan.

## Where to cut

1. **Each setting has one home.** Every setting that changes model
   behaviour lives in exactly one component. Guidance about a specific
   output field lives with that field; guidance about the task as a whole
   lives in the prompt.
2. **A component means the same thing in every pairing.** Where validity
   depends on what a component is paired with (`top_k` on a server that
   ignores it, for example), a compile step checks it and fails loudly. It
   never drops a setting silently.
3. **The three axes stay apart.** What drives accuracy (the recipe), what
   drives cost and latency (the deployment), and what measures (dataset,
   reference, grader) never share a record. A change on one axis then can't
   pass for a change on another.
4. **A fingerprint describes behaviour.** It covers exactly what reaches the
   model or changes processing:
   - order, wherever the model sees order;
   - defaults, made explicit;
   - the code versions of tools and graders.

   It never covers names, owners, tags, endpoints or credentials.
5. **Each audience gets its own handle.** Names are for people, hashes are
   for machines, and factors are for statistics. Analysis reads a flat factor
   vector derived from the resolved recipe, never branch names or hashes.

## The model

```
Configuration: content-addressed specs, named and owned through the branch layer
  Agent ─┬─ Model ◄─────────── Deployment   (bound per arm, not part of the agent)
         ├─ Inference
         ├─ Prompt ─── Example*
         ├─ ResponseFormat ─── OutputContract
         ├─ Toolset ─── Tool*
         └─ Strategy

Evaluation assets
  Case ◄── Reference ── Concept*     Dataset = frozen [(Case, Reference)] + splits     Grader (── judge Agent)

Study design and results
  Study(Dataset@v, Grader*, replicates, grid) ─► Arm(Agent, Deployment) ─► Trial(Case, replicate) ─► Score(Grader, Reference, metric)
                                                                               └─► Message*  (transcript)
```

### Configuration

- **Model** identifies the weights.
  - Fields: `family`, `name`, `revision`, `quantization` (bf16 | fp8 |
    awq-int4 | gguf-q4_k_m …), `params_b` (total and active),
    `context_window`, `reasoning` (none | toggle | effort | budget |
    always-on) and `open_weights`.
  - `revision` is a Hugging Face commit or a dated API snapshot, never a
    floating alias.
- **Deployment** records where and how a model is served. It carries the
  cost and latency axis.
  - `model → Model`.
  - `api`: openai-chat | openai-responses | anthropic | google | …. This
    selects the adapter.
  - `engine` and its version: vLLM, SGLang, llama.cpp or a vendor API.
  - `hardware`, for example "1× RTX 5090".
  - `honours`: the settings this serving setup actually applies
    (temperature, top_k, min_p, seed, JSON-schema decoding, tools, reasoning
    control).
  - `pricing`: cost per million tokens for input, output and cached input,
    or a GPU-hour cost plus measured throughput.
  - `max_concurrency`.
  - Recorded but kept out of identity: `endpoint`, `served_name`,
    `credential_ref`.
- **Inference** holds request-level settings that carry over to any model.
  - `reasoning` is a first-class field: off | minimal | low | medium | high
    | xhigh, or a token budget.
  - Sampling and limits: `temperature`, `top_p`, `top_k`, `min_p`,
    `max_output_tokens`, the repetition penalties, `stop`, and
    `seed_policy` (fixed | per replicate).
  - `overrides` passes raw provider parameters. It is allowed, but it is
    marked as not carrying over to other models and appears as a factor of
    its own.
- **Prompt** holds all text the model reads except the case itself and the
  output schema.
  - `system`: a template.
  - `case_framing`: a template for how a case becomes the user message.
  - `examples`: an ordered list, each a case plus its ideal output. Examples
    may not come from the study's test split.
  - `response_language`.
  - Templates declare their variables (`case`, `tools`, …). A variable that
    is undeclared, or declared but never placed, is a compile error.
- **OutputContract** defines what consumers depend on: the UI and the
  graders.
  - `name@version`.
  - `schema`: a JSON Schema whose key order is kept.
  - `bindings`: a map from schema paths to clinical concepts: `ddx.items`,
    `ddx.item.label`, `ddx.item.critical`, `plan.workup`, `plan.treatment`,
    `plan.disposition`, `warnings`.
  - Graders read bindings rather than schema paths, so a contract can change
    without rewriting its graders.
- **ResponseFormat** defines how the model is made to produce the contract.
  It is an accuracy factor.
  - `contract → OutputContract`.
  - `schema`: the schema the model sees. It defaults to the contract's, but
    may reorder fields, add a leading `reasoning` field, or reword
    descriptions.
  - `projection` maps that schema onto the contract (identity by default).
  - `mode`: native | tool | prompted | free text followed by extraction,
    with `extractor → Agent` for the last.
  - `max_retries` and `on_invalid` (retry | fail). The output is never
    modified.
- **Toolset**
  - `tools`: an ordered list. Each tool has a name, description, parameters,
    and `impl`: a code reference plus a hash of that code.
  - `guidance`: text the prompt places through `{{ tools }}`.
  - `policy`: tool_choice, a maximum number of calls, and whether calls may
    run in parallel.
  - Retrieval corpora are tools that carry a `corpus_version`.
- **Strategy** covers orchestration and budget. The `n` that sampling params
  carry today belongs here.
  - Kinds: single call | self-consistency (k samples plus an aggregation
    step) | staged (differential first, then plan) | critique-and-revise
    (a number of rounds).
  - `budget`: maximum model calls, maximum tokens and maximum wall-clock
    time.
- **Agent**
  - Components: `model`, `inference`, `prompt`, `response_format`,
    `toolset`, `strategy`.
  - It has **no deployment**. The same recipe run on a 3090, a 5090 or a
    hosted API is still one agent.
  - Each agent yields a factor vector, for example:

    ```
    model.family=qwen3 model.params_b=8 model.quantization=awq-int4
    inference.reasoning=off inference.temperature=0.7
    prompt=ddx-v3 prompt.examples=0 prompt.case_framing=sectioned
    response.contract=management_plan@1 response.mode=native response.schema=rationale-first
    toolset=none strategy=single
    ```

### Evaluation assets

- **Case**
  - `presentation`: free text, or sections (complaint, history, vitals,
    exam, results).
  - `language`, `source` (dataset, original id, licence) and `setting`.
  - `stage`: triage | post-exam | post-results. This lets a study ask how
    early accurate answers appear.
  - `translation_of → Case` and `deidentified`.
- **Concept** is a shared vocabulary for diagnoses and actions, so results
  can be pooled by condition.
  - Fields: `system` (SNOMED CT | ICD-10 | local), `code`, `label`,
    `synonyms`.
  - A `local` concept is just a synonym set, so today's regex alternatives
    carry over directly.
- **Reference** is an answer key written by clinicians. A case may have one
  per rater.
  - Diagnoses: `final_diagnosis → Concept`, `acceptable → [Concept]`,
    `must_not_miss → [Concept]`.
  - `critical_actions`: each has a category (workup | treatment | consult |
    disposition), a concept or text, and a weight.
  - `harmful_actions`: each has a concept or text and a severity.
  - `disposition`.
  - Provenance: the authors, how disagreements were settled and the
    agreement measured, and the guideline the answers rest on, with its
    date.
  - A **Snapshot** is a separate record with no clinical meaning. It holds
    the exact output expected by a determinism or regression test.
- **Dataset** is a frozen, ordered list of `[(Case, Reference)]` pairs, with
  `splits` (dev | test).
  - Its version is a hash of its contents.
  - It is built from tags once, then frozen.
  - Prompts are tuned on dev; results are reported on test.
- **Grader** is a versioned measuring instrument.
  - `kind`: matcher | llm_judge | human.
  - Either an implementation (`impl` plus a code hash), or `judge → Agent`
    running on a pinned deployment with its rubric. The judge does not see
    which arm produced the output.
  - Declared `metrics`, each with a name, type, range, direction and the
    binding it reads.
  - `calibration`: agreement with clinicians on a labelled subset.
  - Standard metrics:
    - the rank of the final diagnosis, from which top-1, top-3, top-5 and
      MRR follow;
    - recall of must-not-miss diagnoses;
    - weighted recall of critical actions;
    - the number of harmful actions;
    - agreement on disposition;
    - whether the output satisfies the contract.

### Study design and results

- **Study**
  - The question, `dataset@version` plus the split, `graders`,
    `primary_metric`, `replicates` and `seed_policy`.
  - A `base → Agent` plus a `grid`, or an explicit list of arms. A grid maps
    factor paths to levels, as a full or fractional factorial design.
  - The allowed deployments, and the analysis plan.
- **Arm**: an (Agent, Deployment) pair, a snapshot of its `factors`, the
  factors this study `varied`, and its `effective_fingerprint`.
- **Trial** is one observation: (Arm, Case, replicate).
  - Run state: `seed`, `status`, and the queued, started and finished
    times.
  - The compiled `request`: the rendered messages, the parameters sent, the
    parameters dropped and why, and the schemas. It also stores the
    resulting `effective_fingerprint`.
  - `served_model`, as the server reported it.
  - Output: `output_text`; `output`, parsed and mapped onto the contract;
    `valid`; `attempts`.
  - `usage`: model calls; input, cached-input, output and reasoning tokens;
    tool calls.
  - `latency_ms`, `ttft_ms` (time to first token), `cost` and `error`.
  - The transcript, as a list of messages.
- **Score** maps (Trial, Grader, Reference, metric) to a `value`.
  - `detail` holds the matches or the judge's rationale.
  - `judge_trial → Trial`, so a judge's own cost is counted.
  - Grading an output again adds scores. It never generates the output
    again.
- **Derived views**, computed on demand rather than stored:
  - metrics per arm, with bootstrap confidence intervals clustered by case;
  - paired per-case differences between arms;
  - factor effects from a mixed model with case as a random effect;
  - the trade-off frontier between accuracy, latency and cost;
  - rates of invalid output and of errors.
- **The clinical product** keeps sessions and messages as its chat record.
  A `Release` names an (Agent, Deployment) pair promoted from a study.
  `/diagnose` selects a release, and credentials come from
  `Deployment.credential_ref`.

### Identity

- `compile(agent, deployment, case, seed) → EffectiveRequest` is pure and
  deterministic. It:
  - resolves defaults;
  - checks the request against `honours` and `Model.reasoning`;
  - renders the templates;
  - translates portable settings into each provider's own parameters,
    through pydantic-ai's unified `thinking` setting plus a small shim for
    vLLM's `chat_template_kwargs`.
- The **spec fingerprint** covers the recipe as authored.
  - It hashes canonical JSON that keeps key order wherever the model sees
    order: schema properties, examples, tools.
  - It leaves out names, owners, tags, endpoints and credentials, and takes
    in the code hashes of tools and graders.
  - Documents whose order matters are stored as `json` or text, not `jsonb`.
- The **effective fingerprint** is computed per arm. It is the hash of the
  effective request with the case left out. Two trials received the same
  treatment exactly when their effective fingerprints and their served
  models match.
- The **factor vector** is computed per arm. It is what analysis groups by
  and regresses on.

## Why these cuts

- **Reasoning effort** is the biggest single lever on accuracy, latency and
  cost for current models, and every serving setup takes it in a different
  form. So it is a first-class, portable field that `compile` translates per
  deployment.
- **Output format affects accuracy.** Format restrictions can degrade
  reasoning (Tam et al. 2024, "Let Me Speak Freely?"). Constrained decoders
  (OpenAI structured outputs, xgrammar or outlines under vLLM) emit keys in
  schema order, so whether the rationale comes before or after the answer is
  a real factor. So ResponseFormat is kept apart from the contract, and
  order is kept.
- **Sampling several answers and aggregating them** buys accuracy at k times
  the cost: self-consistency, and Medprompt's ensembling in medicine. So
  there is a strategy with a budget.
- **Management plans can't be scored by string matching.** Current practice
  is rubric grading by a model grader validated against physicians
  (HealthBench, 2025). So there are references with weighted actions,
  graders with calibration, and judges that are themselves pinned
  configurations.
- **Outputs vary from run to run** even with a fixed seed at temperature 0,
  because of batching. So replicates and the recorded served model are part
  of the design, not options.
- **API aliases change silently, and quantization shifts accuracy.** So a
  model carries its revision and quantization, and a deployment carries its
  hardware and pricing.

## Today against it

| Today | Verdict | Becomes |
|---|---|---|
| Connection: provider, model, endpoint, profile | split | Model (which weights) + Deployment (where it runs, engine, hardware, supported settings, pricing, credentials) |
| SamplingParams: temperature … n, logit_bias, provider_params | regroup | Inference with a first-class `reasoning`. `n` moves to Strategy. `provider_params` become declared, validated `overrides`. |
| OutputType: definition, coercion and validation strategies, retries | split | OutputContract (consumer schema plus bindings) + ResponseFormat (model-facing schema, mode, retries). `get_agents_endpoint` (`django/api.py`) already picks agents by `definition.title`, treating it as the contract. |
| Instruction: definition | extend | Prompt: system text, case framing and examples, with declared variables |
| ToolGroup (instructions, tools) + Tool | regroup | Toolset: tools with code hashes, a guidance slot and a policy |
| Agent: five foreign keys | the composition holds | An agent over six components, with no deployment, yielding a factor vector |
| Case: payload | extend | Case with presentation, language, source, stage and translation link |
| Expect: payload + scorer | split | Reference (clinical truth) + a grader chosen per study. Regression expectations become snapshots. |
| Scorer: command | extend | Grader with a versioned implementation or judge agent, declared metrics and calibration |
| Batch: one agent × case tags × scorers | replace | Study (frozen dataset, graders, replicates, grid) generating arms |
| Experiment (agent, case, expect) + Run (status, session, result) | regroup | Trial (the generation and what it cost) and Score (the grading), one trial to many scores |
| Session, Message | hold | The transcript store, written by trials and by chat alike |
| Trail and branch layer | holds | Same role. Canonicalization keeps order, and an effective fingerprint is added. |

## Where today falls short

### Fingerprints don't track behaviour

1. **Fingerprinted fields that never reach the model.**
   - `top_k` and `n`. `build_config` (`runtime/builder.py`) hands them on,
     but pydantic-ai's `OpenAIChatModel` (2.41, pinned in `uv.lock`) never
     sends `top_k`, and `n` is not a `ModelSettings` key at all.
   - `provider`. `build_model` always builds an `OpenAIChatModel` over an
     `OpenAIProvider`, and nothing at runtime reads the field.
   - `tool_group.instructions`. `build_agent` renders them only into an
     instruction that contains `{{ tool_group_instructions }}`, and no
     shipped inventory's does.
   - Tools whose type isn't `function`. `build_tools` skips them.
2. **Things that reach the model but not the fingerprint.**
   - **Schema key order.**
     - `generate_fingerprint` (`utils.py`) sorts keys.
     - `JSONSchemaField` (`core/django_fields.py`) is a plain `JSONField`,
       so Postgres stores it as `jsonb`, which keeps keys sorted by length,
       then by bytes.
     - `execute_run` reads the agent back from the database through
       `trail_cache`, so jsonb's order is what the model receives.
     - `data/output_types/ddx_management.json` is written `diagnosis,
       clinical_rationale, key_negatives, urgency, likelyhood`. It goes out
       as `urgency, diagnosis, likelyhood, key_negatives,
       clinical_rationale`, so the model commits to its answer before
       writing the reasoning for it.
     - `data/chatddx/output_types/management_plan_v1.toml` is already in
       jsonb order at every level, so its authored order was lost before it
       reached the repo.
   - Provider defaults behind every `null`. vLLM, for one, falls back to
     the model's own generation config.
   - Tool and scorer code. `command` names a function whose code is not
     versioned.
   - Model revision and quantization. Only a free-text model name is
     stored.
3. **Something in identity that isn't behaviour.** `endpoint` is part of
   `ConnectionTrailSchema`. Move `qwen3-8b` off `pelle.km` and every agent
   that uses it gets a new fingerprint.
4. **Components don't carry over between models.**
   - `disable-thinking` (`extra_body.chat_template_kwargs`, for Qwen on
     vLLM) and `low-reasoning` (`openai_reasoning_effort`) in
     `data/chatddx/lib.toml` express one setting in two provider formats.
     Paired with the other model, either does nothing, and still produces a
     new fingerprint.
   - The work-in-progress inspect test (`eval/tests/wip_inspect_ai_eval.py`)
     already notes that `reasoning_effort` "seems to have no effect".
   - Combining two sampling-params records is a shallow dict merge
     (`merge_entities`, `repo/parsers/inventory.py`), so their
     `provider_params` overwrite each other instead of combining.
   - pydantic-ai's unified `thinking` setting goes unused.
5. **Settings leak between components.**
   - `build_model` writes the output type's `coercion_strategy` into the
     connection's model profile.
   - Whether tool guidance reaches the model depends on the wording of the
     instruction.
   - `validate_output` under `INFORM` writes `__error__` into the output
     clients receive.

### Accuracy isn't measured validly

6. **The management plan is not scored.** Each of the 99 cases in
   `data/cases.toml` has exactly one expectation: a regex over the final
   diagnosis. Nothing covers workup, treatment, disposition or harm.
7. **Output mode is tangled up with the score.** `last_reply`
   (`eval/scorers.py`) reads `Message.content`, which takes only the
   `TextPart`s of the last assistant message. With `coercion_strategy =
   "tool"` the answer is a tool call, so the scorer never sees it, and such
   runs score 0 unless the model also wrote the diagnosis in prose.
8. **Matching is substring-based, with no word boundaries, over the whole
   output.** `_RowParser` compiles `re.escape(literal)`, so:
   - `uti` matches inside "solution" and "therapeutic";
   - `aki` matches inside "taking";
   - `gi & bleed` matches "imaging … bleeding".

   Longer outputs therefore score higher by chance. That favours verbose
   configurations, and management plans above all.
9. **The score has no rank.** `regex_match`'s `100 / line_number` ranks the
   synonym rows of the expectation, not positions in the model's
   differential. Every expectation has one row, so the score is always 0 or
   100. There is no top-k, no rank and no must-not-miss measure.
10. **References have no codes, no provenance and no specificity level.**
    - `openxddx-case_1` expects "acute kidney injury". The vignette (livedo,
      eosinophilia, spindle-shaped vacuoles on biopsy) describes cholesterol
      embolisation.
    - `data/chatddx/cases/expect_*.json` are snapshots of model output, which
      `runtime/tests/test_medical_assistant.py` compares for equality. They are not
      clinical truth, yet they share the "expect" name.
11. **The grader is fixed by the reference.** `score_run` takes the scorer
    from the expectation ("an experiment doesn't pick a scorer of its
    own"), and an experiment pairs agent × case × expect. Grading one
    output a second way means a new experiment and a new run, and so a new
    generation.

### Time and resources aren't recorded

12. **Runs have no resource columns.** `RunModel` has no latency, token,
    cost, call-count or retry columns. It doesn't store the model's output
    either, only the scorer's JSON in `result`. `Session.total_tokens` and
    `Session.processing_time` dig input and output tokens out of message
    JSON at display time.
13. **There is no deployment, hardware or pricing record.** "RTX 3090 vs
    5090 vs API" and "cost per correct plan" cannot be computed.
14. **Frontier models can't run through the pipeline.**
    - `execute_run` calls `run_from_session` without a key, so it falls back
      to `OPENAI_API_KEY`.
    - `swift_diagnose_endpoint` looks keys up by agent branch name.
    - Only OpenAI-compatible endpoints exist.

### The design can't ask "which parameter?"

15. **Factors live only in names**, such as `"gpt-oss-20b management_plan_v1
    seed-locked low-reasoning"` (`data/chatddx/medical-assistant.toml`). Hashes
    are opaque, so comparing two arms means diffing trees by hand.
16. **A `BatchModel` covers one agent.** There is no multi-arm object, no
    grid, no replicate count and no holdout. Re-queueing calls `generate`
    again, which duplicates the experiments.
17. **There is no frozen dataset.** `plan` resolves case tags against the
    owner's current canon each time a batch generates.
18. **There is no aggregate view.** Each run shows one JSON blob, with no
    confidence intervals and no paired comparisons.
19. **Running depends on naming.** `execute_run` fails unless the run's
    owner has a branch on the agent, because `SessionModel.default_agent`
    points at a branch. That is the kind of machine-facing reference
    `branch-identity-and-the-repo-registry.md` says belongs to a trail.
20. **Case framing and language can't be controlled.** The raw payload is
    sent as the user message. Most EDN cases are in Swedish and everything
    else is in English, with no field saying which.

## What holds

- **The content-addressed core.** Trails are immutable, and the database
  enforces it. Configurations are composed by reference, under the rule
  "trail pointers for machines, branch pointers for humans". This is the
  right foundation; only canonicalization needs fixing.
- **The branch layer**: names, owners, collaborators, tags and the closure
  invariant. It is the human-facing registry for every component above.
- **Experiments point at trails, not branches**, so they are reproducible by
  construction.
- **Full transcripts.** `MessageModel` keeps raw pydantic-ai payloads,
  including usage, model name, finish reason and thinking. That is enough to
  back-fill resource metrics.
- **The queue.** pgqueuer with conditional-update claims works, and running
  one trial at a time keeps latency measurements clean.
- **Batch's `plan`/`generate` split** already separates study design from
  execution. It is the seed of Study → Arm → Trial.
- **Declarative TOML inventories** with `extends` and `partial`.
  `sampling_params = [a, b]` is an early form of factor combination that a
  `grid` can generalize.
- **Instruction as its own entity**, from the latest refactor, points the
  right way for Prompt.
- **The adapter layer mostly exists already.** JSON Schema contracts, and in
  pydantic-ai the structured-output modes, the unified `thinking` setting,
  model profiles and usage accounting, cover most of what `compile` needs.
- **The case corpus**: three sources in two languages, with case tags as the
  starting point for datasets.

## Left open

- **Who writes references.** Structured references with weighted actions
  cost clinician time. The model allows one per rater and records agreement,
  but it cannot supply the raters.
- **The terminology.** SNOMED CT gives pooling and must-not-miss lists by
  code, while local synonym sets are cheaper to start with. `Concept` allows
  either.
- **The judge.** Which model grades management plans, and how many human
  ratings its calibration needs, is a study decision, not a schema one.
