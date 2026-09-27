# pyright: basic
from html import escape
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from chatddx.bench.bench import Bench
from chatddx.conftest import Recommit
from chatddx.dev.fake_vllm import FakeTransport
from chatddx.dev.samples import sample
from chatddx.django.portal.admin import CONFIRM, RUN
from chatddx.django.portal.configurations import page_of, page_of_run, parsed
from chatddx.repo.entities.configuration.django import ConfigurationBranchModel
from chatddx.repo.names import short_fingerprint
from chatddx.worker import worker

pytestmark = pytest.mark.django_db

CHANGELIST = reverse("admin:portal_configuration_changelist")
ADD = reverse("admin:portal_batch_add")
PANEL = reverse("admin:portal_batch_status_panel")


def head(name: str, owner: str = "alice") -> ConfigurationBranchModel:
    return ConfigurationBranchModel.objects.filter(owner__name=owner, name=name).latest(
        "timestamp"
    )


def variation(entity: str, name: str, owner: str = "alice") -> int:
    """The version of a variation of the owner's, as a page's address sets it."""
    return Bench(owner).variation_named(entity, name).id  # pyright: ignore[reportArgumentType]


def shown(client: Client, url: str) -> Any:
    response = client.get(url)
    assert response.status_code == 200, response.content

    return response.context["shown"]


def slices(page: Any) -> dict[str, Any]:
    return {each.entity: each for each in page.slices}


def fields(of: Any) -> dict[str, Any]:
    return {str(field.label): field.items or field.value for field in of.fields}


def changes(of: Any) -> list[tuple[str, str | None, str | None]]:
    return [(str(change.label), change.before, change.after) for change in of.changes]


def test_the_list_is_of_the_owner_s_configurations(alice: Client):
    listed = alice.get(CHANGELIST).context["cl"].result_list

    assert "plan-web" in {row.name for row in listed}
    assert {row.owner.name for row in listed} == {"alice"}


def test_a_configuration_s_page_shows_it_slice_by_slice(alice: Client):
    page = shown(alice, page_of(head("plan-web").pk))
    each = slices(page)

    assert (page.label, page.set, page.varies) == ("plan-web", [], None)
    assert list(each) == [
        "instruction",
        "output",
        "coercion",
        "reasoning",
        "sampling",
        "toolset",
    ]
    assert [(e, each[e].name) for e in each] == [
        ("instruction", "ddx"),
        ("output", "management-plan"),
        ("coercion", "native"),
        ("reasoning", "default"),
        ("sampling", "recommended"),
        ("toolset", "web"),
    ]
    assert fields(each["instruction"])["User"] == "{{case}}"
    assert fields(each["reasoning"])["Effort"] == "default"
    assert fields(each["toolset"])["Tools"] == [
        "web_search: Search the web for up-to-date information"
    ]
    [schema] = [f for f in each["output"].fields if str(f.label) == "Answer schema"]
    assert schema.folded and '"diagnoses"' in schema.value


def test_a_variation_says_what_is_set_in_it_and_what_that_does(alice: Client):
    base = head("plan-web")
    url = page_of(
        base.pk,
        {
            "reasoning": variation("reasoning", "high"),
            "coercion": variation("coercion", "tool"),
        },
    )
    page = shown(alice, url)
    each = slices(page)

    assert page.label == "plan-web+coercion=tool+reasoning=high"
    assert page.varies == page_of(base.pk)
    assert [(s.entity, s.name, s.own) for s in page.set] == [
        ("coercion", "tool", "native"),
        ("reasoning", "high", "default"),
    ]
    assert changes(each["reasoning"]) == [("Effort", "default", "high")]
    assert changes(each["coercion"]) == [
        ("Mode", "native", "tool"),
        (
            "Tool description",
            "—",
            "“Give your answer by calling this tool, with the answer as i…”",
        ),
    ]
    assert not each["output"].set and each["output"].changes == []

    content = alice.get(url).content.decode()

    assert (
        f'A variation of <a class="font-semibold underline" href="{page.varies}">plan-web</a>'
        in content
    )
    assert "Effort: default → high" in content


def test_a_toolset_set_to_none_takes_the_tools_out(alice: Client):
    page = shown(alice, page_of(head("plan-web").pk, {"toolset": "none"}))
    [toolset] = page.set

    assert page.label == "plan-web+toolset=none"
    assert (toolset.name, toolset.own) == ("none", "web")
    assert changes(toolset) == [("Tools", "web_search", "none")]
    assert fields(toolset)["Tools"] == "none: no tool is offered"


def test_what_an_address_can_t_set_is_set_aside(alice: Client):
    base = head("plan-web")

    # a version of no variation, one set as the configuration's own, and none
    # but for a toolset
    page = shown(
        alice,
        page_of(
            base.pk, {"reasoning": 999_999, "coercion": variation("coercion", "native")}
        )
        + "&output=none&instruction=x",
    )

    assert (page.label, page.set) == ("plan-web", [])


def test_a_run_s_configuration_is_the_one_it_ran(alice: Client):
    run = sample("alice", "rich", case="case-1")
    run_page = alice.get(reverse("admin:portal_run_change", args=[run.uuid]))
    url = run_page.context["shown"].configuration_page

    assert run_page.context["shown"].configuration == (
        "plan-web+coercion=tool+reasoning=high"
    )
    assert (
        url
        == page_of_run(run)
        == page_of(
            head("plan-web").pk,
            {
                "coercion": variation("coercion", "tool"),
                "reasoning": variation("reasoning", "high"),
            },
        )
    )
    assert f'href="{escape(url)}"' in run_page.content.decode()

    page = shown(alice, url)

    assert page.label == "plan-web+coercion=tool+reasoning=high"
    # it comes to the configuration the run's trial holds
    assert page.fingerprint == short_fingerprint(run.trial.configuration.fingerprint)


def test_a_run_of_a_configuration_as_it_is_saved_is_that_configuration(alice: Client):
    run = sample("alice", "typical", case="case-1")

    assert page_of_run(run) == page_of(head("plan").pk)


def test_a_batch_s_run_goes_by_its_job(alice: Client, fake: FakeTransport):
    asked = {
        "configuration": "free-text",
        "stack": "qwen3-8b-awq@fake",
        "case_tags": ["tag-2"],
        "reasoning": ["off"],
        "seed": "42",
    }
    confirmation = alice.post(ADD, asked)
    [cell] = confirmation.context["shown"].cells
    off = page_of(head("free-text").pk, {"reasoning": variation("reasoning", "off")})

    # the plan's cell, before it is kept, leads to the configuration it runs
    assert cell.page == off

    _ = alice.post(ADD, asked | {CONFIRM: RUN})
    _ = worker.run(fake)
    panel = alice.get(PANEL)
    latest = panel.context["shown"].latest

    # each case taken up leads to the configuration as it ran
    assert {ran.configuration for ran in latest} == {"free-text+reasoning=off"}
    assert {ran.configuration_page for ran in latest} == {off}
    assert f'href="{escape(off)}"' in panel.content.decode()


def test_an_earlier_version_says_a_newer_one_is_saved_and_keeps_what_is_set(
    alice: Client,
):
    bench = Bench("alice")
    earlier = head("plan-web")
    _ = bench.save(bench.cell_of("plan-web", None, {"sampling": "fixed"}), "plan-web")
    latest = head("plan-web")
    high = variation("reasoning", "high")
    page = shown(alice, page_of(earlier.pk, {"reasoning": high}))

    assert (page.version.number, page.version.of) == (1, 2)
    assert page.newer.url == page_of(latest.pk, {"reasoning": high})
    assert [
        (str(c.label), c.before.split(" ")[0], c.after.split(" ")[0])
        for c in page.newer.changes
    ] == [("Sampling", "recommended", "fixed")]
    assert page.after == page_of(latest.pk, {"reasoning": high})


def test_a_configuration_another_keeps_to_themselves_is_not_found(
    alice: Client, recommit: Recommit
):
    recommit("configuration", "plan", owner="other")

    assert alice.get(page_of(head("plan", owner="other").pk)).status_code == 404
    assert (
        alice.get(reverse("admin:portal_configuration_change", args=["x"])).status_code
        == 404
    )


def test_a_label_is_read_from_its_end(alice: Client):
    assert parsed("plan-web+coercion=tool+reasoning=high") == (
        "plan-web",
        ["coercion", "reasoning"],
    )
    assert parsed("archive/plan+toolset=none") == ("archive/plan", ["toolset"])
    # a name that holds a + is none of what is set
    assert parsed("plan+more") == ("plan+more", [])
