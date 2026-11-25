import type { Schemas } from "$lib/api/client";

export type Saving =
  | { to: "nothing"; because: "nameless" | "unchanged" }
  | { to: "version"; version: number; restoring: boolean }
  | { to: "fork"; namesakes: number };

export function whereSaveGoes(given: {
  name: string;
  configuration: Schemas["ThreadDetail"];
  me: string;
  versions: number;
  latest: boolean;
  changed: boolean;
  configurations: Schemas["Thread"][];
}): Saving {
  const name = given.name.trim();
  if (!name) return { to: "nothing", because: "nameless" };
  const own = given.configuration.owner === given.me;
  const same = name === (given.configuration.name ?? given.configuration.title);
  // Policy: an earlier version saved is brought back as the latest, rather than forked, as going back is what saving
  // one is for here.
  if (own && same) {
    if (!given.latest) return { to: "version", version: given.versions + 1, restoring: true };
    return given.changed
      ? { to: "version", version: given.versions + 1, restoring: false }
      : { to: "nothing", because: "unchanged" };
  }
  const namesakes = given.configurations.filter((t) => t.owner === given.me && (t.name ?? t.title) === name).length;
  return { to: "fork", namesakes };
}
