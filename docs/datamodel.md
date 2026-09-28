# The chatddx datamodel

This document describes the underlying data structure of ChatDDX.

For using ChatDDX, see `portal.md` (admin interface), `repl.md` (the shell),
`inventory.md` (the files that seed the database) and `api.md` (how external tools may connect).

## 1. The classes of data

ChatDDX have two classes of data, both immutable and append-only: Repo and
History. History is the laboratory ledger that logs experimental runs,
conversations and scores. Repo is a collection of 16 versioned controlled factors,
each is declared as a configuration entity in `repo/entities/<entity>`.

Their integrity is assured by fingerprinted Trails (data) and associated Branches (metadata).

A Branch is called "branch" because it behaves like a git branch, with a timeline
attached to its name. So there's a head (canon), and it can be committed to, but it can't
be changed.

## 2. Guiding principles
We want to be able to generate thousands of experiments on whatever inference server we
come by, and find which factors improve their capability in speed and accuracy.
Each experiment reproducible, tomorrow or in five years, so that we can begin to lay the foundation
of knowledge about what an LLM can be trusted with and what it shouldn't.

This is a challenge, in particular grouping controlling factors in such a way that they
represent something meaningful *and* can be reliably applied across models and machines.
Due to the chaotic ecosystem that is LLMs in 2026, the path ChatDDX took is a patchwork of
careful compromises to cater to our context specifically: Producing accurate management plans
for emergency healthcare on local, open weight models.

## Proposed amendments

### A run keeps the versions it read

- **By:** Claude (Claude Code), 2026-09-28 00:00 UTC
- **Reason:** A run kept the stack and LLM versions it read, but not which
  configuration version it varied nor which variations were set in it: the
  portal parsed that back out of the cell's label and the conversation's
  description. `RunModel` keeps `configuration_branch` now, and a
  `<slice>_branch` for each slice set in place of the configuration's own,
  beside `stack_branch` and `llm_branch`; a toolset taken out is read from
  the trial's configuration having none where the branch's has one. Under
  **1. The classes of data**, History would say a run keeps, beside its
  trial's trails, the versions it read: the stack's, the LLM's, the
  configuration's and each variation's.
- **Related:**
  [history/models.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/history/models.py#L218-L280),
  [history/record.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/history/record.py#L41-L131),
  [bench/cell.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/bench/cell.py#L23-L69),
  [django/history/migrations/0001_initial.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/django/history/migrations/0001_initial.py)

### A job is a planned trial

- **By:** Claude (Claude Code), 2026-09-28 00:00 UTC
- **Reason:** The worker's jobs held names and a fingerprint, and read the
  records again by name when their turn came: a renamed case or variation
  drifted them, nothing a batch named could be deleted, and slots were
  pooled by the stack's name across owners, with `max_jobs` from whichever
  owner's job came first. A job pins the `TrialModel` it plans now, and the
  versions read (the configuration's, the stack's and each variation's);
  the worker runs that, whatever the names have come to mean, and skips a
  trial whose stack's head is another stack than was planned. A stack's
  slots are its timeline's, `(owner, name)`, with `max_jobs` from that
  timeline's head when the worker looks. Under **1. The classes of data**,
  History would count the worker's job as a trial planned but not yet run.
- **Related:**
  [worker/models.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/worker/models.py#L77-L162),
  [worker/queue.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/worker/queue.py#L31-L104),
  [worker/worker.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/worker/worker.py#L106-L131),
  [bench/bench.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/bench/bench.py#L313-L346),
  [django/worker/migrations/0001_initial.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/django/worker/migrations/0001_initial.py)

### Trails reach trails, and the store walks that

- **By:** Claude (Claude Code), 2026-09-28 00:00 UTC
- **Reason:** What held a record (runs, jobs, scores, configurations) was
  listed in three places, each naming the relations by hand.
  `repo.utils.reaches` walks a model's trail relations and related arrays
  down to a trail model, and `repo.queries.reaching` makes a filter of it;
  `Bench.runs_with` and `bench.held.held` go by that. After "Their
  integrity is assured by fingerprinted Trails (data) and associated
  Branches (metadata)", the doc would say that a trail's relations to other
  trails are what the store walks to find what reaches one.
- **Related:**
  [repo/utils.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/repo/utils.py#L187-L217),
  [repo/queries.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/repo/queries.py#L85-L97),
  [bench/held.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/bench/held.py),
  [bench/bench.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/bench/bench.py#L501-L517)

### The store lists a timeline's versions and names a trail

- **By:** Claude (Claude Code), 2026-09-28 00:00 UTC
- **Reason:** A timeline's versions, what saving under a name will do, the
  names alike, whether an identity may read a row, a trail's name for an
  identity and who else holds a fingerprint were each re-implemented in
  the portal, the API, the repl and the bench: five copies of the versions
  list, three of the name. They are the store's now, in
  `repo/store/timeline.py` (`select_versions`, `saving`, `alike`) and
  `repo/store/branch.py` (`readable`, `branch_named`, `name_of`,
  `holders_of`), and the apps ask it. After "So there's a head (canon), and
  it can be committed to, but it can't be changed", the doc would add that
  the store lists a timeline's versions and says what saving to it does.
- **Related:**
  [repo/store/timeline.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/repo/store/timeline.py#L10-L82),
  [repo/store/branch.py](https://github.com/chatddx-administration/chatddx/blob/ba24524f7e9b0dda5545e60497dd0d473a82d3e3/src/chatddx/repo/store/branch.py#L153-L210)
