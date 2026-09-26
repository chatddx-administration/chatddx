# pyright: basic
import re

import pytest
from django.test import Client
from django.urls import reverse

from chatddx.repo.entities.case.django import CaseBranchModel

pytestmark = pytest.mark.django_db


def header_of(content: bytes) -> list[str]:
    """What the page's header names, part by part, its chevrons left out."""
    found = re.search(rb"<h1[^>]*>(.*?)</h1>", content, re.DOTALL)
    assert found is not None, content

    return [
        " ".join(part.split())
        for part in re.findall(r">([^<>]+)<", found.group(1).decode())
        if part.strip() and part.strip() != "chevron_right"
    ]


def test_the_header_names_a_thing_as_it_is_written_and_labels_as_labels(
    alice: Client,
):
    case = CaseBranchModel.objects.filter(owner__name="alice", name="case-1").latest(
        "timestamp"
    )
    response = alice.get(reverse("admin:portal_case_change", args=[case.pk]))

    assert header_of(response.content) == ["Portal", "Cases", "case-1"]
