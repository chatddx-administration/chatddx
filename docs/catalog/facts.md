# What `facts` says

Written by `chatddx-dev index` from the messages said in `[parts.facts]`'s code in `settings.toml`, its tests left out, as `chatddx locale write` extracts them into the catalogs, sorted by file and then by message whatever its case:

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

## `src/chatddx/facts/lint.py`

`facts.missing`

```
no facts about %(name)s, so model-level checks were skipped
```

`facts.reasoning_unmatched`

```
the configuration's reasoning settings match none of the model's reasoning levels
```

`facts.sampling_unmatched`

```
the configuration's sampling is what the facts recommend for %(others)s, not for %(name)s
```
