<script lang="ts">
  import { untrack } from "svelte";
  import ExpectationEditor from "$lib/editors/ExpectationEditor.svelte";
  import { t, upFirst } from "$lib/locale";
  import type { ExpectationEditing } from "$lib/editors/ExpectationEditor.svelte";
  import Changed from "$lib/thread/Changed.svelte";
  import type { Edited } from "./edited.svelte";
  import type { Measure } from "./measure.svelte";
  import type { Expecting } from "./review";

  let {
    expected,
    editor,
    edited,
    measure,
  }: { expected: Expecting; editor: ExpectationEditing; edited: Edited; measure: Measure } = $props();
  const given = untrack(() => expected);

  let shown = $state(given.history.length - 1);
  const version = $derived(given.history[shown]);
  const before = $derived(shown > 0 ? given.history[shown - 1] : undefined);
  let fields = $state<ExpectationEditor>();

  // Policy: the fields hold the version shown, so that Save makes it the latest; what was
  // typed over the one shown is replaced only once confirmed.
  function step(by: number): void {
    const to = given.history[shown + by];
    if (!to || !version || !fields) return;
    if (!fields.holds(version.data) && !confirm(t("Discard what you changed?"))) {
      return;
    }
    shown += by;
    fields.load(to.data);
  }

  export function current(): unknown {
    return fields?.current();
  }

  function when(stamp: string): string {
    return stamp.slice(0, 16).replace("T", " ");
  }
</script>

<ExpectationEditor bind:this={fields} {editor} {edited} restored={() => (shown = given.history.length - 1)} {measure} />
{#if version && given.history.length > 1}
  <div
    class="mt-4 rounded-lg border border-border/60 p-3 text-sm transition-opacity duration-500 {measure.field !== null
      ? 'opacity-35'
      : ''}"
    inert={measure.field !== null}
  >
    <nav class="mb-2 flex items-center gap-2 text-xs" aria-label={t("Versions")}>
      <button
        type="button"
        class="rounded-md border border-border px-2 py-0.5 hover:bg-muted disabled:opacity-40"
        disabled={shown === 0}
        aria-label={t("Previous version")}
        onclick={() => step(-1)}>◀</button
      >
      <span class="font-medium"
        >{upFirst(t("version %(at)s of %(last)s", { at: shown + 1, last: given.history.length }))}</span
      >
      <button
        type="button"
        class="rounded-md border border-border px-2 py-0.5 hover:bg-muted disabled:opacity-40"
        disabled={shown === given.history.length - 1}
        aria-label={t("Next version")}
        onclick={() => step(1)}>▶</button
      >
      <span class="text-muted-foreground">{when(version.at)}, {version.by}</span>
    </nav>
    {#if shown !== given.history.length - 1}
      <p class="mb-2 text-xs text-muted-foreground">{t("The fields hold this version: Save makes it the latest.")}</p>
    {/if}
    {#if before}
      <Changed before={before.data} after={version.data} />
    {:else}
      <p class="text-xs text-muted-foreground">{t("It is the first.")}</p>
    {/if}
  </div>
{/if}
