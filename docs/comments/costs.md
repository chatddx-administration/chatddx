# Comments in `costs`

Written by `chatddx-dev index` from the comments in `[parts.costs]`'s code in `settings.toml`, sorted by file and then by name whatever its case:

````
## `<file>:<the name it is in or right above>`

```
<the comment, as written>
```
````

- A comment in or above no name is under its file alone, and comments on lines one after another are one.
- A stamp pending is a git conflict, from `<<<<<<< signed` to `=======` as last stamped and on to the `>>>>>>>` closing it as written now, till it is stamped.

## `dev/src/chatddx_dev/costs/__init__.py:Cost`

```
# Duplication: dev/check.sh:spooled writes these columns too, in this order.
```

## `dev/src/chatddx_dev/costs/__init__.py:Costs`

```
# Compromise: timed from when pytest loads its plugins, its own start left out.
```

## `dev/src/chatddx_dev/costs/__init__.py:Costs.pytest_unconfigure`

```
# Accommodating for a checkout without git, such as nix's: nothing is spooled there.
```

## `dev/src/chatddx_dev/costs/__init__.py:MARGIN`

```
# Policy: a whole run varies less than a test does (src/chatddx/test/budget.py:MARGIN), but
# a figure is rewritten only once this far off, lest every turn stamp a new one.
```

## `dev/src/chatddx_dev/costs/__init__.py:pytest_configure`

```
# Accommodating for pytest-xdist, whose workers each run pytest too: the controller alone
# times the run. A run of pytest in a test is rooted elsewhere, and isn't timed either.
```

## `dev/src/chatddx_dev/costs/__init__.py:SPOOL`

```
# Policy: what is timed between commits waits here, out of git, so that a check run between
# turns leaves the worktree clean; write folds it into LOG.
```
