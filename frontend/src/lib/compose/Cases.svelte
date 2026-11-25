<script lang="ts">
  import LoaderCircleIcon from "@lucide/svelte/icons/loader-circle";
  import TriangleAlertIcon from "@lucide/svelte/icons/triangle-alert";
  import * as Alert from "$lib/components/ui/alert";
  import { Input } from "$lib/components/ui/input";
  import { Label } from "$lib/components/ui/label";
  import { displayLanguage, t, tn } from "$lib/locale";
  import { type Group, groups, holds, type Listed, toggled } from "./cases";

  let {
    cases,
    held,
    start,
  }: {
    cases: Listed[];
    held: boolean;
    start: (families: number[], replicates: number, score: boolean) => Promise<string | null>;
  } = $props();

  const grouped = $derived(groups(cases));
  let chosen = $state<number[]>([]);
  let sought = $state("");
  let replicates = $state(1);
  let score = $state(true);
  let starting = $state(false);
  let unstarted = $state<string | null>(null);

  const shown = $derived.by(() => {
    const words = sought.trim().toLowerCase();
    if (!words) return cases;
    return cases.filter((c) => [c.name, ...c.tags, c.language ?? ""].some((w) => w.toLowerCase().includes(words)));
  });

  function said(g: Group): string {
    if (g.by === "all") return t("All");
    return g.by === "language" ? displayLanguage(g.value ?? "") : (g.value ?? "");
  }

  function picked(family: number): void {
    chosen = chosen.includes(family) ? chosen.filter((f) => f !== family) : [...chosen, family];
  }

  async function run(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    starting = true;
    unstarted = await start(chosen, replicates, score);
    starting = false;
  }
</script>

<section class="mb-6 border-t border-border/60 pt-4" aria-label={t("Run it on cases")}>
  <h2 class="mb-2 text-base font-semibold">{t("Run it on cases")}</h2>
  <form class="space-y-3" onsubmit={run}>
    <div class="flex flex-wrap gap-1.5" role="group" aria-label={t("Pick by tag or language")}>
      {#each grouped as g (`${g.by}:${g.value}`)}
        <button
          type="button"
          class="rounded-full border px-2.5 py-0.5 text-xs {holds(chosen, g)
            ? 'border-primary bg-primary/10 text-primary'
            : 'border-border text-muted-foreground hover:bg-muted'}"
          aria-pressed={holds(chosen, g)}
          onclick={() => (chosen = toggled(chosen, g))}
          >{said(g)} <span class="opacity-70">{g.families.length}</span></button
        >
      {/each}
    </div>

    <details class="rounded-lg border border-border/60 p-2">
      <summary class="cursor-pointer text-sm">
        {tn("%(n)s case picked", "%(n)s cases picked", chosen.length, { n: chosen.length })}
      </summary>
      <Input class="my-2 max-w-xs" bind:value={sought} placeholder={t("Find a case")} aria-label={t("Find a case")} />
      <ul class="max-h-72 space-y-0.5 overflow-y-auto text-sm">
        {#each shown as c (c.family)}
          <li>
            <label class="flex items-center gap-2">
              <input type="checkbox" checked={chosen.includes(c.family)} onchange={() => picked(c.family)} />
              <span class="min-w-0 flex-1 truncate">{c.name}</span>
              <span class="text-xs text-muted-foreground"
                >{[...c.tags, ...(c.language ? [displayLanguage(c.language)] : [])].join(" · ")}</span
              >
            </label>
          </li>
        {/each}
      </ul>
    </details>

    <div class="flex flex-wrap items-end gap-4">
      <div class="space-y-1.5">
        <Label for="replicates">{t("Replicates")}</Label>
        <Input id="replicates" type="number" min="1" class="w-24" bind:value={replicates} />
      </div>
      <label class="flex items-center gap-2 text-sm">
        <input type="checkbox" bind:checked={score} />
        {t("Score it once it is finished")}
      </label>
    </div>

    {#if unstarted}
      <Alert.Root variant="destructive">
        <TriangleAlertIcon />
        <Alert.Description>{unstarted}</Alert.Description>
      </Alert.Root>
    {/if}
    <button type="submit" class="run" disabled={held || starting || chosen.length === 0 || !(replicates >= 1)}>
      {#if starting}<LoaderCircleIcon class="animate-spin" />{/if}
      {tn("Run it on %(n)s case", "Run it on %(n)s cases", chosen.length, { n: chosen.length })}
    </button>
  </form>
</section>
