<script lang="ts">
  import { t } from "$lib/locale";
  import type { Edited } from "./edited.svelte";

  let { edited }: { edited: Edited } = $props();

  function restore(): void {
    if (!edited.pending || confirm(t("Discard what you changed?"))) {
      edited.restore();
    }
  }
</script>

{#if edited.problem}<p role="alert" class="text-sm text-destructive">{edited.problem}</p>{/if}
<button type="button" disabled={edited.busy || !edited.restorable} onclick={restore}>{t("Restore")}</button>
<form
  onsubmit={(sent) => {
    sent.preventDefault();
    void edited.save(location.pathname + location.search);
  }}
>
  <button
    class="primary"
    disabled={edited.busy || !edited.pending || !edited.ready}
    data-pressed={edited.busy ? "" : undefined}>{t("Save")}</button
  >
</form>
