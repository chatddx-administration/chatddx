# The chatddx portal

The portal shows you what is yours: your cases, configurations and
variations. The one exception is the stacks and their parts,
a class of record the archive keeps for everyone.

## Cases

**Cases** in the sidebar lists your cases.

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
what is there already does nothing, and a change of tags alone is saved on
the head as it is and does not make a new case.

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
**Score again** makes them. The when opens the run's page (see
[Runs](#runs)).

### Deleting

**Delete this version** deletes a version for good. Deleting the latest
version is an undo: the version before it becomes the head again. A
version that has been used in a run can't be deleted proper, so deleting
it will set its deleted flag to True and never show up anywhere except
where it has been used.

Reading cases takes the view permission on them; saving a new version of
one takes the change permission, a new case the add permission, and
deleting the delete permission.

## The Batch

**Batches** in the sidebar lists your batches; the button at the top right
plans a new one.

### Planning

The portal shows you your own configurations, variations and cases, and the
archive's stacks.

- **Use:** a configuration of yours.
- **On:** a stack.
- **Case tags:** the cases with any of the tags (de-duped).
- **Seed:** A random seed is chosen automatically. Change it or remove it for
the trials run unseeded.

Once there are case tags, the slices come in: instruction, output,
coercion, reasoning, sampling and toolset, each a row of your variations of
it, with the configuration's own ticked.

Tick more, and the batch runs every combination of what is ticked:
reasoning `off` and `on` with sampling `recommended` and `greedy` are four
cells. A slice with nothing ticked keeps the configuration's own.

### Confirming

**Review the batch** shows its plan before anything is kept:

- how many trials it plans: its cells, times its cases;
- each cell, as the configuration and what it sets in place of the
  configuration's own, and its seed: a cell whose sampling is greedy runs
  unseeded, since a seed would change nothing. The configuration opens its
  page, in a tab of its own, with what the cell sets in it (see
  [Configurations](#configurations));
- each cell held back and why: what its stack refuses, as `show` says it,
  or a secret you don't have;
- the cases;
- each scorer: how many of the cells offer what it reads, and how many of
  the cases have the target it holds them to, and which don't.

**Back to the form** brings back what was asked, to change it. **Run it
now** keeps the batch and puts its trials in the worker's queue; **Keep it
for later** keeps it with its trials stored, to run from its page. A plan
with nothing to run can't be kept.

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
- **Stop** takes your queue out. Pressed once let the cases running finish,
  pressed again, as **Stop now**, they are stopped too, written down as
  stopped. Everything that didn't complete is stopped, to resume from its
  batch's page.
- The progress bar counts your batches on their way.
- The cases running, how long each has run, and their tokens.
- Up next: the case your queue runs next, and how many are outstanding.
- The ten cases taken up last, the latest first with links to
  [Configurations](#configurations) and [Stacks](#stacks)).

Watching takes the view permission on batches, and running, adding cases,
pausing and stopping the add permission.

## Runs

**Runs** in the sidebar lists your runs, the latest first: each by the
start of its uuid, when it was sent, its trial, how it came out, and each
scorer's latest score. Search them by their trials.

### A run's page

A run's page shows a read-only view of the run.

- **The run:** its trial (the cell, the case and the seed), how it came
  out (valid, invalid, completed, errored or stopped), when it was sent
  and how long it took. Then its details:
  - why it went wrong, where it did, and how its last response finished.
  - the case: a case of yours opens at the version the run used.
  - the batch it came from, and which of its trial's runs it is.
  - the stack and the LLM, as it read them.
  - the tools it ran, each with its file.
  - the client it was sent from.
  - its tokens, over how many requests.
  - its conversation.
  - the configuration as it ran, with each variation set in it, which
    opens its page (see [Configurations](#configurations))
- **Answer:** each of the output's views of it, and the answer as written.
- **Scores:** each scorer's latest score.
- **Messages:** each message, folded to a line of what it says.
  - Opened, a message shows itself part by part: the instructions where
    they are new, the thinking folded, the text, the answer and each
    call's arguments as JSON, and each return, by the id of the call it
    answers; and the model that wrote it, and how it finished.
  - **Open all** and **Close all** open and close every message.
  - A message can be linked to as `#message-N`.
- **What it sent and got back:** each request as it was sent, and each
  response as it streamed back with its size and events.

The runs are their owner's alone: another's run is not found. Reading them
takes the view permission on runs.

## Configurations

**Configurations** in the sidebar lists your configurations.

### A configuration's page

A configuration's page shows a version of it, read only, with whatever
variations were set in place of its own.

- ◀ and ▶ step through the configuration's versions, with what is set in
  it kept. On an earlier one, a note says a newer one is saved, when, and
  which slices it changed; **Open the latest** opens it.
- **A variation.** Where a cell sets variations in place of the
  configuration's own, as `plan-web+coercion=tool+reasoning=high` does,
  the page says it is a variation of the configuration, which opens it as
  it is saved.
- **Each component**, by the name you have for its variation:
  - the instruction: its system and user templates.
  - the output: its guidance, the views scorers read.
  - the coercion: its mode, the schema prompt, and the tool description;
  - the reasoning: its effort and budget;
  - the sampling: what a setting left out means, and what it sets outright;
  - the toolset: its tools, and its guidance, or none.

## Stacks

**Stacks** in the sidebar lists the stacks you run on, the archive's and
any of your own: each at its latest version, with its LLM, its machine,
its endpoint, its slots, and how many versions it has.

### A stack's page

A stack's page shows a version of it, and never changes it. The list opens
the latest; a run's page, and the cases taken up last on the Status page,
open the version the run read, with the version of the LLM it read.

- ◀ and ▶ step through the versions. On an earlier one, a note says a newer
  one is saved, when, and what it changed; **Open the latest** opens it.
- **The stack:** its endpoint and served name, its API, the secret it takes
  and whether you have it, its slots (how many of the worker's jobs it
  takes at once), and its tags.
- **Its parts**, each by the name you have for it:
  - the **LLM**: its snapshot and source, its specs, and its facts: what
    each reasoning effort sends, or collapses into, or why it is refused;
    the sampling recommended for each; which coercions hold and what they
    need; and its profile. Opened from a run, it is the version the run
    read, with a note where a newer one is saved;
  - the **serving**: its engine, its arguments and environment, what it
    sets for speed, and the parsers it provides;
  - the **machine**: its id, its GPUs, CPU, RAM and location, and whether
    it is a cloud provider's;
  - its **system**, and a container's host's: its toplevel, the flake
    revision, and its host name, kernel, NVIDIA driver and nixpkgs
    revision.

### Testing a stack

**Test** tries the version shown live, as its page shows it, and says how
each check went as it goes. Nothing is written down.

- **The server**, asked what it serves (`GET /v1/models`) and what it is
  (`GET /version`):
  - **Reached**: how soon it answered, or why it didn't: it can't be
    reached, it refuses the secret, or the secret is one you don't have.
    Unreached, nothing further is tried.
  - **Serves the LLM**: it lists the stack's served name; else it says
    what it serves, and the LLM isn't tried.
  - **Loads the snapshot**: what it loaded is the LLM's snapshot. A model
    loaded by its repository name, as the fake vLLM's, can't be told from
    one.
  - **Context**: the tokens it takes in, held to its serving's
    `max-model-len`, or, where that says nothing, to the LLM's whole
    context.
  - **Engine**: its vLLM version, held to its serving's engine.
- **The LLM**, sent to as a run is, by its facts, unseeded:
  - **Answers**: asked for its spec, with its own reasoning and the
    sampling recommended, and streamed as it comes, its thinking and then
    its answer: how soon the first token came and how fast the rest, and
    whether thinking came back as its facts say it does.
  - **Reasoning off**: no thinking comes back, where its facts can turn it
    off.
  - **Native**, **Tool** and **Prompted**: its spec held to a schema each
    way, with the least reasoning its facts allow: guided decoding, the
    schema never shown; a call of the answer tool; the schema shown, and
    nothing more.
  - **Calls a tool**: `probe`, a tool the answer can't be known
    without, called with arguments that hold, and an answer once it
    returned.

  A check the facts or the serving refuse isn't tried, and says why.

Reading stacks, and testing them, take the view permission on stacks.

## Proposed amendments

### A run's page and a batch's cells go by the versions they pinned

- **By:** Claude (Claude Code), 2026-09-28 00:01 UTC
- **Reason:** Under **A run's page**, "the configuration as it ran, with
  each variation set in it" is read from the run's own configuration and
  variation versions now, not parsed from the cell's label and the
  conversation's description: its page is the version it ran, though a
  newer one is saved since. Under **Confirming** and **A batch's page**, a
  batch's trials are planned once, as jobs pinning the trial and the
  versions read: renaming a case, a variation or a configuration afterwards
  changes nothing the batch runs, and the case and cell names the batch and
  **Status** show are those versions'. A trial whose stack's head is
  another stack than was planned is skipped, and says so.
- **Related:**
  [django/portal/configurations.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/django/portal/configurations.py#L106-L133),
  [django/portal/status.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/django/portal/status.py#L199-L256),
  [django/portal/batches.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/django/portal/batches.py#L65-L105),
  [worker/queue.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/worker/queue.py#L71-L104),
  [bench/bench.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/bench/bench.py#L313-L346)

### A stack's slots are its timeline's

- **By:** Claude (Claude Code), 2026-09-28 00:01 UTC
- **Reason:** Under **Status**, "Waiting for our turn, for each stack": the
  slots of a stack are its timeline's, its owner's and its name's, with
  `max_jobs` read from its head when the worker looks. Stacks are the
  archive's to share, so a stack of yours by one of the archive's names has
  slots of its own.
- **Related:**
  [worker/queue.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/worker/queue.py#L31-L69),
  [worker/worker.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/worker/worker.py#L106-L131)
