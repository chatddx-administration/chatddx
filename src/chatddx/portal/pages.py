import json
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, cast
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import JsonValue

from chatddx import locale, settings
from chatddx.api import schemas, threads as api_threads
from chatddx.api.people import COOKIE, ConnDep, drop_cookie, keep_cookie, same_origin
from chatddx.api.state import NO_STORE, state
from chatddx.bench import Bench, Conflict, MovedOn, OverQuota
from chatddx.factors import Worded
from chatddx.factors.base import LANGUAGE
from chatddx.identity import Person
from chatddx.store import People, UnderWay

from .shelves import display_kind
from .titles import display_case, display_thread
from .translations import visible

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
# Accommodating for Jinja, whose tojson sorts keys: an island sends back what it's given,
# and a component's digest holds the order of its keys.
templates.env.policies["json.dumps_kwargs"] = {"sort_keys": False}
templates.env.add_extension("jinja2.ext.i18n")
templates.env.policies["ext.i18n.trimmed"] = True
templates.env.install_gettext_callables(  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    gettext=locale.gettext,
    ngettext=locale.ngettext,
    newstyle=True,
    pgettext=locale.pgettext,
    npgettext=locale.npgettext,
)


def _display_time(at: datetime | None) -> str:
    return "—" if at is None else at.strftime("%Y-%m-%d %H:%M")


def _display_digest(digest: str | None) -> str:
    return "—" if digest is None else digest.removeprefix("sha256:")[:12]


def _display_json(value: JsonValue) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


def _display_between(value: JsonValue) -> str:
    lines = _display_json(value).split("\n")
    return "\n".join(line.removeprefix("  ") for line in lines[1:-1])


def _refusal(error: schemas.Error) -> str:
    assert error.wording is not None
    return locale.refusal(error.wording, error.params or {})


templates.env.filters.update(
    when=_display_time,
    short=_display_digest,
    pretty=_display_json,
    between=_display_between,
    visible=visible,
    kind=display_kind,
    language=locale.display_language,
    listed=locale.display_list,
    case=display_case,
    titled=display_thread,
    localized=locale.localized,
    refusal=_refusal,
    upfirst=locale.upfirst,
)

# Accommodating for Jinja, whose globals are typed as its own defaults are.
cast(dict[str, object], templates.env.globals).update(
    language_pattern=LANGUAGE.pattern.strip("^$"),
    settings=settings,
)

router = APIRouter()

_CHOSEN_FOR = 365 * 24 * 60 * 60


class SignInFirst(Exception):
    def __init__(self, request: Request) -> None:
        super().__init__("sign in first")
        query = request.url.query
        self.next: str = request.url.path + (f"?{query}" if query else "")


def to_sign_in(_: Request, e: Exception) -> Response:
    assert isinstance(e, SignInFirst)
    return RedirectResponse(f"/sign-in?{urlencode({'next': e.next})}", 303)


def page(request: Request, name: str, status: int = 200, **context: Any) -> Response:
    assets = request.app.state.assets
    negotiated = request.app.state.locales.negotiate(
        request.headers.get("accept-language"), request.cookies.get(locale.CHOSEN)
    )
    with locale.localizing(negotiated):
        return templates.TemplateResponse(
            request,
            name,
            {"assets": assets, "locale": negotiated, **context},
            status_code=status,
            headers=NO_STORE,
        )


def within(next: str | None) -> str:
    if next is None or not next.startswith("/") or next.startswith(("//", "/\\")):
        return "/"
    return next


def _person(request: Request, conn: ConnDep) -> Person | None:
    token = request.cookies.get(COOKIE)
    return None if token is None else People(conn).session(token)


def signed_in(request: Request, conn: ConnDep) -> Person:
    person = _person(request, conn)
    if person is None:
        raise SignInFirst(request)
    same_origin(request)
    return person


type PersonDep = Annotated[Person, Depends(signed_in)]


def page_bench(request: Request, conn: ConnDep, person: PersonDep) -> Bench:
    held = state(request)
    return Bench(conn, person, held.inventory)


type BenchDep = Annotated[Bench, Depends(page_bench)]


# Policy: what a person can set right on the page they sent, which shows it again with
# what they typed and why it was refused; the rest is answered as the API answers it.
def refusable(e: ValueError) -> bool:
    return not isinstance(e, (Conflict, MovedOn, OverQuota, UnderWay))


# Policy: what a person can cause is worded, and what isn't worded they couldn't have
# caused, so it is passed on as it is.
def refusal_of(e: Exception) -> str:
    if isinstance(e, Worded) and e.wording is not None:
        return locale.refusal(e.wording, e.params)
    title = locale.upfirst(locale.tr("can't be done"))
    return f"{title}. {locale.tr('Copy this and send it to drift@chatddx.com:')} {e}"


def own_first(bench: Bench, found: list[schemas.Thread]) -> list[schemas.Thread]:
    login = bench.person.login
    return sorted(found, key=lambda t: (t.owner != login, (t.name or t.title).lower()))


def configurations(bench: Bench) -> list[schemas.Thread]:
    """The person's own configurations of generation, by name: those Review runs a case
    under and Compose lists."""
    login = bench.person.login
    found = api_threads.threads(
        bench, "configuration", purpose="generation", owner=login
    )
    return sorted(found, key=lambda t: t.name or t.title)


def _back(request: Request) -> str | None:
    referer = urlsplit(request.headers.get("referer", ""))
    if not referer.path or referer.netloc != request.url.netloc:
        return None
    back = within(referer.path + (f"?{referer.query}" if referer.query else ""))
    here = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return None if request.method == "GET" and back == here else back


def paged(
    answer: Callable[[Request, Any], Response | Awaitable[Response]],
) -> Callable[[Request, Exception], Response]:
    def handle(request: Request, e: Exception) -> Response:
        said = answer(request, e)
        assert isinstance(said, Response)
        if request.url.path.startswith("/api/") or not isinstance(said, JSONResponse):
            return said
        with state(request).connect() as conn:
            person = _person(request, conn)
        error = schemas.Error.model_validate_json(bytes(said.body))
        if error.code == "whoops":
            assert isinstance(error.detail, str)
            error = error.model_copy(update={"detail": locale.whoops(error.detail)})
        return page(
            request,
            "error.html",
            said.status_code,
            error=error,
            person=person,
            back=_back(request),
        )

    return handle


@router.get("/")
def home(request: Request, conn: ConnDep) -> Response:
    if _person(request, conn) is None:
        return page(request, "landing.html")
    bench = page_bench(request, conn, signed_in(request, conn))
    return page(
        request,
        "home.html",
        person=bench.person,
        island="home",
        home={
            "limit": settings.TYPED_TEXT_LIMIT,
            "models": [
                {"name": h.name, "weights": h.weights}
                for h, at in bench.handles()
                if at is not None and bench.inventory.takes_typed(at.name)
            ],
        },
    )


@router.get("/sign-in")
def signing_in_page(
    request: Request, conn: ConnDep, next: str = "/", signed: bool = False
) -> Response:
    if _person(request, conn) is not None:
        return RedirectResponse(within(next), 303)
    return page(request, "sign-in.html", next=within(next), unkept=signed)


@router.post("/sign-in")
def signing_in(
    request: Request,
    conn: ConnDep,
    login: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/",
) -> Response:
    same_origin(request)
    people = People(conn)
    person = people.authenticate(login, password)
    if person is None:
        return page(request, "sign-in.html", next=within(next), login=login, wrong=True)
    # Policy: a sign-in passes by the sign-in page once more, which sends the person on if
    # their browser kept the session's cookie and says so if it didn't.
    query = urlencode({"next": within(next), "signed": "true"})
    signed = RedirectResponse(f"/sign-in?{query}", 303)
    keep_cookie(signed, people.open_session(person.id))
    return signed


@router.post("/locale")
def choosing_locale(
    request: Request, tag: Annotated[str, Form()], next: Annotated[str, Form()] = "/"
) -> Response:
    same_origin(request)
    chosen = RedirectResponse(within(next), 303)
    if tag in request.app.state.locales.by_tag:
        chosen.set_cookie(
            locale.CHOSEN, tag, max_age=_CHOSEN_FOR, secure=True, samesite="lax"
        )
    return chosen


@router.post("/sign-out")
def signing_out(request: Request, conn: ConnDep) -> Response:
    same_origin(request)
    token = request.cookies.get(COOKIE)
    if token is not None:
        People(conn).close_session(token)
    out = RedirectResponse("/sign-in", 303)
    drop_cookie(out)
    return out
