# pyright: basic
from copy import deepcopy
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from chatddx.bench.bench import Bench
from chatddx.conftest import Recommit
from chatddx.core import settings
from chatddx.dev.fake_vllm import FakeTransport
from chatddx.dev.samples import sample
from chatddx.django.portal import samplings, variations
from chatddx.django.portal.admin import CONFIRM, RUN
from chatddx.django.portal.configurations import page_of
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.entities.llm.django import LLMBranchModel
from chatddx.repo.entities.sampling.django import SamplingBranchModel
from chatddx.repo.entities.sampling.pydantic import SamplingTrailOut
from chatddx.repo.queries import head_of
from chatddx.worker import worker

pytestmark = pytest.mark.django_db

CHANGELIST = reverse("admin:portal_sampling_changelist")
ADD = reverse("admin:portal_sampling_add")
CHECK = reverse("admin:portal_sampling_check")
BATCH = reverse("admin:portal_batch_add")


def versions(name: str, owner: str = "alice") -> list[SamplingBranchModel]:
    return variations.versions_of("sampling", owner, name)


def page(row: SamplingBranchModel, *query: str) -> str:
    url = reverse("admin:portal_sampling_change", args=[row.pk])
    return f"{url}?{'&'.join(query)}" if query else url


def asked(row: SamplingBranchModel, **changed: Any) -> dict[str, Any]:
    trail = row.trail
    rows = versions(row.name, row.owner.name)
    number = next(i for i, each in enumerate(rows, 1) if each.pk == row.pk)
    values = {
        "edited": row.name,
        "head": rows[-1].pk,
        "since": "" if number == len(rows) else number,
        "name": row.name,
        "defaults": trail.defaults,
        **{
            name: getattr(trail, name)
            for name in (
                "temperature",
                "top_p",
                "top_k",
                "max_tokens",
                "presence_penalty",
                "frequency_penalty",
            )
        },
        "stop": "\n".join(trail.stop or []),
        **changed,
    }

    return {name: "" if value is None else value for name, value in values.items()}


def said(response: Any) -> str:
    return " ".join(str(response.context["said"].line).split())


def said_to(response: Any) -> list[str]:
    return [str(message) for message in response.context["messages"]]


def configuration(name: str, owner: str = "alice") -> ConfigurationBranchModel:
    return ConfigurationBranchModel.objects.filter(owner__name=owner, name=name).latest(
        "timestamp"
    )


def tried(client: Client, fake: FakeTransport, sampling: str) -> None:
    batch = {
        "configuration": "free-text",
        "stack": "qwen3-8b-awq@fake",
        "case_tags": ["tag-2"],
        "sampling": [sampling],
        "seed": "42",
    }
    _ = client.post(BATCH, batch | {CONFIRM: RUN})
    _ = worker.run(fake)


def test_the_list_is_of_the_owner_s_variations(alice: Client, recommit: Recommit):
    recommit("sampling", "greedy", owner="other")
    listed = alice.get(CHANGELIST).context["cl"].result_list

    assert {row.name for row in listed} == {
        "fixed",
        "generation-config",
        "greedy",
        "recommended",
        "recommended-4k",
    }
    assert {row.owner.name for row in listed} == {"alice"}


def test_a_variation_s_page_edits_its_latest_version(alice: Client):
    [greedy] = versions("greedy")
    response = alice.get(page(greedy))
    form = response.context["form"]

    assert (response.context["version"].number, response.context["version"].of) == (
        1,
        1,
    )
    assert form.initial["defaults"] == "generation_config"
    assert form.initial["temperature"] == 0
    assert form.initial["top_k"] is None
    assert said(response) == "Nothing to save: the latest version holds this already."
    assert response.context["said"].button == "Save"


def test_saving_under_its_name_makes_a_new_version(alice: Client):
    [fixed] = versions("fixed")
    response: Any = alice.post(page(fixed), asked(fixed, temperature="1.1"))
    first, second = versions("fixed")

    assert response.status_code == 302
    assert response.url == page(second)
    assert first.pk == fixed.pk
    assert (first.trail.temperature, second.trail.temperature) == (0.7, 1.1)
    assert second.trail.top_k == first.trail.top_k == 20
    assert said_to(alice.get(response.url)) == ["Saved as version 2 of fixed."]


def test_saving_what_the_latest_holds_makes_no_version(alice: Client):
    [fixed] = versions("fixed")
    response: Any = alice.post(page(fixed), asked(fixed))

    assert len(versions("fixed")) == 1
    assert said_to(alice.get(response.url)) == [
        "Nothing changed: fixed stays at version 1."
    ]


def test_saving_under_a_new_name_makes_a_new_variation(alice: Client):
    [fixed] = versions("fixed")
    response: Any = alice.post(
        page(fixed), asked(fixed, name="warm", temperature="1.1")
    )
    [warm] = versions("warm")

    assert response.url == page(warm)
    assert warm.trail.temperature == 1.1
    assert warm.trail.top_k == 20
    assert [row.pk for row in versions("fixed")] == [fixed.pk]
    assert said_to(alice.get(response.url)) == ["Saved as a new variation, warm."]


def test_a_new_variation_starts_from_the_blank(alice: Client):
    form = alice.get(ADD).context["form"]
    response: Any = alice.post(
        ADD, {"name": " warm ", "defaults": "recommended", "max_tokens": "2048"}
    )
    [warm] = versions("warm")

    assert form.initial == {"defaults": "recommended"}
    assert response.url == page(warm)
    assert (warm.trail.defaults, warm.trail.max_tokens) == ("recommended", 2048)
    assert warm.trail.temperature is None


def test_the_name_of_another_variation_is_refused(alice: Client):
    [fixed] = versions("fixed")
    [greedy] = versions("greedy")
    response: Any = alice.post(page(fixed), asked(fixed, name="greedy"))

    assert response.status_code == 200
    assert response.context["form"].errors["name"] == [
        "greedy is another variation of yours: open it to change it, or name this "
        + "one otherwise."
    ]
    assert response.context["taken_url"] == page(greedy)
    assert [row.pk for row in versions("greedy")] == [greedy.pk]


@pytest.mark.parametrize("name", ["a+b", "a/b", "hot=1", "a×b", "None"])
def test_a_name_can_t_hold_what_parts_names(alice: Client, name: str):
    [fixed] = versions("fixed")
    response: Any = alice.post(page(fixed), asked(fixed, name=name))

    assert response.status_code == 200
    assert "name" in response.context["form"].errors
    assert not versions(name)


@pytest.mark.parametrize(
    ("field", "value"),
    [("temperature", "3"), ("top_p", "0"), ("top_k", "-2"), ("max_tokens", "0")],
)
def test_a_value_out_of_its_range_is_refused_where_it_is(
    alice: Client, field: str, value: str
):
    [fixed] = versions("fixed")
    response: Any = alice.post(page(fixed), asked(fixed, **{field: value}))

    assert response.status_code == 200
    assert list(response.context["form"].errors) == [field]
    assert len(versions("fixed")) == 1


def test_stop_sequences_are_one_a_line_or_a_json_list(alice: Client):
    [fixed] = versions("fixed")
    _ = alice.post(page(fixed), asked(fixed, stop="END\r\n\r\n###"))
    latest = versions("fixed")[-1]
    _ = alice.post(page(latest), asked(latest, stop='["\\n\\n", " "]'))
    first, lines, listed = versions("fixed")

    assert first.trail.stop is None
    assert lines.trail.stop == ["END", "###"]
    assert listed.trail.stop == ["\n\n", " "]
    assert alice.get(page(listed)).context["form"].initial["stop"] == '["\\n\\n", " "]'


def test_an_earlier_version_is_read_and_edited_from(alice: Client):
    [fixed] = versions("fixed")
    _ = alice.post(page(fixed), asked(fixed, temperature="1.1"))
    first, second = versions("fixed")
    read = alice.get(page(first))
    edited = alice.get(page(first, "edit=1"))
    response: Any = alice.post(page(first), asked(first, top_k="40"))
    third = versions("fixed")[-1]

    assert read.context["form"] is None
    assert {str(f.label): f.value for f in read.context["fields"]}["Temperature"] == (
        "0.7"
    )
    assert read.context["after_url"] == page(second)
    assert said(edited) == "Saving makes version 3 of this variation, from version 1."
    assert response.url == page(third)
    assert (third.trail.temperature, third.trail.top_k) == (0.7, 40)


def test_what_a_version_changed_is_said(alice: Client):
    [fixed] = versions("fixed")
    _ = alice.post(page(fixed), asked(fixed, temperature="1.1", top_k=""))
    changes = alice.get(page(versions("fixed")[-1])).context["changes"]

    assert [(str(c.label), c.before, c.after) for c in changes] == [
        ("Temperature", "0.7", "1.1"),
        ("Top k", "20", "—"),
    ]


def test_a_version_saved_since_the_page_opened_is_said_before_saving_after_it(
    alice: Client,
):
    [fixed] = versions("fixed")
    opened = asked(fixed, temperature="0.9")
    _ = alice.post(page(fixed), asked(fixed, temperature="1.1"))
    warned = alice.post(page(fixed), opened)

    assert warned.status_code == 200
    assert said_to(warned)[-1].startswith("fixed has a version 2, saved ")
    assert len(versions("fixed")) == 2

    again = alice.post(page(fixed), warned.context["form"].data)

    assert again.status_code == 302
    assert [row.trail.temperature for row in versions("fixed")] == [0.7, 1.1, 0.9]


def test_the_check_says_what_saving_does_as_it_is_typed(alice: Client):
    [fixed] = versions("fixed")
    [greedy] = versions("greedy")
    typed = alice.post(CHECK, asked(fixed, temperature="1.1"))
    taken = alice.post(CHECK, asked(fixed, name="greedy"))
    out = alice.post(CHECK, asked(fixed, temperature="3"))
    content = typed.content.decode()

    assert said(typed) == "Saving makes version 2 of this variation."
    assert '<span id="variation-save-label" hx-swap-oob="true">Save as version 2' in (
        content
    )
    assert 'id="sampling-realized" hx-swap-oob="true"' in content
    assert "temperature = 1.1" in content
    assert taken.context["taken_url"] == page(greedy)
    assert out.context["realized"] is None
    assert len(versions("fixed")) == 1


def test_another_variation_holding_the_values_is_said(alice: Client):
    [fixed] = versions("fixed")
    [greedy] = versions("greedy")
    greedy_values = asked(
        fixed,
        defaults="generation_config",
        temperature="0",
        top_p="",
        top_k="",
        max_tokens="",
        presence_penalty="",
        frequency_penalty="",
    )
    response: Any = alice.post(CHECK, greedy_values)

    assert [
        (sharer.name, sharer.own, url) for sharer, url in response.context["sharers"]
    ] == [("greedy", True, page(greedy))]
    assert "holds these values too" in response.content.decode()


def test_what_it_does_is_said_on_each_llm_for_each_reasoning(alice: Client):
    trail = SamplingTrailOut.model_validate(versions("recommended")[0].trail)
    rows = samplings.realized_on("alice", trail).rows

    assert [
        (row.llm, [intent for intent, _ in row.intents], row.source) for row in rows
    ] == [
        ("gpt-oss-20b", ["low"], "recommended for 'low'"),
        ("gpt-oss-20b", ["medium"], "recommended for 'medium'"),
        ("gpt-oss-20b", ["high"], "recommended for 'high'"),
        ("qwen3-8b-awq", ["off"], "recommended for 'off'"),
        ("qwen3-8b-awq", ["on"], "recommended for 'on'"),
    ]
    assert [row.intents for row in rows if row.llm == "qwen3-8b-awq"] == [
        [("off", False)],
        [("on", True)],
    ]


def test_the_reasonings_it_comes_to_the_same_on_share_a_row(alice: Client):
    trail = SamplingTrailOut.model_validate(versions("greedy")[0].trail)
    realizing = samplings.realized_on("alice", trail)

    assert [
        (row.llm, [intent for intent, _ in row.intents]) for row in realizing.rows
    ] == [
        ("gpt-oss-20b", ["low", "medium", "high"]),
        ("qwen3-8b-awq", ["off", "on"]),
    ]
    assert realizing.greedy == "all"
    assert realizing.rows[0].writes == ["temperature = 0.0"]


def test_what_an_llm_s_facts_can_t_say_is_refused(alice: Client, recommit: Recommit):
    llm = head_of(
        LLMBranchModel.objects.all(), settings.ARCHIVE_IDENTITY_NAME, "gpt-oss-20b"
    )
    assert llm is not None
    facts = deepcopy(llm.details["facts"])
    del facts["sampling"]["generation_config"]
    recommit("llm", "gpt-oss-20b", facts=facts)
    trail = SamplingTrailOut.model_validate(versions("generation-config")[0].trail)
    [refused, *others] = samplings.realized_on("alice", trail).rows

    assert refused.llm == "gpt-oss-20b"
    assert refused.refused == "the LLM's facts say nothing on its generation config"
    assert refused.writes is None
    assert {row.llm for row in others} == {"qwen3-8b-awq"}


def test_what_goes_by_its_name_is_said(alice: Client):
    _ = sample("alice", "typical", case="case-1")
    holds = alice.get(page(versions("recommended")[0])).context["holds"]

    assert {holding.name for holding in holds.configurations} >= {"plan", "plan-web"}
    assert {holding.version for holding in holds.configurations} == {1}
    assert holds.runs == 1
    assert (holds.earlier, holds.trials) == (0, 0)
    assert holds.configurations[0].page == page_of(
        configuration(holds.configurations[0].name).pk
    )


def test_a_configuration_s_earlier_version_goes_by_its_name(alice: Client):
    bench = Bench("alice")
    _ = bench.save(bench.cell_of("plan-web", None, {"sampling": "fixed"}), "plan-web")
    recommended = variations.holds_of("sampling", "alice", versions("recommended"))
    fixed = variations.holds_of("sampling", "alice", versions("fixed"))

    assert "plan-web" not in {holding.name for holding in recommended.configurations}
    assert recommended.earlier == 1
    assert [holding.name for holding in fixed.configurations] == ["plan-web"]


def test_a_variation_nothing_goes_by_is_deleted_for_good(alice: Client):
    [fixed] = versions("fixed")
    _ = alice.post(page(fixed), asked(fixed, temperature="1.1"))
    asking = alice.get(reverse("admin:portal_sampling_delete", args=[fixed.pk]))
    response: Any = alice.post(reverse("admin:portal_sampling_delete", args=[fixed.pk]))

    assert not asking.context["holds"].anything
    assert asking.context["versions"] == 2
    assert response.url == CHANGELIST
    assert versions("fixed") == []
    assert said_to(alice.get(CHANGELIST)) == ["fixed is gone for good."]


def test_a_variation_something_goes_by_is_not_deleted(alice: Client):
    [recommended] = versions("recommended")
    response: Any = alice.post(
        reverse("admin:portal_sampling_delete", args=[recommended.pk])
    )

    assert response.status_code == 200
    assert response.context["holds"].configurations
    assert "can't be deleted" in response.content.decode()
    assert [row.pk for row in versions("recommended")] == [recommended.pk]


def test_a_variation_a_batch_tried_goes_by_its_name(alice: Client, fake: FakeTransport):
    tried(alice, fake, "greedy")
    holds = variations.holds_of("sampling", "alice", versions("greedy"))

    assert holds.runs > 0
    assert holds.trials > 0
    assert holds.configurations == []
    assert not variations.delete_variation("sampling", "alice", "greedy")
    assert len(versions("greedy")) == 1


def test_what_holds_values_another_variation_holds_goes_by_neither(
    alice: Client, fake: FakeTransport
):
    [greedy] = versions("greedy")
    tried(alice, fake, "greedy")
    _ = alice.post(page(greedy), asked(greedy, name="zero"))
    zero = variations.holds_of("sampling", "alice", versions("zero"))

    assert (zero.runs, zero.trials) == (0, 0)
    assert variations.holds_of("sampling", "alice", versions("greedy")).runs == 0
    assert variations.delete_variation("sampling", "alice", "zero")
    assert variations.holds_of("sampling", "alice", versions("greedy")).runs > 0


def test_another_s_variation_is_not_found(alice: Client, recommit: Recommit):
    recommit("sampling", "greedy", owner="other")
    [other] = versions("greedy", owner="other")

    assert alice.get(page(other)).status_code == 404
    assert alice.post(page(other), asked(other)).status_code == 404
    assert (
        alice.get(reverse("admin:portal_sampling_delete", args=[other.pk])).status_code
        == 404
    )
    assert (
        alice.get(reverse("admin:portal_sampling_change", args=["x"])).status_code
        == 404
    )


def test_the_configuration_page_leads_to_the_variation_its_sampling_is(
    alice: Client,
):
    [recommended] = versions("recommended")
    [greedy] = versions("greedy")
    greedy_id = Bench("alice").variation_named("sampling", "greedy").id
    own = alice.get(page_of(configuration("plan-web").pk)).context["shown"]
    set_ = alice.get(
        page_of(configuration("plan-web").pk, {"sampling": greedy_id})
    ).context["shown"]
    pages = {each.entity: each.page for each in own.slices}

    assert pages["sampling"] == page(recommended)
    assert {entity for entity, url in pages.items() if url is None} == {
        "instruction",
        "output",
        "coercion",
        "reasoning",
        "toolset",
    }
    assert {each.entity: each.page for each in set_.slices}["sampling"] == page(greedy)
