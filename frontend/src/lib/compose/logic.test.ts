import { describe, expect, it } from "vitest";
import type { Schemas } from "$lib/api/client";
import { whereSaveGoes } from "./logic";

const DIGEST = (n: number) => `sha256:${String(n).padStart(64, "0")}`;

function thread(id: number, name: string | null, owner: string | null, digest: string): Schemas["Thread"] {
  return {
    id,
    kind: "chunk.reasoning",
    word: "reasoning",
    name,
    title: name ?? `untitled ${id}`,
    owner,
    tags: [],
    language: null,
    translated: [],
    head: {
      id: id * 10,
      digest,
      compilation: null,
      based_on: null,
      by: owner ?? "nobody",
      at: "2026-10-13T12:00:00Z",
      labels: null,
    },
    outdated: false,
  };
}

describe("where a save goes", () => {
  const configuration = (owner: string, name: string | null): Schemas["ThreadDetail"] => ({
    ...thread(1, name, owner, DIGEST(1)),
    kind: "skeleton",
    word: "configuration",
    description: null,
    collaborators: [],
    forked_from: null,
    recipe: null,
    deleted: false,
  });
  const configurations = [thread(1, "plan", "alice", DIGEST(1)), thread(2, "terse", "alice", DIGEST(2))];
  const given = {
    name: "plan",
    configuration: configuration("alice", "plan"),
    me: "alice",
    versions: 2,
    latest: true,
    changed: true,
    configurations,
  };

  it("is a new version of the person's own, on its latest version and under its name", () => {
    expect(whereSaveGoes(given)).toEqual({ to: "version", version: 3, restoring: false });
    expect(whereSaveGoes({ ...given, name: "  plan " })).toEqual({ to: "version", version: 3, restoring: false });
    expect(whereSaveGoes({ ...given, changed: false })).toEqual({ to: "nothing", because: "unchanged" });
  });

  it("brings an earlier version of the person's own back as the latest, changed or not", () => {
    const back = { to: "version", version: 3, restoring: true };
    expect(whereSaveGoes({ ...given, latest: false })).toEqual(back);
    expect(whereSaveGoes({ ...given, latest: false, changed: false })).toEqual(back);
    expect(whereSaveGoes({ ...given, latest: false, name: "fresh" })).toEqual({ to: "fork", namesakes: 0 });
  });

  it("is a fork otherwise, counting the person's own of that name", () => {
    expect(whereSaveGoes({ ...given, name: "terse" })).toEqual({ to: "fork", namesakes: 1 });
    expect(whereSaveGoes({ ...given, name: "fresh" })).toEqual({ to: "fork", namesakes: 0 });
    const others = { ...given, configuration: configuration("archive", "plan"), changed: false };
    expect(whereSaveGoes(others)).toEqual({ to: "fork", namesakes: 1 });
  });

  it("is nowhere without a name", () => {
    expect(whereSaveGoes({ ...given, name: "  " })).toEqual({ to: "nothing", because: "nameless" });
  });
});
