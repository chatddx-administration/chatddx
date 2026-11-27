# What `review` says

Written by `chatddx-dev index` from the messages said in `[parts.review]`'s code in `settings.toml`, its tests left out, as `chatddx locale write` extracts them into the catalogs, sorted by file and then by message whatever its case:

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

## `frontend/src/lib/review/About.svelte`

```
a new tag
```

```
Change its language
```

```
language
```

```
Take away the tag %(tag)s
```

## `frontend/src/lib/review/Appendices.svelte`

```
Add an appendix
```

```
Change it
```

## `frontend/src/lib/review/AppendixForm.svelte`

```
name
```

```
Text, as it is added to the vignette
```

## `frontend/src/lib/review/Expected.svelte`

```
Discard what you changed?
```

```
It is the first.
```

```
Next version
```

```
Previous version
```

```
The fields hold this version: Save makes it the latest.
```

```
version %(at)s of %(last)s
```

```
Versions
```

## `frontend/src/lib/review/Faring.svelte`

```
%(value)s, above %(share)s%% of the other cases
```

```
%(value)s: %(num)s cases, %(drawn)s of them drawn: %(names)s
```

```
Above
```

```
Configuration
```

```
Configurations
```

```
drawn
```

```
Legend
```

```
none yet
```

```
not scored
```

```
Numbers
```

```
Other cases
```

```
Other cases, drawn
```

```
Other cases, run
```

```
out of date
```

`in progress`

```
reading
```

```
Replicate %(n)s: %(value)s
```

```
Replicates
```

```
Scores
```

```
the whole answer
```

```
This case
```

```
This case: %(value)s, above %(share)s%% of the other cases
```

```
This World draws scores for every case and configuration none of your runs scored: lighter, they show how a case would sit among others, not how any did.
```

```
three replicates and a repeat, as things are now
```

```
under way
```

```
View
```

## `frontend/src/lib/review/Measuring.svelte`

```
%(answers)s answers, scored %(scored)s times.
```

```
%(num)s alternative
```

```
%(num)s alternatives
```

```
and %(more)s more
```

```
Close
```

```
Found
```

```
Measuring
```

```
Missed
```

```
none
```

```
not scored
```

```
Score
```

```
Scores every answer again against the field as it is written now, saved or not
```

`in progress`

```
scoring
```

```
Show
```

```
Show %(more)s more
```

```
Update
```

```
Where
```

## `frontend/src/lib/review/Run.svelte`

`a button`

```
Run
```

## `frontend/src/lib/review/Save.svelte`

```
Discard what you changed?
```

```
Restore
```

```
Save
```

## `frontend/src/lib/review/Vignette.svelte`

```
can't be shown
```

```
the vignette
```

```
This isn't the text the case was made from any more.
```

## `frontend/src/lib/review/faring.ts`

```
it has no runs of the case yet
```

```
it isn't scored against the expectation as it is
```

```
it stopped before it finished
```

```
it was halted before it finished
```

```
its configuration has changed since it ran
```

```
its latest runs of the case aren't three replicates and a repeat
```

```
no translation into %(language)s
```

```
out of date
```

```
under way
```

```
update it on its page
```
