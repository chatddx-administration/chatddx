<script lang="ts">
  import { onMount } from "svelte";
  import ActivityIcon from "@lucide/svelte/icons/activity";
  import LoaderCircleIcon from "@lucide/svelte/icons/loader-circle";
  import SparklesIcon from "@lucide/svelte/icons/sparkles";
  import StethoscopeIcon from "@lucide/svelte/icons/stethoscope";
  import TriangleAlertIcon from "@lucide/svelte/icons/triangle-alert";
  import * as Alert from "$lib/components/ui/alert";
  import { Button } from "$lib/components/ui/button";
  import * as Card from "$lib/components/ui/card";
  import { Label } from "$lib/components/ui/label";
  import * as NativeSelect from "$lib/components/ui/native-select";
  import { Textarea } from "$lib/components/ui/textarea";
  import { api, type Schemas, why } from "$lib/api/client";
  import { displayLanguage, t, th, tn } from "$lib/locale";
  import { watch } from "$lib/runs/events";
  import { begun, failed, fold } from "$lib/runs/progress";
  import ManagementPlan from "$lib/plan/ManagementPlan.svelte";
  import { isPlan, PLAN } from "$lib/plan/types";
  import { outcome } from "$lib/runs/outcomes";

  type Phase = "idle" | "typing" | "running" | "reading" | "done";

  let { limit, models }: { limit: number; models: { name: string; weights: string }[] } = $props();
  let login = $state<string>();
  let text = $state("");
  // Accommodating for Python, which counts a text's code points where JavaScript counts its
  // UTF-16 units.
  const characters = $derived([...text].length);
  let configurations = $state<Schemas["Thread"][]>([]);
  let configuration = $state<number>();
  let model = $state<string>();
  let language = $state<string>();
  const languages = $derived(spoken(configurations.find((t) => t.id === configuration)));
  let phase = $state<Phase>("idle");
  let progress = $state(begun());
  const streamed = $derived(progress.items[0]?.kind ? progress.items[0] : null);
  let failure = $state<string | null>(null);
  let item = $state<Schemas["ItemDetail"] | null>(null);
  let typed: { text: string; language: string; family: number } | null = null;

  const busy = $derived(phase === "typing" || phase === "running" || phase === "reading");

  onMount(async () => {
    const [me, found] = await Promise.all([
      api.GET("/api/me"),
      api.GET("/api/threads", { params: { query: { kind: "configuration", answers: PLAN } } }),
    ]);
    if (!me.data || !found.data) {
      failure = why(me.error ?? found.error);
      return;
    }
    login = me.data.login;
    // Policy: what is out of date isn't offered, as only a researcher can update it.
    configurations = preferred(found.data.filter((c) => !c.outdated));
    model = models[0]?.name;
    configuration = configurations[0]?.id;
  });

  $effect(() => {
    if (language === undefined || !languages.includes(language)) language = languages[0];
  });

  function spoken(thread: Schemas["Thread"] | undefined): string[] {
    if (thread === undefined) return [];
    const found = [...new Set([thread.language, ...thread.translated].filter((l) => l !== null))];
    return found.length ? found : ["en"];
  }

  function named(thread: Schemas["Thread"]): string {
    const name = thread.name ?? thread.title;
    return thread.owner === login || thread.owner === null ? name : `${thread.owner}/${name}`;
  }

  function preferred(threads: Schemas["Thread"][]): Schemas["Thread"][] {
    const own = new Set(threads.filter((t) => t.owner === login).map((t) => t.name ?? t.title));
    return threads.filter((t) => t.owner === login || !own.has(t.name ?? t.title));
  }

  async function analyze(event: SubmitEvent) {
    event.preventDefault();
    if (configuration === undefined || model === undefined || language === undefined || !text.trim()) return;
    failure = null;
    item = null;
    progress = begun();
    try {
      phase = "typing";
      if (typed?.text !== text || typed.language !== language) {
        const made = await api.POST("/api/families", { body: { text, language } });
        if (!made.data) throw new Error(why(made.error));
        typed = { text, language, family: made.data.id };
      }
      phase = "running";
      const compiled = configurations.find((t) => t.id === configuration)?.head.compilation;
      const started = await api.POST("/api/runs", {
        body: {
          configuration,
          ...(compiled
            ? { parts: { model: models.find((m) => m.name === model)?.weights ?? null } }
            : { under: model }),
          families: [typed.family],
          score: false,
        },
      });
      if (!started.data) throw new Error(why(started.error));
      const run = started.data.runs[0]?.run;
      if (run === undefined) throw new Error(t("no run was started"));
      await watch(run, (name, data) => fold(progress, name, data));
      failure = failed(progress);
      phase = "reading";
      const items = await api.GET("/api/runs/{run}/items", { params: { path: { run } } });
      if (!items.data) throw new Error(why(items.error));
      item = items.data[0] ?? null;
      phase = "done";
    } catch (e) {
      failure = e instanceof Error ? e.message : String(e);
      phase = "idle";
    }
  }

  const SAYING: Record<Phase, string> = {
    idle: "",
    typing: t("Keeping the case…"),
    running: t("Waiting for the model…"),
    reading: t("Reading the answer…"),
    done: "",
  };
</script>

<div class="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
  <div class="absolute top-20 left-10 size-72 animate-floating rounded-full bg-primary/5 blur-3xl"></div>
  <div
    class="absolute right-10 bottom-20 size-96 animate-floating rounded-full bg-accent/5 blur-3xl"
    style:animation-delay="-2s"
  ></div>
</div>

<div class="relative z-10 mx-auto max-w-4xl px-4 py-10 sm:py-16">
  <header class="mb-10 animate-fade-in text-center sm:mb-14">
    <div
      class="glow-primary mb-6 inline-flex size-20 items-center justify-center rounded-3xl bg-gradient-to-br from-primary to-accent"
    >
      <StethoscopeIcon class="size-10 text-primary-foreground" />
    </div>
    <h1 class="mb-4 text-4xl font-bold tracking-tight sm:text-5xl">
      {@html th(
        '<span class="gradient-text">Emergency</span> <span class="text-foreground">Differential Diagnostics</span>',
      )}
    </h1>
    <p class="mx-auto max-w-xl text-lg leading-relaxed text-muted-foreground">
      {t("Describe the patient's symptoms and history for a differential and a management plan.")}
    </p>
  </header>

  <Alert.Root class="pane mb-8 animate-slide-up border-warning/20" style="animation-delay: 100ms">
    <TriangleAlertIcon class="text-warning" />
    <Alert.Description class="text-muted-foreground">
      <p>
        {@html th(
          '<strong class="font-semibold text-foreground">Important:</strong> for testing only. It does not replace clinical judgment or medical consultation.',
        )}
      </p>
      <p>
        {t(
          "Enter nothing that could identify a patient. De-identifying a case is the responsibility of the clinician or researcher who enters it.",
        )}
      </p>
    </Alert.Description>
  </Alert.Root>

  <Card.Root class="pane mb-8 animate-slide-up" style="animation-delay: 200ms">
    <Card.Header>
      <div class="flex items-center gap-3">
        <div class="rounded-xl bg-primary/10 p-2"><ActivityIcon class="size-5 text-primary" /></div>
        <div>
          <Card.Title class="font-display text-xl">{t("Symptoms & history")}</Card.Title>
          <Card.Description>
            {t("Current symptoms, duration, severity, and relevant medical history.")}
          </Card.Description>
        </div>
      </div>
    </Card.Header>
    <Card.Content>
      <form class="space-y-5" onsubmit={analyze}>
        <Textarea
          bind:value={text}
          aria-label={t("The case")}
          placeholder={t(
            "65-year-old man with sudden chest pain for 2 hours, radiating to the left arm, nausea, cold sweats. History of hypertension and type 2 diabetes.",
          )}
          class="min-h-40 resize-y rounded-xl bg-background/50 text-base leading-relaxed"
          disabled={busy}
        />
        {#if characters > limit}
          <p class="text-sm text-destructive">
            {tn(
              "A case holds at most %(num)s character; this one has %(given)s.",
              "A case holds at most %(num)s characters; this one has %(given)s.",
              limit,
              { num: limit, given: characters },
            )}
          </p>
        {/if}
        <div class="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div class="flex flex-col gap-4 sm:flex-row">
            <div class="grid gap-2">
              <Label for="model">{t("Model")}</Label>
              <NativeSelect.Root id="model" class="min-w-52" bind:value={model} disabled={busy}>
                {#each models as m (m.name)}
                  <NativeSelect.Option value={m.name}>{m.name}</NativeSelect.Option>
                {/each}
              </NativeSelect.Root>
            </div>
            <div class="grid gap-2">
              <Label for="configuration">{t("Configuration")}</Label>
              <NativeSelect.Root id="configuration" bind:value={configuration} disabled={busy}>
                {#each configurations as c (c.id)}
                  <NativeSelect.Option value={c.id}>{named(c)}</NativeSelect.Option>
                {/each}
              </NativeSelect.Root>
            </div>
            <div class="grid gap-2">
              <Label for="language">{t("Written in")}</Label>
              <NativeSelect.Root id="language" bind:value={language} disabled={busy}>
                {#each languages as l (l)}
                  <NativeSelect.Option value={l}>{displayLanguage(l)}</NativeSelect.Option>
                {/each}
              </NativeSelect.Root>
            </div>
          </div>
          <Button
            type="submit"
            size="lg"
            class="gap-2 rounded-xl px-6 font-semibold shadow-lg shadow-primary/20"
            disabled={busy || !text.trim() || characters > limit || configuration === undefined || model === undefined}
          >
            {#if busy}
              <LoaderCircleIcon class="animate-spin" />
              {SAYING[phase]}
            {:else}
              <SparklesIcon />
              {t("Analyze")}
            {/if}
          </Button>
        </div>
        {#if phase === "running" && streamed}
          <p class="text-sm text-muted-foreground" aria-live="polite">
            {streamed.kind === "reasoning"
              ? tn("Thinking: %(n)s token", "Thinking: %(n)s tokens", streamed.tokens, { n: streamed.tokens })
              : tn("Writing: %(n)s token", "Writing: %(n)s tokens", streamed.tokens, { n: streamed.tokens })}
          </p>
        {/if}
      </form>
    </Card.Content>
  </Card.Root>

  {#if failure}
    <Alert.Root variant="destructive" class="mb-8 rounded-2xl">
      <TriangleAlertIcon />
      <Alert.Title>{t("It didn't go through")}</Alert.Title>
      <Alert.Description>{failure}</Alert.Description>
    </Alert.Root>
  {/if}

  {#if item}
    {@const answer = item.answer}
    <div class="animate-scale-in space-y-6">
      {#if answer.value === null}
        <Alert.Root variant="destructive" class="rounded-2xl">
          <TriangleAlertIcon />
          <Alert.Title>{t("No answer to show")}</Alert.Title>
          <Alert.Description>{answer.problem ?? item.why ?? outcome(item.outcome)}</Alert.Description>
        </Alert.Root>
      {:else}
        {#if answer.problem || answer.salvaged}
          <Alert.Root class="rounded-2xl border-warning/30">
            <TriangleAlertIcon class="text-warning" />
            <Alert.Title
              >{answer.salvaged ? t("The answer was cut short") : t("The answer breaks its schema")}</Alert.Title
            >
            {#if answer.problem}<Alert.Description>{answer.problem}</Alert.Description>{/if}
          </Alert.Root>
        {/if}
        {#if typeof answer.value === "string"}
          <div class="pane rounded-2xl p-6 whitespace-pre-wrap text-muted-foreground">{answer.value}</div>
        {:else if isPlan(answer.value)}
          <ManagementPlan plan={answer.value} />
        {/if}
      {/if}
    </div>
  {/if}
</div>
