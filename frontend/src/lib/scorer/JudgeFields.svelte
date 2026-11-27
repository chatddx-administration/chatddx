<script lang="ts">
  import { untrack } from "svelte";
  import { t, upFirst } from "$lib/locale";
  import { FIELD } from "$lib/utils";
  import type { Option } from "./judging";

  let {
    configurations,
    models,
    made,
    hint = null,
    configuration = $bindable(),
    weights = $bindable(),
    seeds = $bindable(),
  }: {
    configurations: Option[];
    models: Option[];
    made: Record<string, string>;
    hint?: string | null;
    configuration: string;
    weights: string;
    seeds: string;
  } = $props();

  let picked = untrack(() => configuration);

  $effect(() => {
    if (configuration === picked) return;
    picked = configuration;
    const held = made[configuration];
    if (held) weights = held;
  });
</script>

<label class="grid gap-1"
  ><span class="text-muted-foreground">{t("Request")}</span>
  <select class={FIELD} bind:value={configuration}>
    {#each configurations as c (c.key)}<option value={c.value}>{c.label}</option>{/each}
  </select></label
>
<label class="grid gap-1"
  ><span class="text-muted-foreground">{t("Model")}</span>
  <select class={FIELD} bind:value={weights}>
    {#each models as m (m.key)}<option value={m.value}>{m.label}</option>{/each}
  </select>
  {#if hint}<span class="text-xs text-warning">{hint}</span>{/if}</label
>
<label class="grid gap-1"
  ><span class="text-muted-foreground">{upFirst(t("seeds"))}</span><input
    class="{FIELD} font-mono"
    inputmode="numeric"
    placeholder="1"
    bind:value={() => seeds, (typed) => (seeds = typed.replace(/[^\d,\s]/g, ""))}
  /></label
>
