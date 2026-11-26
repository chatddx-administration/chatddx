<script lang="ts">
  import LoaderCircleIcon from "@lucide/svelte/icons/loader-circle";
  import RefreshCwIcon from "@lucide/svelte/icons/refresh-cw";
  import XIcon from "@lucide/svelte/icons/x";
  import { untrack } from "svelte";
  import { api, type Schemas, why } from "$lib/api/client";
  import { worded } from "$lib/kinds";
  import { displayLanguage, t, tp, upFirst } from "$lib/locale";
  import { SLOTS } from "$lib/scorer/texts";
  import { lines, overlaid, type Piece, pretty, read, type Row, rows } from "./diffing";
  import { same } from "./drafting";
  import type { Asked, Sending } from "./sending.svelte";

  let { thread, own, sending }: { thread: number; own: string | null; sending: Sending } = $props();

  type Previewed = Schemas["Previewed"];

  let got = $state<Previewed | null>(null);
  // Policy: what it sends is marked against what the version drafted on sends in the same language, saved; saving
  // makes the next of them.
  let saved = $state<Record<string, Previewed>>({});
  let sent = $state<Asked | null>(null);
  let problem = $state<string | null>(null);
  let loading = $state(false);
  let raw = $state(false);
  let asked = 0;

  const changed = $derived(sent === null || !same(sending.current(), sent));
  const language = $derived(sending.language ?? own);

  const against = $derived(got === null || sent === null ? null : (saved[sent.language ?? ""] ?? null));
  const saidRun = (r: Schemas["Stretch"]) => read(r, SLOTS, (n) => t("appendix %(n)s", { n }));
  const said = (m: Schemas["PreviewMessage"]) => m.runs.map(saidRun).join("");
  const marked = $derived(
    got === null || against === null || same(got.request, against.request)
      ? null
      : { messages: rows(against.messages, got.messages, said), body: lines(against.request, got.request) },
  );

  async function compiled(body: Asked): Promise<Previewed | string> {
    const res = await api.POST("/api/threads/{thread}/previews", { params: { path: { thread } }, body });
    return res.data ?? why(res.error);
  }

  async function update(): Promise<void> {
    const now = ++asked;
    const body = sending.current();
    const key = body.language ?? "";
    loading = true;
    const [drafted, kept] = await Promise.all([
      compiled(body),
      saved[key] ?? compiled({ head: body.head, ...(body.language ? { language: body.language } : {}) }),
    ]);
    if (now !== asked) return;
    loading = false;
    sent = body;
    if (typeof kept !== "string") saved[key] = kept;
    if (typeof drafted !== "string") {
      got = drafted;
      problem = null;
    } else problem = drafted;
  }

  function settled(before: Record<string, unknown>, after: Record<string, unknown>): [string, Piece[]][] {
    const keys = [...Object.keys(after), ...Object.keys(before).filter((k) => !(k in after))];
    return keys
      .filter((k) => !OWN.has(k))
      .map((k) => {
        const was = k in before ? shown(before[k]) : null;
        const now = k in after ? shown(after[k]) : null;
        if (was === now) return [k, [{ value: now ?? "", added: false, removed: false }]];
        return [
          k,
          [
            ...(was === null ? [] : [{ value: was, added: false, removed: true }]),
            ...(now === null ? [] : [{ value: now, added: true, removed: false }]),
          ],
        ];
      });
  }

  // Policy: besides Update, it compiles as it opens on nothing compiled, and as it shows another language's tab than it
  // was compiled in, as it would show nothing or another language otherwise.
  $effect(() => {
    if (!sending.open) return;
    const shown = sending.language;
    if (untrack(() => sent === null || (sent.language ?? null) !== shown)) void untrack(update);
  });

  const ORIGINS: Record<string, () => string> = {
    instructions: () => worded("instructions"),
    few_shot: () => worded("few_shot"),
    prompt: () => worded("prompt"),
    output_guidance: () => t("Output guidance"),
    output_schema: () => upFirst(t("the answer's schema")),
    tool_guidance: () => t("Tool guidance"),
    appendix_layout: () => t("How appendices are laid out"),
    joining: () => t("Put between them as it is compiled"),
  };
  // Policy: what a message holds of its own part stands unmarked, what is put into it is tinted.
  const TINTS: Record<string, string> = {
    output_guidance: "bg-primary/10",
    output_schema: "bg-primary/10",
    tool_guidance: "bg-success/15",
    appendix_layout: "bg-muted",
    joining: "bg-muted",
  };
  const OWN = new Set(["messages", "tools", "tool_choice", "response_format"]);

  function origin(name: string | null | undefined): string {
    return name ? (ORIGINS[name]?.() ?? name) : "";
  }

  function answered(contract: Record<string, unknown>): string {
    if (contract.kind === "native") return t("As JSON to its schema, which response_format holds.");
    if (contract.kind === "tool")
      return t("As a call to %(name)s, its schema the tool's parameters.", { name: String(contract.name) });
    if (contract.json_schema) return t("As text, its schema told where it is inserted.");
    return `${upFirst(t("as text"))}.`;
  }

  function offered(request: Record<string, unknown>, contract: Record<string, unknown>): string[] {
    const tools = Array.isArray(request.tools) ? request.tools : [];
    return tools
      .map((tool) => String((tool as { function?: { name?: unknown } }).function?.name ?? ""))
      .filter((n) => n && !(contract.kind === "tool" && n === contract.name));
  }

  function shown(value: unknown): string {
    return typeof value === "string" ? value : JSON.stringify(value);
  }
</script>

{#snippet stretch(r: Schemas["Stretch"], text: string, added: boolean)}{#if r.slot}<span
      class="rounded-full bg-primary/10 px-1.5 text-primary">‹{SLOTS[r.slot] ?? r.slot}›</span
    >{:else if r.appendix}<span class="rounded-full bg-primary/10 px-1.5 text-primary"
      >‹{t("appendix %(n)s", { n: r.appendix })}›</span
    >{:else}<span
      class="{TINTS[r.origin ?? ''] ?? ''} {r.untranslated ? 'underline decoration-warning decoration-wavy' : ''} {added
        ? 'bg-success/15 text-success'
        : ''}"
      title={r.untranslated ? t("%(part)s, not yet translated", { part: origin(r.origin) }) : origin(r.origin)}
      >{#if added}<ins class="no-underline">{text}</ins>{:else}{text}{/if}</span
    >{/if}{/snippet}

{#snippet piece(p: Piece)}{#if p.added}<ins class="bg-success/15 text-success no-underline">{p.value}</ins
    >{:else if p.removed}<del class="bg-destructive/10 text-destructive">{p.value}</del>{:else}{p.value}{/if}{/snippet}

<div class="flex h-full flex-col">
  <header class="border-b border-border/60 px-4 pt-3 pb-2">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-base font-semibold">{t("What it sends")}</h2>
        <p class="text-xs text-muted-foreground">
          {language ? displayLanguage(language) : t("As written")}
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-2">
        <button
          type="button"
          class="small"
          disabled={loading || !changed}
          title={t("Compiles it again as it is written now, saved or not")}
          onclick={update}
        >
          {#if loading}<LoaderCircleIcon class="size-4 animate-spin" />{:else}<RefreshCwIcon class="size-4" />{/if}
          {t("Update")}
        </button>
        <button type="button" class="icon" aria-label={t("Close")} title={t("Close")} onclick={() => sending.close()}>
          <XIcon class="size-4" />
        </button>
      </div>
    </div>
    {#if got}
      <nav class="mt-2 flex gap-1 text-xs" aria-label={t("Views")}>
        <button
          type="button"
          class="rounded-md px-2 py-0.5 {raw ? '' : 'bg-muted font-medium'}"
          aria-current={raw ? undefined : "page"}
          onclick={() => (raw = false)}>{t("As read")}</button
        >
        <button
          type="button"
          class="rounded-md px-2 py-0.5 {raw ? 'bg-muted font-medium' : ''}"
          aria-current={raw ? "page" : undefined}
          onclick={() => (raw = true)}>{t("As sent")}</button
        >
      </nav>
    {/if}
  </header>

  <div class="min-h-0 flex-1 overflow-y-auto px-4 py-3 text-sm">
    {#if problem}<p role="alert" class="mb-3 text-destructive">{problem}</p>{/if}
    {#if got === null}
      {#if !problem}<p class="text-muted-foreground">
          {t("Update compiles it as it is written now, saved or not.")}
        </p>{/if}
    {:else}
      <div class={problem ? "opacity-50" : ""} data-preview>
        {#if raw}
          {#if marked}
            <pre
              class="overflow-x-auto rounded-md bg-muted/40 p-2 text-xs">{#each marked.body as p, i (i)}{@render piece(
                  p,
                )}{/each}</pre>
          {:else}
            <pre class="rounded-md bg-muted/40 p-2 text-xs break-all whitespace-pre-wrap">{JSON.stringify(
                got.request,
                null,
                2,
              )}</pre>
          {/if}
        {:else}
          <ol class="space-y-3">
            {#each marked?.messages ?? got.messages.map((message): Row => ({ was: "same", message })) as row, i (i)}
              {@const role = row.message.role}
              <li>
                <p class="mb-0.5 text-[0.7rem] tracking-wide text-muted-foreground uppercase">
                  {role}{#if row.was === "added"}, <span class="text-success normal-case">{tp("change", "added")}</span
                    >{:else if row.was === "removed"}, <span class="text-destructive normal-case"
                      >{tp("change", "removed")}</span
                    >{/if}
                </p>
                <p
                  class="rounded-md border px-2 py-1 whitespace-pre-wrap {row.was === 'added'
                    ? 'border-success/60'
                    : row.was === 'removed'
                      ? 'border-destructive/60 line-through opacity-70'
                      : 'border-border/60'}"
                >
                  {#if row.was === "changed"}{#each overlaid(row.message.runs, row.words, saidRun) as o, at (at)}{#if "removed" in o}<del
                          class="bg-destructive/10 text-destructive">{o.removed}</del
                        >{:else}{@render stretch(
                          o.run,
                          o.text,
                          o.added,
                        )}{/if}{/each}{:else}{#each row.message.runs as r, at (at)}{@render stretch(
                        r,
                        r.text ?? "",
                        false,
                      )}{/each}{/if}
                </p>
              </li>
            {/each}
          </ol>
          {@const request = got.request as Record<string, unknown>}
          {@const contract = got.contract as Record<string, unknown>}
          {@const tools = offered(request, contract)}
          <dl class="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-xs">
            {#each settled((against?.request as Record<string, unknown> | undefined) ?? request, request) as [k, ps] (k)}
              <dt class="text-muted-foreground">{k}</dt>
              <dd class="break-all">
                {#each ps as p, at (at)}{#if at}{" → "}{/if}{@render piece(p)}{/each}
              </dd>
            {/each}
            {#if tools.length}
              <dt class="text-muted-foreground">{t("Tools offered")}</dt>
              <dd>{tools.join(", ")}</dd>
            {/if}
            <dt class="text-muted-foreground">{upFirst(t("the answer"))}</dt>
            <dd>{answered(contract)}</dd>
          </dl>
        {/if}
      </div>
    {/if}
  </div>
</div>
