import type { Schemas } from "$lib/api/client";

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
