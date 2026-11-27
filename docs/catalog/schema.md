# What `schema` says

Written by `chatddx-dev index` from the messages said in `[parts.schema]`'s code in `settings.toml`, its tests left out, as `chatddx locale write` extracts them into the catalogs, sorted by file and then by message whatever its case:

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

## `frontend/src/lib/schema/SchemaField.svelte`

```
%(field)s by %(author)s
```

```
It isn't JSON yet: %(error)s
```

```
Leave out %(name)s
```

```
none expected
```

## `frontend/src/lib/schema/form.ts`

`a field`

```
answer
```

`a field`

```
comment
```

`a field`

```
Disposition
```

`a field`

```
Final diagnosis
```

`a field`

```
Match
```

`a field`

```
Must not be missed
```

`a field`

```
Own note
```

`a field`

```
Possible warnings
```

`a field`

```
Statement
```
