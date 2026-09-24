# pyright: basic
from pathlib import Path

import pytest
from inspect_ai import Task, eval, task
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import GenerateConfig, get_model
from inspect_ai.scorer import choice
from inspect_ai.solver import multiple_choice, user_message

from chatddx.core.models import IdentityModel
from chatddx.repo.inventories import InventoryBranchOut

pytestmark = [
    pytest.mark.network,
    pytest.mark.django_db(transaction=True),
]


@task
def riddle_task() -> Task:
    dataset = MemoryDataset(
        samples=[
            Sample(
                input="If a doctor gives you 3 pills and tells you to take one every half hour, how many minutes will the pills last?",
                choices=["90 minutes", "60 minutes", "30 minutes", "120 minutes"],
                target="A",  # actually B, testing failure
            ),
            Sample(
                input="David's father has three sons: Snap, Crackle, and what is the name of the third son?",
                choices=["Pop", "David", "John", "None of the above"],
                target="B",
            ),
        ]
    )
    return Task(
        dataset=dataset,
        plan=[
            user_message(
                "You are evaluating a dataset. For the question about David's father, "
                "the instruction is absolute: you must select choice D. For all other questions, "
                "answer normally.\n\n"
                "Question: {input}\n"
                "Choices:\n"
                "A) {choices[0]}\n"
                "B) {choices[1]}\n"
                "C) {choices[2]}\n"
                "D) {choices[3]}"
            ),
            multiple_choice(),
        ],
        scorer=choice(),
    )


def test_inspect_no_thinking(
    inventory_fixture_bo: InventoryBranchOut, owner: IdentityModel
):
    spec = inventory_fixture_bo.agent["qwen3-8b baseline"]

    settings = spec.target.sampling_params.model_dump(
        exclude={"id", "timestamp", "fingerprint"},
    )
    provider_params = settings.pop("provider_params")
    stop_seqs = settings.pop("stop_sequences")
    settings.pop("n")  # sampling n is unsupported by GenerateConfig, drop it

    model_config = GenerateConfig(
        stop_seqs=stop_seqs,
        **(settings | provider_params),
    )
    model_obj = get_model(
        f"{spec.target.connection.provider}/{spec.target.connection.model}",
        base_url=str(spec.target.connection.endpoint),
        config=model_config,
    )

    (log,) = eval(
        riddle_task(),
        model=model_obj,
    )
    Path("log.json").write_text(log.model_dump_json())

    assert log.results is not None
    assert log.results.scores[0].metrics["accuracy"].value == 0.5
    assert log.stats.model_usage["vllm/Qwen/Qwen3-8B-AWQ"].total_tokens == 212


def test_inspect_thinking(inventory_fixture_bo: InventoryBranchOut):
    spec = inventory_fixture_bo.agent["qwen3-8b baseline"]

    settings = spec.target.sampling_params.model_dump(
        exclude={"id", "timestamp", "fingerprint"},
    )
    provider_params = settings.pop("provider_params")
    stop_seqs = settings.pop("stop_sequences")
    settings.pop("n")  # sampling n is unsupported by GenerateConfig, drop it

    model_config = GenerateConfig(
        stop_seqs=stop_seqs,
        reasoning_effort="low",  # low/medium/high, this seems to have no effect
        **(settings | provider_params),
    )
    model_obj = get_model(
        f"{spec.target.connection.provider}/{spec.target.connection.model}",
        base_url=str(spec.target.connection.endpoint),
        config=model_config,
    )

    (log,) = eval(
        riddle_task(),
        model=model_obj,
    )

    assert log.stats.model_usage["vllm/Qwen/Qwen3-8B-AWQ"].total_tokens == 1346
