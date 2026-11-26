# Locale: work in progress

The portal in more than one language: its pages, its islands and the words its own code says, in the language of the
person reading them. "Decided" means the user said so; "Take" is the agent's recommendation and still open.

The name is `locale`, as `:Translations` is the domain's already: a chunk that carries a recipe's texts into a case's
language, with its own Library tab and page (`src/chatddx/portal/translations.py`). A locale is the portal's language,
never what is sent to a model.

It is a package of its own, `chatddx.locale` (`src/chatddx/locale/`): the catalogs, what reads them at boot, the
callables that say a message in the request's locale, and what keeps the catalogs in step with the code. The portal is
the only package that says what it says through it, and it keeps only how it does: its templates' callables, the
middleware on its app and the messages of its own.

## Start with this

1. **Decided: gettext, with Babel**, one catalog for the server and the islands. English is the source: a message's
   English is its key, and a request no catalog fits is answered in English, as every page is now.
2. **Take: Swedish first**, beside English. Both have one plural form besides the singular, so nothing in the first step
   needs more than gettext's plurals.
3. **Take: the portal only.** The API, the repl, the CLI and the docs stay English.
4. **Take: the browser's language first**, `Accept-Language`, matched against the catalogs there are, unless the person
   chose one with the switch in the header (see "The server").
5. **Decided: what clinicians and researchers read is localized; what developers and ops read is raw.** A whoops says
   what is going on and what the person can do now, its `message`, which is translated where it is shown, and what they
   are to pass on to developers and ops, its `pass_on`, which isn't (`src/chatddx/whoops.py:Whoops`).
6. **Decided: numbers and dates are written one way, whatever the locale.** A number by a simple global default, a space
   between thousands and a decimal point (`1 000.34`); a date as ISO writes it (`2026-10-23 14:16`).

## What there is to translate

| Where                               | How much                        | Held as                                 |
| ----------------------------------- | ------------------------------- | --------------------------------------- |
| the templates                       | ~510 runs of text, ~2,600 words | text between tags, Jinja expressions    |
| the islands                         | ~150 runs of text, ~970 words   | Svelte markup, and messages built in TS |
| attributes of both                  | ~90                             | `placeholder`, `aria-label` and `title` |
| the portal's Python                 | ~95 strings, ~650 words         | `SHELVES` above all                     |
| what the portal shows from below it | open-ended                      | findings and API errors, by code        |
| what data sets hold                 | open-ended                      | schemas' names, titles and descriptions |

The templates are in `src/chatddx/portal/templates/` and the islands in `frontend/src/`; `SHELVES` is
`src/chatddx/portal/shelves.py:SHELVES`.

Some 600 to 800 messages, of which three habits of the templates make more work than their count:

- **Sentences put together from pieces**, such as `{{ k.mine }} yours · {{ k.seen - k.mine }} shared with you`, a
  fragment added under an `{% if %}`, and `"Pick none" if every else "Pick every one shown"`. A translator needs the
  whole sentence, to put its words in another order.
- **A kind's word dropped into a sentence**, as `word | replace("_", " ")` is in many places. Swedish inflects it
  (konfiguration, konfigurationen) and compounds it, so a word dropped in reads wrong more often than not.
- **English plurals by hand**, `"" if n == 1 else "s"`, in 13 places.

The rest holds already: dates are written `%Y-%m-%d %H:%M` (`src/chatddx/portal/pages.py:_display_time`), which Swedish
reads as it is, and `src/chatddx/portal/templates/base.html` has a `lang` to set.

## How it works

### The catalog

Built: one `.po` file a locale in `src/chatddx/locale/catalogs/`, `sv.po` begun empty, packaged with `chatddx.locale`
and read at boot (`src/chatddx/locale/locale.py:Locales`) with Babel's `read_po`, then turned into a gettext catalog in
memory: no compiled file in git or in the build. A catalog is read as last stamped (`src/chatddx/markers.py:signed`), so
that a translation pending is said as it was, and a message whose translation is missing in English.

Built: boot fails on a catalog that doesn't parse, or whose reviewed translations' `%(name)s` placeholders aren't their
messages', which Babel's catalog checks find. A translation pending is left out of that, as it isn't said; what is left
to translate is a flag, not a failure (see "Checks"). A message with no translation is written anew from the code each
time, so that Babel matches a changed message only to one translated.

### The scenario index

Decided: a catalog is the scenario index, a message to a scenario, so that every code path that says a scenario says it
by the one message and a translation is made once. A message is tested against it as it is written or changed: what
scenario its code says it in, and whether a message says that scenario already, in which case the code says that one, as
it is or reworded for each code path that says it.

- **Its case is the running text's**, raised to start a heading, a label or a sentence by the portal's `upfirst` filter
  and the islands' `upFirst()` (`src/chatddx/locale/locale.py:upfirst`), and its ending punctuation, or an ellipsis,
  where it is shown, so that `cases` is one message as a heading and in a list.
- **A context says what tells scenarios said alike apart** for a translator, never where a message comes from: two
  translations that differ, by gender, number or meaning, are two scenarios (`Unanswered` of cases, `unanswered` of a
  case). What fills a message is named as it is said, as a translation inflects by it: `%(trial)s` and
  `%(configuration)s` are told apart in Swedish.
- **Checked**, built: `chatddx locale check` fails on messages said alike, their words the same but for case and ending
  punctuation, in the same context or in one that says only where it comes from, `refusal` or `whoops`
  (`src/chatddx/locale/locale.py:said_alike`); what holds no words, `%(label)s: %(said)s`, is layout and left out.
- **Left as they are**: the kinds' words in their context `kind`, beside the same word said otherwise, till "Open" 1 is
  settled; and a finding's message in its code's context, its code the scenario.

### The server

- **The locale**, built: picked a request at a time, from `Accept-Language` against the catalogs there are, with Babel's
  `negotiate_locale` (`src/chatddx/locale/locale.py:Locales.negotiate`). `src/chatddx/portal/pages.py:page` sets it
  around the page's rendering (`src/chatddx/locale/locale.py:localizing`) and gives it as `locale`, whose `tag` is
  `base.html`'s `lang`.
- **The person's own language**, built: a switch in every page's header, the catalogs' languages each by its own name,
  posts the one picked to `/locale` (`src/chatddx/portal/pages.py:choosing_locale`), which keeps it a year in the cookie
  `src/chatddx/locale/locale.py:CHOSEN` and leads back to the page. A locale chosen wins over `Accept-Language`, for the
  pages and the API alike. Take: a cookie rather than the store, so that it holds before signing in, on the landing page
  and the sign-in page.
- **The templates**, built: Jinja's `i18n` extension, newstyle and trimmed, on `src/chatddx/portal/pages.py:templates`,
  with `_()`, `ngettext()`, `pgettext()`, `npgettext()` and `{% trans %}…{% pluralize %}`. The callables read the locale
  set around the rendering rather than the template's context, which a macro imported without context, as most are,
  doesn't see. Newstyle escapes what is put into a message and fails on a placeholder left out, so a message with a `%`
  of its own writes it `%%`, and `ngettext()`'s count is `%(num)s` unless it is given a name.
- **The portal's Python**, built, marks what it says with a no-op `N_()` where it is defined, as `SHELVES` is at import,
  and the template that shows it translates it with `_()`. What a function says in answer to a request is translated
  where it is said, from the request's locale, which `src/chatddx/locale/locale.py:Localizing`, a middleware on the
  portal's app, sets around each request; `page` still sets it around rendering, as a page answering an unexpected error
  is rendered outside the middleware. A message is written as a template's are, and besides:
  - translated and filled in one call, `tr("…%(name)s…", name=…)` (`src/chatddx/locale/locale.py:tr`), never an
    f-string, and `%(given)r` where the English quotes what was typed;
  - with the callables imported by name, never as `_`, which the code uses to discard a value, and so `tr` where a
    template says `_`;
  - a word drawn from a fixed set, such as a configuration's purpose or a part of a response, from a table of
    `pgettext_noop` marks, translated with `pgettext()` and the same context.
- **A kind's word**, built: drawn by one filter, `{{ word | kind }}`, translated with `pgettext("kind", …)` from
  `src/chatddx/portal/shelves.py:_WORDS`, which a no-op `pgettext_noop` marks and boot holds to the kinds shelved and
  shown in the World, so that whether Swedish translates it is decided in the catalog (see "Open"). A list of kinds is
  sorted by its words as said (`src/chatddx/portal/shelves.py:Shelved.display_kind`).
- **How a message is written**, as every page's are:
  - a sentence whole, its alternatives each a message (`_("None you see of these.") if … else _("None you see.")`);
  - a sentence with links or markup in it a `{% trans %}` block, the markup in its message;
  - what is set apart by `·` a message apiece, the separator left out;
  - anything counted with `ngettext()`, even where English says it the same either way (`%(num)s yours`), as Swedish
    doesn't;
  - a word that could be read more ways than one, or a note that follows a button, with `pgettext()` and a context
    naming what it is or follows (`"outcome"`, `"after the button Run the picked"`);
  - a sentence a kind's word agrees with, such as `A new configuration`, a message per kind, as `begun.html`'s titles
    are, since Swedish says `en ny` or `ett nytt` by the word;
  - two counts in one sentence each counted on its own, then put into a sentence of its own
    (`_("%(queued)s, %(under_way)s.", queued=ngettext(…), under_way=ngettext(…))`);
  - no variable of a template named `_`, which is the callable that translates.

  A message's translation is trusted markup, as newstyle marks it safe: an apostrophe in it is written as itself, not as
  `&#39;`, which tests reading a page's HTML meet.

### The islands

- **The catalog** an island needs, built, is put in its page, as its props are: `base.html`'s
  `<script type="application/json" id="locale">`, holding the locale's tag and the reviewed translation of each message
  said in `frontend/src/`, and of each whoops, which the API may answer an island with
  (`src/chatddx/locale/locale.py:Locale.islands`, made at boot); nothing on a page without an island.
- **`t()`**, built (`frontend/src/lib/locale.ts`), looks a message up and puts its `%(name)s` placeholders in, the same
  placeholders as the server's, so one check covers both; `tn()`, `tp()` and `tnp()` are gettext's `ngettext`,
  `pgettext` and `npgettext`; a plural picks its form with `Intl.PluralRules`, whose `one` and `other` are gettext's two
  forms for English and Swedish. A message given nothing for a placeholder throws, as the server's do.
- **How an island writes a message**, built, as a template does, and besides:
  - a sentence with markup in it is `{@html th(…)}`, a translation being trusted markup as the server's are, and what is
    put into it escaped, as a `{% trans %}` block's variables are;
  - what the server says too is said with the server's message, context and placeholders, so that it is translated once:
    an outcome's word (`frontend/src/lib/runs/outcomes.ts`), a kind's (`frontend/src/lib/kinds.ts`), `view %(n)s`,
    `%(sent)s in, %(got)s out`;
  - a list of words is put together by the page's locale (`display_list()`, the islands' `displayList()`,
    `Intl.ListFormat`);
  - a table of words defined at a module's top is translated there, as an island's script runs once the page that holds
    its catalog is parsed.
- **A whoops**, built, is `Whoops(message, pass_on)`: the API answers it with `detail`, its message, and `pass_on`, as
  it is; the error page says the one in the request's locale and the other after
  `Copy this and send it to drift@chatddx.com:`, and so does an island (`frontend/src/lib/api/client.ts:why`).
- **Dates and numbers** an island writes are written as the server writes them, whatever the locale (see "Start with
  this"): a date `%Y-%m-%d %H:%M`, and a number, as yet, without the space between thousands (see "Steps").

### Findings

- **A finding the portal may show**, built, is made with its message as written and its parameters,
  `Finding.of(code, "…%(name)s…", name=…)` (`src/chatddx/factors/base.py:Finding.of`), or a singular and a plural
  counted by `num`, as Swedish needs even where English says it the same either way. It fills its English, `message`, as
  before, and keeps its `wording`, the message as written, and `params` beside it, in the ledger as in the API; a
  record's canonical form leaves out what is default, so a record written before reads and seals as it was.
- **Take: its code is its context**: a message a code, as `vllm.temperature_clamped` names what it says to a translator
  as it does to the glossary. A code may say more than one message (`score.run_unfinished`), each its own.
- **Localized where it is shown**, built, by `src/chatddx/locale/locale.py:localized`, the portal's `localized` filter
  (`macros.html`'s `findings`) and the islands' `localized()` (`frontend/src/lib/locale.ts`): in the locale where its
  translation is reviewed, else the English as it comes, as is a finding made otherwise or read from a record written
  before. An island says as it comes what its page's catalog doesn't hold, as JavaScript writes some numbers otherwise
  than Python does.
- **A message only `%(name)s` fills**, built, as an island fills only those: what a finding puts in quotes is filled
  `repr`'d, and a list joined, as data.
- **Take: left as they come**, made with `Finding(code, message)`:
  - what a finding passes on of something else's: an exception's, a parser's, jsonschema's, a call's error and the
    facts' reasons (`call.failed`, `case.unreadable`, `answer.*`, `verdict.*`, `expectation.invalid`,
    `expectation_schema.invalid`, `output.schema_invalid`, `facts.budget_refused`, `facts.output_refused`,
    `facts.output_note`);
  - `attestation.model`, which drops `engine` or `judge engine` into its sentence: a message for each, when it's worth
    the change to `src/chatddx/ledger/call.py:attest_model`;
  - what developers and ops read (see "Start with this"): the inventory's findings, an o11n import's, the chat
    template's and `bundle.recanonicalized`, which the CLI and the importer say.

### Refusals

- **A refusal a person can cause**, built, is raised with its wording and parameters,
  `NotFound.of("no person %(login)s", login=…)`, as a finding is made: `src/chatddx/factors/base.py:Worded` is on the
  bench's, the catalog's, the store's, the facts' and the gate's refusals, `Invalid` is a plain `ValueError`'s and
  `Missing` a `LookupError`'s. Its English is `str(e)`, as before, for the repl, the CLI and the logs.
- **Take: its context is `refusal`**, the English as written its key, as a whoops's is; a code of its own only where one
  is needed, which nothing needs yet.
- **Extracted**, built, from each `raise X.of(…)` in `src/chatddx/` (`src/chatddx/locale/locale.py:_refusals`); a
  wording not written where it is raised is marked where it is written, with `pgettext_noop("refusal", …)`.
- **Answered**, built: the API's `Error` carries `wording` and `params` beside `detail`
  (`src/chatddx/api/schemas.py:Error.of`), through `src/chatddx/api/state.py:refused` too
  (`src/chatddx/api/state.py:Refusing`).
- **Said where it is shown**, built, by `src/chatddx/locale/locale.py:refusal`: the error page (`error.html`), a refusal
  shown on the page that was sent (`src/chatddx/portal/pages.py:refusal_of`), a field's, from pydantic's context
  (`src/chatddx/portal/fields.py:_refusal`), and an island's (`frontend/src/lib/api/client.ts:why`). What isn't worded
  is its code's title and `Copy this and send it to drift@chatddx.com:` with the English.
- **Take: left unworded**: what a person can't cause through the portal (the API's shape, an id they don't see, the
  kinds a person doesn't write, the store's integrity); the facts' reasons, which are data; a scorer's problems, which
  the Composer is to prevent; and the gate's secret and engine, which boot is to check. pydantic's own messages on a
  field are said as they come.

### Extraction

Built: `chatddx locale write` extracts, with Babel, what the portal's Python says, its tests left out; what a whoops
says, wherever in `src/chatddx/` it is raised, in the context `whoops`; what a finding says, wherever in `src/chatddx/`
`Finding.of` makes it, in its code's context, with `src/chatddx/locale/locale.py:_findings`, which fails on a code or
message not written out, or a `%` other than `%(name)s` and `%%`; what a refusal says, wherever in `src/chatddx/`
`raise X.of` raises it, in the context `refusal`, with `src/chatddx/locale/locale.py:_refusals`; the templates, with
Jinja's `babel_extract`; and the islands' `t()`, `tn()`, `tp()`, `tnp()` and `th()` in `.svelte` and `.ts`, with
`src/chatddx/locale/locale.py:_islands`, their tests, declarations and shadcn's components left out. It brings each
catalog up to that on both sides of its stamps, in the order of its messages, a changed message untranslated, and begins
a catalog of each tag it is given, such as `chatddx locale write sv`. A catalog keeps which file says each message but
not the line, so that moving code leaves it as it is, and the file is how the islands' share is told: what they say,
whoopses and what is said below the portal, which the API may answer them with. It fails on a message said both counted
and not in the same context, which gettext holds as one plural message, leaving the other untranslatable.

### Checks

- **`chatddx locale check`** and **`chatddx locale pending`**, built: in the `locale` and `pending` checks of
  `dev/check.sh`, the first failing while a catalog is behind the code or messages are said alike (see "The scenario
  index"), the second while a message is left untranslated. A turn's end writes the catalogs, has the agent translate
  what is left untranslated, and stamps each translation that changed since the turn's start (`chatddx-dev stamp docs`),
  which `chatddx-dev stamp pending` flags till it is stamped.
- **Tests**: the ones there were stay English, as no request of theirs asks for another language. Built: in
  `src/chatddx/locale/test/test_locale.py`, a request's language negotiated, boot failing on wrong placeholders, the
  islands' messages found, a finding's found where it is made, a finding said by its code, a catalog kept in step with
  the code, and the islands' share of a catalog; in `src/chatddx/portal/test/test_localized.py`, a reviewed message said
  in a macro imported without context and a pending one not, a finding said by its code in `findings`, a page's `lang`,
  the catalog only in an island's page, and the shelves, a 404's detail and a form's refusal said in the request's
  locale, the shelves sorted by their headings as said; a finish record reading back as written, its findings said or
  not (`src/chatddx/ledger/test/test_ledger.py`). `frontend/src/lib/locale.test.ts`: `t()` and its kin, in English and
  in a catalog's locale, and `localized()`. In a browser (`src/chatddx/portal/test/test_browser.py`), an island said in
  Swedish, a plural put into a sentence among it; and a whoops said in Swedish with what it passes on as it is
  (`src/chatddx/portal/test/test_compose.py`).

## Steps

Each step leaves the portal working in English, and Swedish appearing only where messages are reviewed.

1. **The plumbing**, built: Babel as a dependency, which uv2nix takes into the flake from `uv.lock`; the locale in
   `page`, the `i18n` extension, `lang`, an empty `sv.po`, the boot check, the extractor and the check in
   `dev/check.sh`. Nothing marked, nothing seen to change.
2. **`base.html`, the macros and the Library**, built: each sentence made whole, each plural made `ngettext`, each
   kind's word drawn by `kind`, each message marked; 122 messages. What the Library still says in English comes from the
   portal's Python, the shelves' headings and what each kind is, and waits for step 4.
3. **The other pages**, built: Review, the Lab (now Compose), Scoring, Runs, a run's, a thread's and a case's, the
   World, and every template besides; 613 messages in all. Every page rendered in a locale that brackets each message it
   says leaves unbracketed only the name ChatDDX, data (names, tags, a schema's field names) and what comes from the
   portal's Python and the API, which step 4 and step 6 take.
4. **The portal's Python**, built: `SHELVES`, the refusals of `src/chatddx/portal/fields.py` and of each module's
   routes, the 404s of an address that names nothing, and what the modules name things by (`, an earlier version`,
   `view %(n)s`); 709 messages in all, 96 of them the Python's. What the portal shows from below it stays English: the
   API's and the bench's refusals, pydantic's messages, a scorer's problems and a JSON error's, which step 6 takes.
5. **The islands**, built: `t()` and its kin, the catalog in the page, each message marked, and a whoops's two parts;
   964 messages in all, 324 of them the islands', 73 of which the server says too. Every island page opened in a locale
   that brackets each message leaves unbracketed only data, symbols, and what the API says, which step 6 takes.
6. **Findings and API errors**: a message a code, with its parameters, where one is written, else the English as it
   comes (`src/chatddx/portal/pages.py:refusable`).
   - **Findings**, built: 48 messages of 38 codes, made in the lints, a look at translations, the ledger's checks of a
     run and a score, and the runner; 1011 messages in all (see "Findings").
   - **Decided: the split.** What a person can cause through the portal, typing something wrong, the world moving under
     them or a quota, is worded; what the portal can keep them from, it keeps them from; what is known at boot crashes
     at boot; and the rest, which a person couldn't have caused, is shown as its code's title and
     `Copy this and send it to drift@chatddx.com:` with the English, as a whoops is.
   - **Refusals**, built: 130 wordings, 45 of them the portal's own; 1097 messages in all (see "Refusals").
   - **Decided: no boot checks.** Of what looked known at boot, the shipped scorers' code and an endpoint's engine being
     a trial's turn on what a person writes and picks, and the two that are, an endpoint's engine missing from the store
     and its secret unset, stay borne as warnings: `endpoint.engine_unknown`, the World page and the repl show such an
     endpoint, and the test World keeps `unknown@remote` without its secret.
   - **Prevention**, built: a language field takes only a tag, by the pattern of `src/chatddx/factors/base.py:LANGUAGE`;
     the home page's case holds no more than its limit, counted in code points as Python counts them, and Analyze waits
     while it is over. The names a form asks for were required and the Composer paired a scorer's metrics and judges
     already. Take: not prevented, as it would take a script or refuse what the server takes: picking a trial or a run,
     the concurrency an endpoint takes, a collaborator's login and a label in the labels' JSON, which stay worded.
7. **Swedish**: Take: an agent drafts each translation, which a turn's end stamps, unsaid till a human reviews it by
   stamping it.
   - **Drafted**: all 1099 messages, fuzzy, each placeholder, plural form and piece of markup as its English has them,
     which Babel's catalog checks and the boot check pass with every mark cleared; the portal says nothing in Swedish
     until a mark is cleared.
   - **Take: the words**, as the glossary's terms are drafted, for a reviewer to hold the rest to: case _fall_, family
     _familj_, vignette _vinjett_, appendix _bilaga_, configuration _konfiguration_, recipe _recept_, part _del_, chunk
     _block_, output _svarsform_, passthrough _genomsläpp_, toolset _verktygsuppsättning_, few shot _exempel_, run
     _körning_, item _post_, replicate _replikat_, view _vy_, metric _mått_, finding _anmärkning_, lint _kontroll_,
     model _modell_, endpoint _ändpunkt_, thread _tråd_, fork _förgrening_, origin _ursprung_, cleared _godkänd_,
     sensitive _känslig_, the Library _Biblioteket_, Compose _Sammansättningen_, Review _Granskning_.
   - **Decided: the words reviewed**: the World _Miljön_; scorer _rättare_, score and Scoring _rättning_, to score
     _rätta_; judge _bedömare_, its grading _bedöma_, verdict _omdöme_; expectation _facit_, expectation schema
     _facitschema_; trial _försök_, an attempt always _anropsförsök_; kind _typ_; follow _uppdatera_; handle _alias_;
     out of date _ouppdaterad_ and to update _uppdatera_, with _Uppdatera alla_; seed _seed_; engine _inferensserver_;
     skeleton _förfrågningsmall_; greedy _temperatur 0_, saying where it matters that it always picks the most likely
     next token; the outcomes _giltig_, _slutförd_, _räddad_, _ogiltig_, _med fel_, _oläsbar_ and _stoppad_, cut short
     _avkortat_, and halt _avbryta_; what you see _det du har tillgång till_.
   - **Decided: a language by its name**, in the reader's locale (`src/chatddx/locale/locale.py:display_language`, the
     `language` filter and the islands' `displayLanguage()`), wherever a language is shown, and in a finding or a
     refusal whose parameter is named `language`, `into` or `languages`, the last tags separated by `, `; a field a tag
     is typed in takes a tag.
   - **Decided: a list as the reader's locale says one**, in a finding or a refusal whose parameter is named `slots`,
     `inserts` or `worked`, names separated by `, ` (`src/chatddx/locale/locale.py:_LISTED_PARAMS`), as `languages` is.
   - **Decided: a run is titled from its parts** (`src/chatddx/bench/seen.py:Seen.titled`), said by the portal's
     `run_title` macro and the islands' `runTitle()` as one sentence: its case or how many, in its language, with its
     configuration's name in backticks and what its variation replaced in parentheses, each by its part's word and what
     it holds, on its model, and its seeds in parentheses: ``3 svenska fall med `diagnoses` på qwen3-8b (seed 7)``.
     `Seen.described` stays English, for the repl, the CLI and the logs.
   - **Decided: a case is titled from its parts** (`src/chatddx/catalog/titles.py:case_title`), said by the portal's
     `case` filter (`src/chatddx/portal/titles.py:display_case`) and the islands' `caseTitle()`:
     `%(case)s with %(appendices)s`, and briefly `%(case)s + %(num)s appendices` in a run's title; the English stays
     what the repl and scripted runs name a case by.
   - **Decided: what is shown has a name**, and a title derived of what a thread holds is the repl's: an expectation
     with no name is said by its case (`expecting`, the `titled` filter), a fork of one takes no derived name, and a
     thread's page no longer shows its derived title under its name.
   - **Decided: the cases left out are said once**, with the languages a variation is sent in, in a sentence of their
     own where the configuration has no translations into theirs, not as `translations.missing`.
   - **Decided: no "it" in a button or a heading**, where Swedish would say _den_ or _det_ by a word the message doesn't
     know: `Delete it` is _Radera_, `Its versions` _Versioner_.
   - **Decided: one message for ops**, `Copy this and send it to drift@chatddx.com:`, wherever a page or an island
     passes something on, the address written into it until it is a setting.
   - **Open: the kinds' words** (see "Open") are drafted translated, as `kind` messages a reviewer can leave unreviewed
     to keep them English.
8. **Numbers**: the global default, `1 000.34`, wherever the server and the islands write a number, counts put into
   messages among them.

## Open

1. **The kinds' words**: translated, kept as the glossary's (they are the API's, the docs' and the address's,
   `?kind=configuration`), or both, as the Library is to teach the data model. Step 2 draws them in one place, so this
   is settled in the catalog whenever it is.
2. **Refusals**: they are English. A code for each, translated where shown; translated where shown with the English as
   the key, as a whoops's `said` is; or English for now. A whoops is settled (see "Start with this"), and so is a
   finding, by its code (see "Findings"), and a refusal, by its wording (see "Refusals").
3. **What data sets hold**: a schema's titles and descriptions in more than one language is a question of the data
   format, and left out of these steps.
4. **A locale with more plural forms** than one and other: the islands' `t()` would need gettext's forms in the order of
   CLDR's categories, which Babel derives its own from.
