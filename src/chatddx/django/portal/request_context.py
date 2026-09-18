from dataclasses import dataclass, field
from weakref import WeakKeyDictionary

from django.http import HttpRequest

from chatddx.repo.families.django import BranchModel


@dataclass
class RequestContext:
    canon: BranchModel
    created: bool
    changed: list[str] = field(default_factory=list)

    @property
    def is_noop(self) -> bool:
        return not self.created and not self.changed


type RequestContexts = WeakKeyDictionary[HttpRequest, RequestContext]

request_contexts: RequestContexts = WeakKeyDictionary()
