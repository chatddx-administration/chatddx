<script lang="ts">
  import LoaderCircleIcon from "@lucide/svelte/icons/loader-circle";
  import RotateCcwIcon from "@lucide/svelte/icons/rotate-ccw";
  import TriangleAlertIcon from "@lucide/svelte/icons/triangle-alert";
  import * as Alert from "$lib/components/ui/alert";
  import { Button } from "$lib/components/ui/button";
  import { Input } from "$lib/components/ui/input";
  import { Label } from "$lib/components/ui/label";
  import { api, why } from "$lib/api/client";
  import { displayLanguage, t, tn, tp, upFirst } from "$lib/locale";
  import {
    type Body,
    type Chunk,
    cleaned,
    kept as keptLanguages,
    restaled,
    same,
    settled as lookedOver,
    type Stale,
  } from "$lib/compose/drafting";
  import { said, tally } from "$lib/compose/baseline";
  import type { Following } from "$lib/compose/following.svelte";
  import { whereSaveGoes } from "$lib/compose/logic";
  import Cases from "$lib/compose/Cases.svelte";
  import type { Props } from "$lib/compose/props";
  import type { Sending } from "$lib/compose/sending.svelte";
  import Settings from "$lib/compose/Settings.svelte";
  import Texts from "$lib/compose/Texts.svelte";
  import { untrack } from "svelte";

  let { held, sending, following }: { held: Props; sending: Sending; following: Following } = $props();
  const given = untrack(() => held);
  const { configuration, me, versions, head, drafted } = given;
  const latest = versions.at(-1);
  const version = versions.find((v) => v.id === head)?.version ?? 0;

  let chunks = $state(structuredClone(drafted?.chunks));
  let model = $state(drafted?.model ?? null);
  let into = $state(structuredClone(drafted?.into ?? {}));
  let texts = $state(structuredClone(drafted?.texts ?? {}));
  let baseline = $state.raw($state.snapshot(drafted?.chunks));
  let stale = $state<Stale>({});
  let tab = $state<string | null>(null);
  const translating = $derived(tab !== null && tab in into);
  untrack(() => (sending.current = previewed));
  $effect(() => {
    sending.language = translating ? tab : null;
  });

  function previewed() {
    return {
      head,
      chunks: $state.snapshot(chunks) ?? {},
      ...(model !== null ? { model } : {}),
      translations: cleaned($state.snapshot(into)),
      ...(translating ? { language: tab } : {}),
    };
  }
  let drafting: ReturnType<typeof setTimeout> | null = null;
  let draftingNow: Promise<void> | null = null;
  let draftFailure = $state<string | null>(null);
  let waiting = $state(false);
  let name = $state(configuration.name ?? configuration.title);
  let saving = $state(false);
  let unsaved = $state<string | null>(null);
  let independent = $state(false);
  let running = $state(false);

  const changed = $derived(
    given.varied ||
      !same(chunks, drafted?.chunks) ||
      model !== (drafted?.model ?? null) ||
      !same(cleaned(into), cleaned(drafted?.into ?? {})),
  );
  const goes = $derived(
    whereSaveGoes({
      name,
      configuration,
      me,
      versions: Math.max(0, ...versions.map((v) => v.version)),
      version,
      latest: version === latest?.version,
      changed,
      configurations: given.configurations,
    }),
  );

  const runnable = $derived(
    given.baseline !== null &&
      !saving &&
      !waiting &&
      !running &&
      (goes.to === "nothing"
        ? !changed && !following.running && (given.baseline.behind || following.whole || following.ended)
        : true),
  );
  const counted = $derived(tally(following.runs));

  function saves(): string {
    if (goes.to === "nothing" && goes.because === "nameless") return t("Give it a name to save it.");
    if (goes.to === "nothing") return t("Nothing to save: this is the configuration as it is.");
    if (goes.to === "version" && goes.from === goes.version)
      return t("Brings version %(n)s of this configuration back as the latest.", { n: goes.version });
    if (goes.to === "version" && goes.from !== null)
      return t("Saves version %(n)s of this configuration, from version %(was)s.", { n: goes.version, was: goes.from });
    if (goes.to === "version") return t("Saves version %(n)s of this configuration.", { n: goes.version });
    if (independent)
      return t("Saves a new configuration of yours, “%(name)s”, independent of this one.", { name: name.trim() });
    return t("Saves a new configuration of yours, “%(name)s”, forked from version %(n)s of this one.", {
      name: name.trim(),
      n: version,
    });
  }

  function set(part: Chunk, body: Body | null): void {
    if (!chunks) return;
    chunks[part] = body;
    if (drafting !== null) clearTimeout(drafting);
    waiting = true;
    drafting = setTimeout(() => {
      drafting = null;
      draftingNow = draft();
    }, 400);
  }

  // Policy: a text's translations follow it as it is typed, so the translations are drafted on the server alongside
  // the chunks, and aren't typed in meanwhile.
  let drafts = 0;
  async function draft(): Promise<void> {
    const drafted = ++drafts;
    const after = $state.snapshot(chunks);
    const sent = cleaned($state.snapshot(into));
    const got = await api.POST("/api/threads/{thread}/drafts", {
      params: { path: { thread: configuration.id } },
      body: { head, before: baseline ?? {}, after: after ?? {}, translations: sent },
    });
    if (drafted !== drafts) return;
    waiting = false;
    if (!got.data) {
      draftFailure = why(got.error);
      return;
    }
    draftFailure = null;
    texts = got.data.texts;
    stale = restaled(stale, sent, got.data.translations);
    into = keptLanguages(into, got.data.translations);
    baseline = after;
  }

  async function settled(): Promise<void> {
    if (drafting !== null) {
      clearTimeout(drafting);
      drafting = null;
      draftingNow = draft();
    }
    await draftingNow;
  }

  function translate(language: string, text: string, said: string): void {
    into[language] = { ...into[language], [text]: said };
    settle(language, text);
  }

  function settle(language: string, text: string): void {
    stale = lookedOver(stale, language, text);
  }

  function dropped(language: string): void {
    const { [language]: _, ...rest } = into;
    into = rest;
  }

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const id = await written();
    if (id !== null) location.assign(`/compose/${id}`);
  }

  const again = $derived(goes.to === "nothing" && following.whole);

  // Policy: Run saves what there is to save first, an earlier version being brought back, and runs the configuration it
  // saved into; with nothing to save, it runs the version open.
  async function run(): Promise<void> {
    const id = goes.to === "nothing" ? configuration.id : await written();
    if (id === null) return;
    running = true;
    const form = document.createElement("form");
    form.method = "post";
    form.action = `/compose/${id}/runs`;
    if (goes.to === "nothing") {
      const version = document.createElement("input");
      version.type = "hidden";
      version.name = "head";
      version.value = String(head);
      form.append(version);
    }
    document.body.append(form);
    form.submit();
  }

  // Policy: running on cases saves what there is to save first, as Run does, and runs the configuration it saved into.
  async function runOn(families: number[], replicates: number, score: boolean): Promise<string | null> {
    const kept = goes.to === "nothing";
    const id = kept ? configuration.id : await written();
    if (id === null) return unsaved;
    const got = await api.POST("/api/runs", {
      body: { configuration: id, ...(kept ? { head } : {}), families, replicates, score },
    });
    if (!got.data) {
      saving = false;
      return why(got.error);
    }
    location.assign(`/runs/${got.data.runs[0]?.run}`);
    return null;
  }

  async function written(): Promise<number | null> {
    const to = goes.to;
    if (to === "nothing") return null;
    saving = true;
    unsaved = null;
    await settled();
    if (draftFailure !== null) {
      unsaved = draftFailure;
      saving = false;
      return null;
    }
    const got = await api.POST("/api/threads/{thread}/saves", {
      params: { path: { thread: configuration.id } },
      body: {
        head: to === "version" ? (latest?.id ?? head) : head,
        ...(to === "fork" ? { name: name.trim(), independent } : {}),
        chunks: $state.snapshot(chunks) ?? {},
        ...(model !== null && model !== drafted?.model
          ? { model }
          : goes.to === "version" && goes.from !== null && drafted
            ? { model: drafted.model }
            : {}),
        translations: cleaned($state.snapshot(into)),
      },
    });
    if (!got.data) {
      unsaved = why(got.error);
      saving = false;
      return null;
    }
    return got.data.id;
  }
</script>

{#if chunks && drafted}
  <div class="@container">
    <div>
      {#if !sending.open}
        <div class="mb-2 flex justify-end">
          <button type="button" class="small" onclick={() => sending.show()}>{t("What it sends")}</button>
        </div>
      {/if}
      <Texts
        {chunks}
        settled={baseline ?? chunks}
        {drafted}
        language={configuration.language}
        {into}
        {texts}
        {stale}
        {waiting}
        bind:tab
        {set}
        {translate}
        {settle}
        {dropped}
      />
      {#if !translating}<Settings
          {chunks}
          {model}
          models={given.modelChoices}
          facts={given.facts}
          tools={drafted.tools}
          toolChoices={given.toolChoices}
          {set}
          pick={(m) => {
            model = m || null;
          }}
        />{/if}
      {#if draftFailure}
        <Alert.Root variant="destructive" class="mb-4">
          <TriangleAlertIcon />
          <Alert.Description>{draftFailure}</Alert.Description>
        </Alert.Root>
      {/if}

      <section class="mb-6 border-t border-border/60 pt-4" aria-label={t("Saving it")}>
        <form class="space-y-3" onsubmit={save}>
          <div class="space-y-1.5">
            <Label for="saved-name">{upFirst(t("name"))}</Label>
            <Input id="saved-name" bind:value={name} class="max-w-md" autocomplete="off" />
          </div>
          {#if goes.to === "fork"}
            <label class="flex items-center gap-2 text-sm">
              <input type="checkbox" bind:checked={independent} />
              {t("Independent of this one: not a fork of it, nor of its parts")}
            </label>
          {/if}
          <p class="text-sm" aria-live="polite">
            {saves()}
            {#if goes.to === "fork" && goes.namesakes}
              <span class="text-warning">
                {tn(
                  "You have one named so already; names needn't be unique.",
                  "You have %(n)s named so already; names needn't be unique.",
                  goes.namesakes,
                  { n: goes.namesakes },
                )}
              </span>
            {/if}
          </p>
          {#if unsaved}
            <Alert.Root variant="destructive">
              <TriangleAlertIcon />
              <Alert.Description>{unsaved}</Alert.Description>
            </Alert.Root>
          {/if}
          <div class="flex flex-wrap gap-2">
            <Button type="submit" disabled={goes.to === "nothing" || saving || waiting}>
              {#if saving}<LoaderCircleIcon class="animate-spin" />{/if}
              {t("Save")}
            </Button>
            {#if given.baseline}
              <button type="button" class="run" disabled={!runnable} onclick={() => void run()}
                >{#if again}<RotateCcwIcon />{/if}{tp("a button", "Run")}</button
              >
            {/if}
          </div>
          {#if following.running}
            <div class="max-w-md space-y-2 text-sm" role="status" aria-live="polite">
              <p class="flex items-center gap-2 text-muted-foreground">
                <LoaderCircleIcon class="size-4 animate-spin" aria-hidden="true" />{t("under way")}
                {#if counted.of}
                  ·
                  {tn("%(ended)s of %(of)s item ended", "%(ended)s of %(of)s items ended", counted.of, {
                    ended: counted.ended,
                    of: counted.of,
                  })}
                {/if}
              </p>
              {#if counted.of}
                <div class="h-1.5 overflow-hidden rounded-full bg-muted">
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
              {/if}
              {#if following.runs.length}
                <ul class="space-y-0.5">
                  {#each following.runs as r (r.id)}
                    <li>
                      <a href={`/runs/${r.id}`} class="flex flex-wrap items-baseline gap-x-2">
                        <code class="text-xs">{r.id.slice(0, 8)}</code>
                        {#if r.language}<span>{displayLanguage(r.language)}</span>{/if}
                        <span class="text-muted-foreground">{said(r)}</span>
                      </a>
                    </li>
                  {/each}
                </ul>
              {/if}
              {#if following.problem}<p role="alert" class="text-destructive">{following.problem}</p>{/if}
            </div>
          {/if}
        </form>
      </section>
      {#if given.cases.length}
        <Cases
          cases={given.cases}
          held={saving || waiting || running || (goes.to === "nothing" && changed)}
          start={runOn}
        />
      {/if}
    </div>
  </div>
{:else}
  <p class="mb-6 text-sm text-muted-foreground">{t("It holds no recipe, so its parts can't be changed here.")}</p>
{/if}
