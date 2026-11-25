import { describe, expect, it } from "vitest";
import type { Schemas } from "$lib/api/client";
import { differs, estimated, grouped, languages, mean, named, scattered, unanswered } from "./breakdown";

function point(at: string): Schemas["BrokenPoint"] {
  return {
    started: "00000000-0000-0000-0000-000000000000",
    at,
    version: 1,
    means: [],
    spread: [],
    alike: 0,
    compared: 0,
    languages: [],
    failed: 0,
    seconds: 1,
    tokens: null,
    stale: false,
    missing: 0,
  };
}

function gathering(
  version: number,
  estimates: Schemas["BrokenGathering"]["estimates"] = [],
  paired: Schemas["BrokenGathering"]["paired"] = [],
): Schemas["BrokenGathering"] {
  return { digest: "d", point: { ...point("2026-01-01T00:00:00Z"), version }, estimates, values: [], paired };
}

describe("how a configuration fared", () => {
  it("is grouped by the field each view reads, in the order the views come", () => {
    const view = (field: string | null) => ({ scorer: "s", view: 0, label: "l", field });
    const broken = {
      name: "plan",
      tag: "akm",
      cases: 2,
      views: [view("diagnosis"), view("warning"), view("diagnosis")],
      gatherings: [],
      peers: [],
    };
    expect(grouped(broken)).toEqual([
      { field: "diagnosis", views: [0, 2] },
      { field: "warning", views: [1] },
    ]);
  });

  it("names a gathering by the version it ran", () => {
    expect(named(gathering(3))).toBe("v3");
  });

  it("scatters a gathering's cases within a third of its column, the same way each time", () => {
    const found = scattered(9);
    expect(found).toEqual(scattered(9));
    expect(Math.max(...found.map(Math.abs))).toBeLessThanOrEqual(1 / 6);
    expect(new Set(found.slice(0, 7)).size).toBe(7);
  });

  it("says how many cases a gathering left unanswered", () => {
    expect(unanswered(point("2026-01-01T00:00:00Z"), 12)).toBeNull();
    expect(unanswered({ ...point("2026-01-01T00:00:00Z"), missing: 3 }, 12)).toBe("3 of 12 cases unanswered");
  });

  it("gives a gathering's estimate and how it differs from the one before", () => {
    const version = gathering(3, [{ mean: 0.625, half: 0.08, n: 40 }, null], [{ mean: -0.1, half: 0.05, n: 20 }, null]);
    expect(estimated(version, 0)).toBe("v3: 0.63 ±0.08 (n=40), Δ −0.10 (n=20)");
    expect(estimated(version, 1)).toBe("v3: —");
    expect(differs({ mean: 0.2, half: null, n: 1 })).toBe("+0.20 (n=1)");
    expect(mean([0.5, null, 1])).toBe(0.75);
    expect(mean([null])).toBeNull();
  });

  it("counts a baseline's cases by the language each was sent in", () => {
    const held = {
      ...point("2026-01-01T00:00:00Z"),
      languages: [
        { language: null, cases: 1 },
        { language: "sv", cases: 18 },
      ],
    };
    expect(languages(held)).toBe("— 1, Swedish 18");
  });
});
