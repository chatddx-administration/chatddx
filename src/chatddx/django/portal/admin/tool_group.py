# pyright: basic
from django.contrib import admin

from chatddx.django.portal.admin.base import BranchModelAdmin
from chatddx.django.portal.forms import ToolGroupForm
from chatddx.django.portal.forms.tool import ToolForm
from chatddx.repo import proxies


@admin.register(proxies.ToolGroup)
class ToolGroupAdmin(BranchModelAdmin[proxies.ToolGroup]):
    form = ToolGroupForm
    name = "tool_group"
    list_display = BranchModelAdmin.list_display + []  # pyright: ignore


@admin.register(proxies.Tool)
class ToolAdmin(BranchModelAdmin[proxies.Tool]):
    form = ToolForm
    name = "tool"

    list_display = BranchModelAdmin.list_display + [  # pyright: ignore
        "type",
    ]

    @admin.display(
        description="Type",
        ordering="target__type",
    )
    def type(self, obj: proxies.Tool) -> str:
        return obj.target.get_type_display()  # pyright: ignore
