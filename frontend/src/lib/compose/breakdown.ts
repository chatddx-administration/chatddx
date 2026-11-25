import type { Schemas } from "$lib/api/client";
import { displayLanguage, tn } from "$lib/locale";

type Broken = Schemas["Broken"];
type Gathering = Schemas["BrokenGathering"];
type Point = Schemas["BrokenPoint"];

export type Group = { field: string | null; views: number[] };

export function grouped(broken: Broken): Group[] {
  const found: Group[] = [];
  broken.views.forEach((view, at) => {
    let group = found.find((g) => g.field === view.field);
    if (!group) found.push((group = { field: view.field, views: [] }));
    group.views.push(at);
  });
  return found;
}

export function named(gathering: Gathering): string {
  return `v${gathering.point.version}`;
}

// Policy: a gathering's cases scatter across a third of its column in a fixed pattern, so that cases on one value
// stay apart and the scatter stays put between reads.
export function scattered(n: number): number[] {
  return Array.from({ length: n }, (_, k) => (((k * 3) % 7) - 3) / 18);
}

export function estimated(gathering: Gathering, view: number): string {
  const e = gathering.estimates[view];
  const said = e
    ? `${named(gathering)}: ${e.mean.toFixed(2)}${e.half === null ? "" : ` ±${e.half.toFixed(2)}`} (n=${e.n})`
    : `${named(gathering)}: —`;
  const d = gathering.paired[view];
  return d ? `${said}, Δ ${differs(d)}` : said;
}

export function unanswered(point: Point, of: number): string | null {
  if (!point.missing) return null;
  return tn("%(missing)s of %(of)s case unanswered", "%(missing)s of %(of)s cases unanswered", of, {
    missing: point.missing,
    of,
  });
}

export function differs(d: Schemas["Estimated"]): string {
  return `${d.mean >= 0 ? "+" : "−"}${Math.abs(d.mean).toFixed(2)} (n=${d.n})`;
}

export function languages(point: Point): string {
  return point.languages.map((l) => `${l.language === null ? "—" : displayLanguage(l.language)} ${l.cases}`).join(", ");
}

export function mean(values: (number | null)[]): number | null {
  const held = values.filter((v): v is number => v !== null);
  return held.length ? held.reduce((a, b) => a + b, 0) / held.length : null;
}
