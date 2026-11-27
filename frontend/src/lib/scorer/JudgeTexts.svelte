<script lang="ts" module>
  import type { JudgeChoice } from "./judging";
  import type { Texts } from "./rewriting";

  export type Rewriting = JudgeChoice & { texts: Texts; body: Record<string, unknown>; head: number };
</script>

<script lang="ts">
  import { untrack } from "svelte";
  import { api } from "$lib/api/client";
  import Findings from "$lib/editors/Findings.svelte";
  import { type Checked, checked, type Component } from "$lib/editors/writing";
  import { displayList, t, upFirst } from "$lib/locale";
  import { type Part, rewritten } from "./rewriting";
  import TextSegments from "./TextSegments.svelte";
  import { asked, type Seg, segmentsOf, textOf } from "./texts";

  let {
    judge,
    expectation,
    data,
    me,
    made,
    left,
  }: {
    judge: Rewriting;
    expectation: string;
    data: unknown;
    me: string;
    made: (judge: Rewriting) => void;
    left: () => void;
  } = $props();
  const given = untrack(() => judge);
  const parts = given.texts.parts;
  const judgeSlots = ["completion", "expectation"];
  const guiding = ["output_guidance", "tool_guidance"];

  let instructions = $state<Seg[]>(segmentsOf(parts.instructions?.body.text));
  let prompt = $state<Seg[]>(segmentsOf(parts.prompt?.body.segments));
  let guidance = $state<Seg[]>(segmentsOf(parts.output?.body.guidance ?? ""));
  let picked = $state<unknown[] | null>(null);
  let found = $state<Partial<Record<Part, Checked>>>({});
  let problem = $state<string | null>(null);
  let busy = $state(false);
  let picking = 0;
  let checking = 0;

  const preview = $derived(
    asked(
      parts.instructions ? { role: String(parts.instructions.body.role ?? "system"), segs: instructions } : null,
      prompt,
      parts.output ? guidance : null,
      picked,
    ),
  );

  function bodies(): Partial<Record<Part, Record<string, unknown>>> {
    const out: Partial<Record<Part, Record<string, unknown>>> = {};
    const now: Record<Part, Record<string, unknown> | null> = {
      instructions: parts.instructions ? { ...parts.instructions.body, text: textOf(instructions) } : null,
      prompt: parts.prompt ? { ...parts.prompt.body, segments: textOf(prompt) } : null,
      output: parts.output
        ? { ...parts.output.body, guidance: textOf(guidance) === "" ? null : textOf(guidance) }
        : null,
    };
    for (const part of ["instructions", "prompt", "output"] as Part[]) {
      const body = now[part];
      const was = parts[part]?.body;
      if (body && JSON.stringify(body) !== JSON.stringify(was)) out[part] = body;
    }
    if (out.prompt && !Array.isArray(out.prompt.segments)) out.prompt.segments = [out.prompt.segments];
    return out;
  }

  const changed = $derived.by(() => {
    void [instructions, prompt, guidance];
    return Object.keys(bodies()) as Part[];
  });
  const blocked = $derived(changed.some((p) => found[p] && "problem" in (found[p] as object)));

  $effect(() => {
    const document = JSON.parse(JSON.stringify(data ?? null)) as unknown;
    if (document === null) return;
    const at = ++picking;
    const timer = setTimeout(async () => {
      const got = await api.POST("/api/picks", { body: { document: document as never, selectors: [expectation] } });
      if (at === picking) picked = got.data?.[0]?.items ?? null;
    }, 300);
    return () => clearTimeout(timer);
  });

  $effect(() => {
    const sent = bodies();
    const at = ++checking;
    const timer = setTimeout(async () => {
      const results: Partial<Record<Part, Checked>> = {};
      for (const [part, body] of Object.entries(sent) as [Part, Record<string, unknown>][]) {
        results[part] = await checked(body as Component);
      }
      if (at === checking) found = results;
    }, 400);
    return () => clearTimeout(timer);
  });

  function saves(): string {
    if (!changed.length) return t("Nothing changed yet.");
    const said = changed.map((p) =>
      p === "output" ? t("what it is told to answer") : p === "prompt" ? t("its prompt") : t("its instructions"),
    );
    return t("Saves %(parts)s as your own.", { parts: displayList(said) });
  }

  async function save(): Promise<void> {
    busy = true;
    problem = null;
    const got = await rewritten(given, bodies(), me);
    busy = false;
    if ("problem" in got) problem = got.problem;
    else made(got.judge);
  }
</script>

<section class="space-y-3 rounded-lg border border-dashed border-primary/40 p-2.5" aria-label={t("Texts")}>
  <p class="text-muted-foreground">
    {t(
      "What %(judge)s is asked, written as you would have it. Saving keeps each text you change as a version of your own, the judge's request with them, and a judge of your own asked through it. The scorers asking %(judge)s keep asking the version they ask until they follow yours, from its page.",
      { judge: given.name },
    )}
  </p>
  <div class="grid gap-3 lg:grid-cols-2">
    <div class="space-y-3">
      {#if parts.instructions}
        <TextSegments label={t("Instructions")} segs={instructions} set={(s) => (instructions = s)} inserts={guiding} />
      {/if}
      {#if parts.output}
        <TextSegments
          label={upFirst(t("what it is told to answer"))}
          segs={guidance}
          set={(s) => (guidance = s)}
          inserts={parts.output.body.json_schema ? ["schema"] : []}
        />
      {/if}
      {#if parts.prompt}
        <TextSegments
          label={t("Prompt")}
          segs={prompt}
          set={(s) => (prompt = s)}
          slots={judgeSlots}
          inserts={guiding}
        />
      {/if}
    </div>
    <div>
      <p class="mb-1 font-medium">{t("Preview")}</p>
      <ol class="space-y-1.5" aria-label={t("Preview")}>
        {#each preview as m, i (i)}
          <li>
            <span class="font-medium text-muted-foreground">{m.role}</span>
            <div
              class="mt-0.5 whitespace-pre-wrap rounded bg-background/70 p-2 font-mono text-[0.7rem] leading-relaxed"
            >
              {m.content}
            </div>
          </li>
        {/each}
      </ol>
    </div>
  </div>
  {#each changed as part (part)}
    {#if found[part]}<Findings found={found[part] ?? null} />{/if}
  {/each}
  {#if problem}<p class="text-destructive">{problem}</p>{/if}
  <p class="text-muted-foreground">
    {saves()}
  </p>
  <div class="flex gap-2">
    <button
      type="button"
      class="rounded-md bg-primary px-3 py-1 font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
      disabled={busy || changed.length === 0 || blocked}
      onclick={save}>{t("Save what it is asked")}</button
    >
    <button type="button" class="rounded-md border border-border px-3 py-1 hover:bg-muted" onclick={left}
      >{t("Not now")}</button
    >
  </div>
</section>
