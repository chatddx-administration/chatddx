from dataclasses import dataclass

from chatddx.bench import KINDS, WRITTEN, Bench
from chatddx.catalog import threads as catalog_threads
from chatddx.identity import sees
from chatddx.locale import N_, pgettext, pgettext_noop, tr, upfirst


@dataclass(frozen=True)
class Shelf:
    heading: str
    about: str | None
    kinds: dict[str, str]
    read_only: bool = False


SHELVES = (
    Shelf(
        N_("cases"),
        None,
        {
            "case": N_(
                "A vignette and the appendices sent with it, so that every model is "
                + "asked the same."
            ),
            "expectation": N_(
                "What a good answer to one case holds, so that answers to it can be "
                + "graded."
            ),
        },
    ),
    Shelf(
        N_("Configurations"),
        None,
        {
            "configuration": N_(
                "Everything sent with a case, put together from parts, so that one can "
                + "change while the rest hold still."
            ),
            "few_shot": N_(
                "Worked examples sent before the case, to show the model what is wanted."
            ),
            "instructions": N_(
                "The first message, telling the model its role and its task."
            ),
            "output": N_(
                "The shape an answer must take, so that it can be read and graded."
            ),
            "passthrough": N_(
                "For request options no other part covers, sent as written."
            ),
            "prompt": N_(
                "The last message, which puts the case to the model and asks for an "
                + "answer."
            ),
            "reasoning": N_(
                "How much the model thinks before it answers, which can change the "
                + "answer."
            ),
            "sampling": N_(
                "To steer how freely the model picks its words, and how long it may "
                + "answer."
            ),
            "toolset": N_(
                "The tools a configuration offers and how to use them, so that a model "
                + "can look things up."
            ),
            "translations": N_(
                "A configuration's texts in another language, so that a case is asked "
                + "in its own language."
            ),
        },
    ),
    Shelf(
        N_("Scoring"),
        None,
        {
            "judge": N_(
                "A model that grades what no pattern can, asked the same way each time."
            ),
            "scorer": N_(
                "Grades answers against expectations, so that configurations can be "
                + "compared by numbers."
            ),
        },
    ),
    Shelf(
        N_("Trials"),
        None,
        {
            "trial": N_(
                "A configuration with its cases and seeds fixed, so that its run can be "
                + "repeated."
            )
        },
    ),
    Shelf(
        N_("Operations"),
        N_(
            "Shipped with the data sets by developers and ops, so that everyone picks "
            + "from the same; read here, not written."
        ),
        {
            "canary_set": N_(
                "Fixed probes sent with a run, to catch an engine that changed between "
                + "runs."
            ),
            "expectation_schema": N_(
                "The form expectations are written in, so that a scorer knows where to "
                + "look."
            ),
            "tool": N_(
                "A function a model may call, such as a web search, to look up what it "
                + "doesn't know."
            ),
        },
        read_only=True,
    ),
)

# Dependency: the cards of src/chatddx/portal/templates/world.html, by the kinds they
# show.
IN_WORLD = {"model": "handle", "engine": "engine", "facts": "facts"}

# Policy: an appendix is written and shown in Review alone, in the case it goes with, so
# the Library shelves none and has no page of one; a case built of appendices is written
# there too, so the Library shelves cases locked.
IN_REVIEW = frozenset({"appendix"})
REVIEWED = frozenset({"case"})

# Accommodating for configurations, which a person writes as recipes, not as components.
AUTHORED = WRITTEN | {"skeleton"}

_SHELVED = sorted(w for s in SHELVES for w in s.kinds)
if sorted([*_SHELVED, *IN_WORLD, *IN_REVIEW]) != sorted([*KINDS, "case"]):
    raise RuntimeError(
        "the Library shelves once every kind the World and Review don't show: it "
        + f"shelves {', '.join(_SHELVED)}, the World shows {', '.join(IN_WORLD)}, "
        + f"Review {', '.join(IN_REVIEW)}, the kinds are "
        + f"{', '.join(sorted([*KINDS, 'case']))}"
    )
_READ = sorted(w for w in _SHELVED if w in KINDS and not set(KINDS[w]) & AUTHORED)
_OPERATED = sorted(w for s in SHELVES if s.read_only for w in s.kinds)
if _READ != _OPERATED:
    raise RuntimeError(
        "the read-only shelves hold the kinds nobody writes here: they hold "
        + f"{', '.join(_OPERATED)}, nobody writes {', '.join(_READ)}"
    )


_WORDS = {
    "appendix": pgettext_noop("kind", "appendix"),
    "canary_set": pgettext_noop("kind", "canary set"),
    "case": pgettext_noop("kind", "case"),
    "configuration": pgettext_noop("kind", "configuration"),
    "engine": pgettext_noop("kind", "engine"),
    "expectation": pgettext_noop("kind", "expectation"),
    "expectation_schema": pgettext_noop("kind", "expectation schema"),
    "facts": pgettext_noop("kind", "facts"),
    "few_shot": pgettext_noop("kind", "few shot"),
    "instructions": pgettext_noop("kind", "instructions"),
    "judge": pgettext_noop("kind", "judge"),
    "model": pgettext_noop("kind", "model"),
    "output": pgettext_noop("kind", "output"),
    "passthrough": pgettext_noop("kind", "passthrough"),
    "prompt": pgettext_noop("kind", "prompt"),
    "reasoning": pgettext_noop("kind", "reasoning"),
    "sampling": pgettext_noop("kind", "sampling"),
    "scorer": pgettext_noop("kind", "scorer"),
    "tool": pgettext_noop("kind", "tool"),
    "toolset": pgettext_noop("kind", "toolset"),
    "translations": pgettext_noop("kind", "translations"),
    "trial": pgettext_noop("kind", "trial"),
}
if sorted(_WORDS) != sorted([*_SHELVED, *IN_WORLD, *IN_REVIEW]):
    raise RuntimeError(
        "a word for each kind the Library shelves or the World or Review shows: "
        + f"{', '.join(sorted(_WORDS))} are worded, {', '.join(_SHELVED)} shelved and "
        + f"{', '.join([*IN_WORLD, *IN_REVIEW])} shown"
    )


def display_kind(word: str) -> str:
    return pgettext("kind", _WORDS.get(word, word.replace("_", " ")))


@dataclass(frozen=True)
class Shelved:
    word: str
    about: str
    mine: int
    seen: int
    reviewed: bool

    @property
    def display_kind(self) -> str:
        return display_kind(self.word)


def shelved(bench: Bench) -> list[tuple[Shelf, list[Shelved]]]:
    counted = _counted(bench)
    return [
        (
            shelf,
            [
                Shelved(w, shelf.kinds[w], *counted[w], w in REVIEWED)
                for w in shelf.kinds
            ],
        )
        for shelf in sorted(
            SHELVES, key=lambda s: (s.read_only, upfirst(tr(s.heading)))
        )
    ]


def _counted(bench: Bench) -> dict[str, tuple[int, int]]:
    person = bench.person.id
    counted: dict[str, tuple[int, int]] = {}
    for word in _SHELVED:
        if word == "case":
            continue
        seen = [
            a
            for k in KINDS[word]
            for _, a in catalog_threads.heads(bench.rows, k)
            if sees(person, a)
        ]
        counted[word] = (sum(a.owner == person for a in seen), len(seen))
    families = bench.families()
    counted["case"] = (sum(f.about.owner == person for f in families), len(families))
    return counted
