import { describe, expect, it } from "vitest";
import { type Followed, open, said, tally, whole } from "./baseline";

type Job = NonNullable<Followed["job"]>;

function run(items: number, job: Partial<Job> | null, finished = false): Followed {
  return {
    cases: ["a", "b", "c"],
    seeds: [7],
    items: Array.from({ length: items }),
    finished,
    job:
      job === null
        ? null
        : { status: "under way", why: null, halt: false, ahead: null, queued: "", ended: null, ...job },
  } as unknown as Followed;
}

describe("a baseline under way", () => {
  it("counts the items ended over every run", () => {
    expect(tally([run(1, {}), run(3, {}, true)])).toEqual({ ended: 4, of: 6 });
  });

  it("is open while any job is queued or under way", () => {
    expect(open(run(0, { status: "queued", ahead: 2 }))).toBe(true);
    expect(open(run(3, { status: "finished" }, true))).toBe(false);
    expect(open(run(3, null, true))).toBe(false);
  });

  it("is whole once every run finished and was scored", () => {
    expect(whole([run(3, { status: "finished" }, true)])).toBe(true);
    expect(whole([run(3, { status: "finished" }, true), run(2, { status: "failed", why: "gone" })])).toBe(false);
    expect(whole([])).toBe(false);
  });

  it("says where each run stands", () => {
    expect(said(run(0, { status: "queued", ahead: 2 }))).toBe("queued, 2 ahead");
    expect(said(run(0, { status: "queued", ahead: null }))).toBe("queued, paused");
    expect(said(run(1, {}))).toBe("Sending");
    expect(said(run(3, {}, true))).toBe("Scoring");
    expect(said(run(2, { status: "failed", why: "gone" }))).toBe("failed: gone");
  });
});
