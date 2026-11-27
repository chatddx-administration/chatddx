from functools import partial
from pathlib import Path
from textwrap import dedent

import pytest
from babel.messages.catalog import Catalog

from chatddx import locale, markers
from chatddx.markers import stamped
from chatddx_dev import index as indexes, project
from chatddx_dev.index import Proof, anchored, bash, proofs, surfaces
from chatddx_dev.index.code import Code
from chatddx_dev.index.trace import Trace
from chatddx_dev.project import Class, Part, Stage

CLOSING = stamped("## e\n", "## e\na\n").splitlines()[-1]
PENDING = stamped("## e\na\n", "## e\nb\n")


def sourced(tmp_path: Path, files: dict[str, str]) -> Path:
    for name, source in files.items():
        path = tmp_path / "src" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(dedent(source))
    return tmp_path / "src"


def entries(proof: str) -> str:
    return proof.partition(f"{markers.PENDING}\n")[2]


def surface_in(code: Code, trace: Trace, package: str, repo: Path) -> str:
    shown = [e for _, e in surfaces.entries(code, trace, package, repo)]
    return surfaces.surfaced(
        package, f"`{package}`", [("Python", surfaces.LEGEND)], shown
    )


def written(tmp_path: Path, files: dict[str, str]) -> str:
    code = Code(sourced(tmp_path, files), "proj")
    trace = Trace(code, "proj.base.Finding", "proj.whoops.Whoops")
    return entries(surface_in(code, trace, "proj.alpha", tmp_path))


def comments_in(code: Code, package: str, repo: Path) -> str:
    where = code.src.joinpath(*package.split("."))
    files = sorted(where.rglob("*")) if where.is_dir() else [where.with_suffix(".py")]
    read = [
        anchored.read(code, p, repo)
        for p in files
        if p.suffix in (".py", *anchored.SCANNED, *bash.SUFFIXES)
    ]
    return anchored.commented(package, f"`{package}`", read)


def indexed(tmp_path: Path, files: dict[str, str]) -> str:
    code = Code(sourced(tmp_path, {"proj/__init__.py": "", **files}), "proj")
    return entries(comments_in(code, "proj.alpha", tmp_path))


def whoopses_in(code: Code, package: str, repo: Path) -> str:
    where = code.src.joinpath(*package.split("."))
    files = sorted(where.rglob("*")) if where.is_dir() else [where.with_suffix(".py")]
    read = [
        anchored.claimed(code, p, repo, "proj.whoops.Whoops")
        for p in files
        if p.suffix == ".py"
        and not anchored.tested(p, where if where.is_dir() else code.src)
    ]
    return anchored.whooped(package, f"`{package}`", read)


def whooped(tmp_path: Path, files: dict[str, str]) -> str:
    code = Code(sourced(tmp_path, files), "proj")
    return entries(whoopses_in(code, "proj.alpha", tmp_path))


def entry(page: str, heading: str) -> list[str]:
    lines = page.splitlines()
    start = lines.index(heading)
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return [line for line in lines[start + 1 : end] if line]


WHOOPS = {
    "proj/__init__.py": "",
    "proj/whoops.py": "class Whoops(Exception): ...\n",
}


def faked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *found: tuple[str, str | None, str]
) -> None:
    docs = tmp_path / "docs" / "surfaces"
    docs.mkdir(parents=True)
    held = [
        Proof(docs / f"{name}.md", current, written) for name, current, written in found
    ]
    for s in held:
        if s.current is not None:
            _ = s.path.write_text(s.current)
    monkeypatch.setattr(project, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(indexes, "SURFACES", docs)
    monkeypatch.setattr(indexes, "PARTS", tmp_path / "docs" / "parts")
    monkeypatch.setattr(project, "PARTS", {})
    monkeypatch.setattr(indexes, "COMMENTS", tmp_path / "docs" / "comments")
    monkeypatch.setattr(indexes, "WHOOPSES", tmp_path / "docs" / "whoopses")
    monkeypatch.setattr(indexes, "CATALOG", tmp_path / "docs" / "catalog")
    catalogs = tmp_path / "src" / "chatddx" / "locale" / "catalogs"
    monkeypatch.setattr(locale, "catalogs", lambda: locale.locale.catalogs(catalogs))

    def listed(*_: object) -> list[Proof]:
        return held

    monkeypatch.setattr(indexes, "proofs", listed)


def test_a_surface_lists_the_public_names_alphabetically_whatever_their_case(
    tmp_path: Path,
) -> None:
    found = written(
        tmp_path,
        {
            "proj/alpha/__init__.py": "",
            "proj/alpha/things.py": """
                from json import dumps

                GAMMA = 1


                def beta() -> None: ...


                def _hidden() -> None: ...


                class Alpha: ...
            """,
        },
    )
    headings = [line for line in found.splitlines() if line.startswith("## ")]
    assert headings == ["## `Alpha`", "## `beta`", "## `GAMMA`"]
    assert entry(found, "## `beta`") == [
        "`src/proj/alpha/things.py:beta`",
        "* ∟`None`",
    ]
    assert entry(found, "## `GAMMA`")[1:] == ["`GAMMA = 1`"]
    assert "dumps" not in found


def test_a_signature_is_a_list_of_its_parameters_as_the_code_writes_them(
    tmp_path: Path,
) -> None:
    found = written(
        tmp_path,
        {
            "proj/alpha/signed.py": """
                import functools


                @functools.cache
                def every[T](
                    a: int, /, b: str = "x", *more: int, c: bool = False, **rest: str
                ) -> list[T]: ...


                def keyed(a, *, b=1): ...
            """,
        },
    )
    assert entry(found, "## `every` `@functools.cache` `[T]`")[1:] == [
        "* `a: int`",
        "* `/`",
        '* `b: str = "x"`',
        "* `*more: int`",
        "* `c: bool = False`",
        "* `**rest: str`",
        "* ∟`list[T]`",
    ]
    assert entry(found, "## `keyed`")[1:] == ["* `a`", "* `*`", "* `b=1`"]


def test_a_class_lists_its_fields_and_each_method_is_an_entry_of_its_own(
    tmp_path: Path,
) -> None:
    found = written(
        tmp_path,
        {
            "proj/alpha/held.py": """
                from dataclasses import dataclass, field


                class Store:
                    def __init__(self, path: str) -> None:
                        self.path: str = path
                        self._open: bool = False

                    @property
                    def name(self) -> str:
                        return self.path

                    @staticmethod
                    def default() -> "Store":
                        return Store("store")


                @dataclass(frozen=True)
                class Kept(LookupError):
                    digest: str
                    kind: str = "case"
                    labels: dict[str, str] = field(
                        default_factory=dict
                    )


                KINDS: dict[str, str] = {
                    "case": "case",
                }
            """,
        },
    )
    headings = [line for line in found.splitlines() if line.startswith("## ")]
    assert headings == [
        "## `Kept` `@dataclass(frozen=True)` `(LookupError)`",
        "## `KINDS`",
        "## `Store`",
        "## `Store.__init__`",
        "## `Store.default` `@staticmethod`",
        "## `Store.name` `@property`",
    ]
    assert entry(found, "## `Store`")[1:] == ["* `path: str`"]
    assert entry(found, "## `Store.__init__`")[1:] == ["* `path: str`"]
    assert entry(found, "## `Store.name` `@property`")[1:] == ["* ∟`str`"]
    assert entry(found, "## `Kept` `@dataclass(frozen=True)` `(LookupError)`")[1:] == [
        "* `digest: str`",
        '* `kind: str = "case"`',
        "* `labels: dict[str, str] = field(…)`",
    ]
    assert entry(found, "## `KINDS`")[1:] == ["`KINDS: dict[str, str] = {…}`"]


def test_a_function_a_class_binds_is_written_once_as_the_class_s_method(
    tmp_path: Path,
) -> None:
    found = written(
        tmp_path,
        {
            "proj/alpha/acting.py": """
                from .seen import Seen


                def act(seen: Seen, times: int) -> int:
                    seen._counted(times)
                    return times
            """,
            "proj/alpha/seen.py": """
                class Seen:
                    def _counted(self, times: int) -> None:
                        if times < 0:
                            raise ValueError("a negative number of times")
            """,
            "proj/alpha/bench.py": """
                from .acting import act
                from .seen import Seen


                class Bench(Seen):
                    act = act
            """,
        },
    )
    assert "## `act`" not in found
    assert entry(found, "## `Bench.act`") == [
        "`src/proj/alpha/acting.py:act`",
        "* `times: int`",
        "* ∟`int`",
        "Raises:",
        '1. `ValueError`: `"a negative number of times"` (through `Seen._counted`)',
    ]


def test_a_raise_is_said_with_its_message_as_the_code_writes_it(
    tmp_path: Path,
) -> None:
    found = written(
        tmp_path,
        {
            "proj/alpha/finding.py": """
                NONE = "nothing to find"


                class Missing(LookupError):
                    @classmethod
                    def of(cls, wording: str, /, **params: str) -> "Missing":
                        return cls(wording % params)


                def find(name: str) -> None:
                    if not name:
                        raise ValueError(NONE)
                    if name == "all":
                        raise ValueError(name)
                    if name == "none":
                        raise Missing
                    if name == "some":
                        raise Missing.of("no %(name)s in the store", name=name)
                    raise Missing(f"no {name!r} in " + "the store")
            """,
        },
    )
    assert entry(found, "## `find`")[4:] == [
        '1. `ValueError`: `"nothing to find"`',
        "2. `ValueError`: `name`",
        "3. `Missing`",
        '4. `Missing`: `"no %(name)s in the store", name=name`',
        '5. `Missing`: `"no {name!r} in the store"`',
    ]


def test_an_argument_that_isn_t_text_is_said_as_written(tmp_path: Path) -> None:
    found = written(
        tmp_path,
        {
            "proj/alpha/problems.py": """
                class Problem(Exception):
                    def __init__(self, status: int, detail: str = "") -> None:
                        super().__init__(status, detail)


                def _refused(detail: str = "refused") -> Problem:
                    return Problem(403, detail)


                def checked(n: int) -> None:
                    if n < 0:
                        raise Problem(422, f"{n} is negative")
                    if n == 0:
                        raise Problem(status=404, detail="nothing")
                    raise _refused("too many")
            """,
        },
    )
    assert entry(found, "## `checked`")[4:] == [
        '1. `Problem`: `422, "{n} is negative"`',
        '2. `Problem`: `status=404, detail="nothing"`',
        '3. `Problem`: `"too many"` (through `_refused`)',
    ]


def test_code_holding_backticks_is_fenced_with_more_of_them(tmp_path: Path) -> None:
    found = written(
        tmp_path,
        {
            "proj/alpha/quoting.py": """
                def quoted() -> None:
                    raise ValueError("write ``x``, not `x`")
            """,
        },
    )
    assert entry(found, "## `quoted`")[2:] == [
        "Raises:",
        '1. `ValueError`: ``` "write ``x``, not `x`" ```',
    ]


def test_a_name_two_modules_define_is_headed_with_its_module(tmp_path: Path) -> None:
    found = written(
        tmp_path,
        {
            "proj/alpha/one.py": "log = 1\n",
            "proj/alpha/two.py": "log = 2\n",
        },
    )
    headings = [line for line in found.splitlines() if line.startswith("## ")]
    assert headings == ["## `one.log`", "## `two.log`"]


def test_raises_are_in_the_order_the_code_reaches_them_helpers_included(
    tmp_path: Path,
) -> None:
    found = written(
        tmp_path,
        {
            "proj/alpha/helped.py": """
                def _checked(times: int) -> None:
                    if times < 0:
                        raise ValueError("a negative number of times")


                def counted(times: int) -> None:
                    raise KeyError("uncounted")


                def done(times: int) -> None:
                    _checked(times)
                    if times > 9:
                        raise OverflowError("too many times")
                    counted(times)
                    _checked(times - 1)
            """,
        },
    )
    assert "\nRaises:\n1. `ValueError`" in found
    assert entry(found, "## `done`")[4:] == [
        '1. `ValueError`: `"a negative number of times"` (through `_checked`)',
        '2. `OverflowError`: `"too many times"`',
    ]


def test_what_a_function_catches_isn_t_said_to_be_raised_unless_raised_again(
    tmp_path: Path,
) -> None:
    found = written(
        tmp_path,
        {
            "proj/alpha/caught.py": """
                REFUSALS = (KeyError, LookupError)


                class Missing(LookupError): ...


                def _inner() -> None:
                    raise Missing("gone")


                def held() -> None:
                    try:
                        _inner()
                    except REFUSALS:
                        return None


                def passed() -> None:
                    try:
                        _inner()
                    except LookupError:
                        print("passing it on")
                        raise


                def translated() -> None:
                    try:
                        _inner()
                    except LookupError as e:
                        raise ValueError(str(e)) from None
            """,
        },
    )
    assert entry(found, "## `held`")[1:] == ["* ∟`None`"]
    assert entry(found, "## `passed`")[1:] == [
        "* ∟`None`",
        "Raises:",
        '1. `Missing`: `"gone"` (through `_inner`)',
    ]
    assert entry(found, "## `translated`")[1:] == [
        "* ∟`None`",
        "Raises:",
        "1. `ValueError`: `str(e)` (from `LookupError`)",
    ]


def test_a_validator_s_raise_is_said_of_its_class_in_a_validation_error(
    tmp_path: Path,
) -> None:
    found = written(
        tmp_path,
        {
            "proj/alpha/model.py": """
                from pydantic import BaseModel, field_validator


                class Person(BaseModel):
                    login: str

                    @field_validator("login")
                    @classmethod
                    def _login(cls, login: str) -> str:
                        if not login:
                            raise ValueError("a login can't be empty")
                        return login
            """,
        },
    )
    assert entry(found, "## `Person` `(BaseModel)`")[1:] == [
        "* `login: str`",
        "Raises:",
        '1. `ValueError`: `"a login can\'t be empty"` '
        + "(through `Person._login`, in a `ValidationError`)",
    ]


def test_a_finding_is_listed_where_the_code_makes_it(tmp_path: Path) -> None:
    found = written(
        tmp_path,
        {
            "proj/base.py": """
                from dataclasses import dataclass


                @dataclass(frozen=True)
                class Finding:
                    code: str
                    message: str
                    level: str = "warning"

                    @classmethod
                    def of(
                        cls, code: str, said: str | tuple[str, str], /, **params: int
                    ) -> "Finding":
                        return cls(code, said if isinstance(said, str) else said[1])
            """,
            "proj/alpha/linting.py": """
                from proj.base import Finding


                def _pair(n: int) -> list[Finding]:
                    if n % 2:
                        return [Finding(code="pair.odd", message=f"{n} is odd", level="info")]
                    return []


                def lint(n: int, code: str) -> list[Finding]:
                    found = [Finding(code="lint.started", message="linting")]
                    found += _pair(n)
                    try:
                        _ = int(code)
                    except ValueError as e:
                        found.append(Finding(code=code, message=str(e)))
                    found.append(
                        Finding.of(
                            "lint.counted", ("%(num)s digit", "%(num)s digits"), num=n
                        )
                    )
                    return found
            """,
        },
    )
    assert "\nFinds:\n1. `lint.started`" in found
    assert entry(found, "## `lint`")[4:] == [
        "Finds:",
        '1. `lint.started`: `"linting"`',
        '2. `pair.odd`: `"{n} is odd"` (`info`, through `_pair`)',
        "3. `{code}`: `str(e)` (from `ValueError`)",
        '4. `lint.counted`: `"%(num)s digit" / "%(num)s digits"`',
    ]


def test_a_comment_is_indexed_under_the_name_it_is_in_or_right_above(
    tmp_path: Path,
) -> None:
    found = indexed(
        tmp_path,
        {
            "proj/alpha/__init__.py": "# Scope: the package.\n",
            "proj/alpha/held.py": """
                import json  # the standard library's

                # Policy: one, ever.
                LIMIT = 1


                class Store:
                    # Policy: the store's own.
                    kind = "store"

                    @property
                    # Compromise: under the decorator.
                    def name(self) -> str:
                        # Policy: a name is its kind,
                        # and stays it.
                        return self.kind  # as it is

                    def opened(self) -> None:
                        def inner() -> None:
                            # Scope: within.
                            pass

                        # Scope: the method's.
                        inner()


                # Scope: a section.

                def after() -> None: ...
            """,
            "proj/alpha/test/test_held.py": """
                # Policy: a test's are indexed too.
                def test_held() -> None:
                    _ = "# not a comment"
            """,
        },
    )
    assert (
        found.splitlines()
        == dedent(
            """
        ## `src/proj/alpha/__init__.py`

        ```
        # Scope: the package.
        ```

        ## `src/proj/alpha/held.py`

        ```
        # the standard library's
        ```

        ```
        # Scope: a section.
        ```

        ## `src/proj/alpha/held.py:LIMIT`

        ```
        # Policy: one, ever.
        ```

        ## `src/proj/alpha/held.py:Store.kind`

        ```
        # Policy: the store's own.
        ```

        ## `src/proj/alpha/held.py:Store.name`

        ```
        # Compromise: under the decorator.
        ```

        ```
        # Policy: a name is its kind,
        # and stays it.
        ```

        ```
        # as it is
        ```

        ## `src/proj/alpha/held.py:Store.opened`

        ```
        # Scope: the method's.
        ```

        ## `src/proj/alpha/held.py:Store.opened.inner`

        ```
        # Scope: within.
        ```

        ## `src/proj/alpha/test/test_held.py:test_held`

        ```
        # Policy: a test's are indexed too.
        ```
        """
        ).splitlines()
    )


def test_sql_and_toml_comments_are_read_past_their_strings(tmp_path: Path) -> None:
    found = indexed(
        tmp_path,
        {
            "proj/alpha/setup.sql": """
                -- Policy: one row,
                -- ever.
                CREATE TABLE "a--b" (c text DEFAULT 'it''s -- text'); -- trailing
                /* Scope: a block
                   of two lines. */
            """,
            "proj/alpha/models.toml": """
                # Policy: shipped.
                a = "# text"  # trailing
                b = 'C#'
                c = \"\"\"
                # still text
                \"\"\"
            """,
            "proj/alpha/notes.txt": "# not read\n",
        },
    )
    assert entry(found, "## `src/proj/alpha/models.toml`") == [
        "```",
        "# Policy: shipped.",
        "```",
        "```",
        "# trailing",
        "```",
    ]
    assert entry(found, "## `src/proj/alpha/setup.sql`") == [
        "```",
        "-- Policy: one row,",
        "-- ever.",
        "```",
        "```",
        "-- trailing",
        "```",
        "```",
        "/* Scope: a block",
        "   of two lines. */",
        "```",
    ]
    assert "notes.txt" not in found


def test_a_comment_holding_backticks_is_fenced_with_more_of_them(
    tmp_path: Path,
) -> None:
    found = indexed(tmp_path, {"proj/alpha/held.py": "# a ``` fence\n"})
    assert entry(found, "## `src/proj/alpha/held.py`") == [
        "````",
        "# a ``` fence",
        "````",
    ]


def test_a_whoops_or_an_assert_is_indexed_under_the_name_it_is_in_as_written(
    tmp_path: Path,
) -> None:
    found = whooped(
        tmp_path,
        WHOOPS
        | {
            "proj/alpha/__init__.py": "assert __debug__\n",
            "proj/alpha/held.py": """
                from proj.whoops import Whoops as Oops


                class Store:
                    def opened(self, rows: list[int]) -> int:
                        def inner() -> None:
                            assert rows, "no rows"

                        if not rows:
                            raise ValueError("no rows")
                        if len(rows) > 9:
                            raise Oops(
                                f"{len(rows)} rows, though a store holds nine"
                            ) from None
                        inner()
                        return rows[0]
            """,
            "proj/alpha/sub/__init__.py": "",
            "proj/alpha/sub/deep.py": """
                from ...whoops import Whoops


                def deep() -> None:
                    raise Whoops
            """,
            "proj/alpha/conftest.py": "assert True\n",
            "proj/alpha/test_held.py": "assert True\n",
            "proj/alpha/test/helpers.py": "assert True\n",
        },
    )
    assert (
        found.splitlines()
        == dedent(
            """
        ## `src/proj/alpha/__init__.py`

        ```
        assert __debug__
        ```

        ## `src/proj/alpha/held.py:Store.opened`

        ```
        raise Oops(
            f"{len(rows)} rows, though a store holds nine"
        ) from None
        ```

        ## `src/proj/alpha/held.py:Store.opened.inner`

        ```
        assert rows, "no rows"
        ```

        ## `src/proj/alpha/sub/deep.py:deep`

        ```
        raise Whoops
        ```
        """
        ).splitlines()
    )


def test_a_whoops_isn_t_said_to_be_raised_on_a_surface(tmp_path: Path) -> None:
    found = written(
        tmp_path,
        WHOOPS
        | {
            "proj/alpha/__init__.py": "",
            "proj/alpha/held.py": """
                from proj.whoops import Whoops


                def _helper() -> None:
                    raise Whoops("deferred")


                def opened(rows: int) -> None:
                    if rows < 0:
                        raise ValueError("fewer than none")
                    if rows > 9:
                        raise Whoops("too many")
                    _helper()
            """,
        },
    )
    assert entry(found, "## `opened`")[3:] == [
        "Raises:",
        '1. `ValueError`: `"fewer than none"`',
    ]


def test_a_first_page_is_its_head_and_one_stamp_of_its_entries() -> None:
    first = stamped(None, "# a\n\n## b\nc\n")
    assert first == f"# a\n\n<<<<<<< signed\n=======\n## b\nc\n{CLOSING}\n"
    assert stamped(first, "# a\n\n## b\nc\n") == first


def test_what_changed_is_stamped_in_its_place_as_a_git_conflict() -> None:
    assert stamped("## e\na\nb\nc\n", "## e\nA\nb\nd\n") == dedent(
        f"""\
        ## e
        <<<<<<< signed
        a
        =======
        A
        {CLOSING}
        b
        <<<<<<< signed
        c
        =======
        d
        {CLOSING}
        """
    )
    assert stamped("## e\na\nb\n", "## e\nb\nc\n") == dedent(
        f"""\
        ## e
        <<<<<<< signed
        a
        =======
        {CLOSING}
        b
        <<<<<<< signed
        =======
        c
        {CLOSING}
        """
    )


def test_what_comes_before_the_first_entry_is_written_as_it_is_and_not_stamped() -> (
    None
):
    old = "# a\n\nread it so\n\n## e\nb\n"
    assert stamped(old, "# a\n\nread it otherwise\n\n## e\nb\n") == (
        "# a\n\nread it otherwise\n\n## e\nb\n"
    )


def test_a_heading_in_a_fence_is_still_before_the_first_entry() -> None:
    old = "# a\n\n````\n## `<x>`\n```\n## y\n```\n````\n\n## e\nb\n"
    new = old.replace("<x>", "<z>")
    assert stamped(old, new) == new


def test_each_kind_of_proof_says_how_to_read_it_before_its_first_entry(
    tmp_path: Path,
) -> None:
    files = {
        "proj/__init__.py": "",
        "proj/alpha.py": "# Policy: one.\ndef f() -> None:\n    assert True\n",
    }
    code = Code(sourced(tmp_path, files), "proj")
    trace = Trace(code, "proj.base.Finding", "proj.whoops.Whoops")
    for proof in (
        surface_in(code, trace, "proj.alpha", tmp_path),
        comments_in(code, "proj.alpha", tmp_path),
        whoopses_in(code, "proj.alpha", tmp_path),
        anchored.cataloged("alpha", "`alpha`", [], Catalog()),
    ):
        assert markers.PENDING in proof.splitlines()
        reread = proof.replace(markers.PENDING, "- read it otherwise")
        assert stamped(proof, reread) == reread


def test_a_proof_counts_the_stamps_it_holds_and_those_a_write_would_add() -> None:
    once = stamped("## e\na\nb\nc\n", "## e\nA\nb\nc\n")
    twice = stamped(once, "## e\nA\nb\nC\n")
    assert Proof(Path("s.md"), once, twice).pending == 1
    assert Proof(Path("s.md"), once, twice).new == 1
    assert Proof(Path("s.md"), twice, twice).new == 0
    assert Proof(Path("s.md"), None, "## e\na\n").new == 0


def test_a_module_s_stage_says_what_is_written_of_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = sourced(
        tmp_path,
        {
            "chatddx/__init__.py": "",
            "chatddx/alpha/__init__.py": "def f() -> None:\n    pass\n",
            "chatddx/beta.py": "# Policy: one.\ndef g() -> None:\n    assert True\n",
            "chatddx/gamma/__init__.py": "",
        },
    )
    stages = {
        "alpha": Stage.SOLIDIFIED,
        "beta": Stage.DRAFTED,
        "gamma": Stage.PLANNED,
        "delta": Stage.SOLIDIFIED,
    }
    monkeypatch.setattr(project, "PROJECT_ROOT", tmp_path)
    for docs in ("surfaces", "comments", "whoopses", "catalog"):
        monkeypatch.setattr(indexes, docs.upper(), tmp_path / docs)
    monkeypatch.setattr(
        project,
        "PARTS",
        {
            name: Part(stage, Class.MACHINERY, None, (f"src/chatddx/{name}",))
            for name, stage in stages.items()
        }
        | {
            "beta": Part(Stage.DRAFTED, Class.MACHINERY, None, ("src/chatddx/beta.py",))
        },
    )
    found = {str(s.path.relative_to(tmp_path)): s.written for s in proofs()}
    assert list(found) == [
        "surfaces/alpha.md",
        "comments/alpha.md",
        "whoopses/alpha.md",
        "comments/beta.md",
        "whoopses/beta.md",
    ]
    assert "## `src/chatddx/beta.py:g`" in found["comments/beta.md"]
    assert "comments in `[parts.beta]`'s code" in found["comments/beta.md"]
    assert "## `src/chatddx/beta.py:g`" in found["whoopses/beta.md"]
    assert "`src/chatddx/alpha/__init__.py:f`" in found["surfaces/alpha.md"]
    beta = Part(Stage.SOLIDIFIED, Class.MACHINERY, None, ("src/chatddx/beta.py",))
    monkeypatch.setattr(project, "PARTS", {**project.PARTS, "beta": beta})
    assert "`src/chatddx/beta.py:g`" in proofs(["beta"])[0].written


def test_check_fails_on_a_proof_behind_the_code_and_not_on_stamps_pending(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    faked(monkeypatch, tmp_path, ("a", "## e\n", "## e\n"))
    indexes.check()
    assert capsys.readouterr() == ("ok\n", "")

    faked(monkeypatch, tmp_path / "pending", ("a", PENDING, PENDING))
    indexes.check()
    assert capsys.readouterr() == ("ok\n", "")

    faked(
        monkeypatch,
        tmp_path / "behind",
        ("a", PENDING, "## e\nc\n"),
        ("b", None, "## e\n"),
    )
    with pytest.raises(
        SystemExit,
        match="^index: docs/surfaces/a.md, docs/surfaces/b.md behind the code: ",
    ):
        indexes.check()


def test_check_flags_what_parts_hold_amiss_a_proof_no_module_writes_and_a_broken_stamp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    faked(monkeypatch, tmp_path, ("a", "## e\n", "## e\n"))
    _ = (tmp_path / "docs" / "surfaces" / "gone.md").write_text("## e\n")
    (tmp_path / "docs" / "comments").mkdir()
    _ = (tmp_path / "docs" / "comments" / "gone.md").write_text("## e\n")
    (tmp_path / "docs" / "whoopses").mkdir()
    _ = (tmp_path / "docs" / "whoopses" / "gone.md").write_text("## e\n")
    (tmp_path / "docs" / "catalog").mkdir()
    _ = (tmp_path / "docs" / "catalog" / "gone.md").write_text("## e\n")
    _ = sourced(
        tmp_path,
        {
            "chatddx/loose.py": "",
            "chatddx/lost/__init__.py": "",
            "chatddx/split/__init__.py": "",
            "chatddx/split/page.py": "",
            "chatddx/torn/__init__.py": "",
            "chatddx/torn/page.py": "",
        },
    )
    (tmp_path / "docs" / "parts").mkdir()
    _ = (tmp_path / "docs" / "parts" / "astray.md").write_text("# Astray\n")
    lib = tmp_path / "frontend" / "src" / "lib"
    (lib / "x").mkdir(parents=True)
    _ = (lib / "x" / "y.ts").write_text("")
    _ = (lib / "stray.ts").write_text("")
    machinery = partial(Part, Stage.NAMED, Class.MACHINERY)
    monkeypatch.setattr(
        project,
        "PARTS",
        {
            "a": machinery(
                "docs/parts/gone.md",
                ("frontend/src/lib/x", "nix", "src/chatddx/split/__init__.py"),
            ),
            "b": machinery(
                None,
                (
                    "frontend/src/lib/x/y.ts",
                    "src/chatddx/split/page.py",
                    "src/chatddx/torn/page.py",
                ),
            ),
        },
    )
    with pytest.raises(SystemExit) as e:
        indexes.check()
    assert e.value.code == 1
    assert capsys.readouterr().err.splitlines() == [
        "flag: frontend/src/lib/stray.ts: no part's code in project.PARTS holds it",
        "flag: src/chatddx/loose.py: no part's code in project.PARTS holds it",
        "flag: src/chatddx/lost: no part's code in project.PARTS holds it",
        "flag: src/chatddx/torn: no part's code in project.PARTS holds it",
        "flag: nix: in a's code, but isn't there",
        "flag: frontend/src/lib/x: held by a and b",
        "flag: docs/parts/astray.md: no part in project.PARTS has it as its doc",
        "flag: docs/parts/gone.md: a's doc, but isn't there",
        "flag: docs/catalog/gone.md: no part writes it at its stage",
        "flag: docs/comments/gone.md: no part writes it at its stage",
        "flag: docs/surfaces/gone.md: no part writes it at its stage",
        "flag: docs/whoopses/gone.md: no part writes it at its stage",
    ]

    def broken(*_: object) -> list[Proof]:
        raise ValueError("docs/surfaces/a.md: line 2: a stamp isn't closed")

    monkeypatch.setattr(indexes, "proofs", broken)
    with pytest.raises(SystemExit):
        indexes.check(["a"])
    assert "flag: docs/surfaces/a.md: line 2: a stamp isn't closed" in (
        capsys.readouterr().err
    )


def test_write_says_how_many_stamps_it_wrote_to_each_proof(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    faked(
        monkeypatch,
        tmp_path,
        ("a", "## e\na\n", PENDING),
        ("b", None, "## e\n"),
        ("c", "# old\n\n## e\n", "# new\n\n## e\n"),
        ("d", "## e\n", "## e\n"),
    )
    indexes.write()
    assert capsys.readouterr().out.splitlines() == [
        "docs/surfaces/a.md: 1 stamp",
        "docs/surfaces/b.md: new",
        "docs/surfaces/c.md: 0 stamps",
    ]
    assert (tmp_path / "docs" / "surfaces" / "b.md").read_text() == "## e\n"

    faked(monkeypatch, tmp_path / "again", ("a", "## e\n", "## e\n"))
    indexes.write()
    assert capsys.readouterr().out == "nothing to write\n"


@pytest.mark.slow
def test_each_surface_is_as_chatddx_stamp_writes_it() -> None:
    for s in proofs():
        assert not s.behind, "chatddx-dev index"


def test_a_catalog_lists_the_messages_said_in_its_files_by_file_then_message() -> None:
    said = Catalog()
    _ = said.add("Saved", locations=[("a.html", 3), ("b.py", 1), ("elsewhere.py", 2)])
    _ = said.add("Name", locations=[("a.html", 1)], context="a field")
    _ = said.add(("%(num)s case", "%(num)s cases"), locations=[("a.html", 2)])
    _ = said.add("Unsaid", locations=[("elsewhere.py", 1)])
    found = entries(anchored.cataloged("alpha", "`alpha`", ["a.html", "b.py"], said))
    assert found.split("\n\n") == [
        "\n## `a.html`",
        "```\n%(num)s case\n```",
        "```\n%(num)s cases\n```",
        "`a field`",
        "```\nName\n```",
        "```\nSaved\n```",
        "## `b.py`",
        "```\nSaved\n```\n",
    ]


def test_a_part_has_a_catalog_from_its_stage_while_its_code_says_a_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = sourced(
        tmp_path,
        {
            "chatddx/__init__.py": "",
            "chatddx/portal/__init__.py": "",
            "chatddx/portal/pages.py": 'tr("Saved")\n',
            "chatddx/quiet.py": "",
        },
    )
    monkeypatch.setattr(project, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(indexes, "CATALOG", tmp_path / "catalog")
    portal = ("src/chatddx/portal/pages.py",)
    monkeypatch.setattr(
        project,
        "PARTS",
        {
            "pages": Part(Stage.DRAFTED, Class.MACHINERY, None, portal),
            "quiet": Part(
                Stage.DRAFTED, Class.MACHINERY, None, ("src/chatddx/quiet.py",)
            ),
        },
    )
    [found] = proofs(kinds=["catalog"])
    assert found.path == tmp_path / "catalog" / "pages.md"
    assert "## `src/chatddx/portal/pages.py`\n\n```\nSaved\n```\n" in found.written
    monkeypatch.setattr(
        project, "PARTS", {"pages": Part(Stage.PLANNED, Class.MACHINERY, None, portal)}
    )
    assert proofs(kinds=["catalog"]) == []
