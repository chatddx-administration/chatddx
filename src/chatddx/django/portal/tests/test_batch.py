# pyright: basic
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from chatddx.bench.bench import SEEDS, Bench
from chatddx.bench.cell import SLICES
from chatddx.django.portal.admin import CONFIRM, RUN
from chatddx.django.portal.forms import MOST_CELLS
from chatddx.django.portal.models import BatchModel

pytestmark = pytest.mark.django_db

ADD = reverse("admin:portal_batch_add")
CHANGELIST = reverse("admin:portal_batch_changelist")

FREE_TEXT = {
    "configuration": "free-text",
    "stack": "qwen3-8b-awq@fake",
    "case_tags": ["tag-2"],
    "seed": "42",
}


def confirmed(asked: dict[str, Any], how: str = RUN) -> dict[str, Any]:
    """What was asked, confirmed: to run now, or to keep for later."""
    return asked | {CONFIRM: how}


def labels(response: Any) -> list[str]:
    """The cells a confirmation plans, as the repl labels them."""
    return [ready.cell.label for ready in response.context["plan"].ready]


def test_the_form_offers_what_the_repl_can_use(alice: Client):
    response = alice.get(ADD)
    form = response.context["adminform"].form
    bench = Bench("alice")

    assert response.status_code == 200
    assert list(form.fields) == [
        "configuration",
        "stack",
        "case_tags",
        "seed",
        *SLICES,
    ]
    assert [name for name, _ in form.fields["configuration"].choices] == [
        "",
        *bench.names("configuration"),
    ]
    assert [name for name, _ in form.fields["stack"].choices] == [
        "",
        *bench.names("stack"),
    ]
    assert [name for name, _ in form.fields["case_tags"].choices] == [
        "tag-1",
        "tag-2",
    ]
    assert [name for name, _ in form.fields["reasoning"].choices] == bench.names(
        "reasoning"
    )
    assert [name for name, _ in form.fields["toolset"].choices] == [
        *bench.names("toolset"),
        "none",
    ]
    # a seed drawn, as the repl draws one
    assert 0 <= form.initial["seed"] < SEEDS


def test_the_slices_come_in_once_case_tags_are_picked(alice: Client):
    response = alice.get(ADD)
    conditional = response.context["adminform"].model_admin.conditional_fields

    assert set(conditional) == set(SLICES)
    assert all("case_tags" in shown for shown in conditional.values())
    assert b'x-show="case_tags &amp;&amp; case_tags.length"' in response.content


def test_a_configuration_put_in_ticks_its_own_variations(alice: Client):
    response = alice.get(f"{ADD}?configuration=plan")
    form = response.context["adminform"].form

    assert {entity: form.initial[entity] for entity in SLICES} == {
        "instruction": ["ddx"],
        "output": ["management-plan"],
        "coercion": ["native"],
        "reasoning": ["default"],
        "sampling": ["recommended"],
        "toolset": ["none"],
    }
    # and what each configuration has is at hand for the script to tick
    assert b"data-variations=" in response.content


def test_a_valid_post_is_shown_its_plan_and_nothing_is_kept(alice: Client):
    response = alice.post(ADD, FREE_TEXT)

    assert response.status_code == 200
    assert response.templates[0].name == "portal/batch/confirmation.html"
    assert labels(response) == ["free-text"]
    assert [case.name for case in response.context["plan"].cases] == [
        "case-1",
        "case-2",
    ]
    assert response.context["shown"].trials == 2
    assert f'name="{CONFIRM}"'.encode() in response.content
    assert not BatchModel.objects.exists()


def test_the_variations_ticked_are_crossed_greedy_cells_unseeded(alice: Client):
    response = alice.post(
        ADD,
        FREE_TEXT | {"reasoning": ["off", "on"], "sampling": ["recommended", "greedy"]},
    )
    shown = response.context["shown"]

    assert labels(response) == [
        "free-text+reasoning=off",
        "free-text+reasoning=off+sampling=greedy",
        "free-text+reasoning=on",
        "free-text+reasoning=on+sampling=greedy",
    ]
    assert [(cell.seed, cell.greedy) for cell in shown.cells] == [
        (42, False),
        (None, True),
        (42, False),
        (None, True),
    ]
    assert shown.trials == 8
    assert b"unseeded: sampling is greedy" in response.content


def test_a_cell_its_stack_refuses_is_held_back_with_why(alice: Client):
    response = alice.post(
        ADD,
        {
            "configuration": "baseline",
            "stack": "gpt-oss-20b@fake",
            "case_tags": ["tag-1"],
            "reasoning": ["off", "on"],
            "seed": "",
        },
    )
    [held_back] = response.context["shown"].held_back

    assert labels(response) == ["baseline+reasoning=on"]
    # what runs, the cell held back aside
    assert response.context["description"] == (
        "baseline+reasoning=on × gpt-oss-20b@fake × 1 case tagged tag-1"
    )
    assert held_back.label == "baseline+reasoning=off"
    assert held_back.why == [
        "refused: reasoning: always reasons: vLLM rejects reasoning_effort = none"
        + " for harmony"
    ]
    assert b"always reasons" in response.content


def test_the_confirmation_says_which_cases_each_scorer_can_hold_the_cells_to(
    alice: Client,
):
    response = alice.post(ADD, FREE_TEXT | {"output": ["free-text", "diagnoses"]})
    scorers = {row.name: row for row in response.context["scorers"]}

    # free text offers text and a differential, diagnoses a differential
    assert scorers["reciprocal_rank"].offered == 2
    assert scorers["reciprocal_rank"].have == 2
    assert scorers["first_mention"].offered == 1
    assert scorers["warning_mentions"].offered == 0
    assert scorers["warning_mentions"].have is None


def test_confirming_keeps_the_batch_and_shows_it(alice: Client):
    asked = FREE_TEXT | {"reasoning": ["default", "off"]}
    response = alice.post(ADD, confirmed(asked), follow=True)
    batch = BatchModel.objects.get()

    assert response.redirect_chain == [
        (reverse("admin:portal_batch_change", args=[batch.pk]), 302)
    ]
    assert batch.owner.name == "alice"
    assert (batch.configuration, batch.stack, batch.tags, batch.seed) == (
        "free-text",
        "qwen3-8b-awq@fake",
        ["tag-2"],
        42,
    )
    assert batch.variations == {"reasoning": ["default", "off"]}
    assert [(cell["label"], cell["set"], cell["seed"]) for cell in batch.cells] == [
        ("free-text", {}, 42),
        ("free-text+reasoning=off", {"reasoning": "off"}, 42),
    ]
    assert all(cell["fingerprint"].startswith("cddx-trail/") for cell in batch.cells)
    assert [case["name"] for case in batch.cases] == ["case-1", "case-2"]
    assert batch.held_back == []
    assert batch.trials == 4
    assert any(
        f"Batch {str(batch.uuid)[:8]} is kept, and its 4 trials queued" in str(message)
        for message in response.context["messages"]
    )


def test_nothing_to_run_is_shown_and_never_kept(alice: Client):
    asked = {
        "configuration": "baseline",
        "stack": "gpt-oss-20b@fake",
        "case_tags": ["tag-1"],
        "reasoning": ["off"],
        "seed": "5",
    }
    response = alice.post(ADD, asked)

    assert response.context["shown"].trials == 0
    assert f'name="{CONFIRM}"'.encode() not in response.content

    response = alice.post(ADD, confirmed(asked))

    assert response.status_code == 200
    assert not BatchModel.objects.exists()


def test_what_can_t_be_planned_comes_back_as_the_form(alice: Client):
    untagged = alice.post(ADD, FREE_TEXT | {"case_tags": []})
    vast = alice.post(
        ADD,
        FREE_TEXT
        | {
            "instruction": ["ddx", "bare"],
            "output": ["free-text", "diagnoses", "raw"],
            "coercion": ["native", "tool"],
            "reasoning": ["default", "off", "on", "low", "high"],
            "sampling": ["recommended", "greedy", "fixed"],
        },
    )

    assert "case_tags" in untagged.context["adminform"].form.errors
    assert f"a batch holds {MOST_CELLS} at most" in str(
        vast.context["adminform"].form.non_field_errors()
    )
    assert not BatchModel.objects.exists()


def test_back_to_the_form_brings_back_what_was_asked(alice: Client):
    asked = FREE_TEXT | {"reasoning": ["off", "on"]}
    back = alice.post(ADD, asked).context["back_url"]
    form = alice.get(back).context["adminform"].form

    assert back.startswith(f"{ADD}?")
    assert form.initial["case_tags"] == ["tag-2"]
    assert form.initial["reasoning"] == ["off", "on"]
    assert form.initial["seed"] == "42"
    # what wasn't asked of a slice is the configuration's own
    assert form.initial["sampling"] == ["recommended"]


def test_the_changelist_shows_one_s_own_batches(alice: Client, bob: Client):
    _ = alice.post(ADD, confirmed(FREE_TEXT))
    _ = bob.post(ADD, confirmed(FREE_TEXT | {"seed": "7"}))

    alices, bobs = BatchModel.objects.order_by("pk")
    response = alice.get(CHANGELIST)

    assert response.status_code == 200
    assert reverse("admin:portal_batch_change", args=[alices.pk]).encode() in (
        response.content
    )
    assert reverse("admin:portal_batch_change", args=[bobs.pk]).encode() not in (
        response.content
    )
    assert b"free-text \xc3\x97 qwen3-8b-awq@fake" in response.content
    assert (
        alice.get(reverse("admin:portal_batch_change", args=[bobs.pk])).status_code
        == 302
    )


def test_a_kept_batch_is_shown_never_changed(alice: Client):
    _ = alice.post(ADD, confirmed(FREE_TEXT | {"reasoning": ["default", "off"]}))
    batch = BatchModel.objects.get()
    response = alice.get(reverse("admin:portal_batch_change", args=[batch.pk]))

    assert response.status_code == 200
    assert b'name="_save"' not in response.content
    assert str(batch.uuid)[:8].encode() in response.content
    assert b"reasoning=off" in response.content
    assert b"case-2" in response.content
    assert (
        alice.get(reverse("admin:portal_batch_delete", args=[batch.pk])).status_code
        == 403
    )


def test_the_portal_is_unfold_s_admin(alice: Client):
    response = alice.get(reverse("admin:index"))

    assert response.status_code == 200
    assert b"ChatDDX Portal" in response.content
    assert CHANGELIST.encode() in response.content


def test_one_with_nothing_to_use_is_told_how_to_get_it(
    client: Client, django_user_model: Any
):
    client.force_login(django_user_model.objects.create_superuser(username="nobody"))
    response = client.get(ADD)

    assert response.status_code == 200
    assert any(
        "chatddx init-data nobody" in str(message)
        for message in response.context["messages"]
    )
