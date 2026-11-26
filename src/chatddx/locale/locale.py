import ast
import re
import sys
from collections.abc import Collection, Generator, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from gettext import GNUTranslations, NullTranslations
from io import BytesIO, StringIO
from pathlib import Path
from typing import IO, Any, Protocol, cast

from babel.core import Locale as Language, UnknownLocaleError, negotiate_locale
from babel.lists import format_list
from babel.messages.catalog import Catalog, Message
from babel.messages.extract import DEFAULT_KEYWORDS, extract
from babel.messages.mofile import write_mo
from babel.messages.pofile import PoFileError, read_po, write_po
from starlette.datastructures import Headers
from starlette.requests import HTTPConnection
from starlette.types import ASGIApp, Receive, Scope, Send

from chatddx import markers, settings
from chatddx.markers import applied, signed

__all__ = [
    "N_",
    "Coded",
    "Locale",
    "Locales",
    "Localizing",
    "Proof",
    "catalogs",
    "check",
    "display_language",
    "display_list",
    "gettext",
    "localized",
    "localizing",
    "ngettext",
    "npgettext",
    "pending",
    "pgettext",
    "pgettext_noop",
    "proofs",
    "refusal",
    "restamped",
    "said_alike",
    "tr",
    "upfirst",
    "whoops",
    "write",
]

_CATALOGS = Path(__file__).parent / "catalogs"
_WHOOPS = "whoops"
_REFUSAL = "refusal"

_KEYWORDS = {**DEFAULT_KEYWORDS, "tr": None, "pgettext_noop": ((1, "c"), 2)}
_ISLANDS = "frontend/src/"
_PORTAL = "src/chatddx/portal/"
_LEFT_OUT = re.compile(r"/test/|\.test\.ts$|\.d\.ts$|/components/ui/")
_STRING = r"""("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')"""
_CALLED = re.compile(
    rf"(?<![\w$.])(tnp|tn|tp|th|t)\(\s*{_STRING}(?:\s*,\s*{_STRING})?(?:\s*,\s*{_STRING})?"
)
_FILLED = re.compile(r"%\(\w+\)s|%%")
_ENDING = re.compile(r"[\s.…:;,!?]+$")
# Policy: a parameter named so holds a language's tag, and one named languages tags
# separated by ", ", each said by its name where the message is said.
_LANGUAGE_PARAMS = ("language", "into")
# Policy: a parameter named so holds names separated by ", ", said as a list.
_LISTED_PARAMS = ("slots", "inserts", "worked")


# Policy: the cookie that keeps the locale a person chose over their browser's.
CHOSEN = "__Host-chatddx-locale"


@dataclass(frozen=True)
class Locale:
    tag: str
    translations: NullTranslations
    islands: dict[str, str | list[str]] = field(default_factory=dict)

    @property
    def name(self) -> str:
        said = Language.parse(self.tag, sep="-").get_display_name(self.tag) or self.tag
        return said[:1].upper() + said[1:]


_ENGLISH = Locale("en", NullTranslations())

# Accommodating for Jinja, whose macros imported without context see nothing of the page
# rendering them: a page is said in the locale set around its rendering.
_LOCALIZING: ContextVar[Locale] = ContextVar("localizing", default=_ENGLISH)


class Locales:
    def __init__(self, catalogs: Path = _CATALOGS) -> None:
        self.by_tag: dict[str, Locale] = {_ENGLISH.tag: _ENGLISH}
        for path in sorted(catalogs.glob("*.po")):
            self.by_tag[path.stem] = _locale(path)

    def negotiate(
        self, accept_language: str | None, chosen: str | None = None
    ) -> Locale:
        if chosen is not None and chosen in self.by_tag:
            return self.by_tag[chosen]
        preferred = _preferred(accept_language or "")
        tag = negotiate_locale(preferred, list(self.by_tag), sep="-")
        return self.by_tag.get(tag or _ENGLISH.tag, _ENGLISH)


class Localizing:
    def __init__(self, app: ASGIApp) -> None:
        self.app: ASGIApp = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        locales: Locales = scope["app"].state.locales
        asked = Headers(scope=scope).get("accept-language")
        chosen = HTTPConnection(scope).cookies.get(CHOSEN)
        with localizing(locales.negotiate(asked, chosen)):
            await self.app(scope, receive, send)


@contextmanager
def localizing(locale: Locale) -> Generator[None]:
    token = _LOCALIZING.set(locale)
    try:
        yield
    finally:
        _LOCALIZING.reset(token)


def gettext(message: str) -> str:
    return _LOCALIZING.get().translations.gettext(message)


def tr(message: str, /, **values: object) -> str:
    return gettext(message) % values


def ngettext(singular: str, plural: str, n: int) -> str:
    return _LOCALIZING.get().translations.ngettext(singular, plural, n)


def pgettext(context: str, message: str) -> str:
    return _LOCALIZING.get().translations.pgettext(context, message)


def npgettext(context: str, singular: str, plural: str, n: int) -> str:
    return _LOCALIZING.get().translations.npgettext(context, singular, plural, n)


def N_(message: str) -> str:
    return message


# Policy: a message is said in its case where it is said in the running text, and raised
# to start a heading, a label or a sentence, so that it is one message wherever it is
# said; raising, unlike lowering, holds in every language.
def upfirst(said: str) -> str:
    return said[:1].upper() + said[1:]


def pgettext_noop(_context: str, message: str) -> str:
    return message


def whoops(message: str) -> str:
    return pgettext(_WHOOPS, message)


class Coded(Protocol):
    @property
    def code(self) -> str: ...
    @property
    def message(self) -> str: ...
    @property
    def wording(self) -> str | Sequence[str] | None: ...
    @property
    def params(self) -> Mapping[str, object]: ...


def localized(coded: Coded) -> str:
    if coded.wording is None:
        return coded.message
    return _localized(coded.code, coded.wording, coded.params)


def refusal(wording: str | Sequence[str], params: Mapping[str, object]) -> str:
    return _localized(_REFUSAL, wording, params)


def display_language(tag: str) -> str:
    try:
        said = Language.parse(tag, sep="-").get_display_name(_LOCALIZING.get().tag)
    except (ValueError, UnknownLocaleError):
        return tag
    return tag if said is None else said


def display_list(items: Sequence[str]) -> str:
    return format_list(list(items), locale=_LOCALIZING.get().tag)


def _localized(
    context: str, wording: str | Sequence[str], params: Mapping[str, object]
) -> str:
    named = _said(params)
    if isinstance(wording, str):
        return pgettext(context, wording) % named
    singular, plural = wording
    return npgettext(context, singular, plural, cast(int, params["num"])) % named


def _said(params: Mapping[str, object]) -> dict[str, object]:
    found = dict(params)
    for key in _LANGUAGE_PARAMS:
        if isinstance(held := found.get(key), str):
            found[key] = display_language(held)
    if isinstance(held := found.get("languages"), str):
        found["languages"] = display_list(
            [display_language(tag) for tag in held.split(", ")]
        )
    for key in _LISTED_PARAMS:
        if isinstance(held := found.get(key), str):
            found[key] = display_list(held.split(", "))
    return found


def _islands(
    fileobj: IO[bytes],
    _keywords: Collection[str],
    _comment_tags: Collection[str],
    **_options: Mapping[str, Any],
) -> Iterator[tuple[int, str, str | tuple[str, ...], list[str]]]:
    text = fileobj.read().decode()
    for found in _CALLED.finditer(text):
        name, *given = found.groups()
        literals = [_literal(s) for s in given if s is not None]
        lineno = text.count("\n", 0, found.start()) + 1
        if name in ("t", "th"):
            yield lineno, "gettext", literals[0], []
        elif name in ("tn", "tp") and len(literals) >= 2:
            yield (
                lineno,
                "ngettext" if name == "tn" else "pgettext",
                tuple(literals[:2]),
                [],
            )
        elif name == "tnp" and len(literals) == 3:
            yield lineno, "npgettext", tuple(literals), []


def _findings(
    fileobj: IO[bytes],
    _keywords: Collection[str],
    _comment_tags: Collection[str],
    **_options: Mapping[str, Any],
) -> Iterator[tuple[int, str, tuple[str, ...], list[str]]]:
    source = fileobj.read()
    if b"Finding.of(" not in source:
        return
    calls = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and (node.func.value.id, node.func.attr) == ("Finding", "of")
    ]
    for node in sorted(calls, key=lambda n: (n.lineno, n.col_offset)):
        where = f"{getattr(fileobj, 'name', '?')}:{node.lineno}"
        code, wording = (_written(a) for a in node.args[:2])
        if not isinstance(code, str) or wording is None:
            raise ValueError(
                f"{where}: Finding.of's code and message aren't as written"
            )
        yield _worded(where, node.lineno, code, wording)


# Policy: a refusal whose wording isn't written where it is raised is marked where it is
# written, with pgettext_noop and the context refusal.
def _refusals(
    fileobj: IO[bytes],
    _keywords: Collection[str],
    _comment_tags: Collection[str],
    **_options: Mapping[str, Any],
) -> Iterator[tuple[int, str, tuple[str, ...], list[str]]]:
    source = fileobj.read()
    if b".of(" not in source:
        return
    raised = [
        node.exc
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Raise)
        and isinstance(node.exc, ast.Call)
        and isinstance(node.exc.func, ast.Attribute)
        and node.exc.func.attr == "of"
        and node.exc.args
    ]
    for node in sorted(raised, key=lambda n: (n.lineno, n.col_offset)):
        if (wording := _written(node.args[0])) is not None:
            where = f"{getattr(fileobj, 'name', '?')}:{node.lineno}"
            yield _worded(where, node.lineno, _REFUSAL, wording)


def _worded(
    where: str, lineno: int, context: str, wording: str | tuple[str, str]
) -> tuple[int, str, tuple[str, ...], list[str]]:
    forms = (wording,) if isinstance(wording, str) else wording
    if any("%" in _FILLED.sub("", f) for f in forms):
        raise ValueError(f"{where}: {wording!r} has a % other than %(name)s or %%")
    return (
        lineno,
        "pgettext" if isinstance(wording, str) else "npgettext",
        (context, *forms),
        [],
    )


def _written(node: ast.expr) -> str | tuple[str, str] | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _written(node.left), _written(node.right)
        if isinstance(left, str) and isinstance(right, str):
            return left + right
    if isinstance(node, ast.Tuple) and len(node.elts) == 2:
        singular, plural = (_written(e) for e in node.elts)
        if isinstance(singular, str) and isinstance(plural, str):
            return singular, plural
    return None


_SOURCES = (
    ("src/chatddx/portal/**/*.py", "python", _KEYWORDS, None),
    # Policy: what a whoops tells the person is said in their locale wherever it is raised;
    # what it has them pass on to developers and ops isn't.
    ("src/chatddx/**/*.py", "python", {"Whoops": (1,)}, _WHOOPS),
    ("src/chatddx/**/*.py", _findings, _KEYWORDS, None),
    ("src/chatddx/**/*.py", _refusals, _KEYWORDS, None),
    (
        "src/chatddx/portal/templates/**/*.html",
        "jinja2.ext:babel_extract",
        _KEYWORDS,
        None,
    ),
    (f"{_ISLANDS}**/*.ts", _islands, _KEYWORDS, None),
    (f"{_ISLANDS}**/*.svelte", _islands, _KEYWORDS, None),
)


def _extracted(root: Path = settings.PROJECT_ROOT) -> Catalog:
    template = Catalog(fuzzy=False)
    for pattern, method, keywords, kind in _SOURCES:
        for path in sorted(root.glob(pattern)):
            where = path.relative_to(root).as_posix()
            if _LEFT_OUT.search(where):
                continue
            with path.open("rb") as held:
                # Accommodating for Babel, whose type for an extraction method's results
                # leaves out the name of the function called, which it reads.
                for lineno, message, _, context in extract(
                    cast(Any, method), held, keywords, options={"trimmed": "true"}
                ):
                    msgid = message if isinstance(message, str) else message[0]
                    found = template.get(msgid, kind or context)
                    if found and found.pluralizable != isinstance(message, tuple):
                        raise ValueError(
                            f"{where}:{lineno}: {msgid!r} is said both counted and not, "
                            + "which gettext holds as one message: give one a context"
                        )
                    _ = template.add(
                        message, "", [(where, lineno)], context=kind or context
                    )
    return template


@dataclass(frozen=True)
class Proof:
    path: Path
    current: str | None
    written: str
    untranslated: int

    @property
    def behind(self) -> bool:
        return self.current != self.written


def catalogs(where: Path = _CATALOGS) -> list[Path]:
    return sorted(where.glob("*.po"))


def proofs(
    tags: Iterable[str] = (),
    root: Path = settings.PROJECT_ROOT,
    catalogs: Path = _CATALOGS,
) -> list[Proof]:
    template = _extracted(root)
    paths = {p.stem: p for p in catalogs.glob("*.po")}
    paths |= {tag: catalogs / f"{tag}.po" for tag in tags}
    found: list[Proof] = []
    for tag, path in sorted(paths.items()):
        current = path.read_text() if path.exists() else None
        written, now = _restamped(tag, current, current, template)
        untranslated = sum(not _translated(m) for m in now if m.id)
        found.append(Proof(path, current, written, untranslated))
    return found


def restamped(
    tag: str, then: str | None, now: str, root: Path = settings.PROJECT_ROOT
) -> str:
    return _restamped(tag, then, now, _extracted(root))[0]


# Policy: a catalog is written in step with the code on both sides of its stamps, each
# matched to the code by its messages alone, never by a guess at a changed message's
# closest translation, which is left untranslated to be translated anew, and in the
# order of the messages, so that what is left to stamp is the translations alone.
def _restamped(
    tag: str, then: str | None, now: str | None, template: Catalog
) -> tuple[str, Catalog]:
    last = _updated(tag, None if then is None else signed(then), template)
    written = _updated(tag, None if now is None else applied(now), template)
    return markers.restamped(_po(last), _po(written)), written


def _updated(tag: str, lines: list[str] | None, template: Catalog) -> Catalog:
    if lines is None:
        catalog = _begun(tag)
    else:
        catalog = read_po(StringIO("\n".join(lines) + "\n"), tag)
    # Accommodating for Babel, which matches a new message to an untranslated plural one as
    # if it were translated: what holds no translation comes anew from the code.
    for m in [m for m in catalog if m.id and not _translated(m)]:
        catalog.delete(m.id, m.context)
    catalog.update(template, no_fuzzy_matching=True, update_creation_date=False)
    for m in catalog:
        m.flags.discard("fuzzy")
    return catalog


def _po(catalog: Catalog) -> str:
    written = BytesIO()
    write_po(
        written, catalog, include_lineno=False, ignore_obsolete=True, sort_output=True
    )
    return written.getvalue().decode()


def check() -> None:
    alike = said_alike(_extracted())
    if alike:
        print("\n".join(_alike(group) for group in alike), file=sys.stderr)
        raise SystemExit(
            "locale: messages said alike: one message for one scenario, raised with "
            + "upfirst where it starts a heading, a label or a sentence, or a context "
            + "for what tells them apart"
        )
    behind = [p for p in proofs() if p.behind]
    if behind:
        shown = ", ".join(_shown(p.path) for p in behind)
        raise SystemExit(f"locale: {shown} behind the code: run chatddx locale write")
    print("ok")


def said_alike(catalog: Catalog) -> list[list[Message]]:
    """The groups of a catalog's messages said alike: their words the same but for
    case and the punctuation that ends them, in the same context or in one that says
    only where the message comes from. What fills a message is named as it is said,
    as a translation inflects by it. Costs a pass over the catalog."""
    groups: dict[tuple[str, str | None], list[Message]] = {}
    for m in catalog:
        if not m.id:
            continue
        msgid = m.id if isinstance(m.id, str) else m.id[0]
        words = _ENDING.sub("", " ".join(msgid.casefold().split()))
        if not any(c.isalpha() for c in _FILLED.sub("", words)):
            continue
        context = None if m.context in (_REFUSAL, _WHOOPS) else m.context
        groups.setdefault((words, context), []).append(m)
    return [g for g in groups.values() if len(g) > 1]


def _alike(group: list[Message]) -> str:
    said = [
        f"  {m.context + ': ' if m.context else ''}{m.id!r}, in "
        + ", ".join(sorted({where for where, _ in m.locations}))
        for m in group
    ]
    return "\n".join(["said alike:", *said])


def pending() -> None:
    flags = [f"{_shown(p.path)}: {_left(p)}" for p in proofs() if p.untranslated]
    for flag in flags:
        print(f"flag: {flag}", file=sys.stderr)
    if flags:
        raise SystemExit(1)
    print("ok")


def write(tags: Iterable[str]) -> None:
    written: list[str] = []
    for p in proofs(tags):
        if not p.behind:
            continue
        p.path.parent.mkdir(parents=True, exist_ok=True)
        _ = p.path.write_text(p.written)
        written.append(
            f"{_shown(p.path)}: {'new, ' if p.current is None else ''}{_left(p)}"
        )
    print("\n".join(written) or "nothing to write")


# Policy: a catalog is said as last stamped, so that a translation pending is said as it
# was, or in English while it's new, till it is stamped.
def _locale(path: Path) -> Locale:
    try:
        reviewed = "\n".join(signed(path.read_text(encoding="utf-8"))) + "\n"
        catalog = read_po(StringIO(reviewed), path.stem, abort_invalid=True)
    except (PoFileError, ValueError) as e:
        raise ValueError(f"{path}: {e}") from None
    wrong = [f"{m.id!r}: {e}" for m, errors in catalog.check() for e in errors]
    if wrong:
        raise ValueError(f"{path}: {'; '.join(wrong)}")
    compiled = BytesIO()
    # Policy: what isn't reviewed is a stamp pending, so a fuzzy flag is said as any other.
    write_mo(compiled, catalog, use_fuzzy=True)
    _ = compiled.seek(0)
    islands = {
        _keyed(m): _forms(m) for m in catalog if m.id and _translated(m) and _shared(m)
    }
    return Locale(path.stem, GNUTranslations(compiled), islands)


# Policy: the catalog put in an island's page holds only what the islands say, and what the
# API may answer them with: the whoopses, and what is said below the portal.
def _shared(message: Message) -> bool:
    return message.context == _WHOOPS or any(
        not where.startswith(_PORTAL) for where, _ in message.locations
    )


def _forms(message: Message) -> str | list[str]:
    string = message.string
    return string if isinstance(string, str) else list(string or ())


def _keyed(message: Message) -> str:
    msgid = message.id if isinstance(message.id, str) else message.id[0]
    return msgid if message.context is None else f"{message.context}\x04{msgid}"


def _preferred(accept_language: str) -> list[str]:
    ranked: list[tuple[float, int, str]] = []
    for at, part in enumerate(accept_language.split(",")):
        tag, _, params = part.partition(";")
        tag = tag.strip()
        weight = 1.0
        for param in params.split(";"):
            key, _, value = param.strip().partition("=")
            if key == "q":
                try:
                    weight = float(value)
                except ValueError:
                    weight = 0.0
        if tag and tag != "*" and weight > 0:
            ranked.append((-weight, at, tag.lower()))
    return [tag for _, _, tag in sorted(ranked)]


def _begun(tag: str) -> Catalog:
    language = Language.parse(tag)
    return Catalog(
        locale=language,
        header_comment=f"# The portal's messages in {language.english_name}.",
        project="chatddx",
        version="portal",
        fuzzy=False,
    )


def _literal(source: str) -> str:
    value = ast.literal_eval(source)
    assert isinstance(value, str)
    return value


def _translated(message: Message) -> bool:
    string = message.string
    return all(string) if isinstance(string, (tuple, list)) else bool(string)


def _left(proof: Proof) -> str:
    return f"{proof.untranslated} untranslated"


def _shown(path: Path) -> str:
    try:
        return str(path.relative_to(settings.PROJECT_ROOT))
    except ValueError:
        return str(path)
