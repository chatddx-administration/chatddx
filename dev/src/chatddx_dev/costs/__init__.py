import re
import shlex
import shutil
import subprocess
import time
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from statistics import median

import pytest

from chatddx.markers import applied_lines
from chatddx_dev import project

LOG = project.PROJECT_ROOT / "dev" / "costs.tsv"
# Policy: what is timed between commits waits here, out of git, so that a check run between
# turns leaves the worktree clean; write folds it into LOG.
SPOOL = project.PROJECT_ROOT / "dev" / "state" / "costs-spool.tsv"
QUOTED_IN = tuple(project.PROJECT_ROOT / path for path in project.COSTS_QUOTED_IN)
RECENT = 5
# Policy: a whole run varies less than a test does (src/chatddx/test/budget.py:MARGIN), but
# a figure is rewritten only once this far off, lest every turn stamp a new one.
MARGIN = 1.5
_FIGURE = re.compile(r"~(\d+(?:\.\d+)?)s\b")
_ITEM = re.compile(r"\s*- ")
_SPAN = re.compile(r"`([^`]+)`")
_VERBOSITY = re.compile(r"-q+|-v+|--quiet|--verbose")


# Duplication: dev/check.sh:spooled writes these columns too, in this order.
@dataclass(frozen=True)
class Cost:
    when: str
    machine: str
    seconds: float
    status: int
    beside: int
    commit: str
    command: str

    @classmethod
    def read(cls, line: str) -> "Cost":
        when, machine, seconds, status, beside, commit, command = line.split("\t", 6)
        return cls(
            when, machine, float(seconds), int(status), int(beside), commit, command
        )

    def written(self) -> str:
        command = " ".join(self.command.split())
        return (
            f"{self.when}\t{self.machine}\t{self.seconds:.1f}\t{self.status}\t"
            + f"{self.beside}\t{self.commit}\t{command}\n"
        )


def command(args: Sequence[str]) -> str:
    """The command pytest ran as, its plugins named by -p and its verbosity left out."""
    kept: list[str] = []
    named = False
    for arg in args:
        if named:
            named = False
        elif arg == "-p":
            named = True
        elif not arg.startswith("-p") and not _VERBOSITY.fullmatch(arg):
            kept.append(arg)
    return shlex.join(["pytest", *kept])


def logged(cost: Cost, spool: Path = SPOOL, log: Path = LOG) -> None:
    """Appends a line to the spool, if in a checkout, as told by the log being there."""
    if log.exists():
        spool.parent.mkdir(exist_ok=True)
        with spool.open("a") as f:
            _ = f.write(cost.written())


def read(*paths: Path) -> list[Cost]:
    return [
        Cost.read(line)
        for path in paths
        if path.exists()
        for line in path.read_text().splitlines()
        if line
    ]


def medians(costs: Iterable[Cost], machine: str) -> dict[str, float]:
    """Each command's median over its RECENT latest passes on the machine, run alone."""
    held: defaultdict[str, list[float]] = defaultdict(list)
    for cost in costs:
        if cost.machine == machine and cost.status == 0 and cost.beside == 0:
            held[cost.command].append(cost.seconds)
    return {command: median(took[-RECENT:]) for command, took in held.items()}


def _shown(seconds: float) -> str:
    return f"{float(f'{seconds:.2g}'):g}"


def _figure(seconds: float, m: re.Match[str]) -> str:
    stated = float(m.group(1))
    off = max(seconds / stated, stated / seconds) if stated and seconds else 0
    return f"~{_shown(seconds)}s" if off > MARGIN else m.group(0)


def quoted(text: str, took: dict[str, float]) -> str:
    """The text, its figures that are off by more than MARGIN made the median.

    A figure is a ~<n>s in a list item whose first code span is the command, and only
    what a stamp pending holds as written now is read.
    """
    lines = text.splitlines(keepends=True)
    shown = applied_lines(text)
    items: list[list[int]] = []
    for at, (n, line) in enumerate(shown):
        if _ITEM.match(line):
            items.append([n - 1])
        elif line.startswith(" ") and items and items[-1][-1] == shown[at - 1][0] - 1:
            items[-1].append(n - 1)
    for item in items:
        span = _SPAN.search("".join(lines[i] for i in item))
        if span is None or span.group(1) not in took:
            continue
        figure = partial(_figure, took[span.group(1)])
        for i in item:
            lines[i] = _FIGURE.sub(figure, lines[i])
    return "".join(lines)


def write(
    spool: Path = SPOOL, log: Path = LOG, quoted_in: Sequence[Path] = QUOTED_IN
) -> None:
    """Folds the spool into the log, and rewrites the figures quoted off the log.

    The figures are those of project.COSTS_QUOTED's machine; it says what it wrote.
    """
    written: list[str] = []
    if spool.exists():
        folded = spool.read_text()
        with log.open("a") as f:
            _ = f.write(folded)
        spool.unlink()
        written.append(f"{log.name}: {len(folded.splitlines())} folded")
    took = medians(read(log), project.COSTS_QUOTED)
    for path in quoted_in:
        current = path.read_text()
        now = quoted(current, took)
        if now != current:
            _ = path.write_text(now)
            written.append(f"{path.name}: figures rewritten")
    print("\n".join(written) or "nothing to write")


def show(spool: Path = SPOOL, log: Path = LOG) -> None:
    """Prints each command's median per machine, as write would quote it."""
    costs = read(log, spool)
    for machine in sorted({c.machine for c in costs}):
        for name, seconds in sorted(medians(costs, machine).items()):
            print(f"{machine}\t{_shown(seconds)}s\t{name}")


# Compromise: timed from when pytest loads its plugins, its own start left out.
class Costs:
    def __init__(self, args: Sequence[str]) -> None:
        self.command: str = command(args)
        self.began: float = time.perf_counter()
        self.status: int | None = None

    def pytest_sessionfinish(self, exitstatus: int) -> None:
        self.status = int(exitstatus)

    def pytest_unconfigure(self) -> None:
        machine = project.machine_class()
        # Accommodating for a checkout without git, such as nix's: nothing is spooled there.
        if machine is None or self.status is None or shutil.which("git") is None:
            return
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=project.PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        logged(
            Cost(
                datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                machine,
                time.perf_counter() - self.began,
                self.status,
                project.beside(),
                head.stdout.strip(),
                self.command,
            )
        )


# Accommodating for pytest-xdist, whose workers each run pytest too: the controller alone
# times the run. A run of pytest in a test is rooted elsewhere, and isn't timed either.
def pytest_configure(config: pytest.Config) -> None:
    if hasattr(config, "workerinput") or config.rootpath != project.PROJECT_ROOT:
        return
    _ = config.pluginmanager.register(Costs(config.invocation_params.args), "run costs")
