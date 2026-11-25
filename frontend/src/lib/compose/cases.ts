export type Listed = { family: number; name: string; tags: string[]; language: string | null };

export type Group = { by: "all" | "tag" | "language"; value: string | null; families: number[] };

export function groups(cases: Listed[]): Group[] {
  const by = (key: "tag" | "language", values: (c: Listed) => string[]): Group[] => {
    const found = new Map<string, number[]>();
    for (const c of cases) for (const v of values(c)) found.set(v, [...(found.get(v) ?? []), c.family]);
    return [...found.keys()].sort().map((value) => ({ by: key, value, families: found.get(value) ?? [] }));
  };
  return [
    { by: "all", value: null, families: cases.map((c) => c.family) },
    ...by("tag", (c) => c.tags),
    ...by("language", (c) => (c.language ? [c.language] : [])),
  ];
}

export function holds(chosen: number[], group: Group): boolean {
  return group.families.length > 0 && group.families.every((f) => chosen.includes(f));
}

// Policy: a group picked whole is let go whole; otherwise each of it is picked, keeping what else is.
export function toggled(chosen: number[], group: Group): number[] {
  if (holds(chosen, group)) return chosen.filter((f) => !group.families.includes(f));
  return [...chosen, ...group.families.filter((f) => !chosen.includes(f))];
}
