# What `runs` says

Written by `chatddx-dev index` from the messages said in `[parts.runs]`'s code in `settings.toml`, its tests left out, as `chatddx locale write` extracts them into the catalogs, sorted by file and then by message whatever its case:

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

## `frontend/src/islands/RunLive.svelte`

```
%(ended)s of %(of)s item ended
```

```
%(ended)s of %(of)s items ended
```

```
%(n)s scored
```

```
%(n)s scored
```

```
%(n)s tool call
```

```
%(n)s tool calls
```

```
%(n)s view
```

```
%(n)s views
```

```
%(num)s token
```

```
%(num)s tokens
```

```
%(scored)s over %(views)s
```

```
%(sent)s in, %(got)s out
```

```
Answer
```

`job`

```
finished
```

```
It ended before this page followed it; its answer is on the run's page once it is done.
```

```
Items ended
```

```
judges answered %(answered)s of %(asked)s
```

```
judges answered %(answered)s of %(asked)s
```

```
Reload the page to see how far it has come.
```

```
Scoring
```

`in progress`

```
scoring
```

`in progress`

```
sending
```

```
sent
```

`job`

```
stopped
```

```
Thinking
```

```
under way
```

`in progress`

```
waiting
```

## `frontend/src/lib/runs/events.ts`

```
the run's events stopped coming
```

## `frontend/src/lib/runs/outcomes.ts`

`outcome`

```
%(num)s completed
```

```
%(num)s completed
```

`outcome`

```
%(num)s errored
```

```
%(num)s errored
```

`outcome`

```
%(num)s invalid
```

```
%(num)s invalid
```

`outcome`

```
%(num)s salvaged
```

```
%(num)s salvaged
```

`outcome`

```
%(num)s stopped
```

```
%(num)s stopped
```

`outcome`

```
%(num)s unread
```

```
%(num)s unread
```

`outcome`

```
%(num)s valid
```

```
%(num)s valid
```

`outcome`

```
completed
```

`outcome`

```
errored
```

`outcome`

```
invalid
```

`outcome`

```
salvaged
```

`outcome`

```
stopped
```

`outcome`

```
unread
```

`outcome`

```
valid
```

## `frontend/src/lib/runs/progress.ts`

`in progress`

```
calling a tool
```

```
the run didn't finish
```

`in progress`

```
thinking
```

`in progress`

```
writing
```

## `frontend/src/lib/runs/titles.ts`

```
%(case)s (earlier)
```

```
%(case)s + %(num)s appendix
```

```
%(case)s + %(num)s appendices
```

```
%(case)s in %(language)s
```

```
%(case)s with %(appendices)s
```

```
%(cases)s with %(configuration)s on %(model)s (%(seeds)s)
```

```
%(num)s %(language)s case
```

```
%(num)s %(language)s cases
```

```
%(num)s case
```

```
%(num)s cases
```

`a part replaced`

```
%(part)s: %(title)s
```

`sampling`

```
greedy
```

```
greedy, %(num)s replicate
```

```
greedy, %(num)s replicates
```

`a part replaced`

```
no %(part)s
```

```
seed %(seeds)s
```

```
seeds %(seeds)s
```
