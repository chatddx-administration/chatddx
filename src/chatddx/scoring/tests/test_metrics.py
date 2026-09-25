import pytest

from chatddx.scoring.metrics import METRICS


@pytest.mark.parametrize(
    "metric, values, expected",
    [
        ("mean", [1.0, 0.5, 0.0], 0.5),
        ("mean", [], 0.0),
        ("std", [1.0, 0.0], 0.7071),
        ("var", [1.0, 0.0], 0.5),
        ("stderr", [1.0, 0.0], 0.5),
        ("stderr", [1.0], 0.0),
        ("std", [], 0.0),
    ],
)
def test_each_metric_is_inspect_s(metric: str, values: list[float], expected: float):
    assert METRICS[metric](values) == pytest.approx(expected, abs=1e-4)  # pyright: ignore[reportArgumentType]
