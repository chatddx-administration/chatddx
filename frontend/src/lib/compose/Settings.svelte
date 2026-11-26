<script lang="ts">
  import * as NativeSelect from "$lib/components/ui/native-select";
  import type { Schemas } from "$lib/api/client";
  import { worded } from "$lib/kinds";
  import { t, tp, upFirst } from "$lib/locale";
  import { type Body, type Chunk, type Chunks } from "./drafting";
  import JsonField from "./JsonField.svelte";
  import type { Facts, ToolChoice } from "./props";

  let {
    chunks,
    model,
    models,
    facts,
    tools,
    toolChoices,
    set,
    pick,
  }: {
    chunks: Chunks;
    model: string | null;
    models: Schemas["Thread"][];
    facts: Record<string, Facts | null>;
    tools: Record<string, Body>;
    toolChoices: ToolChoice[];
    set: (part: Chunk, body: Body | null) => void;
    pick: (model: string) => void;
  } = $props();

  const THINKING: [string, () => string][] = [
    ["model", () => t("As the model does")],
    ["level", () => t("By level")],
    ["hand", () => t("By hand")],
  ];
  const LEVELS = ["default", "off", "on", "minimal", "low", "medium", "high", "xhigh"];
  const EFFORTS = ["none", "minimal", "low", "medium", "high"];
  const VALUES: [string, () => string, string][] = [
    ["temperature", () => t("temperature"), "0.01"],
    ["top_p", () => t("top p"), "0.01"],
    ["top_k", () => t("top k"), "1"],
    ["min_p", () => t("min p"), "0.01"],
    ["presence_penalty", () => t("presence penalty"), "0.01"],
    ["frequency_penalty", () => t("frequency penalty"), "0.01"],
    ["repetition_penalty", () => t("repetition penalty"), "0.01"],
  ];
  const ANSWERS: [string, () => string, () => string][] = [
    ["native", () => t("JSON"), () => t("Held to its schema by the engine, as response_format.")],
    ["tool", () => t("A tool call"), () => t("A call to an answer tool, its parameters the schema.")],
    [
      "text",
      () => upFirst(tp("an output", "text")),
      () => t("As the model writes it; JSON read out of it if it has a schema."),
    ],
  ];

  const known = $derived(model === null ? null : (facts[model] ?? null));
  const sampling = $derived(chunks.sampling ?? { kind: "chunk.sampling" });
  const output = $derived(chunks.output ?? { kind: "chunk.output", contract: { kind: "text" } });
  const contract = $derived((output.contract ?? { kind: "text" }) as Record<string, unknown>);
  const reasoning = $derived(chunks.reasoning);
  const thinking = $derived(reasoning === null ? "model" : reasoning.level != null ? "level" : "hand");
  // Dependency: src/chatddx/factors/request.py:landings follows the level reasoning lands at, or else the default.
  const followed = $derived(
    known?.levels[String(reasoning?.level ?? "default")]?.lands ?? known?.levels.default?.lands ?? null,
  );
  const recommended = $derived(
    sampling.recommended && followed !== null ? (known?.recommended[followed] ?? null) : null,
  );
  const held = $derived(((chunks.toolset?.tools as string[] | undefined) ?? []).filter((d) => d));
  const left = $derived(toolChoices.filter((c) => !held.includes(c.digest)));

  function with_(body: Body, name: string, value: unknown): Body {
    const { [name]: _, ...rest } = body;
    return value === undefined || value === null || value === "" ? rest : { ...rest, [name]: value };
  }

  function number(text: string, whole: boolean): number | undefined {
    if (text.trim() === "") return undefined;
    const n = whole ? Number.parseInt(text, 10) : Number.parseFloat(text);
    return Number.isNaN(n) ? undefined : n;
  }

  function answer(kind: string): void {
    const schema = output.json_schema ?? (kind === "text" ? undefined : { type: "object" });
    const shaped =
      kind === "tool" ? { kind, name: typeof contract.name === "string" ? contract.name : "answer" } : { kind };
    set("output", with_({ ...output, contract: shaped }, "json_schema", schema));
  }

  function think(mode: string): void {
    if (mode === "model") return set("reasoning", null);
    const budget = reasoning?.thinking_token_budget;
    const base = with_({ kind: "chunk.reasoning" }, "thinking_token_budget", budget);
    set("reasoning", mode === "level" ? { ...base, level: "default" } : base);
  }

  function landing(level: string): string {
    if (known === null) return t("No facts are known about the model: a level can't be worked out.");
    const at = known.levels[level];
    if (!at) return "";
    if (at.refused) return at.refused;
    return at.lands === level ? "" : t("Lands at %(level)s.", { level: String(at.lands) });
  }

  function refused(kind: string): string | undefined {
    return known?.output[kind]?.refused;
  }

  function tooled(digests: string[]): void {
    if (!digests.length) return set("toolset", null);
    set("toolset", { ...(chunks.toolset ?? { kind: "chunk.toolset" }), tools: digests });
  }

  function toolName(digest: string): string {
    return toolChoices.find((c) => c.digest === digest)?.name ?? String(tools[digest]?.name ?? digest);
  }

  function toolAbout(digest: string): string {
    return toolChoices.find((c) => c.digest === digest)?.description ?? String(tools[digest]?.description ?? "");
  }
</script>

<section class="mb-6 border-t border-border/60 pt-4" aria-label={t("Its settings")}>
  <div class="space-y-6 text-sm">
    <fieldset>
      <legend class="mb-2 font-medium">{worded("model")}</legend>
      <NativeSelect.Root
        size="sm"
        value={model ?? ""}
        aria-label={worded("model")}
        onchange={(e) => pick(e.currentTarget.value)}
      >
        {#if model === null}<NativeSelect.Option value="">—</NativeSelect.Option>{/if}
        {#each models as m (m.id)}
          <NativeSelect.Option value={m.head.digest}>{m.name ?? m.title}</NativeSelect.Option>
        {/each}
      </NativeSelect.Root>
      {#if known === null}
        <p class="mt-1 text-xs text-muted-foreground">
          {t("No facts are known about it, so a thinking level and recommended sampling can't be worked out.")}
        </p>
      {/if}
    </fieldset>

    <fieldset>
      <legend class="mb-2 font-medium">{upFirst(t("the answer"))}</legend>
      <div class="grid gap-2 @xl:grid-cols-3">
        {#each ANSWERS as [kind, name, about] (kind)}
          {@const no = refused(kind)}
          <label
            class="grid cursor-pointer gap-0.5 rounded-lg border p-3 {contract.kind === kind
              ? 'border-primary bg-primary/5'
              : 'border-border/60'} {no ? 'opacity-60' : ''}"
          >
            <span class="flex items-center gap-2 font-medium">
              <input
                type="radio"
                name="answer"
                value={kind}
                checked={contract.kind === kind}
                onchange={() => answer(kind)}
              />
              {name()}
              {#if known?.answers === kind}<span class="text-xs font-normal text-muted-foreground"
                  >{t("its default")}</span
                >{/if}
            </span>
            <span class="text-xs text-muted-foreground">{about()}</span>
            {#if no}<span class="text-xs text-warning">{no}</span>{/if}
            {#if known?.output[kind]?.note}<span class="text-xs text-muted-foreground">{known.output[kind]?.note}</span
              >{/if}
          </label>
        {/each}
      </div>
      {#if contract.kind === "tool"}
        <div class="mt-3 grid gap-2 @xl:grid-cols-2">
          <label class="grid gap-1">
            <span class="text-xs text-muted-foreground">{t("The answer tool's name")}</span>
            <input
              class="h-8 w-full min-w-0 rounded-md border border-input bg-transparent px-2"
              value={String(contract.name ?? "")}
              oninput={(e) => set("output", { ...output, contract: { ...contract, name: e.currentTarget.value } })}
            />
          </label>
          <label class="grid gap-1">
            <span class="text-xs text-muted-foreground">{t("Its description")}</span>
            <input
              class="h-8 w-full min-w-0 rounded-md border border-input bg-transparent px-2"
              value={String(contract.description ?? "")}
              oninput={(e) =>
                set("output", { ...output, contract: with_(contract, "description", e.currentTarget.value) })}
            />
          </label>
        </div>
      {/if}
      {#if contract.kind === "text"}
        <label class="mt-3 flex items-center gap-2">
          <input
            type="checkbox"
            checked={output.json_schema != null}
            onchange={(e) =>
              set("output", with_(output, "json_schema", e.currentTarget.checked ? { type: "object" } : undefined))}
          />
          {t("Read JSON out of the answer, checked against a schema")}
        </label>
      {/if}
      {#if output.json_schema != null}
        <div class="mt-3">
          <p class="mb-1 text-xs text-muted-foreground">{upFirst(t("the answer's schema"))}</p>
          <JsonField
            value={output.json_schema}
            label={upFirst(t("the answer's schema"))}
            rows={8}
            set={(v) => set("output", { ...output, json_schema: v })}
          />
        </div>
      {/if}
    </fieldset>

    <fieldset>
      <legend class="mb-2 font-medium">{t("Thinking")}</legend>
      <div class="flex flex-wrap gap-x-4 gap-y-1">
        {#each THINKING as [mode, name] (mode)}
          <label class="flex items-center gap-1.5">
            <input type="radio" name="thinking" checked={thinking === mode} onchange={() => think(mode)} />
            {name()}
          </label>
        {/each}
      </div>
      {#if reasoning}
        <div class="mt-3 grid gap-3 @xl:grid-cols-2">
          {#if thinking === "level"}
            <label class="grid gap-1">
              <span class="text-xs text-muted-foreground">{t("Level")}</span>
              <NativeSelect.Root
                size="sm"
                value={String(reasoning.level)}
                onchange={(e) => set("reasoning", { ...reasoning, level: e.currentTarget.value })}
              >
                {#each LEVELS as level (level)}
                  <NativeSelect.Option value={level}
                    >{level === "default" ? t("its default") : level}</NativeSelect.Option
                  >
                {/each}
              </NativeSelect.Root>
              {#if landing(String(reasoning.level))}<span class="text-xs text-muted-foreground"
                  >{landing(String(reasoning.level))}</span
                >{/if}
            </label>
          {:else}
            <label class="grid gap-1">
              <span class="text-xs text-muted-foreground">{t("Effort")}</span>
              <NativeSelect.Root
                size="sm"
                value={String(reasoning.effort ?? "")}
                onchange={(e) => set("reasoning", with_(reasoning, "effort", e.currentTarget.value))}
              >
                <NativeSelect.Option value="">—</NativeSelect.Option>
                {#each EFFORTS as effort (effort)}
                  <NativeSelect.Option value={effort}>{effort}</NativeSelect.Option>
                {/each}
              </NativeSelect.Root>
            </label>
            <div class="grid gap-1">
              <span class="text-xs text-muted-foreground">{t("Chat template arguments")}</span>
              <JsonField
                value={reasoning.chat_template_kwargs ?? {}}
                label={t("Chat template arguments")}
                rows={2}
                set={(v) =>
                  set(
                    "reasoning",
                    with_(reasoning, "chat_template_kwargs", v && Object.keys(v as object).length ? v : undefined),
                  )}
              />
            </div>
          {/if}
          <!-- Policy: a budget the model's facts refuse is offered only to be taken out, as it compiles to nothing else. -->
          {#if typeof known?.budget !== "string" || reasoning.thinking_token_budget != null}
            <label class="grid gap-1">
              <span class="text-xs text-muted-foreground">{t("Thinking token budget")}</span>
              <input
                type="number"
                min="0"
                class="h-8 w-full min-w-0 rounded-md border border-input bg-transparent px-2"
                value={reasoning.thinking_token_budget ?? ""}
                oninput={(e) =>
                  set("reasoning", with_(reasoning, "thinking_token_budget", number(e.currentTarget.value, true)))}
              />
              {#if typeof known?.budget === "string"}<span class="text-xs text-warning">{known.budget}</span>{/if}
            </label>
          {/if}
        </div>
      {/if}
    </fieldset>

    <fieldset>
      <legend class="mb-2 font-medium">{upFirst(t("sampling"))}</legend>
      <label class="flex items-center gap-2">
        <input
          type="checkbox"
          checked={sampling.recommended === true}
          disabled={!sampling.recommended && !Object.keys(known?.recommended ?? {}).length}
          onchange={(e) => set("sampling", with_(sampling, "recommended", e.currentTarget.checked || undefined))}
        />
        {t("Recommended for its thinking level")}
        {#if sampling.recommended && followed}<span class="text-xs text-muted-foreground">({followed})</span>{/if}
      </label>
      <p class="mt-1 mb-3 text-xs text-muted-foreground">
        {sampling.recommended
          ? t("A value given here is used in place of the one recommended.")
          : t("A value left out is the engine's.")}
      </p>
      <div class="grid grid-cols-2 gap-2 @xl:grid-cols-4">
        {#each VALUES as [name, label, step] (name)}
          <label class="grid gap-1">
            <span class="text-xs text-muted-foreground">{label()}</span>
            <input
              type="number"
              {step}
              class="h-8 w-full min-w-0 rounded-md border border-input bg-transparent px-2"
              aria-label={name}
              placeholder={recommended?.[name] != null ? String(recommended[name]) : ""}
              value={sampling[name] ?? ""}
              oninput={(e) => set("sampling", with_(sampling, name, number(e.currentTarget.value, name === "top_k")))}
            />
          </label>
        {/each}
        <label class="grid gap-1">
          <span class="text-xs text-muted-foreground">{t("max output tokens")}</span>
          <input
            type="number"
            min="1"
            class="h-8 w-full min-w-0 rounded-md border border-input bg-transparent px-2"
            value={sampling.max_output_tokens ?? ""}
            oninput={(e) => set("sampling", with_(sampling, "max_output_tokens", number(e.currentTarget.value, true)))}
          />
        </label>
      </div>
      <div class="mt-3">
        <p class="mb-1 text-xs text-muted-foreground">{t("Stop sequences")}</p>
        {#each (sampling.stop as string[] | undefined) ?? [] as stop, i (i)}
          <div class="mb-1 flex items-start gap-2">
            <textarea
              class="w-full rounded-md border border-input bg-transparent px-2 py-1 font-mono text-xs [field-sizing:content]"
              rows="1"
              aria-label={t("Stop sequence %(n)s", { n: i + 1 })}
              value={stop}
              oninput={(e) =>
                set("sampling", {
                  ...sampling,
                  stop: ((sampling.stop as string[]) ?? []).map((s, j) => (j === i ? e.currentTarget.value : s)),
                })}></textarea>
            <button
              type="button"
              class="rounded-md px-1.5 text-muted-foreground hover:bg-muted"
              aria-label={t("Leave out stop sequence %(n)s", { n: i + 1 })}
              onclick={() => {
                const kept = ((sampling.stop as string[]) ?? []).filter((_, j) => j !== i);
                set("sampling", with_(sampling, "stop", kept.length ? kept : undefined));
              }}>×</button
            >
          </div>
        {/each}
        <button
          type="button"
          class="text-xs"
          onclick={() => set("sampling", { ...sampling, stop: [...((sampling.stop as string[]) ?? []), ""] })}
          >+ {t("stop sequence")}</button
        >
      </div>
    </fieldset>

    {#if chunks.toolset || toolChoices.length}
      <fieldset>
        <legend class="mb-2 font-medium">{t("Tools")}</legend>
        <ul class="space-y-1">
          {#each held as digest (digest)}
            <li class="flex items-start gap-2">
              <div class="min-w-0 flex-1">
                <p class="font-medium">{toolName(digest)}</p>
                <p class="text-xs text-muted-foreground">{toolAbout(digest)}</p>
              </div>
              <button
                type="button"
                class="rounded-md px-1.5 text-muted-foreground hover:bg-muted"
                aria-label={t("Leave out %(name)s", { name: toolName(digest) })}
                onclick={() => tooled(held.filter((d) => d !== digest))}>×</button
              >
            </li>
          {/each}
        </ul>
        {#if left.length}
          <NativeSelect.Root
            size="sm"
            value=""
            aria-label={t("Add a tool")}
            onchange={(e) => {
              if (e.currentTarget.value) tooled([...held, e.currentTarget.value]);
            }}
          >
            <NativeSelect.Option value="">{t("Add a tool")}</NativeSelect.Option>
            {#each left as c (c.digest)}
              <NativeSelect.Option value={c.digest}>{c.name}</NativeSelect.Option>
            {/each}
          </NativeSelect.Root>
        {/if}
        {#if chunks.toolset}
          <label class="mt-2 grid max-w-48 gap-1">
            <span class="text-xs text-muted-foreground">{t("Rounds of calls at most")}</span>
            <input
              type="number"
              min="1"
              placeholder="5"
              class="h-8 w-full min-w-0 rounded-md border border-input bg-transparent px-2"
              value={chunks.toolset.max_rounds ?? ""}
              oninput={(e) => {
                if (chunks.toolset)
                  set("toolset", with_(chunks.toolset, "max_rounds", number(e.currentTarget.value, true)));
              }}
            />
          </label>
        {/if}
      </fieldset>
    {/if}

    <details class="rounded-md border border-border/60">
      <summary class="cursor-pointer px-3 py-2 font-medium">{t("Advanced")}</summary>
      <div class="space-y-4 border-t border-border/60 p-3">
        <div>
          <p class="mb-1 font-medium">{worded("passthrough")}</p>
          <p class="mb-1 text-xs text-muted-foreground">
            {t("Further keys of the request, as they are sent; the keys the rest sets are refused.")}
          </p>
          {#if chunks.passthrough}
            {@const passthrough = chunks.passthrough}
            <div class="flex items-start gap-2">
              <div class="min-w-0 flex-1">
                <JsonField
                  value={passthrough.body ?? {}}
                  label={worded("passthrough")}
                  set={(v) => set("passthrough", { ...passthrough, body: v })}
                />
              </div>
              <button
                type="button"
                class="rounded-md px-1.5 text-muted-foreground hover:bg-muted"
                aria-label={t("Leave out %(name)s", { name: worded("passthrough") })}
                onclick={() => set("passthrough", null)}>×</button
              >
            </div>
          {:else}
            <button
              type="button"
              class="text-xs"
              onclick={() => set("passthrough", { kind: "chunk.passthrough", body: {} })}
              >+ {worded("passthrough")}</button
            >
          {/if}
        </div>
        <label class="grid max-w-md gap-1">
          <span class="font-medium">{t("The key for max output tokens")}</span>
          <span class="text-xs text-muted-foreground">{t("The one the engine's API takes.")}</span>
          <NativeSelect.Root
            size="sm"
            value={String(sampling.max_tokens_key ?? "max_completion_tokens")}
            onchange={(e) =>
              set(
                "sampling",
                with_(
                  sampling,
                  "max_tokens_key",
                  e.currentTarget.value === "max_completion_tokens" ? undefined : e.currentTarget.value,
                ),
              )}
          >
            <NativeSelect.Option value="max_completion_tokens">max_completion_tokens</NativeSelect.Option>
            <NativeSelect.Option value="max_tokens">max_tokens</NativeSelect.Option>
          </NativeSelect.Root>
        </label>
        {#if output.json_schema != null}
          <label class="flex items-start gap-2">
            <input
              type="checkbox"
              checked={((output.schema_ops as string[] | undefined) ?? []).includes("inline_refs@1")}
              onchange={(e) =>
                set("output", with_(output, "schema_ops", e.currentTarget.checked ? ["inline_refs@1"] : undefined))}
            />
            <span>
              {t("Inline the schema's references")}
              <span class="block text-xs text-muted-foreground"
                >{t("Its $refs replaced by what they point at before it is sent (inline_refs@1).")}</span
              >
            </span>
          </label>
        {/if}
      </div>
    </details>
  </div>
</section>
