<script lang="ts">
  import { type Snippet, untrack } from "svelte";
  import type { Schemas } from "$lib/api/client";
  import { t, tn, tp, upFirst } from "$lib/locale";
  import type { Schema } from "$lib/schema/form";
  import { FIELD } from "$lib/utils";
  import JudgeEditor from "./JudgeEditor.svelte";
  import { type JudgeChoice, type Judging, type Serving, startingParams, verdictAt } from "./judging";
  import type { ScorerView } from "./scorers";
  import type { Choice } from "./selectors";
  import SelectorPicker from "./SelectorPicker.svelte";

  let {
    views = $bindable(),
    labels = $bindable(),
    judges = $bindable(),
    metrics,
    asked,
    answered,
    titles,
    judging,
    models,
    me,
    inline,
    below,
  }: {
    views: ScorerView[];
    labels: string[];
    judges: JudgeChoice[];
    metrics: Schemas["Metric"][];
    asked: Choice[];
    answered: Choice[];
    titles: Record<string, string>;
    judging: Judging[];
    models: Serving[];
    me: string;
    inline?: Snippet<[number]>;
    below?: Snippet<[ScorerView, number, JudgeChoice | undefined]>;
  } = $props();
  const known = new Map(untrack(() => metrics).map((m) => [m.name, m]));
  const unjudged = untrack(() => metrics).filter((m) => !m.judged);
  const named: Record<string, string> = { at: t("Verdict at"), max: t("Out of") };

  let writing = $state<number | null>(null);

  function added(): void {
    views.push({ metric: unjudged[0]?.name ?? "", expectation: "", output: "" });
    labels.push(t("view %(n)s", { n: labels.length }));
  }

  function described(j: JudgeChoice): string {
    const given = {
      judge: (j.owner && j.owner !== me ? `${j.owner}/` : "") + j.name,
      configuration: j.configuration,
      model: j.model ?? "",
      seeds: tn("%(num)s seed", "%(num)s seeds", j.seeds.length, { num: j.seeds.length }),
    };
    return j.model
      ? t("%(judge)s: %(configuration)s under %(model)s, %(seeds)s", given)
      : t("%(judge)s: %(configuration)s, %(seeds)s", given);
  }

  function moved(at: number, by: number): void {
    const to = at + by;
    const [view] = views.splice(at, 1);
    const [label] = labels.splice(at, 1);
    if (view === undefined || label === undefined) return;
    views.splice(to, 0, view);
    labels.splice(to, 0, label);
  }

  function dropped(at: number): void {
    views.splice(at, 1);
    labels.splice(at, 1);
  }

  function judgeOf(view: ScorerView): JudgeChoice | undefined {
    return judges.find((j) => j.digest === view.judge);
  }

  function metricked(view: ScorerView, name: string): void {
    const metric = known.get(name);
    view.metric = name;
    if (!metric?.judged) {
      view.judge = null;
      view.params = {};
      return;
    }
    judged(view, judgeOf(view) ?? judges[0]);
  }

  function judged(view: ScorerView, judge: JudgeChoice | undefined): void {
    view.judge = judge?.digest ?? null;
    const params = known.get(view.metric)?.params ?? {};
    view.params = startingParams(params, judge?.output_schema ?? null);
  }

  function takes(view: ScorerView, param: string): boolean {
    const properties = known.get(view.metric)?.params?.properties;
    return typeof properties === "object" && properties !== null && param in properties;
  }

  function points(view: ScorerView): [string, Schema][] {
    const params = known.get(view.metric)?.params?.properties;
    if (typeof params !== "object" || params === null) return [];
    return Object.entries(params as Record<string, Schema>).filter(([name]) => name !== "at");
  }
</script>

<ol class="space-y-2">
  {#each views as view, at (at)}
    {@const metric = known.get(view.metric)}
    {@const judge = judgeOf(view)}
    <li class="space-y-2 rounded-lg border border-border/60 bg-background/60 p-2.5">
      <div class="flex items-center gap-2">
        <input class="{FIELD} min-w-0 flex-1 font-medium" aria-label={t("Label")} bind:value={labels[at]} />
        <button
          type="button"
          class="rounded px-1.5 hover:bg-muted disabled:opacity-40"
          aria-label={t("Move it up")}
          disabled={at === 0}
          onclick={() => moved(at, -1)}>↑</button
        >
        <button
          type="button"
          class="rounded px-1.5 hover:bg-muted disabled:opacity-40"
          aria-label={t("Move it down")}
          disabled={at === views.length - 1}
          onclick={() => moved(at, 1)}>↓</button
        >
        <button
          type="button"
          class="rounded px-1.5 hover:bg-muted disabled:opacity-40"
          aria-label={t("Leave it out")}
          disabled={views.length === 1}
          onclick={() => dropped(at)}>×</button
        >
      </div>
      <div class="grid gap-2 sm:grid-cols-2">
        <SelectorPicker
          choices={asked}
          value={view.expectation ?? ""}
          set={(v) => (view.expectation = v)}
          label={t("Reads of what is expected")}
        />
        <div class="grid content-start gap-1">
          <SelectorPicker
            choices={answered}
            value={view.output ?? ""}
            set={(v) => (view.output = v)}
            label={t("Reads of the answer")}
          />
          <label class="flex items-center gap-2">
            <input
              type="checkbox"
              checked={view.split === "lines@1"}
              onchange={(e) => (view.split = e.currentTarget.checked ? "lines@1" : null)}
            />
            {t("line by line, as a list")}
          </label>
        </div>
      </div>
      <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span class="flex items-center gap-2">
          <span class="text-muted-foreground" aria-hidden="true">{t("Compared by")}</span>
          <select
            aria-label={t("Compared by")}
            class={FIELD}
            title={metric?.measures ?? ""}
            value={view.metric}
            onchange={(e) => metricked(view, e.currentTarget.value)}
          >
            {#each metrics as m (m.name)}
              <option value={m.name} title={m.measures}
                >{m.judged
                  ? t("%(metric)s, by a judge", { metric: m.name.replaceAll("_", " ") })
                  : m.name.replaceAll("_", " ")}</option
              >
            {/each}
          </select>
        </span>
        {#if metric?.judged}
          <span class="flex items-center gap-2">
            <span class="text-muted-foreground" aria-hidden="true">{t("Judge")}</span>
            <select
              aria-label={t("Judge")}
              class="{FIELD} max-w-56"
              value={writing === at ? "new" : (view.judge ?? "")}
              onchange={(e) => {
                const picked = e.currentTarget.value;
                if (picked === "new") writing = at;
                else {
                  writing = null;
                  judged(
                    view,
                    judges.find((j) => j.digest === picked),
                  );
                }
              }}
            >
              {#if !judge && view.judge}<option value={view.judge}>{titles[view.judge] ?? t("its judge")}</option>{/if}
              {#each judges as j (j.thread)}
                <option value={j.digest}>{described(j)}</option>
              {/each}
              <option value="new">{t("a new judge")}…</option>
            </select>
          </span>
        {/if}
        {#if metric?.judged && judge}
          {#if takes(view, "at")}
            <span class="min-w-48">
              <SelectorPicker
                choices={verdictAt(judge.output_schema).map((p) => ({
                  label: p.slice(1).replaceAll("/", " › ").replaceAll("_", " "),
                  selector: p,
                }))}
                value={typeof view.params?.at === "string" ? view.params.at : ""}
                set={(v) => (view.params = { ...view.params, at: v })}
                label={named.at ?? tp("a verdict", "at")}
              />
            </span>
          {/if}
          {#each points(view) as [name, param] (name)}
            <label class="flex items-center gap-2">
              <span class="text-muted-foreground">{named[name] ?? name.replaceAll("_", " ")}</span>
              <input
                type="number"
                step={param.type === "integer" ? 1 : "any"}
                class="{FIELD} w-20"
                value={typeof view.params?.[name] === "number" ? view.params[name] : ""}
                oninput={(e) => (view.params = { ...view.params, [name]: Number(e.currentTarget.value) })}
              />
            </label>
          {/each}
        {/if}
        {@render inline?.(at)}
      </div>
      {#if writing === at}
        <section
          class="space-y-2 rounded-lg border border-dashed border-border p-2.5"
          aria-label={upFirst(t("a new judge"))}
        >
          <div class="flex items-center gap-2">
            <p class="text-sm font-medium">{upFirst(t("a new judge"))}</p>
            <button
              type="button"
              class="ml-auto rounded-md border border-border px-3 py-1 hover:bg-muted"
              onclick={() => (writing = null)}>{t("Not now")}</button
            >
          </div>
          <JudgeEditor
            editor={{
              kind: "judge",
              mode: "new",
              name: "",
              body: null,
              configuration: null,
              handle: null,
              problem: null,
              judging,
              models,
              me,
            }}
            made={(j) => {
              judges.push(j);
              writing = null;
              judged(view, j);
            }}
          />
        </section>
      {/if}
      {#if metric?.judged && view.judge}
        {@render below?.(view, at, judge)}
      {/if}
    </li>
  {/each}
</ol>
<button
  type="button"
  class="mt-2 rounded-full border border-dashed border-border px-2.5 py-0.5 text-muted-foreground hover:bg-muted"
  onclick={added}>+ {t("a view")}</button
>
