import { t } from "$lib/locale";
import type { Schema } from "$lib/schema/form";
import { choices } from "./selectors";

export type Judging = {
  digest: string;
  thread: number;
  name: string;
  owner: string | null;
  output_schema: Schema | null;
  weights: string | null;
};
export type Serving = { name: string; weights: string };
export type JudgeChoice = {
  digest: string;
  thread: number;
  name: string;
  owner: string | null;
  configuration: string;
  model: string | null;
  seeds: number[];
  output_schema: Schema | null;
};
export type Option = { key: string; value: string; label: string };
export type Holding = { skeleton: string; configuration: string; weights: string; handle: string | null };

export function configurationChoices(judging: Judging[], me: string, held: Holding | null = null): Option[] {
  const listed = judging.map((j) => ({
    key: String(j.thread),
    value: j.digest,
    label: (j.owner && j.owner !== me ? `${j.owner}/` : "") + j.name,
  }));
  if (!held || listed.some((c) => c.value === held.skeleton)) return listed;
  return [
    {
      key: "held",
      value: held.skeleton,
      label: t("%(configuration)s, as it is asked now", { configuration: held.configuration }),
    },
    ...listed,
  ];
}

export function modelChoices(models: Serving[], held: Holding | null = null): Option[] {
  const listed = models.map((m) => ({ key: m.name, value: m.weights, label: m.name }));
  if (!held || listed.some((c) => c.value === held.weights)) return listed;
  const label = held.handle
    ? t("%(handle)s, the weights it holds", { handle: held.handle })
    : t("the weights it holds");
  return [{ key: "held", value: held.weights, label }, ...listed];
}

export function madeFor(judging: Judging[], models: Serving[]): Record<string, string> {
  const offered = new Set(models.map((m) => m.weights));
  return Object.fromEntries(
    judging.flatMap((j) => (j.weights && offered.has(j.weights) ? [[j.digest, j.weights]] : [])),
  );
}

// Policy: seeds are read from what is typed, whatever it is, so that nothing typed is
// refused: each whole number once, and the seed 1 while none is typed.
export function seedsOf(text: string): number[] {
  const seeds = [...new Set((text.match(/\d+/g) ?? []).map(Number))];
  return seeds.length ? seeds : [1];
}

export function verdictAt(schema: Schema | null): string[] {
  return choices(schema, null, "")
    .filter((c) => c.selector.startsWith("/"))
    .map((c) => c.selector);
}

function field(schema: Schema | null, at: string): Schema | null {
  const name = at.slice(1).split("/")[0] ?? "";
  const properties = schema?.properties;
  if (typeof properties !== "object" || properties === null) return null;
  const found = (properties as Record<string, unknown>)[name];
  return typeof found === "object" && found !== null ? (found as Schema) : null;
}

// Policy: starting params for a judged view: its verdict at the judge's first field that isn't text, and, when the
// metric takes a most, that field's maximum.
export function startingParams(params: Schema, schema: Schema | null): Record<string, unknown> {
  const wanted = typeof params.properties === "object" && params.properties !== null ? params.properties : {};
  const found: Record<string, unknown> = {};
  const at = verdictAt(schema).find((a) => field(schema, a)?.type !== "string" && !a.slice(1).includes("/"));
  if ("at" in wanted && at) found.at = at;
  if ("max" in wanted) {
    const most = at ? field(schema, at)?.maximum : undefined;
    found.max = typeof most === "number" && most > 0 ? most : 1;
  }
  return found;
}
