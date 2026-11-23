import threading
from collections.abc import AsyncGenerator, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from importlib import metadata
from typing import Any

import psycopg
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic.json_schema import models_json_schema
from starlette.exceptions import HTTPException

from chatddx.bench import Ambiguous, Conflict, MovedOn, NotFound, OverQuota
from chatddx.factors import Invalid
from chatddx.inventory import Inventory
from chatddx.runner import Refused
from chatddx.store import UnderWay
from chatddx.whoops import Whoops
from chatddx.worker import Worker

from . import (
    breakdown,
    families,
    faring,
    measuring,
    people,
    queue,
    runs,
    scores,
    threads,
    world,
)
from .listening import Listener
from .schemas import EVENTS, Code, Error
from .state import AppState, Refusing

STATUSES: dict[type[Exception], tuple[int, Code]] = {
    NotFound: (404, "not_found"),
    Ambiguous: (409, "ambiguous"),
    Conflict: (409, "conflict"),
    MovedOn: (409, "moved_on"),
    OverQuota: (429, "over_quota"),
    Refused: (422, "refused"),
    UnderWay: (409, "conflict"),
    Invalid: (422, "refused"),
}

CODES: dict[int, Code] = {
    401: "unauthenticated",
    403: "cross_site",
    404: "not_found",
    405: "not_allowed",
    409: "conflict",
    422: "refused",
    429: "over_quota",
}


def _answer(
    status: int, error: Error, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        error.model_dump(mode="json", exclude_none=True), status, headers
    )


def _status(status: int, code: Code) -> Callable[[Request, Exception], JSONResponse]:
    def handle(_: Request, e: Exception) -> JSONResponse:
        return _answer(status, Error.of(e, code))

    return handle


def _whoops(_: Request, e: Exception) -> JSONResponse:
    assert isinstance(e, Whoops)
    return _answer(500, Error(detail=e.message, code="whoops", pass_on=e.pass_on))


# Compromise: Raw, though it may quote sensitive content, until edges hold that back.
def _raw(_: Request, e: Exception) -> JSONResponse:
    return _answer(500, Error(detail=f"{type(e).__name__}: {e}", code="error"))


# Policy: a value the database can't take, a number past its integers or a text holding U+0000, is
# the request's to set right wherever it was given, so it is refused here once for every route.
def _unstorable(_: Request, e: Exception) -> JSONResponse:
    assert isinstance(e, psycopg.DataError)
    refused = Invalid.of(
        "the request holds a value that can't be kept: a number too large, or a text "
        + "holding U+0000"
    )
    return _answer(422, Error.of(refused, "refused"))


def _http(_: Request, e: Exception) -> JSONResponse:
    assert isinstance(e, HTTPException)
    code = CODES.get(e.status_code, "error")
    error = (
        Error.of(e.refused, code, e.detail)
        if isinstance(e, Refusing)
        else Error(detail=e.detail, code=code)
    )
    return _answer(e.status_code, error, e.headers)


def _invalid(_: Request, e: Exception) -> JSONResponse:
    assert isinstance(e, RequestValidationError)
    return _answer(
        422, Error(detail=jsonable_encoder(e.errors()), code="unprocessable")
    )


def _with_models(made: FastAPI) -> Callable[[], dict[str, Any]]:
    described = made.openapi

    def openapi() -> dict[str, Any]:
        document = described()
        _, models = models_json_schema(
            [(model, "serialization") for model in (*EVENTS.values(), Error)],
            ref_template="#/components/schemas/{model}",
        )
        document["components"]["schemas"].update(models.get("$defs", {}))
        return document

    return openapi


def _lifespan(
    worker: bool,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(made: FastAPI) -> AsyncGenerator[None]:
        held = made.state.chatddx
        assert isinstance(held, AppState)
        stopping = threading.Event()
        serving: threading.Thread | None = None
        made_worker = Worker(held.conninfo, held.inventory)
        if worker:
            serving = threading.Thread(
                target=made_worker.serve,
                args=(stopping,),
                name="chatddx-worker",
                daemon=True,
            )
            serving.start()
        try:
            yield
        finally:
            stopping.set()
            made_worker.wake()
            if serving is not None:
                await run_in_threadpool(serving.join)
            held.listener.stop()

    return lifespan


def app(
    inventory: Inventory,
    conninfo: str,
    worker: bool = False,
    synthetic: int | None = None,
) -> FastAPI:
    made = FastAPI(
        title="chatddx",
        version=metadata.version("chatddx"),
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=_lifespan(worker),
    )
    made.state.chatddx = AppState(conninfo, inventory, Listener(conninfo), synthetic)
    for module in (
        people,
        threads,
        breakdown,
        families,
        faring,
        world,
        runs,
        scores,
        measuring,
        queue,
    ):
        made.include_router(module.router, prefix="/api")
    for error, (status, code) in STATUSES.items():
        made.add_exception_handler(error, _status(status, code))
    made.add_exception_handler(psycopg.DataError, _unstorable)
    made.add_exception_handler(Whoops, _whoops)
    made.add_exception_handler(HTTPException, _http)
    made.add_exception_handler(RequestValidationError, _invalid)
    made.add_exception_handler(Exception, _raw)
    made.openapi = _with_models(made)
    return made
