from pathlib import Path

import pytest

from chatddx.markers import restamped
from chatddx.test.helpers import committing_as_bob, git, needs_git
from chatddx_dev import project, refcheck, stamp

__all__ = ["committing_as_bob"]


def documented(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, files: dict[str, str]
) -> None:
    for name, text in {"docs/glossary.md": ":Term — one.\n", **files}.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        _ = (tmp_path / name).write_text(text)
    monkeypatch.setattr(project, "PROJECT_ROOT", tmp_path)
    for written in ("surfaces", "comments", "whoopses", "catalog"):
        monkeypatch.setattr(stamp, written.upper(), tmp_path / "docs" / written)


def test_what_a_doc_refers_to_is_checked_but_in_a_fence_or_as_last_signed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documented(
        monkeypatch,
        tmp_path,
        {
            "AGENTS.md": "See docs/gone.md, :Term and :Nothing.\n",
            "docs/a.md": '# A\n\nSee docs/b.md ("There") and docs/b.md ("Here").\n'
            + "`src/chatddx/x.py:f` and `src/chatddx/x.py:g`.\n"
            + "```\ndocs/fenced.md\n```\n"
            + restamped("docs/signed.md\n", "docs/written.md\n"),
            "docs/b.md": "# B\n\n## Here\n",
            "docs/surfaces/s.md": "docs/unread.md\n",
            "src/chatddx/x.py": "def f() -> None: ...\n",
        },
    )
    assert refcheck.check() == [
        "AGENTS.md:1: file: docs/gone.md",
        "AGENTS.md:1: term: :Nothing.",
        'docs/a.md:3: section: docs/b.md "There"',
        "docs/a.md:4: code: src/chatddx/x.py:g: no g",
        "docs/a.md:11: file: docs/written.md",
    ]


def test_a_link_to_a_heading_of_its_own_doc_is_checked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documented(
        monkeypatch,
        tmp_path,
        {
            "docs/a.md": "# A\n\n- [Ok](#splits-beyond-lines1)\n- [Gone](#gone)\n\n"
            + "## Splits beyond `lines@1`\n"
        },
    )
    assert refcheck.check() == ["docs/a.md:4: anchor: #gone"]


def test_a_conflict_in_a_doc_that_isn_t_a_stamp_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documented(monkeypatch, tmp_path, {"docs/a.md": "<<<<<<< HEAD\na\n=======\n"})
    with pytest.raises(ValueError, match="^docs/a.md: line 1: a conflict marker"):
        _ = refcheck.check()


@needs_git
@pytest.mark.usefixtures("as_bob")
def test_a_commit_a_doc_names_is_to_be_on_main(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    documented(monkeypatch, tmp_path, {})
    _ = git(tmp_path, "init", "-q")
    _ = git(tmp_path, "commit", "-q", "--allow-empty", "-m", "main")
    _ = git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    on_main = git(tmp_path, "rev-parse", "HEAD")
    _ = git(tmp_path, "commit", "-q", "--allow-empty", "-m", "branch")
    off_main = git(tmp_path, "rev-parse", "HEAD")
    _ = (tmp_path / "AGENTS.md").write_text(f"{on_main}\n{off_main}\nf00ba12\n")
    assert sorted(refcheck.check()) == [
        "AGENTS.md:2: commit: " + off_main + ": not on origin/main",
        "AGENTS.md:3: commit: f00ba12: no such commit",
    ]
