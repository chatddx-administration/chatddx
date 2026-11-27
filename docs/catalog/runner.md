# What `runner` says

Written by `chatddx-dev index` from the messages said in `[parts.runner]`'s code in `settings.toml`, its tests left out, as `chatddx locale write` extracts them into the catalogs, sorted by file and then by message whatever its case:

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

## `src/chatddx/runner/gate.py`

`refusal`

```
endpoint %(endpoint)s isn't cleared for source %(sources)s, which is sensitive
```

`refusal`

```
the configuration's tools would get content from source %(sources)s, which is sensitive, and tools can't be cleared yet
```

## `src/chatddx/runner/run.py`

`run.resumed`

```
resumed after %(done)s of %(num)s items
```

```
resumed after %(done)s of %(num)s items
```

`run.resumed`

```
resumed after %(done)s of %(num)s items by %(now)s, where %(then)s started it
```

```
resumed after %(done)s of %(num)s items by %(now)s, where %(then)s started it
```

## `src/chatddx/runner/score.py`

`answer.salvaged`

```
cut short, and read with its structure closed
```

`answer.salvaged`

```
cut short, and read with its structure closed; the call ended with: %(error)s
```
