# pyright: basic
"""
Every reference one record renders to another goes through here, so the
portal reads the same in a changelist as it does in a read-only form: one
anchor, one class, one rule for the label.

The label is always the target's `__str__` -- the proxies are where a model
says how it reads (`chatddx.history.proxies`,
`chatddx.repo.families.django`) -- so no caller spells a label out for
itself.

`static/css/admin_link.css` is the one place the look is defined; UNFOLD's
STYLES loads it on every admin page.
"""

from typing import Any

from django.db.models import Model
from django.urls import reverse
from django.utils.http import urlencode
from unfold.utils import format_html

from chatddx.repo.families.django import TrailModel

# The hook `admin_link.css` styles. Anything that is a reference to another
# record carries it; nothing else does.
LINK_CLASS = "chatddx-link"


def link(url: str, label: Any):
    return format_html('<a class="{}" href="{}">{}</a>', LINK_CLASS, url, label)


def admin_url(model: type[Model] | Model, view: str, *args: Any, **params: Any) -> str:
    meta = model._meta  # pyright: ignore[reportPrivateUsage]
    url = reverse(f"admin:{meta.app_label}_{meta.model_name}_{view}", args=args)

    return f"{url}?{urlencode(params)}" if params else url


def change_link(obj: Model, label: Any = None, **params: Any):
    """
    `obj`'s change form, under `str(obj)`.

    `label` names it otherwise, for the cases where the thing referred to
    and the page that opens are not the same record: an experiment points
    at an agent *trail*, but what a reader wants to open is their own
    *branch* of it. The label still comes from a `__str__` -- the trail's.
    """
    url = admin_url(obj, "change", obj.pk, **params)

    return link(url, obj if label is None else label)


def add_link(model: type[Model], label: Any, **params: Any):
    """
    A blank add form, seeded through `params`.

    Where a reference points at something the viewer has no branch of, there
    is no change form to open, so the link offers to start one instead.
    """
    return link(admin_url(model, "add", **params), label)


def named[T: TrailModel](trail: T, branch_name: str | None) -> T:
    """
    A trail labelled by the branch the viewer has of it.

    `TrailModel.__str__` reads `branch_name` off the instance, which is where
    `qs_owned_trails` annotates it. Where the name was annotated onto the
    *referring* row instead -- an experiment's `agent_branch_name`, say --
    this puts it where `__str__` looks for it.
    """
    trail.branch_name = branch_name  # pyright: ignore[reportAttributeAccessIssue]

    return trail
