# pyright: basic
"""What the repl does, over HTTP; `/api/docs` lists the endpoints."""

from django.http import HttpRequest
from django.middleware.csrf import get_token
from ninja import NinjaAPI

from chatddx.django.api import cell, registry, runs
from chatddx.django.api.identity import Identified, identity_of
from chatddx.django.api.schemas import Me
from chatddx.django.api.showing import refusals_of
from chatddx.repl.bench import Ambiguous, NotFound
from chatddx.repo.store.branch import AmbiguousBranchError, BranchNotFoundError
from chatddx.runtime.resolution import CellRefused

api = NinjaAPI(
    title="ChatDDX API",
    version="0.0.0+dev",
    auth=Identified(),
    urls_namespace="api",
)

api.add_router("/registry", registry.router)
api.add_router("/", cell.router)
api.add_router("/", runs.router)


@api.get("/me", response=Me, tags=["identity"])
def me(request: HttpRequest):
    """Who the request acts as; it sets the CSRF cookie a session's posts send back."""
    _ = get_token(request)
    return Me(name=identity_of(request), guest=not request.user.is_authenticated)


@api.exception_handler(BranchNotFoundError)
@api.exception_handler(NotFound)
def not_found(request: HttpRequest, error: Exception):
    return api.create_response(request, {"detail": str(error)}, status=404)


@api.exception_handler(AmbiguousBranchError)
@api.exception_handler(Ambiguous)
def ambiguous(request: HttpRequest, error: Exception):
    return api.create_response(request, {"detail": str(error)}, status=409)


@api.exception_handler(CellRefused)
def refused(request: HttpRequest, error: CellRefused):
    return api.create_response(
        request,
        {
            "detail": "the cell is refused on its stack",
            "refusals": [
                refusal.model_dump() for refusal in refusals_of(error.refusals)
            ],
        },
        status=422,
    )
