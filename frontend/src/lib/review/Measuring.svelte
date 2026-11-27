<script lang="ts">
  import { onMount, untrack } from "svelte";
  import { SvelteSet } from "svelte/reactivity";
  import LoaderCircleIcon from "@lucide/svelte/icons/loader-circle";
  import RefreshCwIcon from "@lucide/svelte/icons/refresh-cw";
  import XIcon from "@lucide/svelte/icons/x";
  import { api, why } from "$lib/api/client";
  import { t, tn, tp, upFirst } from "$lib/locale";
  import { fieldName } from "$lib/schema/form";
  import { kept, type Measure, type Measured, segments, type Shown, shownAs, type Text } from "./measure.svelte";

  let {
    measure,
    case: measuring,
    schema,
    current,
  }: { measure: Measure; case: string; schema: string; current: () => unknown } = $props();

  // Policy: so many texts at a time, so that a case read thousands of times opens at once.
  const PAGE = 50;

  let field = $state<string | null>(untrack(() => measure.field));
  let got = $state<Measured | null>(null);
  let problem = $state<string | null>(null);
  let loading = $state(false);
  const shown = new SvelteSet<Shown>(["missed", "unscored", "found"]);
  let alternative = $state<number | null>(null);
  let paged = $state(PAGE);
  let asked = 0;

  async function measured(): Promise<void> {
    if (field === null) return;
    const now = ++asked;
    loading = true;
    const res = await api.POST("/api/expectations/measured", {
      body: { case: measuring, expectation_schema: schema, data: current() as never, field },
    });
    if (now !== asked) return;
    loading = false;
    if (res.data) {
      got = res.data;
      problem = null;
    } else problem = why(res.error);
    alternative = null;
    paged = PAGE;
  }

  // Policy: what was measured stays as the column closes, so that it slides out whole.
  $effect(() => {
    const now = measure.field;
    if (now === null || now === untrack(() => field)) return;
    field = now;
    got = null;
    void untrack(measured);
  });

  onMount(() => {
    if (field !== null) void measured();
  });

  const texts = $derived(got === null ? [] : got.texts.filter((x) => kept(x, shown, alternative)));
  const most = $derived(Math.max(1, ...(got?.alternatives.map((a) => a.found) ?? [])));

  function flipped(at: Shown): void {
    if (shown.has(at)) shown.delete(at);
    else shown.add(at);
    paged = PAGE;
  }

  function valued(text: Text): string {
    if (text.value === null) return "—";
    return text.unit === "@" ? `@${Math.trunc(text.value)}` : text.value.toFixed(2);
  }

  function when(stamp: string): string {
    return stamp.slice(0, 16).replace("T", " ");
  }

  function views(text: Text): string[] {
    return [...new Set(text.seen.map((s) => s.view))];
  }

  const tones: Record<Shown, string> = {
    missed: "bg-destructive",
    unscored: "bg-muted-foreground/40",
    found: "bg-success",
  };
  const said: Record<Shown, () => string> = {
    missed: () => t("Missed"),
    unscored: () => upFirst(t("not scored")),
    found: () => t("Found"),
  };
  const counted: Record<Shown, (m: Measured) => number> = {
    missed: (m) => m.missed,
    unscored: (m) => m.unscored,
    found: (m) => m.found,
  };
</script>

<div class="flex h-full flex-col">
  <header class="border-b border-border/60 px-4 pt-4 pb-3">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="text-[0.7rem] tracking-wide text-muted-foreground uppercase">{t("Measuring")}</p>
        <h2 class="truncate text-base font-semibold">{field === null ? "" : fieldName(field)}</h2>
      </div>
      <div class="flex shrink-0 items-center gap-2">
        <button
          class="small"
          disabled={loading || measure.field === null}
          title={t("Scores every answer again against the field as it is written now, saved or not")}
          onclick={measured}
        >
          {#if loading}<LoaderCircleIcon class="size-4 animate-spin" />{:else}<RefreshCwIcon class="size-4" />{/if}
          {t("Update")}
        </button>
        <button class="icon" aria-label={t("Close")} title={t("Close")} onclick={() => measure.close()}>
          <XIcon class="size-4" />
        </button>
      </div>
    </div>
    {#if got?.pattern}
      <p class="mt-2 truncate font-mono text-xs text-muted-foreground" title={got.pattern}>{got.pattern}</p>
    {/if}
  </header>

  <div class="min-h-0 flex-1 overflow-y-auto px-4 py-3" data-measured>
    {#if problem}
      <p role="alert" class="text-sm text-destructive">{problem}</p>
    {:else if got === null}
      {#if field !== null}
        <p role="status" class="flex items-center gap-2 text-sm text-muted-foreground">
          <LoaderCircleIcon class="size-4 animate-spin" />{upFirst(tp("in progress", "scoring"))}…
        </p>
      {/if}
    {:else}
      {#if got.problem}<p role="alert" class="mb-3 text-sm text-destructive">{got.problem}</p>{/if}
      <p class="mb-3 text-sm text-muted-foreground">
        {t("%(answers)s answers, scored %(scored)s times.", {
          answers: got.answers,
          scored: got.found + got.missed + got.unscored,
        })}
      </p>
      <div class="mb-4 flex flex-wrap gap-1.5" role="group" aria-label={t("Show")}>
        {#each ["missed", "unscored", "found"] as const as at (at)}
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-0.5 text-xs transition-colors hover:bg-muted aria-pressed:border-foreground/40 aria-pressed:bg-muted"
            aria-pressed={shown.has(at)}
            onclick={() => flipped(at)}
            ><span aria-hidden="true" class="size-2 rounded-full {tones[at]}"></span>{said[at]()}
            <span class="text-muted-foreground tabular-nums">{counted[at](got)}</span></button
          >
        {/each}
      </div>

      {#if got.alternatives.length > 1}
        <details open class="group mb-4">
          <summary class="mb-1 cursor-pointer text-xs text-muted-foreground">
            {tn("%(num)s alternative", "%(num)s alternatives", got.alternatives.length, {
              num: got.alternatives.length,
            })}
          </summary>
          <ol class="max-h-56 space-y-1 overflow-y-auto">
            {#each got.alternatives as a, i (i)}
              <li>
                <button
                  type="button"
                  class="grid w-full grid-cols-[minmax(0,10rem)_minmax(0,1fr)_3rem] items-center gap-2 rounded-md px-1.5 py-0.5 text-left text-xs transition-colors hover:bg-muted aria-pressed:bg-muted"
                  aria-pressed={alternative === i}
                  onclick={() => {
                    alternative = alternative === i ? null : i;
                    paged = PAGE;
                  }}
                >
                  <span class="truncate font-mono {a.found ? '' : 'text-muted-foreground'}">{a.pattern}</span>
                  <span class="h-2 overflow-hidden rounded-full bg-muted">
                    <span
                      class="block h-full rounded-full bg-success/70 transition-[width] duration-500"
                      style:width="{(100 * a.found) / most}%"
                    ></span>
                  </span>
                  <span class="text-right tabular-nums {a.found ? '' : 'text-warning'}">{a.found}</span>
                </button>
              </li>
            {/each}
          </ol>
        </details>
      {/if}

      <ol class="space-y-2">
        {#each texts.slice(0, paged) as text, n (n)}
          {@const at = shownAs(text)}
          <li class="relative overflow-hidden rounded-lg border border-border/60 py-2 pr-3 pl-4 text-sm">
            <span aria-hidden="true" class="absolute inset-y-0 left-0 w-1 {tones[at]}"></span>
            <span class="sr-only">{said[at]()}</span>
            {#if text.texts === null || text.texts.length === 0}
              <p class="text-muted-foreground">{text.reason ?? `${upFirst(t("none"))}.`}</p>
            {:else}
              <ol class="space-y-0.5 {text.texts.length > 1 ? 'list-decimal pl-5' : ''}">
                {#each text.texts as item, i (i)}
                  <li class="break-words whitespace-pre-wrap">
                    {#each segments( item, text.marks.filter((m) => m.item === i) ) as segment, s (s)}{#if segment.marked}<mark
                          class="rounded-sm bg-success/20 px-0.5 text-foreground">{segment.text}</mark
                        >{:else}{segment.text}{/if}{/each}
                  </li>
                {/each}
              </ol>
            {/if}
            <div class="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
              <span class="font-medium text-foreground tabular-nums">×{text.count}</span>
              <span class="tabular-nums">{valued(text)}</span>
              {#if text.reason && text.texts?.length}<span>{text.reason}</span>{/if}
              <span class="min-w-0 truncate">{views(text).join(", ")}</span>
            </div>
            <details class="mt-1 text-xs">
              <summary class="cursor-pointer text-muted-foreground">{t("Where")}</summary>
              <ul class="mt-1 space-y-0.5">
                {#each text.seen as s, i (i)}
                  <li class="flex flex-wrap gap-x-2">
                    <span class="font-medium">{s.configuration}</span>
                    <span class="text-muted-foreground tabular-nums">{when(s.at)} · #{s.replicate + 1}</span>
                    <span class="text-muted-foreground">{s.view}</span>
                    {#if s.href}<a href={s.href}>{t("Score")}</a>{/if}
                  </li>
                {/each}
                {#if text.count > text.seen.length}
                  <li class="text-muted-foreground">
                    {t("and %(more)s more", { more: text.count - text.seen.length })}
                  </li>
                {/if}
              </ul>
            </details>
          </li>
        {:else}
          <li class="text-sm text-muted-foreground">{upFirst(t("none"))}.</li>
        {/each}
      </ol>
      {#if texts.length > paged}
        <button class="small mt-3" onclick={() => (paged += PAGE)}
          >{t("Show %(more)s more", { more: Math.min(PAGE, texts.length - paged) })}</button
        >
      {/if}
    {/if}
  </div>
</div>
