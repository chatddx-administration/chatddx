# What `compose` says

Written by `chatddx-dev index` from the messages said in `[parts.compose]`'s code in `settings.toml`, its tests left out, as `chatddx locale write` extracts them into the catalogs, sorted by file and then by message whatever its case:

````
## `<file>`

`<its context>`

```
<the message, as written>
```

```
<its plural>
```
````

- A message said in no context has none before it, and one not counted no plural after it.
- A stamp pending is a git conflict, from `<<<<<<< signed` to `=======` as last stamped and on to the `>>>>>>>` closing it as written now, till it is stamped.

## `frontend/src/islands/Compose.svelte`

```
%(ended)s of %(of)s item ended
```

```
%(ended)s of %(of)s items ended
```

```
Brings version %(n)s of this configuration back as the latest.
```

```
Give it a name to save it.
```

```
Independent of this one: not a fork of it, nor of its parts
```

```
It holds no recipe, so its parts can't be changed here.
```

```
Items ended
```

```
name
```

```
Nothing to save: this is the configuration as it is.
```

```
Request
```

`a button`

```
Run
```

```
Save
```

```
Saves a new configuration of yours, “%(name)s”, forked from version %(n)s of this one.
```

```
Saves a new configuration of yours, “%(name)s”, independent of this one.
```

```
Saves version %(n)s of this configuration, from version %(was)s.
```

```
Saves version %(n)s of this configuration.
```

```
Saving it
```

```
under way
```

```
You have one named so already; names needn't be unique.
```

```
You have %(n)s named so already; names needn't be unique.
```

## `frontend/src/lib/compose/Breakdown.svelte`

```
%(num)s case
```

```
%(num)s cases
```

```
Baseline
```

```
cases
```

```
Configurations
```

`job`

```
failed
```

```
Languages
```

```
Legend
```

```
Mean
```

```
none
```

```
Numbers
```

```
out of date
```

```
Repeats
```

```
runs
```

```
the whole answer
```

```
Tokens
```

`cases`

```
Unanswered
```

```
View
```

## `frontend/src/lib/compose/Cases.svelte`

```
%(n)s case picked
```

```
%(n)s cases picked
```

```
all
```

```
Find a case
```

```
Pick by tag or language
```

```
Replicates
```

```
Run it on %(n)s case
```

```
Run it on %(n)s cases
```

```
Run it on cases
```

```
Score it once it is finished
```

## `frontend/src/lib/compose/JsonField.svelte`

```
Not JSON yet: it is kept as it was till it is.
```

## `frontend/src/lib/compose/Paired.svelte`

```
%(label)s, text %(n)s
```

```
After it:
```

```
Before it:
```

## `frontend/src/lib/compose/Preview.svelte`

`change`

```
added
```

```
appendix %(n)s
```

```
Appendix layout
```

```
As a call to %(name)s, its schema the tool's parameters.
```

```
As JSON to its schema, which response_format holds.
```

```
as text
```

```
As text, its schema told where it is inserted.
```

```
Close
```

```
Compiles it again as it is written now, saved or not
```

```
Formatted
```

```
not translated yet
```

```
Original
```

```
Output guidance
```

```
Put between them as it is compiled
```

```
Raw
```

`change`

```
removed
```

```
Request
```

```
the answer
```

```
the answer's schema
```

```
Tool guidance
```

```
Tools
```

```
Update
```

```
Update compiles it as it is written now, saved or not.
```

```
Views
```

## `frontend/src/lib/compose/Said.svelte`

```
Into %(language)s: %(text)s
```

```
It still reads right
```

```
out of date
```

```
Shared with %(parts)s.
```

## `frontend/src/lib/compose/Settings.svelte`

```
A call to an answer tool, its parameters the schema.
```

```
A tool call
```

```
A value given here is used in place of the one recommended.
```

```
A value left out is the engine's.
```

```
Add a tool
```

```
Advanced
```

```
Answer tool name
```

```
As the model writes it; JSON read out of it if it has a schema.
```

```
Chat template arguments
```

```
default
```

```
Description
```

```
Effort
```

```
frequency penalty
```

```
Further keys of the request, as they are sent; the keys the rest sets are refused.
```

```
Held to its schema by the engine, as response_format.
```

```
Inline the schema's references
```

```
Its $refs replaced by what they point at before it is sent (inline_refs@1).
```

```
JSON
```

```
Lands at %(level)s.
```

```
Leave out %(name)s
```

```
Leave out stop sequence %(n)s
```

```
Level
```

```
Manual
```

```
max output tokens
```

```
min p
```

```
Model default
```

```
No facts are known about it, so a thinking level and recommended sampling can't be worked out.
```

```
presence penalty
```

```
Read JSON out of the answer, checked against a schema
```

```
Recommended sampling
```

```
repetition penalty
```

```
sampling
```

```
Settings
```

```
stop sequence
```

```
Stop sequence %(n)s
```

```
Stop sequences
```

```
temperature
```

`an output`

```
text
```

```
the answer
```

```
the answer's schema
```

```
The key for max output tokens
```

```
The one the engine's API takes.
```

```
Thinking
```

```
Thinking token budget
```

```
Tool rounds
```

```
Tools
```

```
top k
```

```
top p
```

## `frontend/src/lib/compose/Texts.svelte`

```
%(label)s, message %(n)s
```

```
%(n)s to look over
```

```
Appendix layout
```

```
Languages
```

```
Leave out %(name)s
```

```
none
```

```
Original
```

```
Output guidance
```

```
Schemas and tools
```

```
Texts
```

```
the answer's schema
```

```
Tool guidance
```

```
Translate it into %(language)s no more
```

## `frontend/src/lib/compose/baseline.ts`

```
%(num)s ahead
```

```
%(num)s ahead
```

```
%(status)s: %(why)s
```

`job`

```
failed
```

`job`

```
finished
```

```
halting
```

```
paused
```

```
queued
```

`in progress`

```
scoring
```

`in progress`

```
sending
```

`job`

```
stopped
```

## `frontend/src/lib/compose/breakdown.ts`

```
%(missing)s of %(of)s case unanswered
```

```
%(missing)s of %(of)s cases unanswered
```

## `src/chatddx/portal/templates/compose.html`

```
A configuration is <a class="begin" href="/library/new?kind=configuration">written from a recipe</a> in the Library.
```

```
Baseline
```

```
Compose
```

```
Configuration
```

```
Configurations
```

```
Findings
```

```
forked from %(origin)s
```

```
needs scripts
```

```
newer version
```

```
Next version
```

```
no translation into %(language)s
```

```
none you see
```

```
Open the latest
```

```
out of date
```

```
Previous version
```

```
Request
```

```
saved %(at)s by %(by)s
```

```
Show in the Library
```

```
translate it to run the baseline
```

```
update it on its page
```

```
version %(at)s of %(last)s
```

```
Versions
```

## `src/chatddx/portal/templates/gathering.html`

```
%(configuration)s, version %(n)s, on its baseline
```

```
%(missing)s of %(of)s case unanswered
```

```
%(missing)s of %(of)s cases unanswered
```

```
%(num)s case
```

```
%(num)s cases
```

```
%(run)s, the original in %(language)s
```

```
%(run)s, the repeat in %(language)s
```

```
a language unknown
```

```
A value leads to its score, where its answer is read against the expectation.
```

```
Baseline
```

```
Baseline run
```

```
Breadcrumb
```

```
By case, under %(view)s
```

```
Case
```

```
cases
```

```
Its repeats: how far, on average, each case's repeat was from its replicate, and %(alike)s of %(compared)s answered alike to the letter.
```

```
language
```

```
Languages
```

```
Mean
```

```
out of date
```

```
Previous run
```

```
Repeat
```

```
Repeats
```

```
Replicate
```

```
Run
```

```
runs
```

```
Scored
```

```
Scores
```

`cases`

```
Unanswered
```

`a case`

```
unanswered
```

```
up to date
```

```
View
```

```
Δ is against the run before, case by case on the cases both sent.
```
