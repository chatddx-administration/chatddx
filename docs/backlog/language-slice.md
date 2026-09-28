# A language slice

Not built. The research is Swedish, and what holds in English may not hold
in Swedish. So a run is to be in one language throughout: its case, the
instruction, the guidance and every other text a slice brings, and the
targets it is held to, all Swedish or all English, never mixed.

## Where it stands

- **A case names its language:** `language`, a detail, `en` or `sv`. EDN's
  twenty cases are Swedish, and the rest English, Dutch Fall's by
  translation.
- **Everything chatddx writes to an LLM is English,** so a Swedish case
  runs in a mixed language. Its targets' patterns name their words in both
  languages, to hold an answer in either.

## The design

It is the way translation files have long done it:

- **Language is a slice, realized by translation.** A text a slice brings
  (an instruction's templates, an output's guidance, a coercion's schema
  prompt and tool description, a toolset's guidance, a tool's description)
  is written once, in a source language. A variation of the language slice
  is a catalog of translations of those texts, as a gettext `.po` file is
  of a program's messages: each entry a source text and its translation.
  Resolution renders every text through the cell's catalog.
- **A text with no translation refuses the cell,** for want of a
  translation, as a reasoning intent with no fact does: nothing is guessed,
  and nothing mixes. A source text that changes finds no translation until
  one is written for it, as gettext finds no message for a changed `msgid`.
- **A catalog is content,** a trail like any variation, so a changed
  translation is a new version and a run names the catalog it read. `.po`
  files are how it would travel to translators and back.
- **A case is in the cell's language, or the cell refuses it.** A case
  translated from another is a case of its own, with targets of its own in
  its language, and names the case it translates (`translation_of`), so a
  study can pair them.
- **Languages are compared** by varying the language slice over cases
  paired by translation: each language's cells run on that language's
  cases, every other slice held.
- **An inspect log carries it:** the cell's language and the case's in each
  sample's metadata (`export.md`).

## Rejected

Parallel variations per language (`ddx-sv`, `free-text-sv`) would do
without a new slice, but nothing would hold them to one another or to
completeness, and comparing languages would mean varying several slices in
lockstep.
