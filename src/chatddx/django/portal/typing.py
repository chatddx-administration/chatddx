from typing import cast, override

from django.db.models import Model, QuerySet
from django.http import HttpRequest
from unfold.admin import ModelAdmin  # pyright: ignore[reportMissingTypeStubs]


class TypedModelAdmin[T: Model](ModelAdmin):
    @override
    def get_queryset(self, request: HttpRequest) -> QuerySet[T]:
        return cast(QuerySet[T], super().get_queryset(request))
