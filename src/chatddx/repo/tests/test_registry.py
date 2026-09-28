from typing import assert_type

import pytest

from chatddx.repo.bundles import (
    ALL_ENTITIES,
    RegistryCollisionError,
    _index_by_class,  # pyright: ignore[reportPrivateUsage]
    entity_of,
)
from chatddx.repo.entities.configuration.django import (
    ConfigurationBranchModel,
    ConfigurationTrailModel,
)
from chatddx.repo.entities.configuration.pydantic import (
    ConfigurationBranchOut,
    ConfigurationTrailIn,
    ConfigurationTrailOut,
)
from chatddx.repo.entity_names import ENTITY_NAMES
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
    InventoryTrailIn,
    ParsedInventory,
)
from chatddx.repo.parsers.inventory import (
    _relations,  # pyright: ignore[reportPrivateUsage]
)
from chatddx.repo.registry import CONFIGURATION


def test_the_registry_is_the_new_datamodel_s():
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
    for entity in ENTITY_NAMES:
        for relation in _relations(entity).values():
            assert ENTITY_NAMES.index(relation.entity) < ENTITY_NAMES.index(entity), (
                f"{entity} references {relation.entity}, committed after it"
            )


def test_a_subclass_answers_its_entity():
    class Subclass(ConfigurationTrailIn):
        pass

    assert entity_of(Subclass) is CONFIGURATION


def test_two_entities_may_not_claim_one_class():
    with pytest.raises(RegistryCollisionError, match="ConfigurationBranchOut"):
        _ = _index_by_class((CONFIGURATION, CONFIGURATION))


def test_the_request_time_slices_have_no_details():
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
        "stack": ["endpoint", "served_name", "api", "credential", "max_jobs"],
        "tool": ["implementation"],
        "case": ["language", "targets", "deleted"],
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
