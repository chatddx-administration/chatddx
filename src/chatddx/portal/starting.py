from dataclasses import dataclass
from typing import Annotated, cast, get_args

from fastapi import APIRouter, Form, Query, Request, Response
from fastapi.responses import RedirectResponse

from chatddx.api import schemas, threads as api
from chatddx.api.state import refused
from chatddx.bench import Bench, Endpoint, NotFound
from chatddx.factors.base import Invalid, resolve
from chatddx.factors.trial import Order, Trial
from chatddx.locale import pgettext_noop, refusal

from .pages import BenchDep, page

router = APIRouter()


@dataclass(frozen=True)
class _Starting:
    thread: schemas.Thread
    versions: list[schemas.Versioned]
    trial: Trial
    endpoint: Endpoint | None
    refused: str | None


@router.get("/lab/run")
def beginning(
    request: Request,
    bench: BenchDep,
    trial: Annotated[list[int] | None, Query()] = None,
) -> Response:
    return page(
        request,
        "starting.html",
        person=bench.person,
        trials=[_starting(bench, t) for t in dict.fromkeys(trial or ())],
        orders=get_args(Order),
    )


@router.post("/lab/run")
def starting(
    bench: BenchDep,
    version: Annotated[list[str] | None, Form()] = None,
    concurrency: Annotated[str, Form()] = "",
    order: Annotated[str, Form()] = "",
    score: Annotated[bool, Form()] = False,
) -> Response:
    with refused():
        if order and order not in get_args(Order):
            raise Invalid.of(
                "no order %(order)s: the orders are %(orders)s",
                order=repr(order),
                orders=", ".join(get_args(Order)),
            )
        picked = [int(v) for v in version or () if v]
        if not picked:
            raise Invalid.of("pick a trial to run")
        runs = bench.start_trials(
            picked,
            int(concurrency) if concurrency.strip() else None,
            cast(Order, order) if order else None,
        )
    for running in runs:
        _ = bench.queue(running, score)
    return RedirectResponse(f"/runs/{runs[0].run}", 303)


def _starting(bench: Bench, thread: int) -> _Starting:
    shown = api.thread(bench, thread)
    if shown.kind != "trial":
        raise NotFound.of(
            "no trial %(thread)s for %(login)s", thread=thread, login=bench.person.login
        )
    held = resolve(bench.store.get, shown.head.digest, Trial)
    versions = api.edits(bench, thread)
    try:
        at = bench.endpoint(bench.inventory.serving(held.engine))
    except LookupError:
        named = shown.name or shown.title
        why = refusal(
            pgettext_noop("refusal", "%(trial)s is out of date: update it on its page"),
            {"trial": named},
        )
        return _Starting(shown, versions, held, None, why)
    return _Starting(shown, versions, held, at, None)
