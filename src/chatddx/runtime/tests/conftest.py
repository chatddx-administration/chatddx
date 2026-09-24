from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from pydantic_ai import AgentRunResult, AgentRunResultEvent

from chatddx.repo.inventories import ParsedInventory
from chatddx.runtime.resolution import Resolution, resolve
from chatddx.runtime.trial import Trial

type Cell = Callable[..., Resolution]
type Ran = Callable[[Trial], Coroutine[Any, Any, AgentRunResult[Any]]]


@pytest.fixture
def cell(test_inventory: ParsedInventory) -> Cell:
    """A test configuration resolved on a stack, with variations set in it by name."""

    def cell(configuration: str, stack: str, **variations: str) -> Resolution:
        trail, _ = test_inventory.configuration[configuration]
        trail = trail.model_copy(
            update={
                entity: getattr(test_inventory, entity)[name][0]
                for entity, name in variations.items()
            }
        )
        stack_trail, details = test_inventory.stack[stack]
        facts = next(
            llm.facts
            for llm_trail, llm in test_inventory.llm.values()
            if llm_trail.fingerprint == stack_trail.llm.fingerprint
        )

        return resolve(trail, details, facts, stack_trail.serving)

    return cell


@pytest.fixture
def entry_points(test_inventory: ParsedInventory) -> dict[str, str]:
    """What each of the test inventory's tools runs, by the tool's name."""
    return {
        trail.name: details.implementation.function
        for trail, details in test_inventory.tool.values()
        if details.implementation is not None
    }


@pytest.fixture
def ran() -> Ran:
    """A trial run to its result."""

    async def ran(trial: Trial) -> AgentRunResult[Any]:
        async with trial.stream() as events:
            async for event in events:
                if isinstance(event, AgentRunResultEvent):
                    return event.result

        raise AssertionError("the run ended with no result")

    return ran
