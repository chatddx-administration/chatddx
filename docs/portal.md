# The chatddx portal

The portal is chatddx in a browser: Django's admin, dressed by unfold, at
`/admin/`. It is being ported to the new datamodel page by page, and its
first page is the Batch: the repl's `batch`, with its slices varied.

## Serving it

The portal has settings of its own, `chatddx.django.settings.portal`: the
minimal settings the CLI, the repl and the API's tests keep to, and what
serving the portal takes on top of them (unfold, the portal's app, the web's
middleware, languages and time zone, CORS for the API). Nothing but the
portal's server and its tests reads them.

```
export DJANGO_SETTINGS_MODULE=chatddx.django.settings.portal
django migrate                        # the portal's own table too
chatddx init-data alice               # alice, and the archive's inventory
django createsuperuser --username alice
django runserver
```

A user signs in as the identity of their name, as the API's session does.
`DJANGO_MODE=main` serves it for real: the secret key from
`SECRET_KEY_FILE`, `HOST` as the allowed host, and secure cookies.

## The Batch

**Batches** in the sidebar lists your batches; the button at the top right
plans a new one.

### Planning

The form begins as the repl's cell does:

- **Use:** a configuration, yours or the archive's.
- **On:** a stack.
- **Case tags:** the cases to run, those with any of the tags. A vignette
  under two names runs once.
- **Seed:** drawn as the repl draws one. Empty, the trials go unseeded.

Once there are case tags, the slices come in: instruction, output,
coercion, reasoning, sampling and toolset, each a row of your variations of
it, with the configuration's own ticked. Putting in another configuration
ticks its own instead, forgetting what was ticked, as `use` forgets what
`set` held.

Tick more, and the batch runs every combination of what is ticked:
reasoning `off` and `on` with sampling `recommended` and `greedy` are four
cells. A slice with nothing ticked keeps the configuration's own, and a
batch crosses into 100 cells at most.

### Confirming

**Review the batch** shows its plan before anything is kept:

- how many trials it plans: its cells, times its cases;
- each cell, as the configuration and what it sets in place of the
  configuration's own, and its seed: a cell whose sampling is greedy runs
  unseeded, since a seed would change nothing;
- each cell held back and why: what its stack refuses, as `show` says it,
  or a secret you don't have;
- the cases;
- each scorer: how many of the cells offer what it reads, and how many of
  the cases have the target it holds them to, and which don't.

**Back to the form** brings back what was asked, to change it. **Save the
batch** keeps it; a plan with nothing to run can't be saved.

### What a batch keeps

A batch keeps what was asked (the configuration and the stack by name, the
case tags, the variations ticked, the seed) and the plan confirmed: each
cell to run, with what it sets, the fingerprint of the configuration it
comes to and its seed; each cell held back and why; and each case, by name
and fingerprint. It is shown, never changed or deleted.

Nothing runs a batch yet: a worker to drain the batches kept comes next.

The batch is the portal's own. No run points at one, and nothing outside
the portal refers to it (`backlog/post-endgame.md`).

## Beside the repl and the API

The repl, the API and the portal plan and run a cell the same way, through
`chatddx.bench`: a bench is the registry as an identity sees it, a cell is
a configuration and a stack with what is set in them, and a plan is a
batch's cells, each ready or held back, on its cases under one seed.

| repl | portal |
| --- | --- |
| `use`, `on` | Use, On |
| `set SLICE VARIATION` | a variation ticked in place of the configuration's |
| `seed [SEED]` | Seed |
| `show tag TAG...` | the confirmation |
| `batch TAG...` | a batch of one cell |
