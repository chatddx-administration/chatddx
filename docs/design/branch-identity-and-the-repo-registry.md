# Branch identity and the repo registry

Why the Case change form showed other cases' expectations, why `expects` was
accepted on entities that never read it, and why `bundle_of` needed
`SUPER_AGENT` to come last. They are one defect, and this is what was done
about it.

## One root cause

Three arrows, one direction:

```
branch row  --target-->  trail row  --FK-->  nested trail rows
(owner, name, timestamp)  (fingerprint, payload)
```

Trails are deduplicated on purpose -- `dump_trail` does
`get_or_create(fingerprint=...)` -- and made immutable in the database by the
triggers in `repo/sql/`. That part is sound.

The defect is that identity was then read back *out of* the deduplicated
layer. Four places walk the arrow backwards, and each is guessing:

| Site | Backward walk | Consequence |
|---|---|---|
| `pages/expect.py` `get_form_queryset` | trail -> every branch on it | the Case inline fans out |
| `qs.py` `qs_experiments` | trail -> `order_by("-timestamp")[:1]` | arbitrary branch name on an experiment |
| `qs.py` `qs_owned_trails` | trail -> `annotate(branch_name=...)` | arbitrary label in the Experiment dropdown |
| `forms/agent.py`, `forms/super_agent.py` | trail fingerprint -> owner's branch, else commit one | invents a branch named after a hash |

A dedup key answers *what is this*. It cannot answer *which one is this* --
that question has N answers.

The rule that falls out:

> A **trail** pointer is for machine-facing references: reproducing a run.
> A **branch** pointer is for human-facing references: anything that renders
> a name or offers an edit.

The Case inline is a human-facing reference built on a machine-facing
pointer. The Experiment form is not affected because it never needs a name
-- `ExperimentModel` holds trail FKs, the choice fields are populated from
trails, and `expects_by_case` reads the through table as trail-id to
trail-id without joining a branch table at all.

## What git actually teaches

The vocabulary is borrowed, so it is worth checking the borrowing.

| git | here | gap |
|---|---|---|
| blob / tree | `TrailModel` | merged into one layer; fine |
| commit | a `BranchModel` **row** | no `parent`; ordered by wall clock |
| ref | "canon", the newest row for `(owner, name)` | derived by query, not stored |

1. **Git never resolves an object back to what references it.**
   `git log --find-object` exists, is documented as an expensive full-history
   scan, and returns a *set*. Forward pointers only; store the reference at
   the granularity you need to read it back.

2. **A submodule pins a commit, not a tree.** This is the precedent for
   pointing `CaseBranchModel.expects` at `ExpectBranchModel`. It pins content
   transitively *and* keeps identity. The reproducibility objection is
   answerable: a branch row's `target` is never written after insert, so a
   branch pointer is exactly as reproducible as a trail pointer -- it is just
   not yet *enforced* to be.

3. **A commit is not identified by its tree.** Two commits with identical
   trees are different commits; git ships `--allow-empty` for the case.
   `commit()` here refuses a new row when the fingerprint matches and then
   mutates the existing row's relations in place -- a system recording a
   change whose content hash did not move, with nowhere to put it.

4. **Refs are cheap, stored, and separate from objects.** Canon is
   recomputed on every admin page by a `DISTINCT ON` plus a `Count`
   subquery.

5. **Porcelain is not plumbing.** `super_agent` is a form registered in the
   object registry. That is the whole of the third smell.

## Standards worth borrowing

- **Content-addressable storage** (Nix, Bazel, OCI, IPFS): the deduplicated
  object is never the identity you reference. An OCI manifest names layer
  digests; nobody dereferences a layer digest back to "which images use
  this."
- **SCD Type 2** (Kimball): this schema is textbook -- natural key
  `(owner, name)`, surrogate `id`, `timestamp`. The standard remedy for
  "latest by timestamp" is a stored current-row marker or a validity range.
- **SQL:2011 system-versioned tables**: Postgres has the pieces --
  `tstzrange` with `EXCLUDE USING gist` turns an invariant held by
  convention into one held by the database.
- **Datomic / XTDB**: immutable facts plus "as of" queries, the shape being
  reached for.

## Was a RDBMS for configuration misconceived?

No, and it is worth being precise about what was, because the real mistake
is portable.

Postgres has everything this needs: content hashes, immutability triggers
(already in use), range types, exclusion constraints, recursive CTEs.
Nothing here is fighting the RDBMS.

The misconception is one layer up: **content-addressing was applied at the
right layer and then read at the wrong one.** Dedup by fingerprint is a
storage optimisation; making the trail the thing you *reference* turned
every "which one is this" into a guess. Git avoids this not by avoiding
content-addressing but by never letting a blob be an identity.

The sharing model compounds it.
`test_expects_belong_to_the_owner_not_to_the_payload` asserts that two
owners' cases are literally the same trail row. That is dedup working. It
leaks as a bug only because the reverse arrow gets walked. Fix the arrows
and the feature stays.

## What was changed

### Entity and View are different records

`Bundle` conflated two questions. `AGENT` and `SUPER_AGENT` shared seven of
ten member classes, so the class-to-bundle relation was not a function, and
`ALL_BUNDLES` order made it one by fiat via `setdefault`.

- `Entity` is what an entity *is*: the table pair and the schemas that read
  and write it. One entity, one pair of tables.
- `View` is how an entity is *presented*: a proxy and its form data. An
  agent has two -- the flat `super_agent` form and the plain one.

`bundle_of` split into `entity_of` and `view_of`. Both indexes are built
with a collision check instead of a precedence rule; with views out of the
entity list there is nothing left for declaration order to decide. The MRO
walk stays, but raises a `KeyError` naming the class rather than letting
`next()` leak a `StopIteration`.

`"super_agent"` left `EntityName`. It was reachable through `bundle_of` from
one test only; `SuperAgentFormDataIn` was dead, because `SuperAgentForm`
validates as an agent. The `super_agent` key of the five `Inventory*` models
duplicated every agent under a second name.

Three consequences the ordering rule never covered:

- `entity_of` now answers `agent` for all four agent proxies. Before,
  `SuperAgent` answered `super_agent` (a registered member) while
  `SharedSuperAgent` answered `agent` (fell through the MRO). That name
  reaches `ensure_tag`, so the two siloed tags under different entity
  strings.
- `owned_inventory` no longer selects `AgentBranchModel` twice, and
  `wipe_data` no longer deletes it twice.
- The admin's `template_data` blob dropped from 10 keys to 9 and from 1137
  queries to 1104 per change-form render, measured against the giftbag
  dataset. The duplicate block was byte-identical to `agent` and no selector
  ever read it.

### An entity carries only what it declares

`expects` lived on the shared `BranchSchemaDetails` and was read in exactly
one place, behind `isinstance(branch_model, CaseBranchModel)`. Setting it on
an agent was accepted and dropped without a word.

Now each entity names its own details model, `branch_details` /
`branch_details_patch` on `Entity`, and only `CASE` declares `expects`. The
base models are `extra="forbid"`, so naming something an entity does not
carry is an error.

Relations are declared, not hard-coded: a details field tags itself with
`json_schema_extra={RELATION: ...}` -- the same idiom
`TrailSchema.as_fingerprint` already uses for `exclude_from_fingerprint` --
and `commit_relations` iterates those tags against `RELATION_RESOLVERS`.
The `isinstance` special case and the concrete-entity import inside the
generic shuffler are both gone.

`commit()` widens whatever details it is handed to the entity's own, so the
four callers that pass a bare `BranchSchemaDetails` for a case still get
inherit-from-superseded behaviour.

`find_field` in the inventory parser used to reverse-search
`InventoryTrailSchema`'s field types -- a second class-to-name lookup with
the same agent/super_agent collision, resolved by dict insertion order. It
asks the registry now.

### Also

`qs_canon` and `qs_canon_col` order by `("owner_id", "name", "-timestamp")`
and `DISTINCT ON` the first two. With no tiebreak, two rows sharing a
microsecond picked nondeterministically. `"-id"` added. Latent, not
observed.

`registry-redacted.py` deleted -- a stale context artifact whose
`SUPER_AGENT` was even named `"agent"`.

## Known, not fixed

**`AgentForm.get_initial`'s dangling-branch path is broken**, and predates
this work. When an agent's relation trail has no branch for the owner,
`BranchNotFoundError` is caught and the handler calls `commit()` with the
pre-refactor four-positional-argument signature, then reads `branch_model`,
which is unbound on that path. The happy path is unaffected because
`relations_dict` is only populated inside the `except`, which is why nothing
caught it. `SuperAgentForm` implements the same fallback correctly;
`test_super_agent_change_recreates_dangling_connection_branch` covers that
one and there is no equivalent for `AgentForm`.

Repairing it is not just a signature fix: `AgentForm`'s relation fields are
trail choosers (`qs_owned_trails`), so the initial value wants a trail pk,
while the handler builds form data via `load_form_data` and then reads a
`"pk"` key that `AgentFormDataOut` does not have. What that form's initial
relation values should be is a design question of its own.

## Next

Recorded so it need not be re-derived:

- `parent` FK on branch rows; order history by ancestry, not wall clock.
- A ref table `(owner, entity, name) -> head`, retiring the `DISTINCT ON`.
- Fingerprint the commit, not only the tree, so a change to
  `tags`/`collaborators`/`expects` has an identity instead of mutating a row.
- The three remaining backward walks: store the branch pointer where a name
  is needed.
- Hardening for the `expects` link once it names branches: `PROTECT` rather
  than `CASCADE`, `unique(case, expect)`, and extending the `repo/sql`
  trigger pattern to reject `UPDATE` of `target_id` / `name` / `owner_id` on
  branch tables -- which is what makes a branch pointer *provably* as
  reproducible as a trail pointer.
