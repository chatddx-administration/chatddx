import json
import tomllib
from dataclasses import replace
from typing import cast

from jsonschema import validators
from pydantic import JsonValue

from chatddx.catalog import threads
from chatddx.curation import Plan, load_cases
from chatddx.curation.plan import PLANNED_TABLES
from chatddx.factors.base import Fingerprint, StructuralError, resolve
from chatddx.factors.facts import ModelFacts, Refusal
from chatddx.factors.request import Compilation, Translations, compiled
from chatddx.inventory import DirectorySource, Inventory, World
from chatddx.rig import rig
from chatddx.store import People, Rows
from chatddx.store.store import Connection
from chatddx.test.helpers import Loaded, sampled_template
from chatddx.test.world import (
    GPT_OSS_MODEL,
    KOMPISMOLN,
    QWEN_MODEL,
    SAMPLE,
    WORLDS,
    world_plan,
)

__all__ = ["sampled_template"]

MISTRAL_SMALL = "mistralai/Mistral-Small-3.2-24B-Instruct-2506"


def sample_plan() -> Plan:
    return world_plan(WORLDS / "sample", SAMPLE)


def test_the_sample_s_texts_are_english_and_translated_into_swedish() -> None:
    sample = sample_plan()
    assert {(r.table, r.name) for r in sample.stanzas if r.language == "en"} == {
        ("output", name)
        for name in (
            "management-plan",
            "management-plan-shown",
            "management-plan-prompted",
            "diagnoses",
            "diagnoses-tool",
            "free-text",
            "verdict",
            "grade",
        )
    } | {
        ("toolset", "web"),
        ("instructions", "clinician"),
        ("instructions", "judge"),
        ("prompt", "judge"),
        ("few_shot", "worked-example"),
    }
    assert not [r for r in sample.stanzas if r.language not in (None, "en")]
    get = sample.registry.get
    translations = sample.named("translations", "sample")
    assert list(resolve(get, translations.digest, Translations).into) == ["sv"]
    recipes = {r.name: r for r in sample.stanzas if r.table == "recipe"}
    assert set(recipes) == {
        "plan",
        "plan-shown",
        "plan-prompted",
        "diagnoses",
        "diagnoses-tool",
        "free-text",
        "free-text-guided",
        "judge-graded",
        "judge",
    }
    guided = recipes["free-text-guided"].compilation
    assert guided is not None
    assert resolve(get, guided, Compilation).recipe.translations == (
        translations.digest
    )
    assert sample.untranslated == []


def test_the_sample_s_translations_carry_its_recipes_into_swedish() -> None:
    sample = sample_plan()
    get = sample.registry.get
    translations = sample.named("translations", "sample").digest
    carried: set[str] = set()
    for r in sample.stanzas:
        if r.table != "recipe" or r.compilation is None:
            continue
        held = resolve(get, r.compilation, Compilation)
        recipe = held.recipe.model_copy(update={"translations": translations})
        facts = sample.facts.about(recipe.model, get)
        try:
            skeleton, _ = compiled(recipe, get, rig(), facts, into="sv")
        except StructuralError:
            continue
        assert skeleton.digest != r.digest, r.name
        carried.add(r.name)
    assert carried == {
        r.name
        for r in sample.stanzas
        if r.table == "recipe" and not r.name.startswith("judge")
    }


def test_kompismoln_s_facts_are_the_bundled_ones_as_its_engines_serve_them() -> None:
    assert World.load(WORLDS / "kompismoln").facts == ()
    plan = world_plan(WORLDS / "kompismoln", KOMPISMOLN)
    qwen, gpt_oss = (plan.facts.models[m] for m in (QWEN_MODEL, GPT_OSS_MODEL))
    assert (qwen.context_length, gpt_oss.context_length) == (8192, 32768)
    assert isinstance(qwen.reasoning.budget, Refusal)
    assert qwen.reasoning.budget.refused.startswith("qwen3-8b@pelle serves it without")
    stored = plan.named("facts", QWEN_MODEL).digest
    assert resolve(plan.registry.get, stored, ModelFacts) == qwen


def test_kompismoln_s_data_is_the_sample_s_without_its_appendices_under_its_own_tags() -> (
    None
):
    sample, kompismoln = load_cases(SAMPLE), load_cases(KOMPISMOLN)
    assert {id for id, c in sample.items() if c.appendices} == {"akm-01", "dutch-11"}
    assert {id: replace(c, tags=()) for id, c in kompismoln.items()} == {
        id: replace(c, tags=(), appendices={}, ordered=()) for id, c in sample.items()
    }
    assert sorted(
        p.name for p in KOMPISMOLN.iterdir() if p.resolve().parent != SAMPLE
    ) == ["cases-en.toml", "cases-sv.toml"]


def test_kompismoln_s_sources_are_the_sample_s() -> None:
    kompismoln = Inventory.load(WORLDS / "kompismoln" / "inventory.toml")
    sample = Inventory.load(WORLDS / "sample" / "inventory.toml")
    assert kompismoln.sources == sample.sources
    assert sample.sources["typed"].cleanup == sample.sources["sample"].cleanup
    assert sample.sources["sample"] == DirectorySource(
        name="sample",
        path=(WORLDS / "sample" / "vignettes").resolve(),
        cleanup=("newlines.lf@1", "unicode.nfc@1", "strip@1", "blank_lines.collapse@1"),
    )


TARGETS_SCHEMA = json.loads((SAMPLE / "schemas" / "targets.json").read_text())


def test_the_targets_schema_takes_the_old_chatddx_s_target_kinds() -> None:
    valid = validators.validator_for(TARGETS_SCHEMA)(TARGETS_SCHEMA).is_valid
    pneumonia: JsonValue = {"pattern": "pneumonia"}
    assert valid({"diagnosis": pneumonia})
    assert valid({"diagnosis": {"text": "Community-acquired pneumonia"}})
    assert valid(
        {
            "diagnosis": {"text": "Pneumonia", "pattern": "pneumonia"},
            "warning": False,
            "dont_miss": {"pattern": "pulmonary embolism"},
        }
    )
    invalid_targets: list[JsonValue] = [
        {"diagnosis": False},
        {"diagnosis": pneumonia, "dont_miss": False},
        {"diagnosis": {}},
        {"diagnosis": {"pattern": ""}},
        {"diagnosis": pneumonia, "critical": pneumonia},
    ]
    for invalid in invalid_targets:
        assert not valid(invalid), invalid


def test_a_case_s_notes_keep_their_author_comment_and_answer_not_a_language() -> None:
    valid = validators.validator_for(TARGETS_SCHEMA)(TARGETS_SCHEMA).is_valid
    note: dict[str, JsonValue] = {"author": "Olof", "comment": "Chock."}
    pneumonia: JsonValue = {"pattern": "pneumonia"}
    assert valid({"diagnosis": pneumonia, "notes": [note]})
    assert valid({"diagnosis": pneumonia, "notes": [note | {"answer": "Rundodla."}]})
    invalid_notes: list[JsonValue] = [
        [],
        [{k: v for k, v in note.items() if k != "author"}],
        [note | {"language": "sv"}],
        [note | {"comment": ""}],
        [note | {"answer": ""}],
        [note | {"date": "2026-09-28"}],
    ]
    for notes in invalid_notes:
        assert not valid({"diagnosis": pneumonia, "notes": notes}), notes


def test_the_sample_holds_olof_s_notes_on_three_cases_as_written() -> None:
    cases = load_cases(SAMPLE)
    valid = validators.validator_for(TARGETS_SCHEMA)(TARGETS_SCHEMA).is_valid
    assert all(valid(case.targets) for case in cases.values())
    noted = {
        id: case.targets["notes"]
        for id, case in cases.items()
        if isinstance(case.targets, dict) and "notes" in case.targets
    }
    assert sorted(noted) == ["akm-01", "dutch-01", "dutch-11"]
    for id, notes in noted.items():
        assert isinstance(notes, list) and len(notes) == 1
        [note] = notes
        assert isinstance(note, dict)
        assert note["author"] == "Olof"
        assert ("answer" in note) == (id != "dutch-01")
    [eleven] = cast(list[dict[str, str]], noted["dutch-11"])
    assert eleven["comment"].startswith("identifiera tecken på prechock eller chock")
    assert eleven["answer"].endswith("påbörja empirisk bredspektrumantibiotika.")


def test_the_sample_world_holds_the_vignettes_at_7893656_but_akm_06_s_amended() -> None:
    source = Inventory.load(WORLDS / "sample" / "inventory.toml").source(
        "sample", DirectorySource
    )
    assert source.sensitive
    assert source.ids() == sorted(load_cases(SAMPLE))
    for id in source.ids():
        _ = source.fetch(id).decode()
    listing = "".join(
        f"{c.vignette.id} {c.vignette.fingerprint.hex}\n" for c in source.cases()
    )
    assert (
        Fingerprint.of(listing.encode()).hex
        == "ca6e9a8afb74ee15eed949a745b853679a8502bd7af37480210ec17ec8571648"
    )


def test_the_sample_s_cases_are_81_english_and_18_swedish() -> None:
    cases = load_cases(SAMPLE)
    assert len(cases) == 99
    assert sum(c.language == "sv" for c in cases.values()) == 18
    assert cases["akm-01"].language == "sv"
    assert cases["akm-05"].language == cases["akm-13"].language == "en"
    assert cases["dutch-11"].language == "en"


def test_the_sample_loads_with_its_world_s_fakes(
    conn: Connection, sampled: Loaded
) -> None:
    assert sample_plan().skipped == []
    lines = sampled.said
    fakes = ("qwen3-8b-awq@fake", "gpt-oss-20b@fake")
    assert [line for line in lines if line.startswith("[lint warning]")] == [
        *(
            f"[lint warning] model.local {name}: model.revision: revision 'fake' is not a "
            + "commit and can move"
            for name in ("qwen3-8b-awq", "gpt-oss-20b")
        ),
        *(
            f"[lint warning] engine.local {name}: engine.closure: closure 'chatddx "
            + "fake-vllm' is not a Nix store path"
            for name in fakes
        ),
    ]
    assert not [line for line in lines if "needs repair" in line]
    rows = Rows(conn)
    archive = People(conn).find("archive")
    assert archive is not None
    [plan_thread] = threads.find(rows, "skeleton", "plan", owner=archive.id)
    [shown] = threads.find(rows, "skeleton", "plan-shown", owner=archive.id)
    diverged = threads.divergence(rows, shown)
    assert diverged is not None and set(diverged.varies) == {"/recipe/output"}
    assert diverged.base.thread == plan_thread


# Policy: the sample is the example a new World follows, so it uses everything a data
# set and a World can hold at least once.
def test_the_sample_uses_every_table_a_data_set_and_a_world_hold() -> None:
    plan = sample_plan()
    assert {r.table for r in plan.stanzas} == {*PLANNED_TABLES, "facts"}
    cases = load_cases(SAMPLE).values()
    assert any(c.appendices for c in cases) and any(c.ordered for c in cases)
    assert {c.language for c in cases} == {"en", "sv"}
    assert any(isinstance(c.targets, dict) and "notes" in c.targets for c in cases)

    path = WORLDS / "sample"
    world = World.load(path)
    assert world.engines and world.facts
    with (path / "inventory.toml").open("rb") as f:
        assert tomllib.load(f)["include"]
    inventory = world.inventory
    assert {s.kind for s in inventory.sources.values()} == {"directory", "database"}
    assert inventory.hosts and inventory.cleared
    endpoints = inventory.endpoints.values()
    assert any(e.credential for e in endpoints) and any(e.host for e in endpoints)
