# Post-endgame matter

What was designed, discussed and set aside. Nothing here is planned: each
entry says what was proposed, how it went, and why it stopped, so that a
later round starts from the reasons rather than from scratch. The entries:
the batch as a record, and clinical sign-off.

## The batch as a record

**Set aside, September 2026.** `batch TAG...` is a repl command, and
nothing more: it runs the held cell on the cases with any of the tags, one
after another, each run recorded as `run` records it. No run points at a
batch, and nothing more is planned for it. The seed is the de facto batch
key until there is a reason to do otherwise.

### What was designed

A batch was to be an order kept in history, naming:

| Field | Held |
|---|---|
| `base` | a configuration and a stack: the variation every slice keeps unless it is varied |
| `varied` | groups of slices, each with its variations, such as `[{stack: [qwen3-8b-awq@pelle, gpt-oss-20b@malborg], reasoning: [off, low, high]}, {output: [management-plan, diagnoses, free-text]}]` |
| `case_tags` | the cases with any of the tags the owner can see, resolved when it runs; a vignette under two names run once |
| `scorers` | the registry's scorers, by their trails |
| `replicates` | its seeds, one per replicate; a replicate's position among them, from 1, its epoch in a cell's inspect log |

- **Cells.** The slices within a group crossed, and the groups varied one
  at a time with every other slice at the base: groups of one slice give a
  one-slice-at-a-time design, one group of every slice a full cross. A cell
  labelled by its varied slices (`stack=gpt-oss-20b@malborg
  reasoning=low`), for people only; to keep one was to commit its
  configuration under a name.
- **A report.** Every cell resolved against its stack before anything ran:
  realized, collapsed into another cell, or refused, with the facts it
  rested on; per cell and scorer, whether the output offers the view; per
  scorer and case, whether the case has the target. This was to be the
  compatibility table of PR #68, derived rather than authored, and kept
  with the batch. The derivation stays: `show` gives the same for the
  repl's cell.
- **A log per cell,** so a batch would have been an inspect eval set in all
  but name, with a reducer per batch for its replicates.
- **`batch --seeds 1,2,3`,** to run replicates in one go, and fractional
  designs later.
- **Languages compared by a batch** varying the language slice over cases
  paired by translation.
- **The old planner's rules carried over** (`history/batches.py`, removed
  in `6ade722`): cases by tag, scorers named or all, two names of one
  vignette run once, a `plan` before `generate` (now `show`), and the order
  kept so it could be generated again.

### Why it was set aside

- **A trial is content.** Its cell, case and seed say what ran, and its
  fingerprints make it reproducible, so a batch adds nothing to what ran:
  it is an initiator. Runs are to be started from anywhere, a chat, the
  repl or a script, and grouped by their parameters, never by what started
  them. `export.md` selects by parameters for that reason.
- **A second grouping costs more than it buys.** A recorded batch would
  give the order itself (who asked for which cells, cases and seeds, and
  when), a report kept with it, and an epoch that is a replicate's place in
  one batch rather than a seed's place in an export's selection. It would
  also be a grouping that a run started from a chat never has, to be kept
  consistent with the parameters beside it.
- **The seed already does most of it,** below.

### The seed as the batch's key

The repl holds a seed, drawn as it starts, and `run` and `batch` send it.
A batch's cases share one seed, and a fresh one is one word away (`seed`).
So every run of a batch carries its seed, and that is the trace it leaves.

What it can do:

- **Find a batch's runs:** the owner's runs of one cell with the seed, over
  the cases with the batch's tags, as long as nothing else ran that cell
  with that seed. A fresh seed per batch makes that the rule.
- **Line its cases up:** every case has the same seed, so the seed is its
  epoch in a log, and two batches under two seeds are two replicates.
- **Say what a later run repeats:** a `run CASE` under the batch's seed is
  another run of the batch's trial, which is how a seed is seen to hold.

What it can't do:

- **Tell a batch from what followed it.** A later `run`, or a second batch,
  under the same seed on the same cell makes more runs of the same trials;
  only times tell them apart.
- **Keep one person's sessions apart.** Two sessions can draw the same
  seed, about one chance in 100,000 per pair; the owner keeps two people's
  apart, not one person's two sessions.
- **Say what was asked for:** not the tags, the scorers, or whether the
  batch ran to its end or was stopped.
- **Mark an unseeded batch,** or a greedy one, which must run unseeded:
  those leave no trace but their cell and their times.
- **Span cells:** a batch runs one cell, and runs of another cell under the
  same seed are another batch's, or a comparison made on purpose.

### What would bring it back

A study whose cells, cases and replicates must be ordered, kept and
generated again as one unit, or runs whose seeds can't tell batches apart.
Then start from the table above, and from the question the deferral left
open: whether the selection of `export.md`, with its manifest, is enough
of a record.

## Clinical sign-off

**Abandoned, September 2026.** The inventory's data is taken as intended:
nothing is signed, marked settled or held back, and nothing reads the
`# guessed` comments. `show` says `missing` where a target is missing, and
running on incomplete data is fine (`clinical-input.md`).

### The question it started from

The inventory marks 198 of its 297 targets `# guessed` (every warning and
every disposition); the 99 diagnoses carry no mark, and their origin isn't
stated. A clinician editing the TOML files (a "hacker clinician") had no
way to tell what was done, and the planned `validate` command had to decide
whether to read those comments, or a flag, to say what was left.

### What was proposed, in order

1. **A status per target, in the case's details.** Each target kind carries
   `status = "guessed" | "settled"`, beside its `text` and `pattern`.
   Simple, but a status says nothing of who settled it, and a later edit
   leaves a stale `settled` unless something remembers to reset it.
2. **A signature relation on branch rows.** Settling became signing: a row
   ties a branch row to the identity that vouches for it (the session's
   owner in the repl or portal, `sign case NAME [PART]`, `unsign`), since a
   branch row has an owner and no author. A signature is not content and
   not a detail: it changes nothing a run or a score reads.
3. **The archive as signatory, and `draft` in the TOML.** `init-data`
   signs, as the archive, every part it commits except those a case's
   `draft = [...]` names (target kinds, `vignette`, `deidentified`). `draft`
   replaces the `# guessed` comments, lives only in the TOML, and is kept
   nowhere: the database records who signed, not what was held back. An
   archive signature meant "came in through the curated inventory", with
   git saying who wrote it.
4. **Signatures keyed by fingerprint, not by row.** Keyed by a fingerprint
   of the part (the case's trail, the part's name, its value), a signature
   outlives `wipe-data` and `init-data` for the same content, and an edit
   starts unsigned with no flag to reset. It left problems open:
   - the archive's signatures are a projection of the inventory, not
     events: `init-data` would have to sign what leaves `draft` and take
     back what enters it, even when nothing else changed;
   - a value edited away and back finds its old signature, given before
     the other value existed;
   - signatures outlive their content, and `wipe-data USER` would have to
     say whether they go;
   - copies with the same content share signatures, so a signature vouches
     for rows its signer never saw;
   - a part's fingerprint needs a canonical form of details, which today
     have none, and a change of that form unsigns everything;
   - the database can't tell "held back" from "forgot" from "no clinician
     yet".
5. **Granularity in two steps.** First a signature covers the whole row
   (the archive signs a case only with an empty `draft`, so today none),
   then one part at a time. Where the second step ends was proposed and
   left open: one signature settles a part; a row may carry several, and a
   second reviewer is possible but not required; `diagnosis` asks for two
   clinicians before a study reports; no reasons, adjudication records or
   electronic-signature guarantees.
6. **`validate` as the clinician's to-do list.** A repl command, called
   first by `run` and `batch`, listing what no one or only the archive had
   signed, what `draft` held back, targets missing for a scorer, patterns
   that don't parse or don't match their own `text`, Swedish cases whose
   pattern names no Swedish word, and cases without a `source`.

### Dismissed along the way

- **De-identification as a signed part** (`deidentified`). If a vignette
  that names a patient enters chatddx, it's already too late: checking for
  it inside chatddx gives a false sense of safety. It is kept out before
  anything is committed, and chatddx doesn't check it.
- **A command-line tool for clinicians** to complete and verify clinical
  data. Discussed earlier and dropped: editing the TOML files already is
  that tool, and a second one would be another way in to maintain.
- **Reading `# guessed` comments, or a flag, in `validate`.** Superseded
  by the verdict: nothing is read, the data is what is meant.
- **The verb `validate`.** It suggested that chatddx judges whether the
  data is right, which it can't. What was planned for it, and the dry run
  of a batch, goes to `show` (`clinical-input.md` §4).

### Why it was abandoned

- **Friction and complexity in a system that must be exact.** Every step
  above added a thing to keep consistent (a relation, a fingerprint form, a
  projection to reconcile on each `init-data`), and each, if wrong, would
  mislead more than it helped. Signing that can drift is worse than none.
- **If the data is there, it will be experimented on.** No flag stops a
  researcher from running a batch, and none should. A result on bad data is
  a result on bad data; the export says which targets it was held to, and
  that is the record.
- **Missing is a clear enough signal.** Where a target is missing, `show`
  and a batch's line say so, and the scorers of that kind leave the case
  out. Nothing else about the data's quality can be known from inside
  chatddx.
- **Editing the TOML files is the verification.** Git says who changed
  what, and when; a signature in the database would say the same thing
  less well.

### What would bring it back

A study that has to report who reviewed each target, with a regulator or a
journal asking for it. Then start at step 4's open problems; step 1 is not
enough, and steps 2 and 3 are where it gets expensive.
