from typing import assert_type

import pytest

from chatddx.repo.bundles import (
    ALL_ENTITIES,
    ALL_PRESENTATIONS,
    RegistryCollisionError,
    _index_by_class,  # pyright: ignore[reportPrivateUsage]
    entity_of,
    presentation_of,
)
from chatddx.repo.entities.case.django import Case, SharedCase
from chatddx.repo.entities.configuration.django import (
    Configuration,
    ConfigurationBranchModel,
    ConfigurationTrailModel,
    SharedConfiguration,
)
from chatddx.repo.entities.configuration.pydantic import (
    ConfigurationBranchOut,
    ConfigurationFormDataOut,
    ConfigurationTrailIn,
    ConfigurationTrailOut,
)
from chatddx.repo.entities.llm.django import LLM as LLMProxy
from chatddx.repo.entity_names import ENTITY_NAMES, EntityName, PresentationName
from chatddx.repo.families.pydantic import (
    BRANCH_FIELDS,
    BranchDetails,
    BranchDetailsPatch,
    plain_detail_fields,
    relation_fields,
)
from chatddx.repo.inventories import (
    InventoryBranchModel,
    InventoryBranchOut,
    InventoryFormDataOut,
    InventoryTrailIn,
    ParsedInventory,
)
from chatddx.repo.parsers.inventory import (
    _relations,  # pyright: ignore[reportPrivateUsage]
)
from chatddx.repo.registry import CASE, CONFIGURATION, LLM


def test_the_registry_is_the_new_datamodel_s():
    """new-datamodel.md §10, in its commit order."""
    assert ENTITY_NAMES == (
        "machine",
        "os",
        "llm",
        "serving",
        "client",
        "stack",
        "tool",
        "toolset",
        "instruction",
        "output",
        "coercion",
        "reasoning",
        "sampling",
        "configuration",
        "case",
        "scorer",
    )
    assert tuple(entity.name for entity in ALL_ENTITIES) == ENTITY_NAMES


def test_what_an_entity_references_is_committed_before_it():
    """
    A commit gives every trail in a closure a branch unless the owner has one.
    Committed in this order, the parts of a composition already have the
    names their records gave them when the composition reaches them.
    """
    for entity in ENTITY_NAMES:
        for relation in _relations(entity).values():
            assert ENTITY_NAMES.index(relation.entity) < ENTITY_NAMES.index(entity), (
                f"{entity} references {relation.entity}, committed after it"
            )


@pytest.mark.parametrize("proxy", [Configuration, SharedConfiguration])
def test_every_configuration_proxy_answers_configuration(proxy: type):
    assert entity_of(proxy) is CONFIGURATION
    assert presentation_of(proxy).entity is CONFIGURATION


def test_a_case_proxy_answers_case():
    for proxy in (Case, SharedCase):
        assert entity_of(proxy) is CASE


def test_an_llm_proxy_answers_llm():
    assert entity_of(LLMProxy) is LLM


def test_two_entities_may_not_claim_one_class():
    with pytest.raises(RegistryCollisionError, match="ConfigurationBranchIn"):
        _ = _index_by_class((CONFIGURATION, CONFIGURATION), "members", "entity")


def test_every_entity_has_a_presentation_of_its_name():
    assert [view.name for view in ALL_PRESENTATIONS] == list(ENTITY_NAMES)

    for entity in ALL_ENTITIES:
        assert presentation_of(entity.name).entity is entity


def test_the_flat_form_is_the_configuration_s():
    """
    super_agent's flat form became the configuration's (new-datamodel.md §7):
    each slice is a template chosen from.
    """
    assert presentation_of(Configuration).form_data_out is ConfigurationFormDataOut

    jsonschema = ConfigurationFormDataOut.model_json_schema(mode="serialization")

    assert [key for key in jsonschema["properties"] if key.endswith("_template")] == [
        "instruction_template",
        "output_template",
        "coercion_template",
        "reasoning_template",
        "sampling_template",
        "toolset_template",
    ]


def test_the_request_time_slices_have_no_details():
    """
    Details are description: what the things below a request are, what a
    tool runs, what a case is expected to yield, and how a scorer's values are
    summed up. The request-time slices have none: all they say is content
    (new-datamodel.md §6, §11).
    """
    described = {
        entity.name: plain_detail_fields(entity.branch_details)
        for entity in ALL_ENTITIES
        if plain_detail_fields(entity.branch_details)
    }

    assert described == {
        "machine": ["unreliable", "specs"],
        "os": ["flake_rev", "specs"],
        "llm": ["source", "specs", "facts"],
        "serving": ["performance"],
        "client": ["rev", "packages"],
        "stack": ["endpoint", "served_name", "api", "credential"],
        "tool": ["implementation"],
        "case": ["targets"],
        "scorer": ["metrics"],
    }

    for entity in ALL_ENTITIES:
        if entity.name not in described:
            assert entity.branch_details is BranchDetails
            assert entity.branch_details_patch is BranchDetailsPatch


def test_details_and_their_patch_say_the_same():
    for entity in ALL_ENTITIES:
        assert plain_detail_fields(entity.branch_details) == plain_detail_fields(
            entity.branch_details_patch
        )
        assert [name for name, _ in relation_fields(entity.branch_details)] == [
            "collaborators",
            "tags",
        ]


def test_content_and_details_share_no_key_but_a_tool_s_name():
    """
    A key is routed to one or the other. `name` is the one both have: a
    branch's name is its record's key, so a tool's `name` can only be the
    name the LLM sees.
    """
    for entity in ALL_ENTITIES:
        shared = set(entity.trail_in.model_fields) & set(
            entity.branch_details_patch.model_fields
        )

        assert shared == ({"name"} if entity.name == "tool" else set())
        assert shared <= BRANCH_FIELDS


def test_every_inventory_holds_every_entity():
    for inventory in (
        ParsedInventory,
        InventoryTrailIn,
        InventoryBranchOut,
        InventoryFormDataOut,
    ):
        assert tuple(inventory.model_fields) == ENTITY_NAMES

    assert tuple(InventoryBranchModel.__annotations__) == ENTITY_NAMES


def test_entity_of():
    configuration_trail_schema = entity_of("configuration").trail_in

    assert configuration_trail_schema is ConfigurationTrailIn
    _ = assert_type(configuration_trail_schema, type[ConfigurationTrailIn])

    configuration_trail_spec = entity_of(configuration_trail_schema).trail_out

    assert configuration_trail_spec is ConfigurationTrailOut
    _ = assert_type(configuration_trail_spec, type[ConfigurationTrailOut])

    configuration_branch_spec = entity_of(configuration_trail_spec).branch_out

    assert configuration_branch_spec is ConfigurationBranchOut
    _ = assert_type(configuration_branch_spec, type[ConfigurationBranchOut])

    assert entity_of(ConfigurationTrailModel) is CONFIGURATION
    assert entity_of(ConfigurationBranchModel) is CONFIGURATION


def test_every_view_is_an_entity_s():
    assert PresentationName.__value__ is EntityName
