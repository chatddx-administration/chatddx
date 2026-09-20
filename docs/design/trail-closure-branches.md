# A commit is not finished until its closure is committed

Why a branch was being invented while a change form rendered, what replaced
it, and how far the replacement's guarantee reaches.

## The hole

A branch points at a trail, and a trail points at more trails: an agent *is*
its connection, sampling params, output type and tool group; a tool group is
its tools; an expectation is its payload and its scorer. `dump_trail` writes
that whole graph, because a fingerprint covers what it points at.

`commit()` then made a branch for the trail it was handed and for nothing
else. So an owner could possess a connection -- their agent points at it --
and have no branch on it. Every part of the app that shows or edits a
relation needs a *branch*, not a trail, because only a branch has a name and
an owner (`docs/design/branch-identity-and-the-repo-registry.md`).

The patch was to make one while rendering the form, and say so:

> Recreated a branch for trail 'connection' with fingerprint 'a1b2c3' fyi 👇

A GET that writes, a name invented from a hash, and a message that reports a
repair rather than an intent. `SuperAgentForm` did it correctly and
`AgentForm` did not -- its handler still called the pre-refactor four-
positional-argument `commit()` and then read an unbound name, which nothing
caught because the happy path never entered the block.

## What it is now

Every branch is made by `commit()`, so the guarantee belongs there.

- `trail_closure(trail)` (`repo/utils.py`) walks the trails a trail reaches,
  the same two field kinds `resolve_trail` walks. It terminates because a
  fingerprint covers the fingerprints below it, so a cycle would have to
  contain its own hash.
- `commit_closure(target, owner)` (`repo/shufflers/branch.py`) commits each
  of those trails **for owners who have no branch on it at all**. Where the
  owner already has one, which version is canon and what it is called is
  theirs, and a save of something that merely points at it is not the place
  to revisit that.
- `resolve_branch_name` (`repo/names.py`) names what is made:
  `{entity} {fingerprint[:6]}`, e.g. `connection a1b2c3`. Deliberately
  plain, and the single place a better answer would be written --
  "connection of agent-1", a slug, a counter -- without revisiting callers.

`commit()` calls it on both paths, the new version and the one where the
fingerprint had not moved, so a commit that changes nothing still repairs a
closure that predates this.

The branches it makes carry nothing beside their content: no tags, no
collaborators, and for a case no expects. They are made on the owner's
behalf rather than saved by them. This is what makes a shared save work
without a special case: a collaborator saving a shared agent commits under
the *owner's* name, so the closure is committed for the owner -- while the
owner's tags and collaborators on those relations, which are not the
collaborator's to write, are silently left out.

`EntityName` was reordered so that what an entity references is committed
before it. The ordering already carried a rule of this shape -- a case's
expects are named by branch name, so expect comes before case -- and a
generated name is the same rule seen from the other side: commit an agent
before its connection and the connection is given a generated name before
the inventory gets to give it the real one, leaving the owner two names for
one trail. After the reorder the test inventory produces exactly two
generated branches, and both are earned: the sampling params agent-2 asks
for as a merge of two others, and the empty tool group it gets by default.
Neither is named anywhere, and both are now reachable by name.

The JIT creation is gone from both forms. `SuperAgentForm.get_initial` looks
its relation branches up; `AgentForm.get_initial` needed no lookup at all --
its relation fields choose trails, and `AgentFormDataOut` already serializes
each relation as its trail's pk. The dangling-branch path listed under
"Known, not fixed" in the previous note is therefore not fixed but deleted.

## How far the guarantee reaches

The invariant: *a trail an owner possesses, directly or through another
trail, has a branch of theirs on it.*

It holds inductively over commits. A branch row comes into being in exactly
one statement, the `objects.create` in `commit()`, and a trail row in
exactly one, the `get_or_create` in `dump_trail`, which outside tests is
only ever reached from `commit()`. So a trail cannot enter an owner's
possession except through a commit, and a commit ends by committing the
closure of its target; a closure commit is itself a `commit()`, so what it
makes is covered in turn. The walk
is transitive rather than one level deep, so an owner who already had a
branch on a tool group with branchless tools is repaired the next time
anything of theirs is committed -- the existence check stops a *commit*, not
the *walk*. `test_closure.py` checks this for every entity the test
inventory has, by listing an owner's branches, walking each closure and
asserting nothing is left branchless.

Two things fall outside it, both by construction rather than oversight:

- **Deletion.** `BranchModelAdmin.delete_queryset` deletes an owner's
  branches by name with nothing to say that another of their trails still
  reaches that one. Delete the connection branch an agent points at and the
  flat agent form raises `BranchNotFoundError` where it used to invent a
  replacement -- the plain one renders either way, since it no longer looks.
  The check belongs at the delete, not back in the render.
- **A trail reached from outside the repo.** An `ExperimentModel` holds
  trail FKs, by design -- it pairs a case trail with an expect trail to
  reproduce a run, and reproducibility is exactly where a trail pointer is
  the right one. Nothing there claims possession, so nothing there is owed a
  branch.
