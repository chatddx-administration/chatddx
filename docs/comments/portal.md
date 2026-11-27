# Comments in `portal`

Written by `chatddx-dev index` from the comments in `[parts.portal]`'s code in `settings.toml`, sorted by file and then by name whatever its case:

````
## `<file>:<the name it is in or right above>`

```
<the comment, as written>
```
````

- A comment in or above no name is under its file alone, and comments on lines one after another are one.
- A stamp pending is a git conflict, from `<<<<<<< signed` to `=======` as last stamped and on to the `>>>>>>>` closing it as written now, till it is stamped.

## `frontend/src/islands/Home.svelte`

```
// Policy: what is out of date isn't offered, as only a researcher can update it.
```

## `frontend/src/islands/Home.svelte:characters`

```
// Accommodating for Python, which counts a text's code points where JavaScript counts its
// UTF-16 units.
```

## `frontend/src/lib/scorer/judging.ts:seedsOf`

```
// Policy: seeds are read from what is typed, whatever it is, so that nothing typed is
// refused: each whole number once, and the seed 1 while none is typed.
```

## `frontend/src/lib/scorer/judging.ts:startingParams`

```
// Policy: starting params for a judged view: its verdict at the judge's first field that isn't text, and, when the
// metric takes a most, that field's maximum.
```

## `frontend/src/lib/scorer/selectors.ts:same`

```
// Policy: a simple dotted path and the JSON Pointer to the same place pick the same, so either finds its choice.
```

## `frontend/src/lib/scorer/texts.ts:asked`

```
// Duplication: As src/chatddx/factors/request.py:compile_request places it, guidance goes where it's inserted, or
// else after the instructions.
```

## `frontend/src/lib/scorer/texts.ts:fillText`

```
// Duplication: src/chatddx/factors/scoring.py:fill_text's "text@1": one text as it is, texts a line each, anything
// else as JSON.
```

## `frontend/src/lib/scorer/texts.ts:textOf`

```
// Duplication: As src/chatddx/factors/request.py:_text keeps a Text, so that a text left as it was compares equal to
// the one stored.
```

## `frontend/src/lib/utils.ts:WithoutChildren`

```
// eslint-disable-next-line @typescript-eslint/no-explicit-any
```

## `src/chatddx/portal/editors.py:_FORMED`

```
# Policy: a field earns its schema's form where what it holds is shaped by the schema;
# one that holds whatever a request or a template takes, or mostly whitespace, is
# clearer as JSON.
```

## `src/chatddx/portal/fields.py:_bracketed`

```
# Policy: a box whose field is an object or a list holds what is between its brackets,
# which the page shows around it, so that what is typed is of its shape whatever it is.
```

## `src/chatddx/portal/fields.py:_engines`

```
# Policy: an engine is picked by its model's handle, as researchers see handles, not
# engines.
```

## `src/chatddx/portal/fields.py:_given`

```
# Accommodating for browsers, which send a textarea's line breaks as CRLF.
```

## `src/chatddx/portal/fields.py:_lines`

```
# Policy: a list of whole numbers is read from whatever is typed, each whole number once,
# so that nothing typed in it is refused.
```

## `src/chatddx/portal/fields.py:listed`

```
# Accommodating for the API, which lists configurations of one purpose at a time.
```

## `src/chatddx/portal/mending.py:_queueing`

```
# Policy: queued once every run is begun, so that the worker sending the first doesn't
# slow beginning the rest, and queued too when beginning one fails, so that none is left
# begun with nothing to send it.
```

## `src/chatddx/portal/mending.py:pressed`

```
# Policy: a press made while something is under way for its run, from a second tab, a
# stale page or a second click, counts as made: the page it leads back to says so.
```

## `src/chatddx/portal/pages.py`

```
# Accommodating for Jinja, whose tojson sorts keys: an island sends back what it's given,
# and a component's digest holds the order of its keys.
```

```
# pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
```

```
# Accommodating for Jinja, whose globals are typed as its own defaults are.
```

## `src/chatddx/portal/pages.py:refusable`

```
# Policy: what a person can set right on the page they sent, which shows it again with
# what they typed and why it was refused; the rest is answered as the API answers it.
```

## `src/chatddx/portal/pages.py:refusal_of`

```
# Policy: what a person can cause is worded, and what isn't worded they couldn't have
# caused, so it is passed on as it is.
```

## `src/chatddx/portal/pages.py:signing_in`

```
# Policy: a sign-in passes by the sign-in page once more, which sends the person on if
# their browser kept the session's cookie and says so if it didn't.
```

## `src/chatddx/portal/review.py:running_in_review`

```
# Policy: as on the run page, a press made while a run of the case is under way
# counts as made.
```

## `src/chatddx/portal/runs.py:halting`

```
# Policy: as with pressed, a run with nothing left under way is halted already.
```

## `src/chatddx/portal/runs.py:run`

```
# Accommodating for a job ending once its run's rows are written: asked before the run
# is read.
```

## `src/chatddx/portal/scores.py:_repeats`

```
# Policy: the person's own runs only, newest first, and each repeat under the same scorer,
# its own scoring's score first, so that a value apart from this one is the run's rather
# than another expectation's unless it says so.
```

## `src/chatddx/portal/shelves.py:AUTHORED`

```
# Accommodating for configurations, which a person writes as recipes, not as components.
```

## `src/chatddx/portal/shelves.py:IN_REVIEW`

```
# Policy: an appendix is written and shown in Review alone, in the case it goes with, so
# the Library shelves none and has no page of one; a case built of appendices is written
# there too, so the Library shelves cases locked.
```

## `src/chatddx/portal/shelves.py:IN_WORLD`

```
# Dependency: the cards of src/chatddx/portal/templates/world.html, by the kinds they
# show.
```

## `src/chatddx/portal/test/conftest.py:paged`

```
# Accommodating for signed's client, which runs the app's lifespan and its worker: this one
# shares them, so it is never entered.
```

## `src/chatddx/portal/test/conftest.py:pytest_collection_modifyitems`

```
# Policy: a browser test starts a browser, so it runs only when asked for by its mark.
```

## `src/chatddx/portal/test/helpers.py:_Submitted`

```
# Accommodating for what a browser sends of a form: a select's chosen option, else its
# first, a checkbox only when checked, and a textarea's text without the line break that
# follows its opening tag.
```

## `src/chatddx/portal/test/helpers.py:ran_template`

```
# Accommodating for pytest, as src/chatddx/test/helpers.py:curated_template does.
```

## `src/chatddx/portal/test/test_browser.py:portal`

```
# Accommodating for a browser, which keeps the __Host- session cookie over plain HTTP
# only on localhost.
```

## `src/chatddx/portal/test/test_browser.py:test_a_press_shows_until_the_next_page_comes_and_sends_its_form_once`

```
# Accommodating for Chromium, which runs no script on a page while a navigation from it is held:
# the navigations a press starts are cancelled instead, which leaves the page as pressed.
```

## `src/chatddx/portal/test/test_library.py:test_a_shelf_is_found_in_by_what_is_said_and_its_cases_narrowed_by_tags`

```
# Accommodating for the test World's shelves, which are shorter than a page: a page
# as long as the shelf gives it its search box.
```

## `src/chatddx/portal/threads.py:_checked`

```
# Policy: a form is read as it is typed as it is read when it is sent, so that the island
# holds it back while it would be refused rather than sending it to be.
```

## `src/chatddx/portal/threads.py:_drawn`

```
# Policy: a new trial is begun with what a start of a variation takes when none is
# given.
```

## `src/chatddx/portal/threads.py:_editable`

```
# Policy: an expectation stays of the case and the schema it was written for; Review
# carries it to a case that replaces its own.
```

## `src/chatddx/portal/threads.py:_shipped`

```
# Policy: a new scorer pins the code chatddx ships, as it is shown and not asked.
```

## `src/chatddx/portal/translations.py:_NEAR`

```
# Policy: an entry under half of whose words are the text's is too far off to start from.
```

## `src/chatddx/portal/translations.py:posted`

```
# Accommodating for browsers, which send a textarea's line breaks as CRLF.
```

## `src/chatddx/portal/world.py:_sent`

```
# Dependency: what src/chatddx/factors/request.py:compile_request sends of a level's
# writes.
```
