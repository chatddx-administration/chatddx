# What `ledger` says

Written by `chatddx-dev index` from the messages said in `[parts.ledger]`'s code in `settings.toml`, its tests left out, as `chatddx locale write` extracts them into the catalogs, sorted by file and then by message whatever its case:

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

## `src/chatddx/ledger/call.py`

`execution.timeout`

```
%(num)s attempt took longer than the %(limit)s s timeout
```

```
%(num)s attempts took longer than the %(limit)s s timeout
```

`execution.retries`

```
%(num)s calls took more than the %(allowed)s attempts allowed
```

```
%(num)s calls took more than the %(allowed)s attempts allowed
```

`execution.concurrency`

```
%(num)s calls were in flight at once, declared %(declared)s
```

```
%(num)s calls were in flight at once, declared %(declared)s
```

`execution.order`

```
%(num)s item was sent before items scheduled ahead of them
```

```
%(num)s items were sent before items scheduled ahead of them
```

## `src/chatddx/ledger/record.py`

`ledger.seal`

```
rows changed after the log was sealed
```

## `src/chatddx/ledger/run.py`

`run.incomplete`

```
%(num)s canary call missing
```

```
%(num)s canary calls missing
```

`canary.phase`

```
%(num)s end canary calls started before the last item call finished
```

```
%(num)s end canary calls started before the last item call finished
```

`attestation.prompt_tokens`

```
%(num)s item has no prompt token fingerprint
```

```
%(num)s items have no prompt token fingerprint
```

`run.incomplete`

```
%(num)s item missing
```

```
%(num)s items missing
```

`canary.phase`

```
%(num)s start canary calls hadn't finished when the first item was sent
```

```
%(num)s start canary calls hadn't finished when the first item was sent
```

`canary.drift`

```
canary %(canary)s answered %(ways)s ways where it was to answer alike
```

`canary.prompt_drift`

```
canary %(canary)s was tokenized %(ways)s ways
```

`tools.stopped`

```
round %(round)s stopped after %(ran)s of %(num)s tool calls, before its call
```

```
round %(round)s stopped after %(ran)s of %(num)s tool calls, before its call
```

`tools.code`

```
the code tool %(tool)s ran with isn't recorded
```

`engine.system_drift`

```
the engine said %(ways)s system fingerprints
```

`tools.unanswered`

```
the last response still calls %(tools)s after %(rounds)s of %(num)s rounds
```

```
the last response still calls %(tools)s after %(rounds)s of %(num)s rounds
```

`case.drift`

```
the vignette read differs from the case's
```

`tools.code`

```
tool %(tool)s ran at version %(ran)s of %(entry_point)s, not the version it pins (%(pinned)s)
```

## `src/chatddx/ledger/score.py`

`score.incomplete`

```
%(num)s item missing
```

```
%(num)s items missing
```

`score.no_expectation`

```
%(num)s of the run's cases have no expectation in the scoring
```

```
%(num)s of the run's cases have no expectation in the scoring
```

`score.run_unfinished`

```
the run hasn't finished
```

`score.run_unfinished`

```
the score started before the run finished
```

`score.scorer_code`

```
the scorer code ran at version %(ran)s of %(entry_point)s, not the version the scorer pins (%(pinned)s)
```

`view.unreachable`

```
view %(view)s picks %(selector)s from the output, but the run's output schema has no %(selector)s
```

`judge.incomplete`

```
view %(view)s's value rests on %(called)s of %(num)s judge seeds
```

```
view %(view)s's value rests on %(called)s of %(num)s judge seeds
```
