<script lang="ts" module>
  export type Telling = {
    family: number;
    tags: string[];
    language: string | null;
    languages: [string, string][];
    editable: boolean;
  };
</script>

<script lang="ts">
  import { untrack } from "svelte";
  import PencilIcon from "@lucide/svelte/icons/pencil";
  import { api, why } from "$lib/api/client";
  import { t, tp, upFirst } from "$lib/locale";
  import type { Edited, Wrote } from "./edited.svelte";
  import { added } from "./review";

  let { about, edited }: { about: Telling; edited: Edited } = $props();
  const given = untrack(() => about);
  const named = new Map(given.languages);

  let tags = $state([...given.tags]);
  let language = $state(given.language);
  let typed = $state("");
  let picking = $state(false);
  let saved = $state({ tags: [...given.tags], language: given.language });

  const next = $derived(added(tags, typed));
  const retagged = $derived(next.join("\n") !== saved.tags.join("\n"));
  const respoken = $derived(language !== saved.language);

  if (given.editable) {
    untrack(() => edited).join({
      rank: 0,
      pending: () => retagged || respoken,
      ready: () => true,
      save: async (): Promise<Wrote> => {
        const body = { tags: next, ...(respoken && language ? { language } : {}) };
        const got = await api.PATCH("/api/families/{family}", {
          params: { path: { family: given.family } },
          body,
        });
        if (!got.data) return { problem: why(got.error) };
        tags = [...got.data.tags];
        typed = "";
        saved = { tags: [...got.data.tags], language: got.data.language };
        return {};
      },
      restore: () => {
        tags = [...saved.tags];
        language = saved.language;
        typed = "";
        picking = false;
      },
    });
  }

  function typedIn(): void {
    tags = next;
    typed = "";
  }

  function spoken(chosen: string): void {
    picking = false;
    if (chosen) language = chosen;
  }
</script>

<div class="flex w-full flex-wrap items-center gap-2 text-xs">
  {#if given.editable}
    <div
      class="flex min-w-0 flex-1 flex-wrap items-center gap-1 rounded-md border border-input px-1.5 py-1 focus-within:border-ring"
    >
      {#each tags as tag (tag)}
        <span class="inline-flex items-center gap-0.5 rounded-full bg-muted py-0.5 pr-1 pl-2 text-muted-foreground">
          {tag}
          <button
            type="button"
            class="rounded-full px-1 hover:bg-background hover:text-foreground"
            aria-label={t("Take away the tag %(tag)s", { tag })}
            onclick={() => (tags = tags.filter((held) => held !== tag))}>×</button
          >
        </span>
      {/each}
      <input
        class="min-w-24 flex-1 bg-transparent px-1 py-0.5 outline-none"
        aria-label={upFirst(t("a new tag"))}
        placeholder={`${t("a new tag")}…`}
        bind:value={typed}
        onkeydown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            typedIn();
          } else if (e.key === "Backspace" && !typed && tags.length) {
            tags = tags.slice(0, -1);
          }
        }}
        onblur={typedIn}
      />
    </div>
  {:else}
    <div class="flex min-w-0 flex-1 flex-wrap items-center gap-1">
      {#each tags as tag (tag)}
        <span class="inline-flex rounded-full bg-muted px-2 py-0.5 text-muted-foreground">{tag}</span>
      {/each}
    </div>
  {/if}
  <div class="ml-auto flex items-center gap-1 text-muted-foreground">
    {#if picking}
      <select
        class="h-7 rounded-md border border-input bg-transparent px-1.5"
        aria-label={t("Its language")}
        value={language ?? ""}
        onchange={(e) => spoken(e.currentTarget.value)}
        onblur={() => (picking = false)}
      >
        {#if !language}<option value="" disabled>{tp("no language", "none")}</option>{/if}
        {#each given.languages as [tag, name] (tag)}<option value={tag}>{name}</option>{/each}
      </select>
    {:else}
      <span>{language ? (named.get(language) ?? language) : t("no language")}</span>
      {#if given.editable}
        <button
          type="button"
          class="rounded-md p-1 hover:bg-muted hover:text-foreground"
          aria-label={t("Change its language")}
          title={t("Change its language")}
          onclick={() => (picking = true)}><PencilIcon class="size-3.5" /></button
        >
      {/if}
    {/if}
  </div>
</div>
