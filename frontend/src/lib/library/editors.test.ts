import { describe, expect, it } from "vitest";
import { labelled, misread, read, segsOf, textOfSegs } from "./editors";

describe("a text with inserts", () => {
  it("is read as text where its form says so, else as its JSON", () => {
    expect(segsOf("Be brief.", true)).toEqual(["Be brief."]);
    expect(segsOf('["Be brief.", {"insert": "output_guidance", "before": "\\n\\n"}]', false)).toEqual([
      "Be brief.",
      { insert: "output_guidance", before: "\n\n" },
    ]);
    expect(segsOf("[ broken", false)).toBeNull();
  });

  it("is written as text while it holds no insert, and as JSON once it does", () => {
    expect(textOfSegs(["Be ", "brief."], true)).toEqual({ asText: true, text: "Be brief." });
    const segs = ["Be brief.", { insert: "output_guidance" }];
    expect(textOfSegs(segs, true)).toEqual({ asText: false, text: JSON.stringify(segs, null, 2) });
  });

  it("is always JSON where the field is a list of segments", () => {
    expect(textOfSegs(["The case:\n", { slot: "vignette" }, ""], false)).toEqual({
      asText: false,
      text: JSON.stringify(["The case:\n", { slot: "vignette" }], null, 2),
    });
  });
});

describe("a scorer's labels", () => {
  it("name each view, by position, and keep the rest as it is", () => {
    const held = read('{"views": ["text", ""], "resources": ["r"]}');
    expect(held.ok && labelled(held.value, 3)).toEqual({
      views: ["text", "view 1", "view 2"],
      rest: { resources: ["r"] },
    });
    expect(labelled(null, 1)).toEqual({ views: ["view 0"], rest: {} });
  });
});

describe("a JSON box", () => {
  it("says what keeps what is typed in it from being sent, and nothing while it holds what it is to", () => {
    expect(misread("", "{}")).toBeNull();
    expect(misread('"enable_thinking": false', "{}")).toBeNull();
    expect(misread('"enable_thinking": fals', "{}")).toMatch(/^It isn't JSON yet: /);
    expect(misread('"a", "b"', "[]")).toBeNull();
    expect(misread("null", null)).toBeNull();
  });
});
