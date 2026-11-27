# What `bench` says

Written by `chatddx-dev index` from the messages said in `[parts.bench]`'s code in `settings.toml`, its tests left out, as `chatddx locale write` extracts them into the catalogs, sorted by file and then by message whatever its case:

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

## `src/chatddx/bench/cases.py`

`refusal`

```
over the day's quota: %(used)s of %(limit)s
```

`refusal`

```
U+0000 can't be stored
```

## `src/chatddx/bench/components.py`

`refusal`

```
%(name)s has no translation into %(languages)s
```

`refusal`

```
%(text)s is in %(held)s already: a text's language is the same wherever it is held
```

`refusal`

```
a trial's cases are in one language, not in %(languages)s
```

## `src/chatddx/bench/runs.py`

`refusal`

```
%(name)s has no translation into %(languages)s
```

`refusal`

```
%(name)s is out of date: update it on its page
```

`refusal`

```
a run holds at most %(num)s item, not %(given)s
```

```
a run holds at most %(num)s items, not %(given)s
```

`refusal`

```
no case can be sent: %(refused)s
```

`refusal`

```
over the day's quota: %(used)s of %(limit)s
```

`refusal`

```
run %(run)s is out of date: run its configuration instead, once that is updated
```

## `src/chatddx/bench/saying.py`

`refusal`

```
no person %(login)s
```

## `src/chatddx/bench/seen.py`

`refusal`

```
%(configuration)s names no model: name the one to run it under
```

`refusal`

```
%(login)s has their own expectation of %(case)s under %(schema)s already, in thread %(thread)s
```

`refusal`

```
%(name)s has no translation into %(languages)s
```

`refusal`

```
%(name)s is out of date: update it on its page
```

`refusal`

```
model %(model)s is deleted: pick another
```

`refusal`

```
no endpoint here serves model %(model)s: pick another
```

`whoops`

```
The model has no handle and can't be used.
```

## `src/chatddx/bench/taking.py`

`refusal`

```
%(login)s has their own expectation of %(case)s under %(schema)s already, in thread %(thread)s
```

## `src/chatddx/bench/updating.py`

`refusal`

```
%(name)s can't be updated until %(judge)s is
```

`refusal`

```
%(name)s can't be updated: %(refused)s
```
