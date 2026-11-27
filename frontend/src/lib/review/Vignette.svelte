<script lang="ts">
  import { onMount } from "svelte";
  import LoaderCircleIcon from "@lucide/svelte/icons/loader-circle";
  import { api, type Schemas, why } from "$lib/api/client";
  import { t, upFirst } from "$lib/locale";

  let { family }: { family: number } = $props();

  let shown = $state<Schemas["Vignette"] | null>(null);
  let problem = $state<string | null>(null);

  onMount(async () => {
    const got = await api.GET("/api/families/{family}/vignette", { params: { path: { family } } });
    if (got.data) shown = got.data;
    else problem = why(got.error);
  });
</script>

{#if shown}
  {#if shown.drifted}
    <p role="alert" class="mb-3 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
      {t("This isn't the text the case was made from any more.")}
    </p>
  {/if}
  <div class="whitespace-pre-wrap leading-relaxed">{shown.text}</div>
{:else if problem}
  <p class="text-sm text-destructive">{upFirst(t("can't be shown"))}: {problem}.</p>
{:else}
  <p class="flex items-center gap-2 text-sm text-muted-foreground">
    <LoaderCircleIcon class="size-4 animate-spin" aria-hidden="true" />
    {upFirst(t("the vignette"))}…
  </p>
{/if}
