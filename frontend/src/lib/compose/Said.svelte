<script lang="ts">
  import { displayLanguage, t, upFirst } from "$lib/locale";

  let {
    language,
    text,
    value,
    waiting,
    stale,
    also,
    translate,
    settle,
  }: {
    language: string;
    text: string;
    value: string;
    waiting: boolean;
    stale: boolean;
    also: string[];
    translate: (language: string, text: string, said: string) => void;
    settle: (language: string, text: string) => void;
  } = $props();
</script>

<div class="grid content-start gap-1">
  <textarea
    class="w-full rounded-md border bg-transparent px-2 py-1 [field-sizing:content] {stale
      ? 'border-warning'
      : 'border-input'}"
    rows="1"
    aria-label={t("Into %(language)s: %(text)s", { language: displayLanguage(language), text })}
    placeholder={text}
    readonly={waiting}
    {value}
    oninput={(e) => translate(language, text, e.currentTarget.value)}></textarea>
  {#if stale}
    <p class="text-xs text-warning">
      {upFirst(t("out of date"))}.
      <button type="button" class="underline" onclick={() => settle(language, text)}>{t("It still reads right")}</button
      >
    </p>
  {/if}
  {#if also.length}
    <p class="text-xs text-muted-foreground">{t("Shared with %(parts)s.", { parts: also.join(", ") })}</p>
  {/if}
</div>
