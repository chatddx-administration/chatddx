## Compose

Compose is where researchers write a configuration from its building blocks, its texts and settings, the evolution of
configurations (`docs/chatddx.md`, "Intended evolution of configurations").

Drafted: `/compose/{id}` (`src/chatddx/portal/compose.py`; `src/chatddx/portal/test/test_compose.py`) is where a
configuration is written and saved, and `/compose` leads to the first in the list. In its address is the variation's
query (`schemas.Varying`, its parts, `head`, `under`, `tag`).

- **Configurations**, always shown: the person's own of generation, by name, as Review runs a case under
  (`src/chatddx/portal/pages.py:configurations`), each fork under the one it was forked from where that is listed too,
  as Review's branches are (`src/chatddx/portal/compose.py:_forks`); no archive's.

- **The configuration**: its name, with **Show in the Library** across from it, as Review's case is; its versions by
  link, numbered by what they hold; **Update** it where it is behind what it was made from; and its island
  (`frontend/src/islands/compose.ts`), which writes its chunks in place rather than picking them:

  - **Its texts**: a tab in its own language with the chunks that hold text, an output's and a toolset's guidance among
    them, and a tab for each language it is translated into, one at a time, marked red while texts are left to translate
    there (`frontend/src/lib/compose/Texts.svelte`). As a text is typed, `POST /api/threads/{id}/drafts` says the texts
    the draft holds and carries each translation over to the text it changed into, in place and in order
    (`src/chatddx/factors/request.py:remapped`).
    - **Translating**: a language's tab pairs the prose, its instructions, few-shot messages, prompt and guidances, a
      row per text between its slots and inserts, the text on the left, editable, and its translation on the right, the
      text its placeholder (`frontend/src/lib/compose/Paired.svelte`). The slots and inserts are the text's, laid out on
      both sides and changed in its own tab. A translation carried over to a text that changed is marked to be looked
      over till it is typed in or said to read right, held by the page alone; one shared with another part says so
      (`frontend/src/lib/compose/Said.svelte`).
    - **Schemas and tools**, folded: the answer's schema and the tools as they are, beside a list of the texts they
      hold, to translate; neither is changed there. What else holds text, the appendices' layout, is listed below it.
    - Its settings are left out while translating.

  - **Its settings**: the chunks that hold no text, by what each decides rather than by its fields
    (`frontend/src/lib/compose/Settings.svelte`), with what the model's facts work out of them
    (`src/chatddx/portal/compose.py:_facts`):
    - **Model**, picked, saying whether its facts work out thinking levels and recommended sampling.
    - **The answer**, the output's contract: JSON, a tool call or text, a contract its facts refuse saying why, its
      default marked; the schema the first two need, and that text may have, to read JSON out of it.
    - **Thinking**, the reasoning: as the model does (none), by level, saying where the level lands, or by hand, with an
      effort and chat template arguments; a thinking token budget either way, unless its facts refuse one.
    - **Sampling**: recommended for the level thinking lands at, the values it recommends as placeholders, or the
      engine's; the values given in place of them, max output tokens and stop sequences.
    - **Tools**, by name and description, the person's own or the Archive's, offered only once there are any.
    - **Advanced**, folded: the passthrough, the key for max output tokens and the schema's inlined references.

  - **What it sends**: a column of its own (`frontend/src/lib/compose/Preview.svelte`), brought in by **What it sends**
    as Review's Measuring is, the configurations sliding out to the left and it in from the right, and after the rest
    below `xl`; `frontend/src/portal.css`'s `[data-slides]` moves both pages' columns. It is compiled as it is first
    shown, as it shows another language's tab than it was compiled in and as **Update** is pressed, which is enabled
    once what it would compile has changed. As read: the messages, each run of text that was put in from another part
    tinted and named on hover, a text not yet translated being the text as it was, marked so; a slot as its chip and the
    appendices as two placeholders laid out by the appendix layout; then the model, the rest of the body as it lands,
    the tools offered and how the answer is held. As sent: the body, without a seed or `return_token_ids`, its texts'
    line breaks breaking its lines. Both are marked against what the version drafted on sends in the same language, as
    saved, once anything differs from it: a message changed word by word in its runs, one added or taken out whole, and
    the body by line; saving makes the next to mark against (`frontend/src/lib/compose/diffing.ts`). What can't be
    compiled says why above the last that could, dimmed. `POST /api/threads/{id}/previews`
    (`src/chatddx/bench/composing.py:preview`) compiles the draft with `src/chatddx/factors/request.py:traced`, of which
    `compile_request` is the skeleton alone. While it is open, the texts and their translations sit side by side only
    where the column leaves room for it.

  - **Save**: `POST /api/threads/{id}/saves` (`src/chatddx/bench/composing.py:compose`) writes, in one transaction, each
    chunk that changed to the thread its own came from, a version where that is the person's and else a fork under its
    name, and then the configuration, as a version or a fork; a fork of the configuration forks the chunks it changes. A
    chunk held by no thread starts one named after the configuration and the part. Saved under a new name, it can be
    **independent of this one** instead: forked from nothing, each chunk it changes starting a thread named after it. An
    earlier version of the person's own, saved under its name, is brought back as the latest rather than forked, and is
    still that version unless changed (`frontend/src/lib/compose/logic.ts:whereSaveGoes`). Tags stay the Library's.

  - **Run**, beside Save, offered where the World names a baseline tag: saves what there is to save, as Save does, then
    `POST /compose/{id}/runs` (`src/chatddx/portal/compose.py:running_in_compose`) brings the configuration it saved
    into to a whole baseline, as Review's Run brings a case to a whole gathering. Its state is how the baseline stands,
    told in no words: enabled while something is behind that a run mends, marked to run again where the baseline is
    whole, and disabled while it is under way; a refusal, or its being out of date, is told among its findings. While it
    is under way, beneath it is how far it has come: the items ended over all its runs, and each run linking to its page
    with where it stands, queued, sending, scoring or ended, each read again while any is open
    (`frontend/src/lib/compose/following.svelte.ts`); once they all end, Run and the breakdown follow without a reload.

  - **Run it on cases**, below Save (`frontend/src/lib/compose/Cases.svelte`), as the Lab's run was: the cases the
    person sees, picked a group at a time by a button for all of them, each tag and each language, a group picked whole
    let go whole (`frontend/src/lib/compose/cases.ts`), or one at a time from a list found in by name, tag or language;
    how many replicates, and whether it is scored once finished. It saves what there is to save, as Run does, then
    `POST /api/runs` runs the configuration it saved into, the version open where there was nothing to save, on the
    cases picked, a run per language, and leads to the first. Held while what is changed can't be saved.

## The baseline

A configuration's baseline sets it on the World's baseline cases, so that what a variation of it changes has something
to be measured against: the bare case of each family tagged with the World's baseline tag
(`src/chatddx/api/standing.py:baseline_cases`). It is a gathering as Review's are, through the same pipeline
(docs/parts/review.md, "Gatherings"), in the baseline's shape, an original of one replicate and a repeat of its seed
(`BASELINE`), over the baseline cases rather than one. Each language the cases are sent in is a run of its own, and a
case that can't be sent, in a language the configuration has no translations into or one whose translation fails to
compile, keeps the whole baseline from running: Run is disabled, the language's tab is marked where it has one with
texts left to translate, the top of the configuration pane says which language to translate it into where it has none,
and why its translation fails otherwise (`src/chatddx/api/standing.py:standing`). A change to an expectation or a scorer
that a view reads puts it behind as not scored as things are now, which Run mends by scoring again alone
(`src/chatddx/portal/test/test_running.py`).

## How it fared

Drafted: below the page, read once scrolled near and again while its baseline is under way, how the configuration fared
on the baseline cases (`frontend/src/lib/compose/Breakdown.svelte`), from `GET /api/threads/{id}/breakdown`
(`src/chatddx/api/breakdown.py`; `src/chatddx/bench/breakdown.py:breakdown`), by field and view:

- **Its runs**, a column each in the order they ran, labelled by the version run, so that v1, v2, v3 and v1 again are
  four columns, the version open marked wherever it ran: each case a faint point, and the mean over the cases with its
  95% interval by Student's t over them (`src/chatddx/bench/breakdown.py:estimate`), linking to its page, ringed where
  it isn't scored as things are now and red where a baseline case as it is now went unanswered, left out, failed or not
  reached. Its difference from the run before, case by case on the cases both sent, is its Δ, on hover and among the
  numbers. A gathering's repeat adds no draw of its own, its seed being its replicate's.
- **Its peers**, beside it: the latest baseline of this configuration and of each of the person's others that shares the
  view.
- **The numbers**, folded: each view's estimate and Δ by run; and by run, how far its repeat's values were from its
  replicate's and how many answered alike to the letter (≡), the exception rather than the norm, its failed items,
  tokens and time, the languages its cases went in, and how many baseline cases it left unanswered.

It says what it can in numbers, symbols and words the portal already has, so that it adds little to translate.

Run saves what there is to save first, an earlier version brought back as the latest, and otherwise takes the version
open, its baseline being that of the latest start of what that version compiles to; on a baseline whole as things are
now it runs again, drawing seeds anew, another column.

What it reads of a run or a score that finished is held as rows (`src/chatddx/bench/observed.py:observed`): a run's
items as whether they failed, how long they took, the tokens they answered in and a digest of what they answered, and a
score's values, without a version; what a run isn't scored by as things are now, while the catalog stands and the run's
scores are the same.

A judge's configuration is written and saved there too.

## A baseline run

Drafted: `/gatherings/{started}` (`src/chatddx/portal/templates/gathering.html`), from `GET /api/gatherings/{started}`
(`src/chatddx/bench/breakdown.py:baseline`), is one baseline gathering of a configuration, the page a column leads to:

- **The run**: the baseline's tag and cases, the languages its cases went in, how many it left unanswered, whether it is
  scored as things are now, its runs, each the original or the repeat in its language, each leading to its page, and the
  run before it.
- **How it fared**: by view, its mean, 95% interval and cases, how far its repeats were from its replicates, and its Δ
  from the run before; a view picked shows below.
- **By case**, under the view picked: each case it sent or the baseline holds now, those first, the language it went in,
  its replicate's value and its repeat's, each leading to its score, where Review's replicates and repeats are read,
  whether the repeat answered alike to the letter, the run before's value and the Δ from it; a case unanswered is
  marked.
