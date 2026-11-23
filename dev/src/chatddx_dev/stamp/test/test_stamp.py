from pathlib import Path
from textwrap import dedent

import pytest

from chatddx import locale, markers
from chatddx.markers import restamped, signed, stamped, stamps
from chatddx.test.helpers import committing_as_bob, git, needs_git
from chatddx_dev import project, stamp
from chatddx_dev.index import Proof

CLOSING = stamped("## e\n", "## e\na\n").splitlines()[-1]
PENDING = stamped("## e\na\n", "## e\nb\n")

__all__ = ["committing_as_bob"]


needs_prettier = pytest.mark.skipif(
    not (
        project.PROJECT_ROOT / "frontend" / "node_modules" / ".bin" / "prettier"
    ).exists(),
    reason="no prettier",
)


def applied(text: str) -> str:
    kept: list[str] = []
    dropping = False
    for line in text.splitlines():
        if line in ("<<<<<<< signed", "======="):
            dropping = line == "<<<<<<< signed"
        elif line != CLOSING and not dropping:
            kept.append(line)
    return "\n".join(kept) + "\n"


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
    monkeypatch.setattr(stamp, "SURFACES", docs)
    monkeypatch.setattr(stamp, "COMMENTS", tmp_path / "docs" / "comments")
    monkeypatch.setattr(stamp, "WHOOPSES", tmp_path / "docs" / "whoopses")
    catalogs = tmp_path / "src" / "chatddx" / "locale" / "catalogs"
    monkeypatch.setattr(locale, "catalogs", lambda: locale.locale.catalogs(catalogs))


def test_stamping_again_gives_the_same_stamps_and_applying_them_none() -> None:
    old, new = "## e\na\nb\nc\nd\ne\n", "## e\na\nx\ny\nc\ne\nf\n"
    once = stamped(old, new)
    assert stamped(once, new) == once
    assert signed(once) == old.splitlines()
    assert applied(once) == new
    assert stamped(applied(once), new) == new


def test_a_line_that_is_a_divider_outside_a_stamp_is_text() -> None:
    assert signed("## e\n=======\n") == ["## e", "======="]


def test_a_conflict_that_isn_t_a_stamp_is_refused() -> None:
    with pytest.raises(ValueError, match="line 2: a conflict marker that isn't"):
        _ = signed("## e\n<<<<<<< HEAD\na\n=======\nb\n>>>>>>> main\n")


def test_an_unclosed_stamp_is_refused() -> None:
    with pytest.raises(ValueError, match="line 1: a stamp isn't closed"):
        _ = signed("<<<<<<< signed\na\n=======\nb\n")


def test_a_doc_is_stamped_whole_from_its_text_at_the_base_to_what_it_says_now() -> None:
    once = restamped("# a\nb\nc\n", "# A\nb\nc\nd\n")
    assert once == dedent(
        f"""\
        <<<<<<< signed
        # a
        =======
        # A
        {CLOSING}
        b
        c
        <<<<<<< signed
        =======
        d
        {CLOSING}
        """
    )
    assert markers.applied(once) == ["# A", "b", "c", "d"]
    assert restamped("# a\nb\nc\n", once) == once
    assert restamped("# a\nb\nc\n", applied(once)) == once
    assert restamped("# a\nb\nc\n", "# a\nb\nc\n") == "# a\nb\nc\n"


def test_a_new_doc_is_one_stamp_and_a_base_s_own_stamps_are_read_as_signed() -> None:
    assert restamped(None, "a\nb\n") == f"<<<<<<< signed\n=======\na\nb\n{CLOSING}\n"
    pending = restamped("a\nb\n", "a\nB\n")
    assert restamped(pending, "a\nb\nc\n") == restamped("a\nb\n", "a\nb\nc\n")


def test_pending_flags_each_doc_s_stamps_pending_and_fails_while_one_is(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    faked(monkeypatch, tmp_path, ("a", PENDING, PENDING), ("b", "## e\n", "## e\n"))
    (tmp_path / "docs" / "parts").mkdir(parents=True, exist_ok=True)
    _ = (tmp_path / "docs" / "parts" / "x.md").write_text(restamped("a\n", "b\n"))
    with pytest.raises(SystemExit) as e:
        stamp.pending()
    assert e.value.code == 1
    assert capsys.readouterr().err.splitlines() == [
        "flag: docs/parts/x.md: 1 stamp pending",
        "flag: docs/surfaces/a.md: 1 stamp pending",
    ]

    _ = (tmp_path / "docs" / "parts" / "x.md").write_text("b\n")
    _ = (tmp_path / "docs" / "surfaces" / "a.md").write_text("## e\nb\n")
    stamp.pending()
    assert capsys.readouterr() == ("ok\n", "")

    _ = (tmp_path / "AGENTS.md").write_text(
        "<<<<<<< HEAD\na\n=======\nb\n>>>>>>> main\n"
    )
    with pytest.raises(
        SystemExit, match="^stamp pending: AGENTS.md: line 1: a conflict marker that "
    ):
        stamp.pending()


def test_check_refuses_a_conflict_in_a_doc_that_isn_t_a_stamp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    faked(monkeypatch, tmp_path, ("a", "## e\n", "## e\n"))
    _ = (tmp_path / "docs" / "x.md").write_text(restamped("a\n", "b\n"))
    stamp.check()
    assert capsys.readouterr() == ("ok\n", "")

    _ = (tmp_path / "AGENTS.md").write_text(
        "<<<<<<< HEAD\na\n=======\nb\n>>>>>>> main\n"
    )
    with pytest.raises(
        SystemExit, match="^stamp: AGENTS.md: line 1: a conflict marker that isn't "
    ):
        stamp.check()


@pytest.mark.slow
@needs_git
@pytest.mark.usefixtures("as_bob")
def test_docs_stamps_each_change_to_a_doc_since_the_commit_it_is_given_or_checks_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def wrote(files: dict[str, str]) -> None:
        for name, text in files.items():
            (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
            _ = (tmp_path / name).write_text(text)

    moved = "".join(f"line {n}\n" for n in range(8))
    wrote(
        {
            "AGENTS.md": "a\nb\n",
            "docs/kept.md": "k\n",
            "docs/moved.md": moved,
            "docs/surfaces/s.md": "## s\n",
            "src/x.md": "x\n",
        }
    )
    _ = git(tmp_path, "init", "-q")
    _ = git(tmp_path, "add", "-A")
    _ = git(tmp_path, "commit", "-qm", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    shown = git(tmp_path, "log", "-1", "--format=%h %s")
    monkeypatch.setattr(project, "PROJECT_ROOT", tmp_path)
    for docs in ("surfaces", "comments", "whoopses"):
        monkeypatch.setattr(stamp, docs.upper(), tmp_path / "docs" / docs)

    (tmp_path / "docs" / "parts").mkdir(parents=True, exist_ok=True)
    _ = git(tmp_path, "mv", "docs/moved.md", "docs/parts/moved.md")
    wrote({"AGENTS.md": "a\nB\n", "docs/parts/moved.md": moved + "more\n"})
    _ = git(tmp_path, "commit", "-qam", "session")
    wrote({"docs/new.md": "n\n", "docs/surfaces/s.md": "## t\n", "src/x.md": "y\n"})
    with pytest.raises(SystemExit, match=r" behind: run \./dev/write\.sh stamps$"):
        stamp.docs(base, check=True)
    assert (tmp_path / "AGENTS.md").read_text() == "a\nB\n"
    _ = capsys.readouterr()
    stamp.docs(base)
    said = capsys.readouterr().out.splitlines()
    assert said[0] == f"against {shown}"
    assert sorted(said[1:]) == [
        "AGENTS.md: 1 stamp",
        "docs/new.md: 1 stamp",
        "docs/parts/moved.md: 1 stamp",
    ]
    assert (tmp_path / "AGENTS.md").read_text() == restamped("a\nb\n", "a\nB\n")
    assert (tmp_path / "docs" / "parts" / "moved.md").read_text() == (
        restamped(moved, moved + "more\n")
    )
    assert (tmp_path / "docs" / "new.md").read_text() == restamped(None, "n\n")
    assert (tmp_path / "docs" / "kept.md").read_text() == "k\n"
    assert (tmp_path / "docs" / "surfaces" / "s.md").read_text() == "## t\n"
    assert (tmp_path / "src" / "x.md").read_text() == "y\n"
    stamp.docs(base)
    assert capsys.readouterr().out == f"against {shown}\nnothing to write\n"
    stamp.docs(base, check=True)
    assert capsys.readouterr().out == f"against {shown}\nok\n"
    _ = git(tmp_path, "add", "-A")
    _ = git(tmp_path, "commit", "-qm", "turn-end")
    wrote({"AGENTS.md": restamped("a\nb\n", "a\nB\n") + "d\n"})
    with pytest.raises(SystemExit, match="^stamp docs: AGENTS.md behind: "):
        stamp.docs(base, check=True)
    _ = capsys.readouterr()
    stamp.docs(base)
    assert (tmp_path / "AGENTS.md").read_text() == restamped("a\nb\n", "a\nB\nd\n")
    _ = capsys.readouterr()
    wrote({"AGENTS.md": restamped("a\nb\n", "a\nB\n")})

    stamped_docs = ("AGENTS.md", "docs/parts/moved.md", "docs/new.md")
    wrote({name: applied((tmp_path / name).read_text()) for name in stamped_docs})
    _ = git(tmp_path, "add", "-A")
    _ = git(tmp_path, "commit", "-qm", "stamp")
    signed_at = git(tmp_path, "log", "-1", "--format=%h %s")
    wrote({"AGENTS.md": "a\nB\nc\n"})
    _ = git(tmp_path, "commit", "-qam", "more")
    stamp.docs("HEAD~1")
    assert capsys.readouterr().out.splitlines() == [
        f"against {signed_at}",
        "AGENTS.md: 1 stamp",
    ]
    assert (tmp_path / "AGENTS.md").read_text() == restamped("a\nB\n", "a\nB\nc\n")


@pytest.mark.slow
@needs_git
@pytest.mark.usefixtures("as_bob")
def test_docs_stamps_a_catalog_s_translations_since_the_commit_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = tmp_path / "src/chatddx/portal/shelves.py"
    code.parent.mkdir(parents=True)
    _ = code.write_text('LIBRARY = N_("Library")\nCASES = N_("Cases")\n')
    catalogs = tmp_path / "catalogs"
    [begun] = locale.proofs(["sv"], tmp_path, catalogs)
    catalogs.mkdir()
    sv = begun.path
    _ = sv.write_text(
        begun.written.replace('"Library"\nmsgstr ""', '"Library"\nmsgstr "Bibliotek"')
    )
    _ = git(tmp_path, "init", "-q")
    _ = git(tmp_path, "add", "-A")
    _ = git(tmp_path, "commit", "-qm", "base")
    base = git(tmp_path, "rev-parse", "HEAD")
    monkeypatch.setattr(project, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(locale, "catalogs", lambda: [sv])
    for docs in ("surfaces", "comments", "whoopses"):
        monkeypatch.setattr(stamp, docs.upper(), tmp_path / "docs" / docs)

    _ = code.write_text(code.read_text() + 'LAB = N_("Lab")\n')
    [step] = locale.proofs([], tmp_path, catalogs)
    _ = sv.write_text(
        step.written.replace('"Cases"\nmsgstr ""', '"Cases"\nmsgstr "Fall"')
    )
    stamp.docs(base)
    assert capsys.readouterr().out.splitlines()[1:] == ["catalogs/sv.po: 1 stamp"]
    assert stamps(sv.read_text()) == [('msgstr ""', "=======", 'msgstr "Fall"')]
    assert not locale.proofs([], tmp_path, catalogs)[0].behind
    with pytest.raises(SystemExit):
        stamp.pending()
    assert "catalogs/sv.po: 1 stamp pending" in capsys.readouterr().err


@needs_git
@pytest.mark.usefixtures("as_bob")
@pytest.mark.slow
@needs_prettier
def test_reflow_formats_each_side_of_a_doc_s_stamps_as_a_doc_of_its_own(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(project, "PROJECT_ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    _ = (tmp_path / "docs" / "plain.md").write_text("*  a\n")
    held = tmp_path / "docs" / "held.md"
    _ = held.write_text(restamped("# t\n\n*  a\n", "# t\n\n*  b\n"))
    with pytest.raises(SystemExit, match="^stamp reflow: docs/held.md, docs/plain.md "):
        stamp.reflow(check=True)

    stamp.reflow(check=False)
    assert (tmp_path / "docs" / "plain.md").read_text() == "- a\n"
    assert held.read_text() == restamped("# t\n\n- a\n", "# t\n\n- b\n")
    stamp.reflow(check=True)


@needs_git
def test_docs_refuses_a_base_that_is_no_commit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = git(tmp_path, "init", "-q")
    _ = git(tmp_path, "commit", "-q", "--allow-empty", "-m", "session")
    monkeypatch.setattr(project, "PROJECT_ROOT", tmp_path)
    with pytest.raises(SystemExit, match="^stamp docs: git rev-parse: "):
        stamp.docs("nowhere")
