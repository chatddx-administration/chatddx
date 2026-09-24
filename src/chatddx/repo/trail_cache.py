from collections import OrderedDict
from typing import cast

from chatddx.repo.bundles import entity_of
from chatddx.repo.families import TrailOut
from chatddx.repo.utils import (
    resolve_trail,
    resolve_trail_async,
)


class TrailCache:
    cache: OrderedDict[tuple[type[TrailOut], int], TrailOut]

    def __init__(self, max_size: int):
        self.max_size: int = max_size
        self.cache = OrderedDict()

    def get_sync[T: TrailOut](self, Spec: type[T], pk: int) -> T:
        key = (Spec, pk)

        if key in self.cache:
            self.cache.move_to_end(key)
            return cast(T, self.cache[key])

        trail_model = entity_of(Spec).trail_model.objects.get(pk=pk)
        spec = Spec.model_validate(resolve_trail(trail_model))

        self._keep(key, spec)

        return spec

    async def get_async[T: TrailOut](self, Spec: type[T], pk: int) -> T:
        key = (Spec, pk)

        if key in self.cache:
            self.cache.move_to_end(key)
            return cast(T, self.cache[key])

        # `resolve_trail` fetches what the trail reaches, a table at a time
        trail_model = await entity_of(Spec).trail_model.objects.aget(pk=pk)
        spec = Spec.model_validate(await resolve_trail_async(trail_model))

        self._keep(key, spec)

        return spec

    def _keep(self, key: tuple[type[TrailOut], int], spec: TrailOut) -> None:
        # a trail is immutable, so what is kept is never stale
        self.cache[key] = spec

        if len(self.cache) > self.max_size:
            _ = self.cache.popitem(last=False)


trail_cache = TrailCache(max_size=100)
