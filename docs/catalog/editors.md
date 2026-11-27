# What `editors` says

Written by `chatddx-dev index` from the messages said in `[parts.editors]`'s code in `settings.toml`, its tests left out, as `chatddx locale write` extracts them into the catalogs, sorted by file and then by message whatever its case:

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

## `frontend/src/lib/editors/ExpectationEditor.svelte`

```
%(problem)s. What you typed is kept: save again to make it the version after the latest.
```

```
Every answer of the case's that this is scored against, and what it finds in each
```

```
Measure
```

```
none expected
```

```
Not as a scorer reads it
```

## `frontend/src/lib/editors/Saving.svelte`

```
%(problem)s. What you typed is kept: save again to make it the version after the latest.
```

```
name
```

```
Save
```

## `frontend/src/lib/editors/writing.ts`

```
Give it a name to save it.
```

```
Saves a new version of it.
```

```
Saves it as “%(name)s”, a fork of your own.
```

```
Writes “%(name)s”, a new thread of your own.
```
