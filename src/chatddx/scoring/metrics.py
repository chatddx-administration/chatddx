"""
inspect's metrics, by name and formula, over the values a scorer made. chatddx
computes them itself rather than load inspect to: a sample's standard
deviation, as `numpy.std(values, ddof=1)` gives it, and 0 where a formula has
too few values. The values are those a score has: one without a value, as an
unscored one, is left out, as inspect leaves it out of its metrics.
"""

import math
import statistics
from collections.abc import Callable

from chatddx.repo.entities.scorer.pydantic import Metric


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def std(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def var(values: list[float]) -> float:
    return statistics.variance(values) if len(values) > 1 else 0.0


def stderr(values: list[float]) -> float:
    return std(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0


METRICS: dict[Metric, Callable[[list[float]], float]] = {
    "mean": mean,
    "stderr": stderr,
    "std": std,
    "var": var,
}
