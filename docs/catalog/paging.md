# What `paging` says

Written by `chatddx-dev index` from the messages said in `[parts.paging]`'s code in `settings.toml`, its tests left out, as `chatddx locale write` extracts them into the catalogs, sorted by file and then by message whatever its case:

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

## `frontend/src/lib/paging/Finding.svelte`

```
%(shown)s of %(of)s
```

```
Find
```

```
Find by what it says
```

## `frontend/src/lib/paging/Pages.svelte`

```
Next
```

```
page %(at)s
```

```
page %(at)s of %(of)s
```

`of a list`

```
Pages
```

```
Previous
```
