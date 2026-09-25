# What clinicians provide, and where

chatddx needs medical judgement in a few places, and nowhere else. This note
names them, says what is expected in each, and settles how a clinician who
edits the inventory's TOML files (a "hacker clinician") can tell what is
done and what isn't. The portal will offer the same fields later, and is
left out here.

Decided, as of this note:

- **A target says in plain words what is expected,** and its pattern is the
  machine's way of finding it. The words are the clinician's; the pattern
  follows them.
- **Settling is signing:** a signature ties a branch row to the identity
  that vouches for it, always the session's owner in the repl or the
  portal, and the archive for what the inventory commits (§6). It is data,
  not a `# guessed` comment, so `validate`, the exports and the portal see
  it.
- **Four kinds of target:** `diagnosis`, `warning`, `disposition`, and a new
  `dont_miss`. What `warning` and `disposition` mean is proposed below, and
  waits on clinical sign-off.
- **Beside the targets, four places are the clinicians',** in this order of
  priority: the judge's rules, the vignettes' provenance, the output's
  guidance and schema texts, and what each scorer measures.

## 1. The places, at a glance

| What | File | Read by | Status today |
|---|---|---|---|
| a case's targets | `data/cases.toml` | the scorers, the judge, every export | 198 of 297 guessed (every warning and disposition); the 99 diagnoses unmarked, of unstated origin |
| the vignette | `data/cases/<name>.txt` | the LLM, as the case | no source, translation or reviewer recorded |
| the judge's rules | `logs/judge.py`, in code | the judge, in inspect | written by a non-clinician |
| guidance, schema texts | `inventory/slices.toml`, `inventory/schemas/*.json` | the LLM, as its instructions | written by a non-clinician |
| what a scorer measures | `inventory/scorers.toml` | the scorers | not described for clinicians |

The rest of the inventory (machines, LLMs, sampling, reasoning, coercion,
tools) is technical, and needs no clinician.

## 2. How a change reaches a score

Nothing reads a TOML file while it runs. The files are an inventory that
`chatddx init-data` commits to the database, and everything reads the
database:

1. **Edit** `cases.toml`, or a vignette.
2. **Commit:** `chatddx init-data USER`. A changed target makes a new
   version of the case; a changed vignette makes a new case (its content is
   what the LLM reads, so its runs are a new trial's).
3. **Check:** `validate` (below) lists what is still missing or unsettled.
4. **Score again:** every earlier run of the case is outstanding for its
   scorers once its target changes, and `score` holds them to it. Nothing
   is generated again.
5. **Export again:** an inspect log keeps the targets it was written with
   (`export.md` §1), so a log written before the change is out of date.
   inspect itself reads nothing from these files: a sample's `target` is
   the case's diagnosis, and its `metadata.targets` every kind, both as the
   database held them at export.

## 3. Targets

### The shape of a target

Each kind has its plain words and its pattern, together; what the
archive doesn't vouch for is named once per case, in `draft`:

```toml
[case.Dutchfall14w]
tags = ["dutch-fall"]
language = "en"
source = "Dutch Fall, case 14w; translated from Dutch"
draft = ["warning", "disposition", "dont_miss"]

targets.diagnosis.text = "Acute exacerbation of COPD"
targets.diagnosis.pattern = "copd | (exacerbation | obstructive) & pulmonary"

targets.warning.text = "Hypercapnic respiratory failure"
targets.warning.pattern = "hypercapni* | respiratory & failure"

targets.disposition.text = "ward"

targets.dont_miss.text = "Pulmonary embolism"
targets.dont_miss.pattern = "pulmonary & embolism | pe"
```

- **`text` is what the clinician means,** in the case's language or in
  English. It is what the judge reads, and what the exports show beside a
  score.
- **`pattern` finds the text in an answer:** whole words, `*` ending a
  stem, `&` both, `|` either, parentheses to group (`scoring/scorers/
  patterns.py`). An alternative is only another way of naming what `text`
  names: a synonym, an abbreviation, a spelling, the Swedish word. A
  different diagnosis is not an alternative. A case that truly accepts two
  says so in its `text` ("Spontaneous coronary artery dissection, or aortic
  dissection"), and only then does its pattern offer both.
- **A Swedish case's pattern names its words in both languages** (§12 of
  `new-datamodel.md`: what chatddx sends is still English, and the LLM may
  answer in either).
- **`draft` names what isn't settled:** target kinds, `vignette` or
  `deidentified`. The archive signs everything else it commits (§6). The
  `# guessed` comments become `draft`: every case's warning and
  disposition today. A clinician settles a part by taking it out of
  `draft` in the inventory, or by signing it as themselves in the repl.
- **`false` still says that none is expected,** where the kind allows it:
  `targets.warning = false`.

### The kinds

| Kind | Proposed meaning (awaits clinical sign-off) | Scored by |
|---|---|---|
| `diagnosis` | the working diagnosis the case is known to have | `reciprocal_rank` (its rank in the differential), `first_mention` (how soon the text names it), the judge |
| `warning` | the dangerous condition the clinician must act on or rule out now; `false` where there is none. The schema's `acute_warning` would ask for the same: conditions, not signs | `warning_mentions` |
| `disposition` | where the patient goes, one of `home`, `observation`, `ward`, `high_dependency` (HDU or ICU), `intervention` (theatre, cath lab); an ordered scale | `disposition_mentions`, then a scorer that reads the scale (open) |
| `dont_miss` | a condition that must appear in the differential however unlikely, as the schema's `critical` flag asks of the LLM | a new scorer: is it in the differential, and is it marked critical (open) |

- **Why say so:** today the warning's patterns list conditions while the
  schema asks for signs, and each is a long list of alternatives any one of
  which counts; disposition is free words with no levels; and the
  schema's `critical` flag is asked for and never scored.
- **Open, for clinicians:** whether a warning names one condition or may
  name several; how near a disposition must be (exact, or one step on the
  scale); how many `dont_miss` conditions a case may have; and whether a
  case with no `dont_miss` says `false`.

## 4. `validate`

The repl's `validate [CASE]` checks what can be checked before anything is
sent, and `run` and `batch` call it first (`new-datamodel.md` §5). For a
clinician it is the to-do list:

- what no one has signed, or only the archive, and what the inventory
  marks `draft`; a target missing for a kind a scorer reads;
- a pattern that doesn't parse, or that doesn't find its own `text` (a
  pattern should always match what its clinician wrote);
- a Swedish case whose pattern names no Swedish word;
- a case without a `source`;
- for the cell in the repl: a case without a target for a scorer the
  cell's output offers, and a slice the stack refuses.

Without an argument it covers every case the identity sees, grouped by what
is missing, so a clinician can work down it.

## 5. The other places, in order

### 5.1 The judge's rules

The judge decides whether a differential names the diagnosis: a synonym, an
abbreviation, another spelling, a more specific form, or the other language
counts; a related diagnosis, a complication or a symptom doesn't. That is a
clinical policy, and it is written in code (`logs/judge.py`).

- **The rules move to data** a clinician edits, `inventory/judge.toml`:
  what counts, what doesn't, with an example of each, in plain words. The
  judge's prompt is built from them, and a log records which version
  judged.
- **The judge reads the target's `text`,** not its pattern, once targets
  have one.
- **Open:** who adjudicates where the judge and the pattern disagree
  (`chatddx agreement` lists those samples), and what agreement is good
  enough.

### 5.2 The vignettes' provenance

A vignette is a text file, and stays one. What the file can't say goes in
its case's record:

- `source`: the dataset and the case's number in it, and where it was
  translated, from what;
- whether a clinician has read the vignette as it is sent, translation
  included, and that it names no patient, are signatures (§6), of the parts
  `vignette` and `deidentified`.

A changed vignette is a new case, so a correction is made in a new file, or
an edited one committed again, and the runs of the old text stay the old
case's.

### 5.3 Guidance and schema texts

What the LLM is asked for is clinical wording: an output's `guidance` in
`inventory/slices.toml` ("Fill in the management plan for the case."), and
each field's `description` in `inventory/schemas/*.json` ("Diagnosis name
(ONE word if possible)", "Include critical rules even if low probability",
"Return null if none").

- **They are content:** changing one makes a new variation of the output,
  and so new cells, never an edit of the old runs. A clinician proposes a
  new variation beside the old one, and a batch compares them.
- **They must agree with the targets:** a field named `acute_warning` that
  asks for signs can't be held to a target that names conditions (§3).

### 5.4 What each scorer measures

`inventory/scorers.toml` names each scorer's function, the view it reads and
the kind of target it holds that to. A clinician needs to know what a value
means, not how it is computed: each scorer gets a `description` in plain
words ("the rank at which the differential first names the diagnosis, as
1/rank"), and a clinician says whether it answers a clinical question.
`first_mention`, which counts characters, may not.

## 6. Signing

### Where it lives

A signature is not content, and not a detail either: it changes nothing a
run or a score reads, and it says who vouches, which a branch row can't (a
row has an owner, and no author). It is kept beside the registry, keyed by
what was signed rather than by the row that holds it: the identity that
signed, the part, when, the chatddx revision, and a fingerprint of what the
part holds.

- **What a part's fingerprint covers:** the case's trail fingerprint, the
  part's name, and its value. For `vignette`, that is the trail; for a
  target kind, its `text` and `pattern` too, which are details and in no
  trail's fingerprint; for the whole row in step 1, the trail and every
  detail a signature covers. A target signed on one case is not signed on
  another that happens to share its words.
- **The signer is the session's owner,** in the repl (`sign case NAME
  [PART]`, `unsign`) or the portal. A signature changes nothing in a row,
  so anyone who can see a case can sign it, the archive's included.
- **An edit starts unsigned.** A changed target or vignette has a new
  fingerprint, and no signature. Nothing has to remember to reset a flag.
- **Signatures outlive their rows.** `wipe-data` and `init-data` remove
  and remake branch rows, and a signature keyed by fingerprint holds for
  the same content when it comes back: a dev cycle doesn't lose its
  sign-offs.
- **A score says what it was held to.** A score keeps the case row it read;
  the row's parts' fingerprints then say whether it was signed when the
  score was made, and whether it is now.
- **It is generic:** an output's guidance and schema, a scorer's
  description, the judge's rules can be signed the same way.

### The archive signs the inventory

`init-data` signs, as the archive, every part it commits but those the
case's `draft` names. `draft` is the inventory's alone: it is read by
`init-data` and kept nowhere, since what the database needs to know is who
signed, not what the archive held back. An archive signature says "this
came in through the curated inventory"; who wrote it is in git, and the
signature keeps the revision it was committed from, so the one leads to
the other. The archive never signs in a session, and a clinician's
signature is never the archive's.

### What signing by fingerprint leaves open

- **The archive's signatures are a projection of the inventory,** not
  events. `init-data` has to sign what is newly out of `draft` even where
  nothing else changed, and a commit that changes nothing does nothing
  today; and it has to take back the archive's signature of a part put
  back in `draft`, which a signature that outlives its row would otherwise
  keep.
- **A value that comes back is signed again.** A target edited from A to B
  and back to A finds A's signature, given before B existed. The
  fingerprint says the content is the same; whether the signer's judgement
  still holds is another matter. The signature's time says when.
- **Signatures without rows.** A signature whose content no row holds any
  longer lingers: harmless, but `validate` should count them, and
  `wipe-data USER` must say whether a user's signatures go with their
  runs, or stay, as a wipe for a test cycle would want.
- **Copies share signatures.** A case the archive signed is signed in
  alex's copy of it too, where the content is the same: right for the
  content, but the signature then vouches for a row its signer never saw.
- **The part's fingerprint is a new one.** Trails are fingerprinted, and
  details aren't; a part's fingerprint needs a canonical form of its
  details (`data-generation.md` §3.2), defined per part, and changed with
  care, since a change of form unsigns everything.
- **What `draft` doesn't say is lost.** The database knows a part is
  unsigned, not whether the inventory meant to hold it back, forgot to, or
  never had a clinician; `validate` reads the inventory to tell.

### Granularity, in two steps

1. **The whole row.** A signature covers everything in the row. The archive
   signs a case only where its `draft` is empty; a clinician signs the
   whole case. Today no case is archive-signed, since every one has guessed
   targets: that is the truth.
2. **The parts.** A signature names one part: a target kind, `vignette`
   (read as sent, translation included), or `deidentified`. The archive
   signs every part but those in `draft`.

**Where step 2 ends is open.** A proposal, weighing complexity against
clinical rigour, for a tool that is primarily for research:

- one signature per part is enough for a part to count as settled;
- a row may carry more than one signature, and `validate` and the exports
  count them, so a second, independent reviewer is possible without being
  required;
- `diagnosis` asks for two clinicians before a study's results are
  reported, the other kinds for one; the judge's disagreements with the
  pattern (`chatddx agreement`) go to a clinician first;
- no reasons, no adjudication records, no electronic-signature
  guarantees: clinical-grade rigour (independent double review with
  adjudication, a full audit trail) is probably not practically achievable
  here, and the note doesn't pretend otherwise.

## 7. Where each field goes

| Field | Home | Why |
|---|---|---|
| `targets.<kind>.pattern` | case branch details (today's `targets`) | the pattern scorers read it; a change is a new version, and makes runs outstanding |
| `targets.<kind>.text` | case branch details, beside the pattern | the judge and the exports read it; a change should make the judge's scores outstanding |
| `draft` | the inventory's TOML only | what the archive doesn't sign; read by `init-data` and `validate`, kept nowhere |
| signatures | a table beside the registry, keyed by the fingerprint of the part signed: identity, part, time, revision | who vouches, which no row records; outlives `wipe-data` and `init-data` for the same content |
| `dont_miss` | a target kind (code vocabulary), a view of the output (the differential's items marked critical), and a scorer | as the other kinds |
| the disposition scale | the arguments of the scorer that reads it (trail content) | it changes scores, so each score cites it |
| the judge's rules | the judge registered as a scorer, its rules in its arguments | a changed rule is a new scorer trail; inspect gets them as options |
| a scorer's `description` | scorer branch details | it changes no score; it is data, not a model's `help_text` |
| `source` | case branch details | it describes the content without changing what the LLM reads; copies carry it |
| guidance and schema texts | output trail content, as today; signed as rows | already fingerprinted |

## 8. Open

- Sign-off on §3's meanings, by whom.
- Where step 2 of signing ends (§6).
- Where `false` is allowed: today only for `warning`; `dont_miss` may want
  it.
