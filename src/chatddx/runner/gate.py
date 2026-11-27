import os

from chatddx.factors.base import Resolver, StructuralError, Worded, resolve
from chatddx.factors.cases import Case
from chatddx.factors.engine import served_model_name
from chatddx.factors.request import Skeleton, Slot
from chatddx.factors.scoring import Judge
from chatddx.factors.trial import Trial
from chatddx.inventory import Inventory

from .wire import served


class Refused(Worded):
    pass


def admit(
    inventory: Inventory,
    get: Resolver,
    endpoint: str,
    trial: Trial,
    judged: tuple[Judge, str] | None = None,
    timeout: float = 10.0,
) -> str | None:
    bar(inventory, get, endpoint, trial, judged)
    engine = trial.engine if judged is None else judged[1]
    key = _secret(inventory, endpoint)
    url = str(inventory.endpoint(endpoint).url)
    try:
        expected = served_model_name(engine, get)
        listed = served(url, secret=key, timeout=timeout)
    except (StructuralError, OSError) as e:
        raise Refused.raw(
            "endpoint %(endpoint)s can't be confirmed: %(error)s",
            endpoint=repr(endpoint),
            error=str(e),
        ) from None
    if not listed:
        raise Refused.raw(
            "endpoint %(endpoint)s can't be confirmed: it serves nothing at %(url)s, "
            + "not %(expected)s",
            endpoint=repr(endpoint),
            url=url,
            expected=expected,
        )
    if expected not in listed:
        raise Refused.raw(
            "endpoint %(endpoint)s can't be confirmed: it serves %(served)s at "
            + "%(url)s, not %(expected)s",
            endpoint=repr(endpoint),
            served=", ".join(listed),
            url=url,
            expected=expected,
        )
    return key


def bar(
    inventory: Inventory,
    get: Resolver,
    endpoint: str,
    trial: Trial,
    judged: tuple[Judge, str] | None = None,
) -> None:
    if judged is None:
        engine, whose = trial.engine, "trial"
        tools = bool(resolve(get, trial.skeleton, Skeleton).tools)
    else:
        (judge, engine), whose, tools = judged, "judge", False
        skeleton = resolve(get, judge.skeleton, Skeleton)
        if read := sorted(_slots(skeleton) & {"vignette", "appendices"}):
            raise Refused(
                f"judge {judge.digest} reads the {' and '.join(read)}, which no judge "
                + "is given"
            )
    try:
        spec = inventory.endpoint(endpoint)
        sources = sorted({resolve(get, c, Case).vignette.source for c in trial.cases})
        sensitive = [s for s in sources if inventory.source(s).sensitive]
    except LookupError as e:
        raise Refused(str(e)) from None
    if spec.engine != engine:
        raise Refused(
            f"endpoint {endpoint!r} serves engine {spec.engine}, the {whose}'s is "
            + engine
        )
    if uncleared := sorted(set(sensitive) - set(inventory.cleared.get(endpoint, ()))):
        raise Refused.of(
            "endpoint %(endpoint)s isn't cleared for source %(sources)s, which is "
            + "sensitive",
            endpoint=repr(endpoint),
            sources=", ".join(uncleared),
        )
    if tools and sensitive:
        raise Refused.of(
            "the configuration's tools would get content from source %(sources)s, "
            + "which is sensitive, and tools can't be cleared yet",
            sources=", ".join(sensitive),
        )


def _slots(skeleton: Skeleton) -> set[str]:
    return {s.slot for m in skeleton.messages for s in m.content if isinstance(s, Slot)}


def _secret(inventory: Inventory, endpoint: str) -> str | None:
    credential = inventory.endpoint(endpoint).credential
    if credential is None:
        return None
    value = os.environ.get(credential)
    if not value:
        raise Refused(
            f"endpoint {endpoint!r} needs the secret in ${credential}, which isn't set"
        )
    return value
