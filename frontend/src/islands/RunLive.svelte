<script lang="ts" module>
  export type Live = { run: string; titles: Record<string, string>; rowsPerPage: number };
</script>

<script lang="ts">
  import { onMount, untrack } from "svelte";
  import InfoIcon from "@lucide/svelte/icons/info";
  import LoaderCircleIcon from "@lucide/svelte/icons/loader-circle";
  import TriangleAlertIcon from "@lucide/svelte/icons/triangle-alert";
  import { Badge } from "$lib/components/ui/badge";
  import { localized, t, tn, tp, upFirst } from "$lib/locale";
  import Finding from "$lib/paging/Finding.svelte";
  import Pages from "$lib/paging/Pages.svelte";
  import { found, paged } from "$lib/paging/paging";
  import { watch } from "$lib/runs/events";
  import { outcome, outcomes } from "$lib/runs/outcomes";
  import { begun, fold, type Item, streaming, tally } from "$lib/runs/progress";

  let { live }: { live: Live } = $props();
  const given = untrack(() => live);

  let progress = $state(begun());
  let lost = $state<string | null>(null);
  const counted = $derived(tally(progress));
  const scoring = $derived(progress.scorings.length > 0);
  const rows = given.rowsPerPage;
  let query = $state("");
  let at = $state(0);
  const listed = $derived(found(progress.items, said, query));
  const shown = $derived(paged(listed, at, rows));

  onMount(() => {
    watch(given.run, (name, data) => fold(progress, name, data))
      .then(() => setTimeout(() => location.reload(), 800))
      .catch((e: unknown) => {
        lost = e instanceof Error ? e.message : String(e);
      });
  });

  function titled(item: Item): string {
    const title = given.titles[item.case] ?? item.case.slice(7, 19);
    return item.replicate ? `${title} #${item.replicate}` : title;
  }

  function said(item: Item): string {
    return [titled(item), item.outcome ? outcome(item.outcome) : "", item.why ?? ""].join(" ");
  }

  function doing(item: Item): string {
    const n = item.tokens;
    if (item.phase === "waiting") return tp("in progress", "waiting");
    if (item.phase === "ended") return t("%(sent)s in, %(got)s out", { sent: item.sent, got: item.received });
    if (item.kind === null) return t("sent");
    return `${streaming(item.kind)}, ${tn("%(num)s token", "%(num)s tokens", n, { num: n })}`;
  }
</script>

<section class="pane mb-6 rounded-2xl p-5 sm:p-6" aria-live="polite">
  <div class="mb-4 flex flex-wrap items-center gap-3">
    <h2 class="text-lg font-semibold">{upFirst(t("under way"))}</h2>
    {#if progress.done}
      <span class="text-sm text-muted-foreground">
        {upFirst(progress.done.halted ? tp("job", "stopped") : tp("job", "finished"))}…
      </span>
    {:else}
      <LoaderCircleIcon class="size-4 animate-spin text-muted-foreground" aria-hidden="true" />
      <span class="text-sm text-muted-foreground"
        >{upFirst(scoring ? tp("in progress", "scoring") : tp("in progress", "sending"))}…</span
      >
    {/if}
  </div>

  {#if lost}
    <p class="mb-4 text-sm text-destructive">{lost}. {t("Reload the page to see how far it has come.")}</p>
  {/if}

  {#if counted.of}
    <div class="mb-2 h-2 overflow-hidden rounded-full bg-muted">
      <div
        class="h-full bg-primary transition-[width]"
        style:width="{(100 * counted.ended) / counted.of}%"
        role="progressbar"
        aria-valuemin="0"
        aria-valuemax={counted.of}
        aria-valuenow={counted.ended}
        aria-label={t("Items ended")}
      ></div>
    </div>
    <p class="mb-4 flex flex-wrap items-center gap-2 text-sm">
      <span
        >{tn("%(ended)s of %(of)s item ended", "%(ended)s of %(of)s items ended", counted.of, {
          ended: counted.ended,
          of: counted.of,
        })}</span
      >
      {#each counted.outcomes as [said, n] (said)}<Badge variant="outline">{outcomes(said, n)}</Badge>{/each}
    </p>

    {#if progress.items.length >= rows}
      <Finding bind:query onchanged={() => (at = 0)} shown={listed.length} of={progress.items.length} />
    {/if}
    <div class="space-y-1.5">
      {#each shown.shown as item (`${item.case}#${item.replicate}`)}
        <details class="rounded-lg border border-border/60 bg-background/40 px-3 py-2">
          <summary class="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span class="font-medium">{titled(item)}</span>
            {#if item.outcome}<Badge
                variant={item.outcome === "valid" || item.outcome === "completed" ? "secondary" : "destructive"}
                >{outcome(item.outcome)}</Badge
              >{/if}
            {#if item.phase === "sending"}<LoaderCircleIcon
                class="size-3.5 animate-spin text-muted-foreground"
                aria-hidden="true"
              />{/if}
            <span class="text-muted-foreground">{doing(item)}</span>
            {#if item.tools}<span class="text-muted-foreground"
                >{tn("%(n)s tool call", "%(n)s tool calls", item.tools, { n: item.tools })}</span
              >{/if}
            {#if item.why}<span class="text-muted-foreground">{item.why}</span>{/if}
          </summary>
          {#if item.text.reasoning}
            <p class="mt-2 text-xs font-medium text-muted-foreground">{t("Thinking")}</p>
            <div class="mt-1 max-h-48 overflow-y-auto whitespace-pre-wrap font-mono text-xs text-muted-foreground">
              {item.text.reasoning}
            </div>
          {/if}
          {#if item.text.content || item.text.tool_call}
            <p class="mt-2 text-xs font-medium text-muted-foreground">{t("Answer")}</p>
            <div class="mt-1 max-h-72 overflow-y-auto whitespace-pre-wrap font-mono text-xs">
              {item.text.content}{item.text.tool_call}
            </div>
          {/if}
          {#if item.phase === "waiting"}<p class="mt-2 text-xs text-muted-foreground">
              {upFirst(tp("in progress", "waiting"))}.
            </p>{/if}
          {#if item.phase === "ended" && !item.text.content && !item.text.reasoning}
            <p class="mt-2 text-xs text-muted-foreground">
              {t("It ended before this page followed it; its answer is on the run's page once it is done.")}
            </p>
          {/if}
        </details>
      {/each}
    </div>
    {#if listed.length > rows}
      <Pages at={shown.at} last={shown.last} onpage={(n) => (at = n)} />
    {/if}
  {/if}

  {#if scoring}
    <h3 class="mt-6 mb-2 text-sm font-medium">{t("Scoring")}</h3>
    <ul class="space-y-1.5 text-sm">
      {#each progress.scorings as s, i (s.scorer)}
        {@const after = progress.scorings.slice(i + 1).some((t) => t.score !== null)}
        <li class="flex flex-wrap items-center gap-x-3">
          <span class="font-medium">{s.name}</span>
          {#if s.score === null}
            <span class="text-muted-foreground">{tp("in progress", "waiting")}</span>
          {:else}
            {#if !after && progress.scores === null}<LoaderCircleIcon
                class="size-3.5 animate-spin text-muted-foreground"
                aria-hidden="true"
              />{/if}
            {@const scored = tn("%(n)s scored", "%(n)s scored", s.scored, { n: s.scored })}
            <span class="text-muted-foreground">
              {s.views
                ? t("%(scored)s over %(views)s", {
                    scored,
                    views: tn("%(n)s view", "%(n)s views", s.views, { n: s.views }),
                  })
                : scored}
            </span>
            {#if s.asked}<span class="text-muted-foreground"
                >{tn(
                  "judges answered %(answered)s of %(asked)s",
                  "judges answered %(answered)s of %(asked)s",
                  s.asked,
                  { answered: s.answered, asked: s.asked },
                )}</span
              >{/if}
          {/if}
        </li>
      {/each}
    </ul>
  {/if}

  {#if progress.noted.length || progress.errors.length}
    <ul class="mt-6 space-y-1.5 text-sm">
      {#each progress.noted as finding, i (i)}
        <li class="flex gap-2">
          {#if finding.level === "warning"}<TriangleAlertIcon
              class="mt-0.5 size-4 shrink-0 text-warning"
            />{:else}<InfoIcon class="mt-0.5 size-4 shrink-0 text-primary" />{/if}
          <span>{localized(finding)}</span>
        </li>
      {/each}
      {#each progress.errors as error, i (i)}
        <li class="flex gap-2 text-destructive">
          <TriangleAlertIcon class="mt-0.5 size-4 shrink-0" /><span>{error}</span>
        </li>
      {/each}
    </ul>
  {/if}
</section>
