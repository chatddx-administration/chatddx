# What `catalog` says

Written by `chatddx-dev index` from the messages said in `[parts.catalog]`'s code in `settings.toml`, its tests left out, as `chatddx locale write` extracts them into the catalogs, sorted by file and then by message whatever its case:

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

## `src/chatddx/catalog/threads.py`

`refusal`

```
case %(case)s has expectations to choose from, in threads %(threads)s
```

`refusal`

```
thread %(thread)s has moved on since edit %(edit)s: its head is edit %(head)s
```
