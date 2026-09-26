# The chatddx portal

The portal is chatddx in a browser: Django's admin, dressed by unfold, at
`/admin/`. It is being ported to the new datamodel page by page, and its
first page is the Batch: the repl's `batch`, with its slices varied, run by
a worker beside the portal, and watched and held from its Status page.

## Serving it

The portal has settings of its own, `chatddx.django.settings.portal`: the
minimal settings the CLI, the repl, the worker and the API's tests keep
to, and what serving the portal takes on top of them (unfold, the portal's
app, the web's middleware, languages, CORS for the API). Nothing but the
portal's server and its tests reads them. The time zone, the lab's, is the
minimal settings', so the repl and the worker tell time as the portal does.

```
export DJANGO_SETTINGS_MODULE=chatddx.django.settings.portal
django migrate                        # the portal's own table too
chatddx init-data alice               # alice, and the archive's inventory
django createsuperuser --username alice
django runserver
```

and beside it, on the minimal settings, the worker that runs the batches:
`chatddx worker serve` (see [The worker](#the-worker)).

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

Saving a batch puts its trials in the worker's queue, cell by cell and
case by case, and its **Ran** counts those the worker has taken up and
finished.

The batch is the portal's own. No run points at one, and nothing outside
the portal refers to it (`backlog/post-endgame.md`).

### Status

**Status**, the tab beside **Batches**, is the worker at its queue: not a
batch's, but what the worker has been at lately, whosever batch it came
from. It follows along every second.

- What the worker is at, in a few words: running, idle, pausing, paused,
  stopping, or not running at all.
- **Pause** holds the queue once the case under way is done, and
  **Resume** lets it go on.
- **Stop** ends the drain as Ctrl-C ends the repl's batch: pressed once,
  when the case under way is done; pressed again, as **Stop now**, with
  it, written down as stopped. What was queued is taken out of the queue
  for good.
- The progress bar counts the drain's cases: running, completed, in all,
  and those a stop took out. A drain runs from an empty queue to an empty
  queue again, so a batch saved while another runs joins its drain.
- The case running: its cell, whose it is, how long it has run, and its
  tokens as the repl tallies them, `~N` as they stream and `N` once the
  server has counted them.
- The ten cases taken up last, the latest first: when, the case, the cell,
  how it went and why, its tokens, and its scores.

Watching takes the view permission on batches, and pausing and stopping the
add permission.

## The worker

The worker runs the queue the batches fill, a case at a time: each trial
as the repl's batch runs one, on the bench of the identity whose batch it
is, sent, streamed back, written down in the history (in a conversation
held in `worker`) and scored.

```
chatddx worker serve    # the queue as it fills, till stopped: the host's service
chatddx worker run      # what is queued, then stop
```

It needs no more than the minimal settings, as the rest of the CLI. The
host runs `chatddx worker serve` as a service beside the portal's server,
and SIGTERM stops it as Ctrl-C would: the case under way is written down as
stopped, and what is queued waits for the worker to come back.

- A trial runs what was confirmed, or not at all: a configuration changed
  since is skipped, and so is a trial its stack now refuses, or whose
  secret is gone, each with why. Its case runs as it was planned.
- While a case runs, the worker beats every half second: the tally the
  status page shows, and a stop pressed. A case whose worker went away and
  has not beaten for 30 seconds is lost.
- Not seen at its queue for 10 seconds, the worker is taken not to be
  running.

The queue is the worker's own table, `worker_queued`, beside a row of its
state, `worker_state`: paused, stopping, and when it was last seen.
`chatddx wipe-data` takes an identity's trials out of it with the rest of
its history.

## Beside the repl and the API

The repl, the API, the portal and its worker plan and run a cell the same
way, through `chatddx.bench`: a bench is the registry as an identity sees
it, a cell is a configuration and a stack with what is set in them, a plan
is a batch's cells, each ready or held back, on its cases under one seed,
and a sending is a trial on its way: sent, streamed back, come to an
outcome, and written down once and scored.

| repl | portal |
| --- | --- |
| `use`, `on` | Use, On |
| `set SLICE VARIATION` | a variation ticked in place of the configuration's |
| `seed [SEED]` | Seed |
| `show tag TAG...` | the confirmation |
| `batch TAG...` | a batch of one cell |
| Ctrl-C | Stop |
| Ctrl-C again | Stop now |
