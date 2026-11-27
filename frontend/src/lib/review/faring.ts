import { type Schemas, why } from "$lib/api/client";
import { displayLanguage, t } from "$lib/locale";

type Fared = Schemas["Fared"];
type Row = Schemas["FaredRow"];
type Behind = Schemas["FaredBehind"];
type Shown = Schemas["FaredShown"];

export type Group = { field: string | null; metrics: { at: number; rows: Row[] }[] };
export type Bin = { at: number; run: number; drawn: number; cases: number[] };

// Policy: so many bins between 0 and 1, so that a mean of four replicates falls on one of its own.
export const BINS = 20;

export function grouped(fared: Fared): Group[] {
  const found: Group[] = [];
  fared.metrics.forEach((metric, at) => {
    const rows = fared.rows.filter((r) => r.metric === at);
    if (!rows.length) return;
    let group = found.find((g) => g.field === metric.field);
    if (!group) found.push((group = { field: metric.field, metrics: [] }));
    group.metrics.push({ at, rows });
  });
  return found;
}

export function binned(row: Row): Bin[] {
  const bins = new Map<number, Bin>();
  row.values.forEach((value, i) => {
    const at = Math.round(Math.min(1, Math.max(0, value)) * BINS);
    const bin = bins.get(at) ?? { at, run: 0, drawn: 0, cases: [] };
    if (row.synthetic[i]) bin.drawn++;
    else bin.run++;
    bin.cases.push(row.cases[i] ?? i);
    bins.set(at, bin);
  });
  return [...bins.values()].sort((a, b) => a.at - b.at);
}

// Policy: the share of the other cases below this one, a tie counting as half, so that a case among equals sits mid-way.
export function below(row: Row): number {
  if (!row.shown || !row.values.length) return 0;
  const value = row.shown.value;
  const under = row.values.reduce((n, v) => n + (v < value ? 1 : v === value ? 0.5 : 0), 0);
  return under / row.values.length;
}

export function said(behind: Behind): string {
  switch (behind.why) {
    case "under_way":
      return t("under way");
    case "outdated":
      return `${t("out of date")}: ${t("update it on its page")}`;
    case "untranslated":
      return t("no translation into %(language)s", { language: displayLanguage(behind.language ?? "") });
    case "refused":
      return why(behind.refusal);
    case "no_runs":
      return t("it has no runs of the case yet");
    case "not_whole":
      return t("its latest runs of the case aren't three replicates and a repeat");
    case "changed":
      return t("its configuration has changed since it ran");
    case "halted":
      return t("it was halted before it finished");
    case "unfinished":
      return t("it stopped before it finished");
    case "unscored":
      return t("it isn't scored against the expectation as it is");
  }
}

export type Tick = { value: number; href: string | null; n: number; offset: number };

// Policy: replicates of a value side by side, so that four alike on a metric that scores 0 or 1 show as four.
export function ticks(shown: Shown): Tick[] {
  const found: Tick[] = [];
  const alike = new Map<number, number>();
  shown.replicates.forEach((r, i) => {
    if (r.value === null) return;
    alike.set(r.value, (alike.get(r.value) ?? 0) + 1);
    found.push({ value: r.value, href: r.href, n: i + 1, offset: 0 });
  });
  const placed = new Map<number, number>();
  for (const tick of found) {
    const k = placed.get(tick.value) ?? 0;
    placed.set(tick.value, k + 1);
    tick.offset = k - ((alike.get(tick.value) ?? 1) - 1) / 2;
  }
  return found;
}
