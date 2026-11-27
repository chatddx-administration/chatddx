import type { Schemas } from "$lib/api/client";
import type { Body } from "./drafting";
import type { Facts } from "./props";

export type Saving =
  | { to: "nothing"; because: "nameless" | "unchanged" }
  | { to: "version"; version: number; from: number | null }
  | { to: "fork"; namesakes: number };

export function whereSaveGoes(given: {
  name: string;
  configuration: Schemas["ThreadDetail"];
  me: string;
  versions: number;
  version: number;
  latest: boolean;
  changed: boolean;
  configurations: Schemas["Thread"][];
}): Saving {
  const name = given.name.trim();
  if (!name) return { to: "nothing", because: "nameless" };
  const own = given.configuration.owner === given.me;
  const same = name === (given.configuration.name ?? given.configuration.title);
  // Policy: an earlier version saved is brought back as the latest, rather than forked, as going back is what saving
  // one is for here; unchanged, it stays the version it was, versions being numbered by what they hold.
  if (own && same) {
    const from = given.latest ? null : given.version;
    if (!given.changed)
      return from === null ? { to: "nothing", because: "unchanged" } : { to: "version", version: from, from };
    return { to: "version", version: given.versions + 1, from };
  }
  const namesakes = given.configurations.filter((t) => t.owner === given.me && (t.name ?? t.title) === name).length;
  return { to: "fork", namesakes };
}

type Fitted = { reasoning: Body | null; sampling: Body };

// Dependency: src/chatddx/factors/request.py:landings, which a level the facts don't land, a budget they don't know
// and a sampling they recommend nothing of at the level followed refuse.
export function fitted(reasoning: Body | null, sampling: Body, facts: Facts | null): Fitted {
  const lands = (level: unknown): boolean => facts?.levels[String(level)]?.lands != null;
  let held = reasoning;
  if (held?.level != null && !lands(held.level)) {
    const { level: _, ...rest } = held;
    held = lands("default") ? { ...rest, level: "default" } : null;
  }
  if (held?.level != null && held.thinking_token_budget != null && facts?.budget !== true) {
    const { thinking_token_budget: _, ...rest } = held;
    held = rest;
  }
  const followed = facts?.levels[String(held?.level ?? "default")]?.lands ?? facts?.levels.default?.lands;
  if (!sampling.recommended || (followed != null && facts?.recommended[followed])) return { reasoning: held, sampling };
  const { recommended: _, ...rest } = sampling;
  return { reasoning: held, sampling: rest };
}
