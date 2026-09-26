// Tie the experiment add form's `expect` field to its `case`: an expectation
// belongs to a case (see `CaseBranchModel.expects`), so there is nothing to
// pick from until a case is picked, and once one is, only its own
// expectations are on offer.
//
// `ExperimentForm` renders the map and the labels this reads; its `clean()`
// is what enforces the pairing for a post that never met this script.
(function () {
  "use strict";

  const readExpectsByCase = (field) => {
    try {
      return JSON.parse(field.dataset.expectsByCase || "{}");
    } catch (error) {
      console.warn("experiment: unreadable expects-by-case, field left as is", error);
      return null;
    }
  };

  const setUp = () => {
    const caseField = document.getElementById("id_case");
    const expectField = document.getElementById("id_expect");

    if (!caseField || !expectField) return;

    const expectsByCase = readExpectsByCase(expectField);
    if (expectsByCase === null) return;

    // Narrowing the field drops options, so keep the full set as rendered:
    // every case draws its own from it.
    const options = Array.from(expectField.options);
    const blank = options.filter((option) => option.value === "");
    const blankLabel = blank.length ? blank[0].textContent : "";
    const noCaseLabel = expectField.dataset.noCaseLabel || blankLabel;

    const refresh = () => {
      const chosen = expectField.value;
      const allowed = new Set((expectsByCase[caseField.value] || []).map(String));

      expectField.replaceChildren(
        ...blank.concat(options.filter((option) => allowed.has(option.value))),
      );

      if (blank.length) {
        blank[0].textContent = caseField.value ? blankLabel : noCaseLabel;
      }

      // Nothing to choose from is nothing to choose: no case, or a case whose
      // version carries no expectations.
      expectField.disabled = allowed.size === 0;
      expectField.value = allowed.has(chosen) ? chosen : "";
    };

    caseField.addEventListener("change", refresh);
    refresh();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setUp);
  } else {
    setUp();
  }
})();
