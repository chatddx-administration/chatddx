from typing import assert_type

import pytest

from chatddx.repo.bundles import (
    ALL_ENTITIES,
    ALL_VIEWS,
    RegistryCollisionError,
    _index_by_class,  # pyright: ignore[reportPrivateUsage]
    entity_of,
    view_of,
)
from chatddx.repo.entities.case.django import Case, SharedCase
from chatddx.repo.entities.configuration.django import (
    Configuration,
    ConfigurationBranchModel,
    ConfigurationTrailModel,
    SharedConfiguration,
)
from chatddx.repo.entities.configuration.pydantic import (
    ConfigurationBranchSpec,
    ConfigurationFormDataOut,
    ConfigurationTrailSchema,
    ConfigurationTrailSpec,
)
from chatddx.repo.entities.model.django import LanguageModel
from chatddx.repo.entity_names import EntityName, ViewName
from chatddx.repo.families.pydantic import (
    BRANCH_FIELDS,
    BranchDetailsPatch,
    BranchSchemaDetails,
    plain_detail_fields,
    relation_fields,
)
from chatddx.repo.inventories import (
    InventoryBranchModel,
    InventoryBranchSpec,
    InventoryFormDataOut,
    InventoryTrailSchema,
    ParsedInventory,
)
from chatddx.repo.parsers.inventory import (
    _relations,  # pyright: ignore[reportPrivateUsage]
)
from chatddx.repo.registry import CASE, CONFIGURATION, MODEL
from chatddx.repo.todo import all_entities


def test_the_registry_is_the_new_datamodel_s():
    """new-datamodel.md §10, in its commit order."""
    assert all_entities == (
        "machine",
        "os",
        "model",
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
    assert tuple(entity.name for entity in ALL_ENTITIES) == all_entities


def test_what_an_entity_references_is_committed_before_it():
    """
    A commit gives every trail in a closure a branch unless the owner has one.
    Committed in this order, the parts of a composition already have the
    names their records gave them when the composition reaches them.
    """
    for entity in all_entities:
        for relation in _relations(entity).values():
            assert all_entities.index(relation.entity) < all_entities.index(entity), (
                f"{entity} references {relation.entity}, committed after it"
            )


@pytest.mark.parametrize("proxy", [Configuration, SharedConfiguration])
def test_every_configuration_proxy_answers_configuration(proxy: type):
    assert entity_of(proxy) is CONFIGURATION
    assert view_of(proxy).entity is CONFIGURATION


def test_a_case_proxy_answers_case():
    for proxy in (Case, SharedCase):
        assert entity_of(proxy) is CASE


def test_the_model_s_proxy_is_not_called_model():
    """
    Every module that star-imports the registry's models would take a proxy
    called `Model` for Django's.
    """
    assert entity_of(LanguageModel) is MODEL


def test_two_entities_may_not_claim_one_class():
    with pytest.raises(RegistryCollisionError, match="ConfigurationBranchSchema"):
        _ = _index_by_class((CONFIGURATION, CONFIGURATION), "members", "entity")


def test_every_entity_has_a_view_of_its_name():
    assert [view.name for view in ALL_VIEWS] == list(all_entities)

    for entity in ALL_ENTITIES:
        assert view_of(entity.name).entity is entity


def test_the_flat_form_is_the_configuration_s():
    """
    super_agent's flat form became the configuration's (new-datamodel.md §7):
    each slice is a template chosen from.
    """
    assert view_of(Configuration).form_data_out is ConfigurationFormDataOut

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
        "model": ["source", "specs", "facts"],
        "serving": ["performance"],
        "client": ["rev", "packages"],
        "stack": ["endpoint", "served_name", "api", "credential"],
        "tool": ["implementation"],
        "case": ["targets"],
        "scorer": ["metrics"],
    }

    for entity in ALL_ENTITIES:
        if entity.name not in described:
            assert entity.branch_details is BranchSchemaDetails
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
    name the model sees.
    """
    for entity in ALL_ENTITIES:
        shared = set(entity.trail_schema.model_fields) & set(
            entity.branch_details_patch.model_fields
        )

        assert shared == ({"name"} if entity.name == "tool" else set())
        assert shared <= BRANCH_FIELDS


def test_every_inventory_holds_every_entity():
    for inventory in (
        ParsedInventory,
        InventoryTrailSchema,
        InventoryBranchSpec,
        InventoryFormDataOut,
    ):
        assert tuple(inventory.model_fields) == all_entities

    assert tuple(InventoryBranchModel.__annotations__) == all_entities


def test_entity_of():
    configuration_trail_schema = entity_of("configuration").trail_schema

    assert configuration_trail_schema is ConfigurationTrailSchema
    _ = assert_type(configuration_trail_schema, type[ConfigurationTrailSchema])

    configuration_trail_spec = entity_of(configuration_trail_schema).trail_spec

    assert configuration_trail_spec is ConfigurationTrailSpec
    _ = assert_type(configuration_trail_spec, type[ConfigurationTrailSpec])

    configuration_branch_spec = entity_of(configuration_trail_spec).branch_spec

    assert configuration_branch_spec is ConfigurationBranchSpec
    _ = assert_type(configuration_branch_spec, type[ConfigurationBranchSpec])

    assert entity_of(ConfigurationTrailModel) is CONFIGURATION
    assert entity_of(ConfigurationBranchModel) is CONFIGURATION


def test_every_view_is_an_entity_s():
    assert ViewName.__value__ is EntityName
