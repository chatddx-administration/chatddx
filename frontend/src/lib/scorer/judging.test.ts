import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  configurationChoices,
  type Holding,
  type Judging,
  madeFor,
  modelChoices,
  seedsOf,
  startingParams,
  verdictAt,
} from "./judging";

const read = (name: string) =>
  JSON.parse(readFileSync(new URL(`../../../../worlds/sample/_data/schemas/${name}`, import.meta.url), "utf8"));
const VERDICT = read("verdict.json");
const GRADE = read("grade.json");
const AT = { type: "object", properties: { at: { type: "string" } }, required: ["at"] };
const AT_MAX = { type: "object", properties: { at: { type: "string" }, max: { type: "number" } } };

describe("seedsOf", () => {
  it("reads each whole number typed once, and the seed 1 while none is", () => {
    expect(seedsOf("1, 2 3")).toEqual([1, 2, 3]);
    expect(seedsOf(" ")).toEqual([1]);
    expect(seedsOf("1, x")).toEqual([1]);
    expect(seedsOf("2, 2")).toEqual([2]);
  });
});

describe("startingParams", () => {
  it("reads a verdict at the judge's first field that isn't text", () => {
    expect(verdictAt(VERDICT)).toEqual(["/meets", "/why"]);
    expect(startingParams(AT, VERDICT)).toEqual({ at: "/meets" });
  });

  it("takes the field's maximum as the most points", () => {
    expect(startingParams(AT_MAX, GRADE)).toEqual({ at: "/points", max: 2 });
    expect(startingParams(AT_MAX, null)).toEqual({ max: 1 });
  });
});

describe("what a judge's fields offer", () => {
  const judging: Judging[] = [
    { digest: "sha256:a", thread: 1, name: "judge", owner: "alice", output_schema: null, weights: "sha256:q" },
    { digest: "sha256:a", thread: 2, name: "judge", owner: "archive", output_schema: null, weights: "sha256:q" },
    { digest: "sha256:b", thread: 3, name: "elsewhere", owner: "alice", output_schema: null, weights: "sha256:g" },
    { digest: "sha256:c", thread: 4, name: "by hand", owner: "alice", output_schema: null, weights: null },
  ];
  const models = [{ name: "qwen3-8b", weights: "sha256:q" }];
  const held: Holding = { skeleton: "sha256:a", configuration: "judge", weights: "sha256:q", handle: "qwen3-8b" };

  it("lists each configuration by thread, another's by owner, and what it holds only when none does", () => {
    expect(configurationChoices(judging, "alice", held)).toEqual([
      { key: "1", value: "sha256:a", label: "judge" },
      { key: "2", value: "sha256:a", label: "archive/judge" },
      { key: "3", value: "sha256:b", label: "elsewhere" },
      { key: "4", value: "sha256:c", label: "by hand" },
    ]);
    expect(configurationChoices(judging, "alice", { ...held, skeleton: "sha256:old" })[0]).toEqual({
      key: "held",
      value: "sha256:old",
      label: "judge, as it is asked now",
    });
  });

  it("knows the model each configuration was made for, among those offered", () => {
    expect(madeFor(judging, models)).toEqual({ "sha256:a": "sha256:q" });
  });

  it("keeps weights no handle holds now", () => {
    expect(modelChoices(models, held)).toEqual([{ key: "qwen3-8b", value: "sha256:q", label: "qwen3-8b" }]);
    expect(modelChoices(models, { ...held, weights: "sha256:old" })[0]).toEqual({
      key: "held",
      value: "sha256:old",
      label: "qwen3-8b, the weights it holds",
    });
  });
});
