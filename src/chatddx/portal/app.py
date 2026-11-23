from pathlib import Path

import psycopg
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from chatddx import settings
from chatddx.api import app as api
from chatddx.inventory import World
from chatddx.locale import Locales, Localizing
from chatddx.whoops import Whoops

from . import (
    cases,
    compose,
    pages,
    review,
    runs,
    scores,
    scoring,
    starting,
    threads,
    world as world_page,
)
from .assets import ROUTE, Assets


def app(
    world: World,
    conninfo: str,
    assets: Path | None = None,
    worker: bool = False,
) -> FastAPI:
    made = api.app(world.inventory, conninfo, worker, world.synthetic)
    made.state.world = world
    made.state.assets = Assets(assets or settings.portal_assets())
    made.state.locales = Locales()
    made.add_middleware(Localizing)
    made.include_router(pages.router, include_in_schema=False)
    made.mount(
        ROUTE,
        StaticFiles(directory=made.state.assets.root, check_dir=False),
        name="static",
    )
    for error in (
        *api.STATUSES,
        psycopg.DataError,
        Whoops,
        HTTPException,
        RequestValidationError,
        Exception,
    ):
        made.add_exception_handler(error, pages.paged(made.exception_handlers[error]))
    made.add_exception_handler(pages.SignInFirst, pages.to_sign_in)
    for router in (
        review.router,
        compose.router,
        starting.router,
        scoring.router,
        scores.router,
        runs.router,
        cases.router,
        threads.router,
        world_page.router,
    ):
        made.include_router(router, include_in_schema=False)
    return made
