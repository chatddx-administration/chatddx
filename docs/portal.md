# The chatddx portal

The portal is chatddx in a browser: Django's admin, dressed by unfold, at
`/admin/`. It is being ported to the new datamodel page by page. Its pages
so far are the Cases, where clinicians go through each case and work with
its vignette and targets, and the Batch: the repl's `batch`, with its
slices varied, run by a worker beside the portal, and watched and held from
its Status page.

The portal shows you what is yours: your cases, configurations and
variations. The one exception is what answers, the stacks and their parts,
a class of record the archive keeps for everyone.

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

## Cases

**Cases** in the sidebar lists your cases, as a to-do list:

- each case's language;
- what its targets still want: a text, a pattern, or a pattern that
  parses;
- its tags, its versions, and when it was last saved.

Filter the list by tag, by language or by what is still wanted, and
search the names and the vignettes. **Add case** starts a blank one.

### A case's page

A case's page shows one version of it, in its timeline:

- ◀ and ▶ step through the versions, with "version i of n" and when each
  was saved.
- It lists what that version changed of the one before: the vignette word
  by word, each target's text and pattern, the language and the tags.
- The cases before and after it in the list it came from are a click
  away, with the list filtered as it was.

The latest version is a form:

- **Name**, **Language** and **Vignette**.
- **Targets**. Each kind has a text, in plain words for people, and a
  pattern, what the scorers look for. Either can wait. **None expected**
  marks a warning that none is expected of.
- **Tags**: those of your cases, or new ones.

The form refuses a pattern that doesn't parse. It trims the whitespace
around a text or a pattern, and an empty one counts as missing.

An earlier version is shown as it was. **Edit from here** puts its content
in the form, and saving it makes a new version from it; the versions after
it stay in the timeline.

### Saving

One save makes one new version, and that version becomes the head. Saving
what is there already makes none, and a change of tags alone is saved on
the head as it is.

The name decides where the save goes. A line under the vignette says so as
you type, and the button says the same:

- **the case's own name:** a new version of it;
- **a new name:** a new case, and this one stays as it is;
- **the name of another case of yours:** a new version of that case,
  replacing its vignette and targets. The save asks first, showing that
  case beside what replaces it. A case you deleted comes back this way.

The tags go with the page. A name can't hold `/`, and the page says when a
name differs from one of yours in capitals alone. If the case has a newer
version since you opened the page, the page says so, and saving again
saves yours on top of it.

The vignette is what the model reads, so a changed vignette is another
case to the runs: the runs of the old vignette keep the targets they had.
A vignette that differs only in its line endings, or in the whitespace
around it, is the same vignette.

Where another case has the page's vignette, the page says so:

- **One of yours.** While both have it, its runs go by neither name, and
  a batch by tag runs it once. **Take its tags off** the other case, or
  open it.
- **One shared with you, the archive's.** Named as it is, yours takes its
  place for you, and the vignette's runs go by that name. **Name it …**
  puts that name in.

### Runs and scores

Under the case are your runs of its vignette, the latest first: when, the
trial, how it ran, and each scorer's score for the targets they are held
to now. A score not yet made for a changed target is **outstanding**, and
**Score again** makes them.

### Deleting

**Delete this version** deletes a version for good. Deleting the latest
version is an undo: the version before it becomes the head again. A
version can't be deleted if scores were held to it, or if runs or trials
of your batches read its vignette and no other version of the case has
it.

**Delete the cases ticked**, in the list, deletes whole cases:

- a case nothing has read is gone for good;
- any other case is taken out of sight. It leaves every list and batch,
  and its runs keep its name and targets.

Deleting a case's only version deletes the case. Right after, **Undo**
brings it back, and so does saving a case under its name.

Reading cases takes the view permission on them; saving a new version of
one takes the change permission, a new case the add permission, and
deleting the delete permission.

## The Batch

**Batches** in the sidebar lists your batches; the button at the top right
plans a new one.

### Planning

The form begins as the repl's cell does, on what is yours: the portal
shows you your own configurations, variations and cases, and the
archive's stacks, what answers being a class of record the archive keeps
for everyone.

- **Use:** a configuration of yours.
- **On:** a stack.
- **Case tags:** the cases of yours to run, those with any of the tags. A
  vignette under two names runs once.
- **Seed:** drawn as the repl draws one. Empty, the trials go unseeded.

`chatddx init-data USER --with-giftbag` gives a new owner the archive's
configurations and variations to start from; their cases they add under
**Cases**.

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

**Back to the form** brings back what was asked, to change it. **Run it
now** keeps the batch and puts its trials in the worker's queue; **Keep it
for later** keeps it with its trials stored, to run from its page. A plan
with nothing to run can't be kept.

### What a batch keeps

A batch keeps what was asked (the configuration and the stack by name, the
case tags, the variations ticked, the seed) and the plan confirmed: each
cell to run, with what it sets, the fingerprint of the configuration it
comes to and its seed; each cell held back and why; and each case, by name
and fingerprint. Its trials are the worker's jobs, cell by cell and case by
case.

The batch is the portal's own. No run points at one, and nothing outside
the portal refers to it (`backlog/post-endgame.md`). Batches are their
owner's alone: **Batches** lists yours, and the status page follows yours.

### A batch's page

A batch's page shows what it keeps, and never changes it. It says how the
batch stands, and follows it every few seconds while it is on its way:

- **Kept for later**, none of it run: **Run the batch**.
- **Queued**: up next, behind another batch of yours on its stack, or
  waiting for our turn, as many cases ahead of ours as the stack has to
  run first.
- **Running**, and how many of its trials have completed.
- **Stopped**, or **Unfinished** where some went wrong: **Resume the
  batch** queues again what didn't complete, stopped, failed or kept.
- **Completed**: **Run it again** queues all of it again.

A trial queued again goes behind what is in the queue, and its runs are
new ones: the runs it had stay in the history.

Its only input is **More cases**: the cases of yours with any of the case
tags picked, or the cases picked, that the batch doesn't hold. The batch's cells
run on them, queued behind its trials while it is on its way, and stored
till it is run otherwise.

### Status

**Status**, the tab beside **Batches**, is the worker at your jobs, whichever
of your batches they came from. It follows along every second.

- What the worker is at with them, in a few words: running, waiting for
  our turn, queued, idle, pausing, paused, stopping, or not running at all.
- Waiting for our turn, for each stack: how many cases are ahead of ours,
  and how many of them run.
- **Pause** holds your queue once the cases running are done, and
  **Resume** lets it go on. Others' jobs go on meanwhile, and yours hold
  no one up.
- **Stop** takes your queue out, as Ctrl-C ends the repl's batch: pressed
  once, what is queued is stopped at once and the cases running finish;
  pressed again, as **Stop now**, they are stopped too, written down as
  stopped. Everything that didn't complete is stopped, to resume from its
  batch's page.
- The progress bar counts your batches on their way, or the last one:
  running, completed, in all, and those that failed and those stopped.
- The cases running: their cells, how long each has run, and their tokens
  as the repl tallies them, `~N` as they stream and `N` once the server has
  counted them.
- Up next: the case your queue runs next, and how many are outstanding.
- The ten cases taken up last, the latest first: when, the case, the cell,
  the batch, how it went and why, its tokens, and its scores.

Watching takes the view permission on batches, and running, adding cases,
pausing and stopping the add permission.

## The worker

The worker runs the queue the batches fill: each job a trial run as the
repl's batch runs one, on the bench of the identity whose batch it is,
sent, streamed back, written down in the history (in a conversation held
in `worker`) and scored.

```
chatddx worker serve    # the queue as it fills, till stopped: the host's service
chatddx worker run      # what is queued, then stop
```

It needs no more than the minimal settings, as the rest of the CLI. The
host runs `chatddx worker serve` as a service beside the portal's server,
and SIGTERM stops it as Ctrl-C would: the cases running are written down as
stopped, and what is queued waits for the worker to come back.

- **Slots.** A stack takes as many jobs at once as its `max_jobs` says
  (`inventory.md`), one by default; the worker runs jobs on different
  stacks side by side. A stack's jobs go first queued, first run, whosever
  they are: a batch queued behind another's waits for its turn.
- **Isolation.** Nothing is shared between owners: two who run the same
  trial (the same greedy cell on the same case, say) each get runs of
  their own, with their own times.
- A trial runs what was confirmed, or not at all: a configuration changed
  since is skipped, and so is a trial its stack now refuses, or whose
  secret is gone, each with why. Its case runs as it was planned.
- While jobs run, the worker beats every half second: the tallies the
  status page shows, and a stop pressed. A job whose worker went away and
  has not beaten for 30 seconds is lost.
- Not seen at its queue for 10 seconds, the worker is taken not to be
  running.

The queue is the worker's own table, `worker_job`: each job stored,
queued, running, or come out completed, errored, aborted (stopped as it
ran), stopped (before its turn), skipped or lost. Beside it are each
owner's controls, `worker_controls` (paused, stopping), and the worker's
`worker_state`, when it was last seen. `chatddx wipe-data` takes an
identity's jobs out with the rest of its history.

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
