<script lang="ts">
  import { worded } from "$lib/kinds";
  import { displayLanguage, t, upFirst } from "$lib/locale";
  import SchemaField from "$lib/schema/SchemaField.svelte";
  import TextSegments from "$lib/scorer/TextSegments.svelte";
  import { merged, type Seg, segmentsOf, textOf } from "$lib/scorer/texts";
  import {
    blank,
    type Body,
    type Chunk,
    type Chunks,
    counted,
    type Drafted,
    type Into,
    messagesOf,
    offered,
    paired,
    type Stale,
    TEXTS,
  } from "./drafting";
  import Paired from "./Paired.svelte";
  import Said from "./Said.svelte";

  let {
    chunks,
    settled,
    drafted,
    language,
    into,
    texts,
    stale,
    waiting,
    tab = $bindable(),
    set,
    translate,
    settle,
    dropped,
  }: {
    chunks: Chunks;
    settled: Chunks;
    drafted: Drafted;
    language: string | null;
    into: Into;
    texts: Record<string, string[]>;
    stale: Stale;
    waiting: boolean;
    tab: string | null;
    set: (part: Chunk, body: Body | null) => void;
    translate: (language: string, text: string, said: string) => void;
    settle: (language: string, text: string) => void;
    dropped: (language: string) => void;
  } = $props();

  const languages = $derived(Object.keys(into).sort());
  const shown = $derived(tab !== null && tab in into ? tab : null);
  // Policy: what is listed rather than paired follows the texts the server last said, so that a text being typed
  // doesn't move between the two meanwhile.
  const pairedNow = $derived(paired(settled));
  const listed = $derived(
    Object.fromEntries(
      TEXTS.map((p) => [p, [...new Set((texts[p] ?? []).filter((k) => !pairedNow.has(k)))]] as const),
    ) as Record<(typeof TEXTS)[number], string[]>,
  );
  const structured = $derived([...new Set([...listed.output, ...listed.toolset])]);
  const elsewhere = $derived(TEXTS.filter((p) => p !== "output" && p !== "toolset" && listed[p].length));

  function partName(part: string): string {
    return part === "appendix_layout" ? t("How appendices are laid out") : worded(part);
  }

  function also(text: string, part: string): string[] {
    return TEXTS.filter((p) => p !== part && texts[p]?.includes(text)).map(partName);
  }

  function value(language: string, text: string, then: string | null): string {
    const entries = into[language] ?? {};
    return entries[text] ?? (waiting && then !== null ? entries[then] : undefined) ?? "";
  }

  function was(part: Chunk, name: string): Seg[] {
    return segmentsOf(settled[part]?.[name] ?? "");
  }

  function message(index: number, content: string): void {
    const held = chunks.few_shot;
    if (!held) return;
    const messages = messagesOf(held).map((m, i) => (i === index ? { ...m, content } : m));
    set("few_shot", { ...held, messages });
  }

  function shownJson(value: unknown): string {
    return JSON.stringify(value, null, 2);
  }

  function field(part: Chunk, name: string, value: unknown): void {
    const held = chunks[part];
    if (held) set(part, { ...held, [name]: value });
  }

  function segs(part: Chunk, name: string): Seg[] {
    return segmentsOf(chunks[part]?.[name] ?? "");
  }

  function guidance(part: Chunk, given: Seg[]): void {
    const text = textOf(given);
    field(part, "guidance", text === "" ? null : text);
  }
</script>

<section class="mb-6 border-t border-border/60 pt-4" aria-label={t("Its texts")}>
  <nav class="mb-4 flex flex-wrap items-center gap-1 border-b border-border/60 text-sm" aria-label={t("Languages")}>
    <button
      type="button"
      class="-mb-px border-b-2 px-3 py-1.5 {shown === null ? 'border-primary font-medium' : 'border-transparent'}"
      aria-current={shown === null ? "page" : undefined}
      onclick={() => (tab = null)}>{language ? displayLanguage(language) : t("As written")}</button
    >
    {#each languages as l (l)}
      {@const [done, all] = counted(texts, into[l] ?? {})}
      {@const looked = stale[l]?.length ?? 0}
      <button
        type="button"
        class="-mb-px border-b-2 px-3 py-1.5 {shown === l ? 'border-primary font-medium' : 'border-transparent'}"
        aria-current={shown === l ? "page" : undefined}
        onclick={() => (tab = l)}
        >{displayLanguage(l)}{#if done < all}<span
            class="ml-1 inline-block size-1.5 rounded-full bg-destructive align-super"
            aria-hidden="true"
          ></span>{/if}
        <span class="text-xs text-muted-foreground"
          >{done}/{all}{#if looked}, <span class="text-warning">{t("%(n)s to look over", { n: looked })}</span
            >{/if}</span
        ></button
      >
    {/each}
  </nav>

  {#if shown === null}
    <div class="space-y-5 text-sm">
      <div>
        <h3 class="mb-1.5 font-medium">{worded("instructions")}</h3>
        {#if chunks.instructions}
          <div class="flex items-start gap-2">
            <div class="min-w-0 flex-1">
              <TextSegments
                segs={segs("instructions", "text")}
                set={(s) => field("instructions", "text", textOf(s))}
                inserts={offered("instructions", chunks, drafted.inserts.instructions ?? [])}
                label={worded("instructions")}
                quiet
              />
            </div>
            <button
              type="button"
              class="rounded-md px-1.5 text-muted-foreground hover:bg-muted"
              aria-label={t("Leave out %(name)s", { name: worded("instructions") })}
              onclick={() => set("instructions", null)}>×</button
            >
          </div>
        {:else}
          <button type="button" class="text-xs" onclick={() => set("instructions", blank("instructions"))}
            >+ {worded("instructions")}</button
          >
        {/if}
      </div>

      <div>
        <h3 class="mb-1.5 font-medium">{worded("few_shot")}</h3>
        {#if chunks.few_shot}
          <div class="flex items-start gap-2">
            <div class="min-w-0 flex-1">
              <SchemaField
                schema={drafted.schemas.few_shot}
                root={drafted.schemas.few_shot}
                value={chunks.few_shot}
                set={(v) => set("few_shot", v as Body)}
                hidden={["kind"]}
                framed={false}
                quiet
              />
            </div>
            <button
              type="button"
              class="rounded-md px-1.5 text-muted-foreground hover:bg-muted"
              aria-label={t("Leave out %(name)s", { name: worded("few_shot") })}
              onclick={() => set("few_shot", null)}>×</button
            >
          </div>
        {:else}
          <button type="button" class="text-xs" onclick={() => set("few_shot", blank("few_shot"))}
            >+ {worded("few_shot")}</button
          >
        {/if}
      </div>

      <div>
        <h3 class="mb-1.5 font-medium">{worded("prompt")}</h3>
        {#if chunks.prompt}
          <TextSegments
            segs={segs("prompt", "segments")}
            set={(s) => field("prompt", "segments", merged(s))}
            slots={drafted.slots[String(chunks.prompt.purpose ?? "generation")] ?? []}
            inserts={offered("prompt", chunks, drafted.inserts.prompt ?? [])}
            label={worded("prompt")}
            quiet
          />
        {/if}
      </div>

      {#if chunks.output}
        <div>
          <h3 class="mb-1.5 font-medium">{t("Output guidance")}</h3>
          <TextSegments
            segs={segs("output", "guidance")}
            set={(s) => guidance("output", s)}
            inserts={offered("output", chunks, drafted.inserts.output ?? [])}
            label={t("Output guidance")}
            quiet
          />
        </div>
      {/if}

      {#if chunks.toolset}
        <div>
          <h3 class="mb-1.5 font-medium">{t("Tool guidance")}</h3>
          <textarea
            class="w-full rounded-md border border-input bg-transparent px-2 py-1 [field-sizing:content]"
            rows="1"
            aria-label={t("Tool guidance")}
            value={String(chunks.toolset.guidance ?? "")}
            oninput={(e) => field("toolset", "guidance", e.currentTarget.value || null)}></textarea>
        </div>
      {/if}
    </div>
  {:else}
    {@const l = shown}
    {#snippet entry(part: string, text: string, then: string | null)}
      <Said
        language={l}
        {text}
        value={value(l, text, then)}
        {waiting}
        stale={stale[l]?.includes(text) ?? false}
        also={also(text, part)}
        {translate}
        {settle}
      />
    {/snippet}
    <div class="space-y-5 text-sm">
      <p class="hidden grid-cols-2 gap-2 text-xs text-muted-foreground @3xl:grid" aria-hidden="true">
        <span>{language ? displayLanguage(language) : t("As written")}</span><span>{displayLanguage(l)}</span>
      </p>

      {#if chunks.instructions}
        <div>
          <h3 class="mb-1.5 font-medium">{worded("instructions")}</h3>
          <Paired
            segs={segs("instructions", "text")}
            was={was("instructions", "text")}
            set={(s) => field("instructions", "text", textOf(s))}
            label={worded("instructions")}
          >
            {#snippet said(text: string, then: string | null)}{@render entry("instructions", text, then)}{/snippet}
          </Paired>
        </div>
      {/if}

      {#if chunks.few_shot}
        {@const before = messagesOf(settled.few_shot)}
        <div>
          <h3 class="mb-1.5 font-medium">{worded("few_shot")}</h3>
          <ol class="space-y-2">
            {#each messagesOf(chunks.few_shot) as m, i (i)}
              <li class="grid gap-2 @3xl:grid-cols-2">
                <label class="grid gap-0.5">
                  <span class="text-xs text-muted-foreground">{m.role}</span>
                  <textarea
                    class="w-full rounded-md border border-input bg-transparent px-2 py-1 [field-sizing:content]"
                    rows="1"
                    aria-label={t("%(label)s, message %(n)s", { label: worded("few_shot"), n: i + 1 })}
                    value={m.content}
                    oninput={(e) => message(i, e.currentTarget.value)}></textarea>
                </label>
                {#if m.content.trim()}
                  <div class="@3xl:pt-4">{@render entry("few_shot", m.content, before[i]?.content ?? null)}</div>
                {/if}
              </li>
            {/each}
          </ol>
        </div>
      {/if}

      {#if chunks.prompt}
        <div>
          <h3 class="mb-1.5 font-medium">{worded("prompt")}</h3>
          <Paired
            segs={segs("prompt", "segments")}
            was={was("prompt", "segments")}
            set={(s) => field("prompt", "segments", merged(s))}
            label={worded("prompt")}
          >
            {#snippet said(text: string, then: string | null)}{@render entry("prompt", text, then)}{/snippet}
          </Paired>
        </div>
      {/if}

      {#if chunks.output && chunks.output.guidance != null}
        <div>
          <h3 class="mb-1.5 font-medium">{t("Output guidance")}</h3>
          <Paired
            segs={segs("output", "guidance")}
            was={was("output", "guidance")}
            set={(s) => guidance("output", s)}
            label={t("Output guidance")}
          >
            {#snippet said(text: string, then: string | null)}{@render entry("output", text, then)}{/snippet}
          </Paired>
        </div>
      {/if}

      {#if chunks.toolset && chunks.toolset.guidance != null}
        {@const text = String(chunks.toolset.guidance)}
        {@const then = settled.toolset?.guidance}
        <div>
          <h3 class="mb-1.5 font-medium">{t("Tool guidance")}</h3>
          <div class="grid gap-2 @3xl:grid-cols-2">
            <textarea
              class="w-full rounded-md border border-input bg-transparent px-2 py-1 [field-sizing:content]"
              rows="1"
              aria-label={t("Tool guidance")}
              value={text}
              oninput={(e) => field("toolset", "guidance", e.currentTarget.value || null)}></textarea>
            {#if text.trim()}{@render entry("toolset", text, typeof then === "string" ? then : null)}{/if}
          </div>
        </div>
      {/if}

      {#if structured.length}
        {@const [done, all] = counted({ all: structured }, into[l] ?? {})}
        <details class="rounded-md border border-border/60">
          <summary class="cursor-pointer px-3 py-2 font-medium"
            >{t("Schemas and tools")} <span class="text-xs text-muted-foreground">{done}/{all}</span></summary
          >
          <div class="grid gap-4 border-t border-border/60 p-3 lg:grid-cols-2">
            <div class="min-w-0 space-y-3">
              {#if chunks.output?.json_schema}
                <div>
                  <h4 class="mb-1 text-xs text-muted-foreground">{upFirst(t("the answer's schema"))}</h4>
                  <pre class="max-h-[60vh] overflow-auto rounded-md bg-muted/40 p-2 text-xs">{shownJson(
                      chunks.output.json_schema,
                    )}</pre>
                </div>
              {/if}
              {#each (chunks.toolset?.tools as string[] | undefined) ?? [] as digest (digest)}
                {@const tool = drafted.tools[digest]}
                {#if tool}
                  <div>
                    <h4 class="mb-1 text-xs text-muted-foreground">{String(tool.name ?? digest)}</h4>
                    <pre class="max-h-[60vh] overflow-auto rounded-md bg-muted/40 p-2 text-xs">{shownJson({
                        description: tool.description,
                        parameters: tool.parameters,
                      })}</pre>
                  </div>
                {/if}
              {/each}
            </div>
            <ol class="min-w-0 space-y-3">
              {#each structured as text (text)}
                <li class="grid gap-1">
                  <p class="whitespace-pre-wrap rounded-md bg-muted/40 px-2 py-1 text-muted-foreground">{text}</p>
                  {@render entry(listed.output.includes(text) ? "output" : "toolset", text, null)}
                </li>
              {/each}
            </ol>
          </div>
        </details>
      {/if}

      {#each elsewhere as part (part)}
        <div>
          <h3 class="mb-1.5 font-medium">{partName(part)}</h3>
          <ol class="space-y-3">
            {#each listed[part] as text (text)}
              <li class="grid gap-2 @3xl:grid-cols-2">
                <p class="whitespace-pre-wrap rounded-md bg-muted/40 px-2 py-1 text-muted-foreground">{text}</p>
                {@render entry(part, text, null)}
              </li>
            {/each}
          </ol>
        </div>
      {/each}

      {#if !Object.values(texts).some((found) => found.length)}
        <p class="text-muted-foreground">{t("Nothing to translate.")}</p>
      {/if}
      <button type="button" class="text-xs" onclick={() => dropped(l)}
        >{t("Translate it into %(language)s no more", { language: displayLanguage(l) })}</button
      >
    </div>
  {/if}
</section>
