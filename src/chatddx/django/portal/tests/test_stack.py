# pyright: basic
import html
import json
import re
from typing import Any, override

import httpx2
import pytest
from django.test import Client
from django.urls import reverse

from chatddx.conftest import Recommit
from chatddx.core.models import IdentityModel
from chatddx.dev.fake_vllm import FakeTransport, models
from chatddx.dev.samples import sample
from chatddx.django.portal import checking
from chatddx.django.portal.stacks import page_of, page_of_run
from chatddx.repo.entities.llm.django import LLMBranchModel
from chatddx.repo.entities.stack.django import StackBranchModel

pytestmark = pytest.mark.django_db

CHANGELIST = reverse("admin:portal_stack_changelist")
FAKE = "qwen3-8b-awq@fake"
PELLE = "qwen3-8b-awq@pelle"


def versions(name: str, owner: str = "archive") -> list[StackBranchModel]:
    return list(
        StackBranchModel.objects.filter(owner__name=owner, name=name).order_by(
            "timestamp", "id"
        )
    )


def shown(client: Client, url: str) -> Any:
    response = client.get(url)
    assert response.status_code == 200, response.content

    return response.context["shown"]


def fields(of: Any) -> dict[str, Any]:
    shown = of.fields if hasattr(of, "fields") else of.details
    return {str(field.label): field.items or field.value for field in shown}


class Serving(FakeTransport):
    def __init__(
        self,
        listed: list[dict[str, Any]] | None = None,
        version: str = "fake",
        status: int = 200,
        down: bool = False,
    ):
        super().__init__()
        self.listed: list[dict[str, Any]] = (
            models()["data"] if listed is None else listed
        )
        self.version: str = version
        self.status: int = status
        self.down: bool = down
        self.headers: list[dict[str, str]] = []

    @override
    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        self.headers.append(dict(request.headers))

        if self.down:
            raise httpx2.ConnectError("[Errno 111] Connection refused", request=request)

        if request.method == "GET" and request.url.path.endswith("/models"):
            return httpx2.Response(
                self.status, json={"object": "list", "data": self.listed}
            )

        if request.method == "GET" and request.url.path == "/version":
            return httpx2.Response(200, json={"version": self.version})

        return await super().handle_async_request(request)


def checked(
    client: Client, url: str, transport: Any, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, tuple[str, str]], list[dict[str, Any]]]:
    monkeypatch.setattr(checking, "TRANSPORT", transport)
    page = client.get(url)
    response: Any = client.post(page.context["test_url"])

    assert response.status_code == 200
    assert response["Content-Type"] == "application/x-ndjson"

    lines = [
        json.loads(line)
        for line in b"".join(response.streaming_content).decode().splitlines()
    ]
    checks: dict[str, tuple[str, str]] = {}

    for line in lines:
        if "html" in line:
            [(key, state)] = re.findall(
                r'id="check-(\w+)" class="portal-check portal-check-(\w+)"',
                line["html"],
            )
            said = re.findall(r'portal-check-said">([^<]*)<', line["html"])
            checks[key] = (state, html.unescape(said[0]) if said else "")

    return checks, [line for line in lines if "stream" in line]


def test_the_list_is_of_the_stacks_the_owner_runs_on(alice: Client):
    listed = alice.get(CHANGELIST).context["cl"].result_list

    assert sorted(stack.name for stack in listed) == [
        "gpt-oss-20b@fake",
        "gpt-oss-20b@malborg",
        "qwen3-8b-awq@fake",
        "qwen3-8b-awq@malborg",
        PELLE,
    ]


def test_a_stack_s_page_shows_it_part_by_part(alice: Client):
    [row] = versions(PELLE)
    page = shown(alice, page_of(row.pk))
    parts = {part.key: part for part in page.parts}

    assert (page.version.number, page.version.of, page.newer) == (1, 1, None)
    assert page.owner == "the archive's"
    assert fields(page)["Endpoint"] == "http://pelle.km:12009/v1/"
    assert fields(page)["Served name"] == "Qwen/Qwen3-8B-AWQ"
    assert fields(page)["Credential"] == "none: it takes no secret"
    assert list(parts) == ["llm", "serving", "machine", "os"]
    assert parts["llm"].name == "qwen3-8b-awq"
    assert (
        "off: chat_template_kwargs = {enable_thinking = false}"
        in fields(parts["llm"])["Reasoning"]
    )
    assert fields(parts["serving"])["Arguments"] == [
        "enable-auto-tool-choice",
        "enforce-eager",
        "max-model-len = 8192",
        "tool-call-parser = hermes",
    ]
    assert fields(parts["serving"])["Provides"] == "a tool-call parser"
    assert fields(parts["machine"])["GPUs"] == [
        "NVIDIA GeForce RTX 3070, 8192 MiB (GPU-6f519b58-d1e4-4366-8603-a0dce09a0589)"
    ]
    assert fields(parts["os"])["Hostname"] == "pelle"


def test_an_earlier_version_says_a_newer_one_is_saved_and_what_it_changed(
    alice: Client, recommit: Recommit
):
    recommit("stack", FAKE, max_jobs=2, endpoint="http://localhost:12100/v1/")
    earlier, latest = versions(FAKE)
    page = shown(alice, page_of(earlier.pk))

    assert (page.version.number, page.version.of) == (1, 2)
    assert page.newer.url == page_of(latest.pk)
    assert [(str(c.label), c.before, c.after) for c in page.newer.changes] == [
        ("Endpoint", "http://localhost:12099/v1/", "http://localhost:12100/v1/"),
        ("Slots", "4", "2"),
    ]
    assert (page.before, page.after) == (None, page_of(latest.pk))
    assert b"A newer version of qwen3-8b-awq@fake is saved: version 2" in (
        alice.get(page_of(earlier.pk)).content
    )

    latest_page = shown(alice, page_of(latest.pk))

    assert (latest_page.newer, latest_page.before) == (None, page_of(earlier.pk))
    assert b"A newer version" not in alice.get(page_of(latest.pk)).content


def test_a_detail_left_out_changes_from_its_default(alice: Client, recommit: Recommit):
    recommit("stack", PELLE, max_jobs=2)
    earlier, _ = versions(PELLE)
    page = shown(alice, page_of(earlier.pk))

    assert [(str(c.label), c.before, c.after) for c in page.newer.changes] == [
        ("Slots", "1", "2")
    ]


def test_a_run_s_stack_is_the_version_it_read_its_llm_s_too(
    alice: Client, recommit: Recommit
):
    run = sample("alice", "typical", case="case-1")
    read = page_of_run(run)
    assert read is not None and run.stack_branch_id is not None
    run_page = alice.get(reverse("admin:portal_run_change", args=[run.uuid]))
    details = {str(d.label): d for d in run_page.context["shown"].details}

    assert read == page_of(run.stack_branch_id, run.llm_branch_id)
    assert details["Stack"].link == read
    assert details["LLM"].link == f"{read}#llm"

    recommit("stack", FAKE, max_jobs=2)
    recommit("llm", "qwen3-8b-awq", source=None)
    page = shown(alice, read)
    [llm] = [part for part in page.parts if part.key == "llm"]

    assert page.row.pk == run.stack_branch_id
    assert page.newer.version.number == 2
    assert (llm.version.number, llm.version.of) == (1, 2)
    assert [str(change.label) for change in llm.newer.changes] == ["Source"]
    assert fields(llm)["Source"] != "—"
    [latest_llm] = [
        part for part in shown(alice, page.newer.url).parts if part.key == "llm"
    ]
    assert (latest_llm.version, fields(latest_llm)["Source"]) == (None, "—")


def test_a_stack_another_keeps_to_themselves_is_not_found(
    alice: Client, recommit: Recommit
):
    recommit("stack", FAKE, owner="other")
    [theirs] = versions(FAKE, owner="other")

    assert alice.get(page_of(theirs.pk)).status_code == 404
    assert (
        alice.get(reverse("admin:portal_stack_change", args=["x"])).status_code == 404
    )


def test_an_llm_the_stack_doesn_t_hold_is_none_of_its_page_s(alice: Client):
    [fake] = versions(FAKE)
    gpt_oss = LLMBranchModel.objects.get(owner__name="archive", name="gpt-oss-20b")
    page = shown(alice, page_of(fake.pk, gpt_oss.pk))
    [llm] = [part for part in page.parts if part.key == "llm"]

    assert (page.query, llm.name, llm.version) == ("", "qwen3-8b-awq", None)


def test_the_test_checks_the_stack_live_and_streams_how_it_goes(
    alice: Client, monkeypatch: pytest.MonkeyPatch
):
    [row] = versions(FAKE)
    checks, streamed = checked(alice, page_of(row.pk), FakeTransport(), monkeypatch)

    assert {key: state for key, (state, _) in checks.items()} == {
        "reached": "passed",
        "served": "passed",
        "snapshot": "warned",
        "context": "passed",
        "engine": "skipped",
        "answers": "passed",
        "off": "passed",
        "native": "passed",
        "tool": "passed",
        "prompted": "passed",
        "tools": "passed",
    }
    assert checks["served"][1] == "serves Qwen/Qwen3-8B-AWQ"
    assert checks["context"][1] == "32768 tokens, the whole of what the LLM takes"
    assert checks["tools"][1] == "sentinel_op(v1=1, v2=1) returned 0, and it answered"
    assert [event["stream"] for event in streamed if event["check"] == "answers"][
        :1
    ] == ["thinking"]
    assert "Fake diagnosis A" in "".join(
        event["text"]
        for event in streamed
        if event["check"] == "answers" and event["stream"] == "answer"
    )


def test_the_test_says_what_the_facts_refuse_and_tries_it_not(
    alice: Client, monkeypatch: pytest.MonkeyPatch
):
    [row] = versions("gpt-oss-20b@fake")
    checks, _ = checked(alice, page_of(row.pk), FakeTransport(), monkeypatch)

    assert checks["off"] == (
        "skipped",
        "always reasons: vLLM rejects reasoning_effort = none for harmony",
    )
    assert checks["answers"][0] == "passed"


def test_the_test_of_a_server_it_can_t_reach_tries_nothing_further(
    alice: Client, monkeypatch: pytest.MonkeyPatch
):
    [row] = versions(PELLE)
    checks, streamed = checked(alice, page_of(row.pk), Serving(down=True), monkeypatch)

    assert checks["reached"] == (
        "failed",
        "can't reach http://pelle.km:12009/v1: ConnectError: [Errno 111] "
        + "Connection refused",
    )
    assert {state for key, (state, _) in checks.items() if key != "reached"} == {
        "skipped"
    }
    assert checks["answers"][1] == "not tried: it can't be reached"
    assert streamed == []


def test_the_test_of_a_server_refusing_the_credential_says_so(
    alice: Client, monkeypatch: pytest.MonkeyPatch
):
    [row] = versions(PELLE)
    checks, _ = checked(alice, page_of(row.pk), Serving(status=401), monkeypatch)

    assert checks["reached"] == ("failed", "refuses the credential: HTTP 401")
    assert checks["answers"] == (
        "skipped",
        "not tried: the server doesn't say what it serves",
    )


class Broken(FakeTransport):
    @override
    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        raise RuntimeError("the wires crossed")


def test_what_breaks_the_test_is_said_where_it_broke(
    alice: Client, monkeypatch: pytest.MonkeyPatch
):
    [row] = versions(FAKE)
    checks, _ = checked(alice, page_of(row.pk), Broken(), monkeypatch)

    assert checks["reached"] == ("failed", "RuntimeError: the wires crossed")
    assert checks["answers"] == ("skipped", "not tried: the Test broke off")


def test_the_test_of_a_server_serving_another_llm_says_what_it_serves(
    alice: Client, monkeypatch: pytest.MonkeyPatch
):
    [row] = versions(PELLE)
    other = [{"id": "Qwen/Qwen3-14B", "root": "Qwen/Qwen3-14B", "max_model_len": 8192}]
    checks, _ = checked(alice, page_of(row.pk), Serving(other), monkeypatch)

    assert checks["served"] == (
        "failed",
        "serves Qwen/Qwen3-14B, not Qwen/Qwen3-8B-AWQ",
    )
    assert checks["answers"] == (
        "skipped",
        "not tried: the server doesn't serve the LLM",
    )


def test_the_test_holds_the_server_to_its_stack_s_records(
    alice: Client, monkeypatch: pytest.MonkeyPatch
):
    [row] = versions(PELLE)
    snapshot = "/nix/store/vmm0f85gk4i6ymz1j8hlk9mfyjy5jq8a-Qwen3-8B-AWQ"
    served = [{"id": "Qwen/Qwen3-8B-AWQ", "root": snapshot, "max_model_len": 8192}]
    checks, _ = checked(
        alice, page_of(row.pk), Serving(served, "0.24.0+cu128"), monkeypatch
    )

    assert checks["snapshot"] == (
        "passed",
        f"loads {snapshot}, the LLM's snapshot",
    )
    assert checks["context"] == (
        "passed",
        "8192 tokens, as its serving's max-model-len says",
    )
    assert checks["engine"] == (
        "passed",
        "vLLM 0.24.0+cu128, as its serving's engine says",
    )

    elsewhere = "/nix/store/2ggzfi36z2c9gckn3fp4mgij41wyf7la-Qwen3-8B-AWQ"
    served = [{"id": "Qwen/Qwen3-8B-AWQ", "root": elsewhere, "max_model_len": 32768}]
    checks, _ = checked(alice, page_of(row.pk), Serving(served, "0.25.0"), monkeypatch)

    assert checks["snapshot"] == (
        "failed",
        f"loads {elsewhere}, not the LLM's snapshot {snapshot}",
    )
    assert checks["context"] == (
        "failed",
        "32768 tokens, where its serving's max-model-len says 8192",
    )
    assert checks["engine"] == (
        "failed",
        "vLLM 0.25.0, where its serving's engine is python3.13-vllm-0.24.0",
    )


def test_the_test_sends_the_stack_s_secret_or_says_it_is_wanting(
    alice: Client, monkeypatch: pytest.MonkeyPatch, recommit: Recommit
):
    recommit("stack", FAKE, credential="fake-key")
    _, latest = versions(FAKE)
    checks, _ = checked(alice, page_of(latest.pk), Serving(), monkeypatch)

    assert checks["reached"] == (
        "failed",
        "it takes the secret fake-key, which you don't have",
    )

    identity = IdentityModel.objects.get(name="alice")
    identity.secrets = {**identity.secrets, "fake-key": "sesame"}
    identity.save()
    serving = Serving()
    checks, _ = checked(alice, page_of(latest.pk), serving, monkeypatch)

    assert checks["reached"][0] == "passed"
    assert {headers.get("authorization") for headers in serving.headers} == {
        "Bearer sesame"
    }


def test_the_test_is_posted(alice: Client):
    [row] = versions(FAKE)
    url = reverse("admin:portal_stack_test", args=[row.pk])

    assert alice.get(url).status_code == 405
