# Comments in `api`

Written by `chatddx-dev index` from the comments in `[parts.api]`'s code in `settings.toml`, sorted by file and then by name whatever its case:

````
## `<file>:<the name it is in or right above>`

```
<the comment, as written>
```
````

- A comment in or above no name is under its file alone, and comments on lines one after another are one.
- A stamp pending is a git conflict, from `<<<<<<< signed` to `=======` as last stamped and on to the `>>>>>>>` closing it as written now, till it is stamped.

## `frontend/src/lib/api/client.ts:why`

```
// Policy: what a person can cause is worded, and what isn't worded they couldn't have
// caused, so it is passed on as it is.
```

## `src/chatddx/api/app.py:_raw`

```
# Compromise: Raw, though it may quote sensitive content, until edges hold that back.
```

## `src/chatddx/api/app.py:_unstorable`

```
# Policy: a value the database can't take, a number past its integers or a text holding U+0000, is
# the request's to set right wherever it was given, so it is refused here once for every route.
```

## `src/chatddx/api/listening.py:_AGAIN`

```
# Policy: how long, in seconds, the listener waits after losing its connection, and at
# most for anything to happen.
```

## `src/chatddx/api/listening.py:BEHIND`

```
# Policy: a stream this many messages behind drops what it holds and reads the ledger
# again.
```

## `src/chatddx/api/measuring.py:_Readings`

```
# Policy: a run's latest score under each scorer alone, so that a run scored again isn't
# told twice.
```

## `src/chatddx/api/measuring.py:_told`

```
# Policy: what was found is told by the items it was found in alone, so that lists that
# differ only elsewhere are told as one; what was missed by all the view picked, so that
# what the pattern should have found is there to see. A view that picked nothing, for
# want of an answer or a target, scored nothing, whatever its value says.
```

## `src/chatddx/api/runs.py:_checked`

```
# Policy: drift is compared across the person's earlier finished runs of the trial at
# the same endpoint too, as decided (docs/backlog.md, "Drift between runs").
```

## `src/chatddx/api/state.py:refused`

```
# Policy: what may be missing of what a request's body or query names is a 422, where
# what its path names is a 404.
```

## `src/chatddx/api/telling.py:KEEP_ALIVE`

```
# Accommodating for proxies, which cut a quiet stream: comment lines, which event
# readers skip, keep it going.
```

## `src/chatddx/api/telling.py:told`

```
# Policy: it listens before it reads, so that no row lands unheard in between.
```

## `src/chatddx/api/test/helpers.py:joined`

```
# Policy: the owner's queue stays paused until the stream has said its first row: by
# then it listens.
```

## `src/chatddx/api/test/helpers.py:listened`

```
# Dependency: served as src/chatddx/cli.py:_serve serves the portal.
```

## `src/chatddx/api/test/helpers.py:UNDER_WAY`

```
# Policy: a fake this slow keeps a run's job under way while a stream asked for at once
# joins it: one asked for after it has ended is told the ledger's rows alone.
```

## `src/chatddx/api/test/helpers.py:world_served`

```
# Accommodating for pytest, as src/chatddx/test/helpers.py:curated_template does.
```

## `src/chatddx/api/test/test_variations.py:test_a_look_s_queries_don_t_grow_with_its_cases`

```
# Accommodating for the components Store.get holds parsed: both looks are made once
# before they are counted, so that neither counts reading what the other read.
```

## `src/chatddx/api/test/test_variations.py:test_a_look_s_queries_don_t_grow_with_its_cases.counting`

```
# Accommodating for the fixtures, which make the next test's database meanwhile:
# only the look's database's queries count.
```

## `src/chatddx/api/threads.py:_expecting`

```
# Policy: an expectation with no name is said by its case, in the reader's locale, rather
# than by a title derived in English.
```

## `src/chatddx/api/threads.py:_THREADS`

```
# Policy: so many listings held and no more; each is what a person was shown of a kind
# under the filters asked, held while the catalog's version stands, as the threads it
# lists and how each is told (titles, whether it is outdated) are read from the catalog,
# the components and the inventory alone, a database being served one World, besides
# logins, which never change.
```
