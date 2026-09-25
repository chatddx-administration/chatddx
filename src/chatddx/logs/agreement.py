"""
How two scorers read the same samples, for scorers whose value is 0 where
the target isn't found, as `reciprocal_rank`'s and the judge's are: how
often both found it, neither did, or one alone; Cohen's kappa on found,
which discounts the agreement chance alone would give; and the samples
whose values differ, which are what a clinician should settle first.

A sample either scorer left unscored, or didn't score, is left out.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass

from inspect_ai.log import EvalLog
from inspect_ai.scorer import Score


@dataclass(frozen=True)
class Disagreement:
    task: str
    sample: str | int
    epoch: int
    values: tuple[float, float]
    answers: tuple[str | None, str | None]


@dataclass(frozen=True)
class Agreement:
    scorers: tuple[str, str]
    both: int
    neither: int
    first_only: int
    second_only: int
    same: int
    disagreements: tuple[Disagreement, ...]

    @property
    def samples(self) -> int:
        return self.both + self.neither + self.first_only + self.second_only

    @property
    def kappa(self) -> float | None:
        """Cohen's kappa on found, or None where every sample fell alike."""
        if not self.samples:
            return None

        observed = (self.both + self.neither) / self.samples
        first = (self.both + self.first_only) / self.samples
        second = (self.both + self.second_only) / self.samples
        chance = first * second + (1 - first) * (1 - second)

        return None if chance == 1 else (observed - chance) / (1 - chance)


def agreement(logs: Iterable[EvalLog], first: str, second: str) -> Agreement:
    """How the scorers `first` and `second` read the samples of `logs`."""
    counts = {(True, True): 0, (False, False): 0, (True, False): 0, (False, True): 0}
    same = 0
    disagreements: list[Disagreement] = []

    for log in logs:
        for sample in log.samples or []:
            scores = sample.scores or {}
            pair = (_value(scores.get(first)), _value(scores.get(second)))

            if pair[0] is None or pair[1] is None:
                continue

            values = (pair[0], pair[1])
            counts[(values[0] > 0, values[1] > 0)] += 1

            if values[0] == values[1]:
                same += 1
                continue

            disagreements.append(
                Disagreement(
                    task=log.eval.task,
                    sample=sample.id,
                    epoch=sample.epoch,
                    values=values,
                    answers=(scores[first].answer, scores[second].answer),
                )
            )

    return Agreement(
        scorers=(first, second),
        both=counts[(True, True)],
        neither=counts[(False, False)],
        first_only=counts[(True, False)],
        second_only=counts[(False, True)],
        same=same,
        disagreements=tuple(disagreements),
    )


def _value(score: Score | None) -> float | None:
    if score is None or not isinstance(score.value, int | float):
        return None

    value = float(score.value)

    return None if math.isnan(value) else value
