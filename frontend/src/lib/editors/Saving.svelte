<script lang="ts">
  import { untrack } from "svelte";
  import LoaderCircleIcon from "@lucide/svelte/icons/loader-circle";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { t, upFirst } from "$lib/locale";
  import Findings from "./Findings.svelte";
  import {
    type Checked,
    checked,
    type Component,
    type Editing,
    type Labelled,
    type Saved,
    said,
    saved,
  } from "./writing";

  type Wrote = Extract<Saved, { to: string }>;

  let {
    editing,
    component,
    digest = null,
    same = true,
    after,
    to,
    made,
    labels,
    quiet = false,
  }: {
    editing: Editing;
    component: () => Component | null;
    digest?: string | null;
    same?: boolean;
    after?: (cases: number) => string;
    to?: (saved: Wrote) => string;
    made?: (saved: Wrote, name: string) => void;
    labels?: () => Labelled;
    quiet?: boolean;
  } = $props();

  let name = $state(untrack(() => editing.name));
  let head = $state(untrack(() => editing.head));
  let found = $state<Checked | null>(null);
  let busy = $state(false);
  let problem = $state<string | null>(null);
  let note = $state<string | null>(null);
  let asked = 0;

  const unchanged = $derived(
    editing.mode === "edit" && same && found !== null && "digest" in found && found.digest === digest,
  );
  const unready = $derived(component() === null || found === null || "problem" in found);
  const nameless = $derived(editing.mode !== "edit" && !name.trim());
  const first = JSON.stringify(untrack(() => $state.snapshot(component())));
  const touched = $derived(JSON.stringify($state.snapshot(component())) !== first);

  $effect(() => {
    const sent = $state.snapshot(component());
    const at = ++asked;
    if (sent === null) return;
    const timer = setTimeout(async () => {
      const got = await checked(sent as Component);
      if (at === asked) found = got;
    }, 350);
    return () => clearTimeout(timer);
  });

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const sent = component();
    if (sent === null) return;
    busy = true;
    problem = null;
    const got = await saved({ ...editing, head }, name, sent, labels?.());
    busy = false;
    if ("to" in got) {
      if (made) {
        made(got, name.trim());
        return;
      }
      const where = to ? to(got) : got.to;
      const cases = Object.keys(got.cases).length;
      if (cases && after) {
        note = after(cases);
        setTimeout(() => location.assign(where), 2500);
      } else location.assign(where);
      return;
    }
    problem = got.problem;
    if (got.moved !== null) {
      head = got.moved;
      problem = t("%(problem)s. What you typed is kept: save again to make it the version after the latest.", {
        problem: got.problem,
      });
    }
  }
</script>

<div class="mt-3 space-y-3">
  {#if editing.mode !== "new" || touched}<Findings {found} />{/if}
  <form class="space-y-3" onsubmit={save}>
    {#if editing.mode !== "edit"}
      <label class="grid max-w-md gap-1 text-sm">
        <span class="font-medium">{upFirst(t("name"))}</span>
        <Input bind:value={name} autocomplete="off" />
      </label>
    {/if}
    {#if !quiet || editing.mode === "edit"}
      <p class="text-sm" aria-live="polite">{said(editing, name, unchanged)}</p>
    {/if}
    {#if problem}<p class="text-sm text-destructive">{problem}</p>{/if}
    {#if note}<p class="text-sm text-success">{note}</p>{/if}
    <Button type="submit" disabled={busy || unready || nameless || (editing.mode === "edit" && unchanged)}>
      {#if busy}<LoaderCircleIcon class="animate-spin" />{/if}
      {t("Save")}
    </Button>
  </form>
</div>
