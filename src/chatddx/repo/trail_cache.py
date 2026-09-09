from collections import OrderedDict
from typing import cast

from chatddx.core.django_fields import (
    resolve_related_array_fields,
    resolve_related_array_fields_async,
)
from chatddx.repo.base import TrailModel, TrailSpec
from chatddx.repo.main import Repo


class TrailCache:
    cache: OrderedDict[tuple[type[TrailSpec], int], TrailSpec]

    def __init__(self, max_size: int):
        self.max_size: int = max_size
        self.cache = OrderedDict()

    def get_sync[T: TrailSpec](self, Spec: type[T], pk: int) -> T:
        trail_model_cls = Repo(Spec, TrailModel)
        key = (Spec, pk)

        if key in self.cache:
            self.cache.move_to_end(key)
            return cast(T, self.cache[key])

        trail_model = trail_model_cls.objects.get(pk=pk)
        trail_model = resolve_related_array_fields(trail_model)
        return Spec.model_validate(trail_model)

    async def get_async[T: TrailSpec](self, Spec: type[T], pk: int) -> T:
        trail_model_cls = Repo(Spec, TrailModel)
        key = (Spec, pk)

        if key in self.cache:
            self.cache.move_to_end(key)
            return cast(T, self.cache[key])

        trail_model = await trail_model_cls.objects.select_related().aget(pk=pk)
        trail_model = await resolve_related_array_fields_async(trail_model)
        spec = Spec.model_validate(trail_model)

        self.cache[key] = spec

        if len(self.cache) > self.max_size:
            _ = self.cache.popitem(last=False)

        return spec


trail_cache = TrailCache(max_size=100)
