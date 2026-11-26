import re
from pathlib import Path
from textwrap import dedent

import pytest
from babel.messages.catalog import Catalog

import chatddx.locale.locale as catalogs
from chatddx.factors import Finding
from chatddx.locale import (
    Locales,
    Proof,
    check,
    display_language,
    localized,
    localizing,
    pending,
    proofs,
    refusal,
    said_alike,
    tr,
    upfirst,
)
from chatddx.locale.test.helpers import catalog
from chatddx.markers import applied, restamped, stamps


def tree(root: Path, files: dict[str, str]) -> Path:
    for name, source in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(dedent(source))
    return root


def test_a_request_is_answered_in_the_language_it_prefers_of_those_there_are(
    tmp_path: Path,
) -> None:
    locales = Locales(catalog(tmp_path, ""))
    for preferred, tag in (
        ("sv-SE,sv;q=0.9,en;q=0.8", "sv"),
        ("en-GB,en;q=0.9,sv;q=0.8", "en"),
        ("de-DE,de;q=0.9", "en"),
        ("de;q=0.9, sv ;q=0.5", "sv"),
        ("sv;q=0, en", "en"),
        ("sv;q=high", "en"),
        ("SV", "sv"),
        ("*", "en"),
        ("", "en"),
        (None, "en"),
    ):
        assert locales.negotiate(preferred).tag == tag, preferred


def test_a_message_is_translated_and_filled_in_one_call(tmp_path: Path) -> None:
    sv = Locales(
        catalog(tmp_path, 'msgid "%(n)s of %(of)s"\nmsgstr "%(n)s av %(of)s"\n')
    ).negotiate("sv")
    with localizing(sv):
        assert tr("%(n)s of %(of)s", n=1, of=2) == "1 av 2"
    assert tr("%(n)s of %(of)s", n=1, of=2) == "1 of 2"
    assert tr("%(message)s: %(given)r", message="seed", given="x") == "seed: 'x'"


def test_boot_fails_on_a_catalog_whose_placeholders_are_not_its_message_s(
    tmp_path: Path,
) -> None:
    drafted = restamped(
        'msgid "%(n)s yours"\nmsgstr ""\n',
        'msgid "%(n)s yours"\nmsgstr "%(antal)s dina"\n',
    )
    assert Locales(catalog(tmp_path, drafted)).negotiate("sv").tag == "sv"
    with pytest.raises(ValueError, match="unknown named placeholder 'antal'"):
        _ = Locales(catalog(tmp_path, 'msgid "%(n)s yours"\nmsgstr "%(antal)s dina"\n'))
    with pytest.raises(ValueError, match="sv.po"):
        _ = Locales(catalog(tmp_path, 'msgid "Library"\nmsgstr "Bibliotek"\nsaid\n'))


def test_a_catalog_is_said_as_last_stamped(tmp_path: Path) -> None:
    then = 'msgid "Library"\nmsgstr "Bibliotek"\n\nmsgid "Lab"\nmsgstr ""\n'
    now = 'msgid "Library"\nmsgstr "Biblioteket"\n\nmsgid "Lab"\nmsgstr "Labbet"\n'
    sv = Locales(catalog(tmp_path, restamped(then, now))).negotiate("sv")
    with localizing(sv):
        assert tr("Library") == "Bibliotek"
        assert tr("Lab") == "Lab"
    unclosed = '<<<<<<< signed\nmsgid "Lab"\nmsgstr "Labbet"\n'
    with pytest.raises(ValueError, match="sv.po: line 1: a stamp isn't closed"):
        _ = Locales(catalog(tmp_path, unclosed))


def test_an_island_s_messages_are_found_in_its_calls_of_t_tn_tp_tnp_and_th(
    tmp_path: Path,
) -> None:
    root = tree(
        tmp_path,
        {
            "frontend/src/lib/Greeting.svelte": """
            <p>{t("Hello")}</p>
            <p>{t('it\\'s %(name)s', { name })}</p>
            <p>{tn("%(n)s run", "%(n)s runs", n, { n })}</p>
            <p>{tp("outcome", "valid")} {tnp("outcome", "%(num)s valid", "%(num)s valid", n)}</p>
            <p>{@html th('<a href="/runs/%(run)s">its run</a>', { run })}</p>
            <p>{t(text)} {shift("No")} {words.t("No")} {tn("No plural", n)} {tp("No", text)}</p>
            """,
        },
    )
    [begun] = proofs(["sv"], root, root / "catalogs")
    found = re.findall(
        r"^(?:msgctxt|msgid|msgid_plural) (.*)$", begun.written, re.MULTILINE
    )
    assert sorted(found) == sorted(
        [
            '""',
            '"Hello"',
            '"it\'s %(name)s"',
            '"%(n)s run"',
            '"%(n)s runs"',
            '"outcome"',
            '"valid"',
            '"outcome"',
            '"%(num)s valid"',
            '"%(num)s valid"',
            '"<a href=\\"/runs/%(run)s\\">its run</a>"',
        ]
    )


def test_a_finding_s_message_is_found_where_it_is_made_its_code_its_context(
    tmp_path: Path,
) -> None:
    lint = "src/chatddx/factors/lint.py"
    root = tree(
        tmp_path,
        {
            lint: """
            def lint(n, error):
                yield Finding.of("case.drift", "the vignette " + "differs")
                yield Finding.of(
                    "run.incomplete",
                    ("%(num)s item missing", "%(num)s items missing"),
                    level="info",
                    num=n,
                )
                yield Finding(code="call.failed", message=error)
                yield Fingerprint.of("Not this")
            """,
            "src/chatddx/factors/test/test_lint.py": 'Finding.of("not.this", "Not this")\n',
        },
    )
    [begun] = proofs(["sv"], root, root / "catalogs")
    for entry in (
        f'#: {lint}\nmsgctxt "case.drift"\nmsgid "the vignette differs"',
        f'#: {lint}\n#, python-format\nmsgctxt "run.incomplete"\n'
        + 'msgid "%(num)s item missing"\nmsgid_plural "%(num)s items missing"',
    ):
        assert entry in begun.written, entry
    assert "Not this" not in begun.written and "call.failed" not in begun.written

    for made, refused in (
        ('Finding.of("case.drift", wording)', "aren't as written"),
        ('Finding.of(code, "the vignette differs")', "aren't as written"),
        ('Finding.of("run.progress", "%(done)d%% done", done=n)', "other than"),
    ):
        _ = (root / lint).write_text(made + "\n")
        with pytest.raises(ValueError, match=refused):
            _ = proofs([], root, root / "catalogs")


def test_a_finding_is_said_in_the_locale_where_its_message_is_translated(
    tmp_path: Path,
) -> None:
    sv = Locales(
        catalog(
            tmp_path,
            """
            msgctxt "case.drift"
            msgid "the vignette differs"
            msgstr "vinjetten skiljer sig"

            msgctxt "run.incomplete"
            msgid "%(num)s item missing"
            msgid_plural "%(num)s items missing"
            msgstr[0] "%(num)s post saknas"
            msgstr[1] "%(num)s poster saknas"
            """,
        )
    ).negotiate("sv")
    found = [
        Finding.of("case.drift", "the vignette differs"),
        Finding.of(
            "run.incomplete", ("%(num)s item missing", "%(num)s items missing"), num=2
        ),
        Finding.of("run.resumed", "resumed after %(done)s items", done=3),
        Finding(code="call.failed", message="the server didn't answer"),
    ]
    with localizing(sv):
        assert [localized(f) for f in found] == [
            "vinjetten skiljer sig",
            "2 poster saknas",
            "resumed after 3 items",
            "the server didn't answer",
        ]
    assert [localized(f) for f in found] == [f.message for f in found]
    assert found[1].message == "2 items missing"


def test_a_refusal_s_wording_is_found_where_it_is_raised_in_the_context_refusal(
    tmp_path: Path,
) -> None:
    runs = "src/chatddx/bench/runs.py"
    root = tree(
        tmp_path,
        {
            runs: """
            def start(n, named, e):
                if not n:
                    raise Invalid.of("a start runs " + "one trial or more")
                if n > 1:
                    raise OverQuota.of(
                        ("%(num)s run too many", "%(num)s runs too many"), num=n
                    )
                if named:
                    raise Invalid.of(NAMED[named])
                raise ValueError(f"no case {n}")
            """,
        },
    )
    [begun] = proofs(["sv"], root, root / "catalogs")
    for entry in (
        f'#: {runs}\nmsgctxt "refusal"\nmsgid "a start runs one trial or more"',
        f'#: {runs}\n#, python-format\nmsgctxt "refusal"\n'
        + 'msgid "%(num)s run too many"\nmsgid_plural "%(num)s runs too many"',
    ):
        assert entry in begun.written, entry
    assert "no case" not in begun.written

    _ = (root / runs).write_text('raise Invalid.of("%(given)r is no case", given=n)\n')
    with pytest.raises(ValueError, match="other than"):
        _ = proofs([], root, root / "catalogs")


def test_a_refusal_is_said_in_the_locale_where_its_wording_is_translated(
    tmp_path: Path,
) -> None:
    sv = Locales(
        catalog(
            tmp_path,
            """
            msgctxt "refusal"
            msgid "%(num)s run too many"
            msgid_plural "%(num)s runs too many"
            msgstr[0] "%(num)s körning för mycket"
            msgstr[1] "%(num)s körningar för mycket"
            """,
        )
    ).negotiate("sv")
    worded = ("%(num)s run too many", "%(num)s runs too many")
    with localizing(sv):
        assert refusal(worded, {"num": 2}) == "2 körningar för mycket"
        assert refusal("no case %(case)s", {"case": "a"}) == "no case a"
    assert refusal(worded, {"num": 1}) == "1 run too many"


def test_a_language_is_said_by_its_name_in_the_locale_and_in_what_names_it(
    tmp_path: Path,
) -> None:
    sv = Locales(
        catalog(
            tmp_path,
            """
            msgctxt "refusal"
            msgid "no translations into %(into)s, nor %(languages)s"
            msgstr "inga översättningar till %(into)s, eller %(languages)s"
            """,
        )
    ).negotiate("sv")
    worded = "no translations into %(into)s, nor %(languages)s"
    given = {"into": "sv", "languages": "en, pt-BR"}
    assert [display_language(tag) for tag in ("sv", "pt-BR", "xx")] == [
        "Swedish",
        "Portuguese (Brazil)",
        "xx",
    ]
    assert refusal(worded, given) == (
        "no translations into Swedish, nor English and Portuguese (Brazil)"
    )
    with localizing(sv):
        assert display_language("en") == "engelska"
        assert refusal(worded, given) == (
            "inga översättningar till svenska, eller engelska och portugisiska "
            + "(Brasilien)"
        )


def test_slots_and_inserts_are_said_as_lists_in_the_locale(tmp_path: Path) -> None:
    sv = Locales(
        catalog(
            tmp_path,
            """
            msgctxt "refusal"
            msgid "judge requests need slots %(slots)s"
            msgstr "bedömningar behöver luckorna %(slots)s"
            """,
        )
    ).negotiate("sv")
    worded = "judge requests need slots %(slots)s"
    given = {"slots": "completion, expectation"}
    assert refusal(worded, given) == (
        "judge requests need slots completion and expectation"
    )
    twice = "inserts used more than once: %(inserts)s"
    assert refusal(twice, {"inserts": "schema, tool_guidance"}) == (
        "inserts used more than once: schema and tool_guidance"
    )
    with localizing(sv):
        assert refusal(worded, given) == (
            "bedömningar behöver luckorna completion och expectation"
        )


def test_a_catalog_is_kept_in_step_with_what_the_code_says(tmp_path: Path) -> None:
    template = "src/chatddx/portal/templates/page.html"
    root = tree(
        tmp_path,
        {
            "src/chatddx/portal/shelves.py": 'SHELF = N_("Cases")\n',
            "src/chatddx/portal/test/test_shelves.py": '_("Not this")\n',
            template: "{{ _('Library') }}\n"
            + "{% trans n=n %}{{ n }} run{% pluralize %}{{ n }} runs{% endtrans %}\n",
            "frontend/src/lib/Greeting.svelte": "<p>{t('Hello')}</p>\n",
            "frontend/src/lib/greeting.test.ts": 't("Not this");\n',
        },
    )
    catalogs = root / "locales"
    [begun] = proofs(["sv"], root, catalogs)
    assert begun.current is None and begun.behind
    assert begun.untranslated == 4
    for entry in (
        '#: src/chatddx/portal/shelves.py\nmsgid "Cases"',
        f'#: {template}\nmsgid "Library"',
        f'#: {template}\n#, python-format\nmsgid "%(n)s run"\nmsgid_plural "%(n)s runs"',
        '#: frontend/src/lib/Greeting.svelte\nmsgid "Hello"',
    ):
        assert entry in begun.written, entry
    assert "Not this" not in begun.written
    said = [
        begun.written.index(f'msgid "{m}"') for m in ("%(n)s run", "Cases", "Hello")
    ]
    assert said == sorted(said)
    catalogs.mkdir()
    _ = begun.path.write_text(
        begun.written.replace(
            'msgid "Library"\nmsgstr ""', 'msgid "Library"\nmsgstr "Bibliotek"'
        )
    )
    [kept] = proofs([], root, catalogs)
    assert not kept.behind and kept.untranslated == 3

    _ = (root / "src/chatddx/portal/templates/other.html").write_text(
        "{{ ngettext('Library', 'Libraries', n) }}\n"
    )
    with pytest.raises(ValueError, match="'Library' is said both counted and not"):
        _ = proofs([], root, catalogs)
    (root / "src/chatddx/portal/templates/other.html").unlink()

    _ = (root / template).write_text("{{ _('The Library') }}\n")
    _ = (root / "src/chatddx/portal/shelves.py").write_text(
        'SHELF = N_("%(n)s runs in all")\n'
    )
    [moved] = proofs([], root, catalogs)
    assert moved.behind and moved.untranslated == 3
    assert "fuzzy" not in moved.written and '"%(n)s run"' not in moved.written
    assert not stamps(moved.written)
    assert f'#: {template}\nmsgid "The Library"\nmsgstr ""' in moved.written

    _ = moved.path.write_text(moved.written)
    [held] = proofs([], root, catalogs)
    assert not held.behind

    _ = moved.path.write_text("\n".join(applied(moved.written)) + "\n")
    [reviewed] = proofs([], root, catalogs)
    assert not reviewed.behind and not stamps(reviewed.written)


def test_an_island_s_page_holds_what_the_islands_say_and_what_is_said_below_the_portal(
    tmp_path: Path,
) -> None:
    sv = Locales(
        catalog(
            tmp_path,
            """
            #: frontend/src/lib/Greeting.svelte
            msgid "Hello"
            msgstr "Hej"

            #: frontend/src/lib/runs/progress.ts src/chatddx/portal/templates/run.html
            msgid "%(n)s run"
            msgid_plural "%(n)s runs"
            msgstr[0] "%(n)s körning"
            msgstr[1] "%(n)s körningar"

            #: src/chatddx/bench/seen.py
            msgctxt "whoops"
            msgid "It broke."
            msgstr "Det gick sönder."

            #: src/chatddx/ledger/run.py
            msgctxt "case.drift"
            msgid "the vignette differs"
            msgstr "vinjetten skiljer sig"

            #: src/chatddx/bench/runs.py
            msgctxt "refusal"
            msgid "no endpoint serves it"
            msgstr "ingen ändpunkt serverar den"

            #: src/chatddx/portal/threads.py
            msgctxt "refusal"
            msgid "a fork is named"
            msgstr "en förgrening har ett namn"

            #: src/chatddx/portal/templates/base.html
            msgid "Library"
            msgstr "Bibliotek"

            #: frontend/src/lib/Greeting.svelte
            msgid "Goodbye"
            msgstr ""
            """,
        )
    ).negotiate("sv")
    assert sv.islands == {
        "Hello": "Hej",
        "%(n)s run": ["%(n)s körning", "%(n)s körningar"],
        "whoops\x04It broke.": "Det gick sönder.",
        "case.drift\x04the vignette differs": "vinjetten skiljer sig",
        "refusal\x04no endpoint serves it": "ingen ändpunkt serverar den",
    }


def test_check_fails_on_a_catalog_behind_the_code_and_pending_on_one_left_to_translate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sv = tmp_path / "sv.po"
    held = [Proof(sv, "a", "a", 0)]
    said = Catalog()

    def found() -> list[Proof]:
        return held

    def extracted() -> Catalog:
        return said

    monkeypatch.setattr(catalogs, "proofs", found)
    monkeypatch.setattr(catalogs, "_extracted", extracted)
    check()
    pending()
    assert capsys.readouterr() == ("ok\nok\n", "")

    held[:] = [Proof(sv, "a", "a", 2)]
    check()
    with pytest.raises(SystemExit) as e:
        pending()
    assert e.value.code == 1
    assert capsys.readouterr() == ("ok\n", f"flag: {sv}: 2 untranslated\n")

    held[:] = [Proof(sv, "a", "b", 0)]
    with pytest.raises(SystemExit, match=f"^locale: {sv} behind the code: run chatddx"):
        check()


def test_messages_said_alike_are_one_scenario_said_twice() -> None:
    held = Catalog()
    for message, context in (
        ("cases", None),
        ("Cases", None),
        ("%(trial)s is out of date", None),
        ("%(trial)s is out of date.", "refusal"),
        ("%(judge)s is out of date", "refusal"),
        ("none", "no language"),
        ("None.", None),
        ("%(a)s: %(b)s", None),
        ("%(c)s: %(d)s", None),
    ):
        _ = held.add(message, context=context)
    alike = [sorted((m.context or "", m.id) for m in g) for g in said_alike(held)]
    assert sorted(alike) == [
        [("", "%(trial)s is out of date"), ("refusal", "%(trial)s is out of date.")],
        [("", "Cases"), ("", "cases")],
    ]
    assert upfirst("cases") == "Cases" and upfirst("") == ""
