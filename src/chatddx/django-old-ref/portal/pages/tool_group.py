# pyright: basic
from django.contrib import admin

from chatddx.django.portal.branch import BranchModelAdmin
from chatddx.django.portal.forms.tool import ToolForm
from chatddx.django.portal.forms.tool_group import ToolGroupForm
from chatddx.repo.entities.tool.django import Tool
from chatddx.repo.entities.tool_group.django import ToolGroup


@admin.register(ToolGroup)
class ToolGroupAdmin(BranchModelAdmin[ToolGroup]):
    form = ToolGroupForm
    name = "tool_group"
    list_display = BranchModelAdmin.list_display


@admin.register(Tool)
class ToolAdmin(BranchModelAdmin[Tool]):
    form = ToolForm
    name = "tool"

    list_display = list(BranchModelAdmin.list_display) + [
        "type",
    ]

    @admin.display(
        description="Type",
        ordering="target__type",
    )
    def type(self, obj: Tool) -> str:
        return obj.target.get_type_display()  # pyright: ignore[reportAttributeAccessIssue]
