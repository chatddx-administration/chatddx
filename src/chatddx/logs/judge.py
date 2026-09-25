"""
A judge for the diagnosis: a grader model reads the differential a run gave
and the diagnosis its case expects, and says which item, if any, is the
first that names it, allowing what a clinician would allow and a pattern
can't: a synonym, an abbreviation, another spelling, the other language.
Its value is 1/rank, and 0 where no item names it, as `reciprocal_rank`'s
is, so that the two can be held to each other and to clinicians.

The grader is the model given, or else the model bound to the `grader`
role, which one must be. It sees the target as the case has it: today the
pattern that `reciprocal_rank` reads, which the template explains. A score
keeps the grader's reasoning as its explanation, and is unscored where the
grader's verdict can't be read.

The file reads nothing but the sample, and imports nothing of chatddx's, so
inspect can load it on its own:

    inspect score LOG --scorer src/chatddx/logs/judge.py@diagnosis_judge \\
        --model-role grader=openai/gpt-4o --action append
"""

import re
from typing import Any

from inspect_ai.model import Model, get_model
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer, stderr
from inspect_ai.solver import TaskState

TEMPLATE = """\
You are checking a differential diagnosis against the diagnosis its case is \
known to have.

The expected diagnosis:

{target}

It may be written as a pattern of words: `&` joins words that are all named, \
`|` separates alternatives, a word ending in `*` stands for any ending, and \
parentheses group. Read it as a description of a diagnosis, not as a rule for \
how to spell it.

The differential, most likely first:

{items}

Which item is the first to name the expected diagnosis? An item names it if a \
clinician would take it for the same diagnosis: a synonym, an abbreviation, \
another spelling, a more specific form of it, or the same diagnosis in Swedish \
or English. A related but different diagnosis, a complication or a symptom \
does not name it.

Reason briefly, then end with a line "RANK: n", where n is the number of the \
item, or "RANK: none" if no item names it.
"""

# the last verdict counts, so that one quoted from the answer can't
VERDICT = re.compile(r"RANK:\s*(\d+|none)\b", re.IGNORECASE)


@scorer(metrics=[mean(), stderr()])
def diagnosis_judge(
    model: str | Model | None = None,
    view: str = "differential",
    target_kind: str = "diagnosis",
    template: str = TEMPLATE,
) -> Scorer:
    """
    Which item of the view, if any, first names the case's target of
    `target_kind`, as the grader judges it.
    """

    async def judge(state: TaskState, target: Target) -> Score:
        del target  # the sample's targets, by kind, are in its metadata

        if state.metadata.get("status") != "completed":
            return Score.unscored(reason="errored")

        views: dict[str, list[str]] | None = state.metadata.get("views")

        if views is not None and view not in views:
            return Score.unscored(reason=f"the output offers no {view}")

        targets: dict[str, Any] = state.metadata.get("targets") or {}
        expected: dict[str, Any] | bool | None = targets.get(target_kind)
        wanted = expected.get("pattern") if isinstance(expected, dict) else None

        if not isinstance(wanted, str):
            return Score.unscored(reason=f"the case has no {target_kind} target")

        items = None if views is None else views[view]

        if items is None:
            return Score(value=0.0, reason="no answer")

        if not items:
            return Score(value=0.0, reason="not listed")

        grader = (
            model
            if isinstance(model, Model)
            else get_model(model)
            if model is not None
            else get_model(role="grader", required=True)
        )
        prompt = template.format(
            target=wanted,
            items="\n".join(f"{rank}. {item}" for rank, item in enumerate(items, 1)),
        )
        verdict = await grader.generate(prompt)
        reasoning = verdict.completion
        found = VERDICT.findall(reasoning)
        metadata = {"target": wanted, "grader": grader.name}

        if not found:
            return Score.unscored(
                reason="grader_failed", explanation=reasoning, metadata=metadata
            )

        said = found[-1].lower()

        if said == "none":
            return Score(
                value=0.0,
                reason="not listed",
                explanation=reasoning,
                metadata=metadata,
            )

        rank = int(said)

        if not 1 <= rank <= len(items):
            return Score.unscored(
                reason="grader_failed", explanation=reasoning, metadata=metadata
            )

        return Score(
            value=1 / rank,
            answer=f"{rank}. {items[rank - 1]}",
            explanation=reasoning,
            metadata=metadata,
        )

    return judge
