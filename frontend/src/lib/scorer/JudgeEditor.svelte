<script lang="ts" module>
  import type { Editing } from "$lib/editors/writing";
  import type { Judging, Serving } from "./judging";

  export type JudgeEditing = Editing & {
    kind: "judge";
    body: { skeleton: string; model: string; seeds: number[]; fill?: string } | null;
    configuration: string | null;
    handle: string | null;
    problem: string | null;
    judging: Judging[];
    models: Serving[];
    me: string;
  };
</script>

<script lang="ts">
  import { untrack } from "svelte";
  import Saving from "$lib/editors/Saving.svelte";
  import { t } from "$lib/locale";
  import type { Component, Saved } from "$lib/editors/writing";
  import JudgeFields from "./JudgeFields.svelte";
  import { configurationChoices, type Holding, type JudgeChoice, madeFor, modelChoices, seedsOf } from "./judging";

  let {
    editor,
    digest = null,
    made,
  }: { editor: JudgeEditing; digest?: string | null; made?: (judge: JudgeChoice) => void } = $props();
  const given = untrack(() => editor);
  const held: Holding | null = given.body && {
    skeleton: given.body.skeleton,
    configuration: given.configuration ?? given.body.skeleton,
    weights: given.body.model,
    handle: given.handle,
  };

  const start = given.body?.skeleton ?? given.judging[0]?.digest ?? "";
  const fitting = madeFor(given.judging, given.models);
  let configuration = $state(start);
  let weights = $state(given.body?.model ?? fitting[start] ?? given.models[0]?.weights ?? "");
  let seeds = $state((given.body?.seeds ?? [1]).join(", "));

  const read = $derived(seedsOf(seeds));
  const hint = $derived(weights === given.body?.model ? given.problem : null);

  function component(): Component | null {
    if (!configuration || !weights) return null;
    const fill = given.body?.fill ?? "text@1";
    return { kind: "judge", skeleton: configuration, model: weights, seeds: read, fill } as never;
  }

  function wrote(saved: Extract<Saved, { to: string }>, name: string): void {
    const from = given.judging.find((j) => j.digest === configuration);
    made?.({
      digest: saved.digest,
      thread: saved.thread,
      name,
      owner: given.me,
      configuration: from?.name ?? "",
      model: given.models.find((m) => m.weights === weights)?.name ?? null,
      seeds: read,
      output_schema: from?.output_schema ?? null,
    });
  }
</script>

<div class="space-y-3 text-sm">
  <div class="grid gap-2 sm:grid-cols-3">
    <JudgeFields
      configurations={configurationChoices(given.judging, given.me, held)}
      models={modelChoices(given.models, held)}
      made={fitting}
      {hint}
      bind:configuration
      bind:weights
      bind:seeds
    />
  </div>
  {#if given.mode !== "new"}
    <p class="text-muted-foreground">
      {t(
        "A scorer asks the version of a judge it names, so the scorers asking this one keep asking the version they ask until they are changed.",
      )}
    </p>
  {/if}
  <Saving editing={given} {component} {digest} made={made && wrote} />
</div>
