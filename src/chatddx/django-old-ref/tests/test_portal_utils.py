from chatddx.django.portal.utils import truncate_for_list_display


def test_truncate_for_list_display_returns_short_text_unchanged():
    assert truncate_for_list_display("short text") == "short text"


def test_truncate_for_list_display_handles_none():
    assert truncate_for_list_display(None) == ""


def test_truncate_for_list_display_breaks_on_a_word_boundary():
    text = "one two three four five six seven eight nine ten eleven twelve"
    result = truncate_for_list_display(text)

    assert result.endswith("…")
    assert not result[:-1].endswith(" ")
    # every whole word kept is one that actually appears at the start of
    # the original text -- nothing was cut off mid-word.
    assert text.startswith(result[:-1].rstrip())


def test_truncate_for_list_display_hard_caps_the_limit_at_50():
    text = "x" * 100
    result = truncate_for_list_display(text, limit=200)

    assert len(result) == 51  # 50 chars + the ellipsis marker
