import { describe, expect, it } from "vitest";
import { groups, holds, toggled } from "./cases";

const CASES = [
  { family: 1, name: "akm-01", tags: ["akm"], language: "sv" },
  { family: 2, name: "dutch-01", tags: ["dutch", "copd"], language: "nl" },
  { family: 3, name: "dutch-02", tags: ["dutch"], language: "nl" },
  { family: 4, name: "oddx-01", tags: ["oddx"], language: "en" },
];

describe("groups", () => {
  it("are every case, then each tag and each language", () => {
    const found = groups(CASES).map((g) => [g.by, g.value, g.families]);
    expect(found).toEqual([
      ["all", null, [1, 2, 3, 4]],
      ["tag", "akm", [1]],
      ["tag", "copd", [2]],
      ["tag", "dutch", [2, 3]],
      ["tag", "oddx", [4]],
      ["language", "en", [4]],
      ["language", "nl", [2, 3]],
      ["language", "sv", [1]],
    ]);
  });
});

describe("toggled", () => {
  const dutch = groups(CASES).find((g) => g.value === "dutch")!;

  it("picks the whole group, keeping what else is picked", () => {
    expect(toggled([1, 2], dutch)).toEqual([1, 2, 3]);
  });

  it("lets go of a group picked whole, and of nothing else", () => {
    expect(toggled([1, 2, 3], dutch)).toEqual([1]);
    expect(holds([1, 2, 3], dutch)).toBe(true);
    expect(holds([2], dutch)).toBe(false);
  });
});
