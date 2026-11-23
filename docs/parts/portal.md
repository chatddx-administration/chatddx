# The portal

The portal is where clinicians review and researchers research, assume they're tech-illiterate with little time and
cognitive reserves.

## Its pages

- **Review**: where clinicians check their vignettes against appendices and expectations, write them, and evaluate a
  case under every configuration they see; how a configuration fares beyond one case is for Scoring and Runs.
- **Compose**: writing configurations from their texts and settings.
- **Scoring**: managing judges and scorers.
- **Runs**: everything run-related: what is under way and what is queued, its order, pausing and halting.
- **Library**: schema driven, instructive of the data model rather than practical. Translations stay in the Library,
  which is the de facto translation page as long as its UX and the Library's philosophy are aligned.
- **World**: a read-only view of the World the portal runs in.
- **Landing**: `/` for whoever isn't signed in, what ChatDDX is for and a tour in screenshots
  (`src/chatddx/portal/templates/landing.html`); signed in, `/` is the home page. The screenshots are of the sample
  World's scripted data (`chatddx scripted-compose`, then `scripted-review` of dutch-10, then `scripted-runs`), kept in
  `frontend/public/landing/` and served at `/static/landing/`.

Take: each page by what it writes, what it weighs and what it only picks, so that a thing is written in one place and
weighed where its consequences show.

| Page    | For                     | Writes                                                          | Weighs                                                     | Picks                  |
| ------- | ----------------------- | --------------------------------------------------------------- | ---------------------------------------------------------- | ---------------------- |
| Review  | clinicians              | appendices, expectations; a case's tags and language            | a case against its expectation under each configuration    | —                      |
| Compose | researchers             | configurations of either purpose, and the chunks they hold      | —                                                          | models                 |
| Scoring | researchers             | judges; a scorer's code, resources, parameters and labels       | what a scorer reads and how it scored; a judge's verdicts  | judges' configurations |
| Runs    | whoever runs and scores | the queue: its order, pausing, halting, stopping; scoring again | what is under way, queued and left to score; runs compared | —                      |
| Library | everyone                | any kind, a field at a time; translations                       | versions, what each changed, findings                      | —                      |
| World   | everyone                | nothing                                                         | the World whole                                            | —                      |

Take, the moves it asks for:

1. **What a judge is asked** is changed on Scoring (`JudgeTexts`), and a scorer's views, with a judge made of a
   configuration, a model and seeds in place (`JudgeEditor`), in the Library (`ScorerViews`), all in
   `frontend/src/lib/scorer/`: Review composes no scorer and says nothing of what reads an expectation. Built.
2. **A judge's configuration** is still written in Compose, beside every other configuration. How its judges fare is on
   Scoring, which links to Compose.
3. **The code a scorer pins**, its metrics and what each measures and takes, is shipped, so it is the World's to show,
   as models are, and Scoring links to it.
4. **Scoring again** stays on Runs, and Scoring links to what is left to score.
5. **The navigation** reads Review, Compose, Scoring, Runs, Library, World: the three benches by who works at them, then
   what runs, the data model and the World. Built.
6. **The name** Scoring, over Judging or Scorers: a run's scoring is what its scorer and judges make of it. Decided, as
   no namespace collides with it: the kind `scoring` stays derived, is a thread kind of the catalog but no word of the
   bench's (`src/chatddx/bench/model.py:KINDS`), so it has no Library tab, no `kind` of the API's threads and no page,
   and nothing plans one.

## The look

The pages are HTML documents, and their look follows from what each element does: `frontend/src/portal.css` styles a
button by being a button and a link by what clicking it does, so a template carries a word of what it is rather than the
utilities of how it looks, and no macro draws a button or a link.

Drafted:

- **Contrast**: text at 4.5:1 at least on a pane, inputs' outlines at 3:1, in both colour schemes; panes solid and
  bordered, and lighter than the page in dark mode, darker than it in light.
- **Buttons**: a `<button>` does something.
- **Links**: an `<a>` goes somewhere:

| Kind       | Clicking it                                                      | Marked by          | Looks                                                   |
| ---------- | ---------------------------------------------------------------- | ------------------ | ------------------------------------------------------- |
| thing      | opens a thing's own page                                         | nothing            | underlined, in the primary colour                       |
| navigation | moves around the portal: the header, sidebars, tabs, breadcrumbs | being in a `<nav>` | not underlined; the current one barred under, or beside |
| jump       | moves down the page                                              | `href="#…"`        | a thing's, with ↓                                       |
| bench      | takes a thing to another bench                                   | `bench`            | a thing's, with →                                       |
| begin      | opens a form that writes something new                           | `begin`            | a thing's, with +                                       |
| view       | changes what the page shows: filters, sorting, paging, versions  | `view`             | grey and dotted; the one in effect bold, with ✓         |

- **Headings**: a section's title in a header ruled off across its pane (`src/chatddx/portal/templates/macros.html`), a
  bare `h2` a pane's title and a bare `h3` a part of one; small capitals only over a table's columns.
- **A press**: the script in `src/chatddx/portal/templates/base.html` marks what was pressed and runs a bar along the
  top until the next page comes, and keeps a form from being sent twice meanwhile; Back, and Stop where the browser has
  the Navigation API, clear it.
- **A long list**: a page holds `settings.ROWS_PER_PAGE` rows, 100. A list that may grow is wrapped in
  `src/chatddx/portal/templates/macros.html:paged`, which gives it a search box from as many rows and a pager past them;
  the script in `base.html` keeps the rows that say every word typed, shows a page of them at a time, and shows the page
  a row is on when it is jumped to or holds the current one. Without scripts every row shows. Runs are searched by their
  titles and paged on the server instead (`src/chatddx/portal/runs.py:runs`), and the Library's own search, with its
  tags and schemas, stays on the server, from as many rows. The islands do the same with `frontend/src/lib/paging/`,
  their page size given in their props: a variation's runs on the server, the cases picked for a run and a run's items
  under way in the browser.

Open:

- The benches keep their own compact headings, as their `h1` is as large as a section's title.
- Inputs, selects and text boxes are still styled by utilities in each template.
- The islands' buttons and links are shadcn's or utilities, of none of these kinds yet.

## The Library

The Library is for schema driven views, threads fit right in, but cases, runs, configurations and translations do not
and are squeezed in for completeness.

- **The sidebar**: the kinds under headings, the headings and the kinds under each sorted alphabetically, always open,
  no deeper tree: what refers to what is a graph, not a hierarchy, and a collapsed branch hides a kind from a person
  with little time.
- **A vignette's text stays out of the Library**, deliberately: a case's section links to it on a page of its own.
- **No sample trials for now**: data sets load none, so the trial shelf starts empty, says how a trial is begun, and
  points to Review, which runs a configuration on a case straight away.

## Scoring

Drafted: `/scoring/{id}` (`src/chatddx/portal/scoring.py`; `src/chatddx/portal/test/test_scoring.py`) shows a scorer or
a judge the person sees, rendered on the server with no island, and writes nothing yet. `/scoring` leads to the person's
first scorer, and the Library's page of a scorer or a judge leads to theirs.

- **Scorers and judges**: each the person sees, their own first, the scorers by the expectation schema they grade
  against and the judges by the model they are asked under.
- **A scorer**: its views, each with its metric and what it measures, what it picks of an answer and of an expectation,
  its judge, flagged where it asks an earlier version, and its parameters. The configurations whose answers it reads and
  those it doesn't (`src/chatddx/factors/scoring.py:View.offered_by`). How many of the cases the person sees they expect
  something of under its schema, with those to choose from and those without, each linking to Review. How it scored: the
  person's runs scored by this version, by their mean under each view, compared on `/runs/compare`. Its findings.
- **A judge**: its configuration, linking to Compose, its model, seeds, fill rule, and the endpoint it is served at now
  or why none. The views of the scorers asking it, by the version of it each asks, or the judge it is forked from, and
  for each scorer asking another, following its latest version: the views asking another are pointed at it, in a new
  version of the person's own scorer or a fork of another's, with its labels. What it is asked, rendered with its first
  seed, a placeholder for the answer, and what a view asking it picks of what a case expects, both picked on the page
  and by default the first such view and the first case it reads something of. What it is asked is changed in place with
  `JudgeTexts` (`frontend/src/islands/scoring.ts`), previewed against the same pick: saving keeps the texts, the judge's
  configuration and the judge as the person's own, and leads to that judge's page. Its verdicts, over the latest score
  of the person's runs under each scorer asking any version of it: the items judged, how many its seeds agree on, how
  many a seed gave none for, the mean, and the items where its seeds disagree. These are the values a view's metric read
  of each seed's verdict, kept in the item's detail, never the verdicts, which are sensitive. Its findings.
