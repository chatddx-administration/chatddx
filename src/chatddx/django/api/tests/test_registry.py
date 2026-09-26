# pyright: basic
from collections.abc import Callable
from typing import Any

import pytest
from django.test import Client

from chatddx.repo.entities.case.django import CaseBranchModel
from chatddx.repo.entities.case.pydantic import CaseBranchDetails
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entity_names import ENTITY_NAMES
from chatddx.repo.families.pydantic import BranchDetails
from chatddx.repo.store.branch import commit

pytestmark = pytest.mark.django_db

type Run = Callable[..., list[dict[str, Any]]]


def named(branches: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {branch["name"]: branch for branch in branches}


def test_every_entity_lists_the_branches_the_identity_can_use(alex: Client):
    for entity in ENTITY_NAMES:
        response = alex.get(f"/api/registry/{entity}")

        assert response.status_code == 200, (entity, response.content)
        assert response.json(), entity


def test_stacks_are_listed_with_what_they_hold_and_where_they_send(alex: Client):
    stacks = named(alex.get("/api/registry/stack").json())

    assert {
        "qwen3-8b-awq@pelle",
        "gpt-oss-20b@malborg",
        "qwen3-8b-awq@malborg",
        "qwen3-8b-awq@fake",
        "gpt-oss-20b@fake",
    } <= set(stacks)

    fake = stacks["qwen3-8b-awq@fake"]

    assert fake["owner"] == "archive"
    assert fake["trail"]["machine"]["name"] == "fake"
    assert fake["trail"]["llm"] == {
        "entity": "llm",
        "name": "qwen3-8b-awq",
        "fingerprint": fake["trail"]["llm"]["fingerprint"],
    }
    assert fake["details"]["endpoint"] == "http://localhost:12099/v1/"
    assert fake["versions"] == 1


def test_configurations_are_listed_with_their_variations(alex: Client):
    free_text = named(alex.get("/api/registry/configuration").json())["free-text"]

    assert {
        entity: ref and ref["name"] for entity, ref in free_text["trail"].items()
    } == {
        "instruction": "ddx",
        "output": "free-text",
        "coercion": "auto",
        "reasoning": "default",
        "sampling": "recommended",
        "toolset": None,
    }


def test_cases_are_listed_by_name_and_kept_to_any_of_the_tags(alex: Client):
    def listed(query: str) -> list[str]:
        return list(named(alex.get(f"/api/registry/case{query}").json()))

    assert listed("") == ["case-1", "case-2"]
    assert listed("?tag=tag-1") == ["case-1"]
    assert listed("?tag=tag-1&tag=tag-2") == ["case-1", "case-2"]
    assert listed("?tag=nowhere") == []


def test_a_case_says_its_text_and_its_targets(alex: Client):
    case = alex.get("/api/registry/case/case-1").json()
    targets = {row.pop("kind"): row for row in case["targets"]}

    assert case["trail"] == {"vignette": "case vignette 1"}
    assert case["details"]["targets"]["diagnosis"] == {
        "text": "Fake diagnosis B",
        "pattern": "fake & diagnosis & (b | 2)",
    }
    assert list(case["details"]["targets"]) == ["diagnosis", "warning", "disposition"]
    assert list(targets) == ["diagnosis", "warning", "disposition", "dont_miss"]
    assert targets["diagnosis"] == {
        "none_expected": False,
        "text": "Fake diagnosis B",
        "pattern": "fake & diagnosis & (b | 2)",
        "unread": None,
    }
    assert (targets["disposition"]["text"], targets["disposition"]["pattern"]) == (
        None,
        "admit*",
    )
    assert targets["dont_miss"] == {
        "none_expected": False,
        "text": None,
        "pattern": None,
        "unread": None,
    }
    assert case["tags"] == ["tag-1", "tag-2"]
    assert case["runs"] == {"runs": 0, "errored": 0, "scorers": []}

    case = CaseBranchModel.objects.get(owner__name="archive", name="case-2")
    _ = commit(
        case.trail,
        CaseBranchDetails(name="calm", owner="alex", targets={"warning": False}),
    )

    calm = alex.get("/api/registry/case/calm").json()
    warning = next(row for row in calm["targets"] if row["kind"] == "warning")

    assert calm["details"]["targets"] == {"warning": False}
    assert (warning["none_expected"], warning["pattern"]) == (True, None)
    assert alex.get("/api/registry/stack/qwen3-8b-awq@fake").json()["targets"] is None


def test_a_branch_counts_your_runs_with_it_by_scorer(alex: Client, run: Run):
    cell = {"configuration": "free-text", "stack": "qwen3-8b-awq@fake"}

    _ = run(**cell, case="case-1", seed="none")
    _ = run(**cell, case="case-1", seed=7)
    _ = run(**cell, case="case-2")

    runs = alex.get("/api/registry/case/case-1").json()["runs"]

    assert (runs["runs"], runs["errored"]) == (2, 0)
    assert {row["scorer"]: row["scores"] for row in runs["scorers"]} == {
        "first_mention": 2,
        "reciprocal_rank": 2,
    }
    by_scorer = {row["scorer"]: row for row in runs["scorers"]}
    assert by_scorer["reciprocal_rank"]["metrics"] == {"mean": 0.5, "stderr": 0.0}

    listed = alex.get("/api/registry/case/case-1/runs").json()

    assert [row["description"] for row in listed] == [
        "free-text × qwen3-8b-awq@fake × case-1 (seed 7)",
        "free-text × qwen3-8b-awq@fake × case-1",
    ]

    scorer = alex.get("/api/registry/scorer/first_mention").json()

    assert scorer["details"] == {"metrics": ["mean", "stderr"]}
    assert scorer["runs"]["runs"] == 3
    assert [row["scorer"] for row in scorer["runs"]["scorers"]] == ["first_mention"]


def test_what_isn_t_there_isn_t_found(alex: Client):
    missing = alex.get("/api/registry/case/nope")

    assert missing.status_code == 404
    assert missing.json() == {"detail": "no case 'nope' for alex"}
    assert alex.get("/api/registry/frobnicate").status_code == 422


def test_another_s_configuration_is_had_by_its_owner(alex: Client):
    plan = ConfigurationBranchModel.objects.get(owner__name="archive", name="plan")
    details = BranchDetails(name="bobs-plan", owner="bob", collaborators=["alex"])
    _ = commit(plan.trail, details)

    assert "bobs-plan" not in named(alex.get("/api/registry/configuration").json())
    assert alex.get("/api/registry/configuration/bobs-plan").status_code == 404

    plan = alex.get("/api/registry/configuration/bobs-plan?owner=bob").json()

    assert (plan["name"], plan["owner"]) == ("bobs-plan", "bob")
    assert plan["trail"]["output"]["name"] == "management-plan"


def test_a_branch_lists_its_versions_the_head_first(alex: Client):
    for reasoning in ("off", "high"):
        saved = alex.post(
            "/api/cell/save",
            {"configuration": "free-text", "reasoning": reasoning, "name": "mine"},
            content_type="application/json",
        )
        assert saved.status_code == 200, saved.content

    versions = alex.get("/api/registry/configuration/mine/versions").json()

    assert [version["trail"]["reasoning"]["name"] for version in versions] == [
        "high",
        "off",
    ]
    assert (
        versions[0]["id"] == alex.get("/api/registry/configuration/mine").json()["id"]
    )
