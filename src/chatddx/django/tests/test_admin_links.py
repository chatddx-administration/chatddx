# pyright: basic
"""
One look for every reference from one record to another.

Each test here names a place where the portal points at another record --
in a changelist and in a read-only form -- and holds down that it renders
through `chatddx.django.portal.links`: an anchor carrying the class the
stylesheet hangs off, reading as the target's `__str__`.

Which page a reference opens is the business of the page that renders it,
and is tested beside it.
"""

import uuid

import pytest
from django.templatetags.static import static
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from pydantic_ai import ModelResponse, TextPart
from pydantic_core import to_jsonable_python

from chatddx.core.choices import RoleChoices, SessionContextChoices
from chatddx.core.models import IdentityModel
from chatddx.django.portal.links import LINK_CLASS, add_link, change_link, link
from chatddx.history.models import (
    ExperimentModel,
    MessageModel,
    RunModel,
    SessionModel,
)
from chatddx.history.proxies import Experiment, Message, Run, Session
from chatddx.repo.entities.super_agent.django import SuperAgent
from chatddx.repo.inventories import InventoryBranchModel


def reference(url: str, label: object) -> str:
    """The markup a reference to `url` is expected to render as."""
    return f'<a class="{LINK_CLASS}" href="{url}">{label}</a>'


@pytest.fixture
def message(
    owner: IdentityModel,
    session: SessionModel,
    run: RunModel,
    inventory_fixture_bm: InventoryBranchModel,
) -> MessageModel:
    response = ModelResponse(parts=[TextPart(content="hello")])

    return MessageModel.objects.create(
        agent_id=inventory_fixture_bm["agent"]["agent-1"].target.pk,
        session=session,
        kind=response.kind,
        run_id=run.uuid,
        role=RoleChoices.ASSISTANT,
        payload=to_jsonable_python(response),
        timestamp=timezone.now(),
    )


@pytest.fixture
def run_with_session(run: RunModel, owner: IdentityModel) -> RunModel:
    run.session = SessionModel.objects.create(
        owner=owner,
        context=SessionContextChoices.EXPERIMENT,
    )
    run.save(update_fields=["session"])

    return run


@pytest.mark.django_db
def test_every_admin_page_loads_the_stylesheet(user_client: Client):
    """
    The class is only worth carrying if the rules that style it are there;
    UNFOLD's STYLES is what puts them on every page, changelist and form
    alike.
    """
    for route in ("admin:index", "admin:orm_run_changelist"):
        content = user_client.get(reverse(route)).content.decode()

        assert static("css/admin_link.css") in content


def test_link_carries_the_class_and_escapes_its_label():
    assert link("/admin/x/", "a & b") == (
        f'<a class="{LINK_CLASS}" href="/admin/x/">a &amp; b</a>'
    )


@pytest.mark.django_db
def test_change_link_reads_as_the_target_str(session: SessionModel):
    proxy = Session.objects.get(pk=session.pk)
    url = reverse("admin:orm_session_change", args=[session.pk])

    assert change_link(proxy) == reference(url, proxy)


@pytest.mark.django_db
def test_links_carry_their_query_string():
    add = add_link(SuperAgent, "label", agent_fingerprint="abc")

    assert reverse("admin:orm_superagent_add") + "?agent_fingerprint=abc" in add


@pytest.mark.django_db
def test_run_changelist_references_experiment_and_session(
    run_with_session: RunModel,
    experiment: ExperimentModel,
    user_client: Client,
):
    content = user_client.get(reverse("admin:orm_run_changelist")).content.decode()

    assert (
        reference(
            reverse("admin:orm_experiment_change", args=[experiment.pk]),
            Experiment.objects.get(pk=experiment.pk),
        )
        in content
    )

    assert (
        reference(
            reverse("admin:orm_session_change", args=[run_with_session.session_id]),
            Session.objects.get(pk=run_with_session.session_id),
        )
        in content
    )


@pytest.mark.django_db
@pytest.mark.parametrize("view", ["changelist", "change"])
def test_experiment_references_its_agent_and_case(
    view: str,
    experiment: ExperimentModel,
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    """
    An experiment points at an agent and a case *trail*; the page each
    reference opens is the viewer's *branch* of it, so the label is the
    trail's `__str__` -- the branch's name and the trail's fingerprint.
    """
    args = [experiment.pk] if view == "change" else []
    url = reverse(f"admin:orm_experiment_{view}", args=args)
    content = user_client.get(url).content.decode()

    agent = inventory_fixture_bm["agent"]["agent-2"]
    case = inventory_fixture_bm["case"]["case-1"]

    assert (
        reference(
            reverse("admin:orm_superagent_change", args=[agent.pk]),
            f"{agent.name} ({agent.target.fingerprint[:6]})",
        )
        in content
    )

    assert (
        reference(
            reverse("admin:orm_case_change", args=[case.pk]),
            f"{case.name} ({case.target.fingerprint[:6]})",
        )
        in content
    )


@pytest.mark.django_db
def test_message_form_references_session_run_and_agent(
    message: MessageModel,
    session: SessionModel,
    run: RunModel,
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    url = reverse("admin:orm_message_change", args=[message.pk])
    content = user_client.get(url).content.decode()

    agent = inventory_fixture_bm["agent"]["agent-1"]

    assert (
        reference(
            reverse("admin:orm_session_change", args=[session.pk]),
            Session.objects.get(pk=session.pk),
        )
        in content
    )

    assert (
        reference(
            reverse("admin:orm_run_change", args=[run.pk]),
            Run.objects.get(pk=run.pk),
        )
        in content
    )

    assert (
        reference(
            reverse("admin:orm_superagent_change", args=[agent.pk])
            + f"?from_message={message.pk}",
            f"{agent.name} ({agent.target.fingerprint[:6]})",
        )
        in content
    )


@pytest.mark.django_db
def test_message_run_falls_back_to_the_uuid_when_the_run_is_gone(
    message: MessageModel,
    user_client: Client,
):
    """
    `MessageModel.run_id` holds a run's uuid rather than a foreign key, so
    the run has to be found by it -- and may be gone.
    """
    orphan_id = uuid.uuid4()
    MessageModel.objects.filter(pk=message.pk).update(run_id=orphan_id)

    url = reverse("admin:orm_message_change", args=[message.pk])
    content = user_client.get(url).content.decode()
    field_html = content.split(">Run</label>")[1][:500]

    assert str(orphan_id) in field_html
    assert f'class="{LINK_CLASS}"' not in field_html


@pytest.mark.django_db
def test_agent_changelist_references_every_relation(
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    content = user_client.get(
        reverse("admin:orm_superagent_changelist")
    ).content.decode()

    agent = inventory_fixture_bm["agent"]["some-agent"]

    for relation in ("connection", "output_type", "sampling_params", "tool_group"):
        branch = inventory_fixture_bm[relation][f"some-{relation}"]
        url = reverse(f"admin:orm_{relation.replace('_', '')}_change", args=[branch.pk])

        assert (
            reference(
                url + f"?from_agent={agent.pk}",
                f"{branch.name} ({branch.target.fingerprint[:6]})",
            )
            in content
        )


@pytest.mark.django_db
def test_session_form_references_each_message_and_its_agent(
    message: MessageModel,
    session: SessionModel,
    inventory_fixture_bm: InventoryBranchModel,
    user_client: Client,
):
    """
    The message cards under a session render outside the changelist
    machinery, through `templates/session_message.html`; they carry the same
    references and read the same way.
    """
    url = reverse("admin:orm_session_change", args=[session.pk])
    content = user_client.get(url).content.decode()

    agent = inventory_fixture_bm["agent"]["agent-1"]

    assert (
        reference(
            reverse("admin:orm_superagent_change", args=[agent.pk])
            + f"?from_message={message.pk}",
            f"{agent.name} ({agent.target.fingerprint[:6]})",
        )
        in content
    )

    assert (
        reference(
            reverse("admin:orm_message_change", args=[message.pk]),
            f"#{message.pk}",
        )
        in content
    )


@pytest.mark.django_db
def test_message_permalink_reads_as_its_number_not_its_content(
    message: MessageModel,
):
    """
    The one reference that is not labelled by `__str__`: a message's
    permalink sits beside the content it points at, so repeating that
    content would say nothing.
    """
    proxy = Message.objects.get(pk=message.pk)

    assert proxy.link == reference(
        reverse("admin:orm_message_change", args=[message.pk]),
        f"#{message.pk}",
    )
