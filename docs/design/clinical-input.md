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
- **Whether a target is settled is data,** not a `# guessed` comment, so
  `validate`, the exports and the portal can see it.
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

Each kind has its plain words, its pattern, and its review state, together:

```toml
[case.Dutchfall14w]
tags = ["dutch-fall"]
language = "en"
source = "Dutch Fall, case 14w; translated from Dutch"

targets.diagnosis.text = "Acute exacerbation of COPD"
targets.diagnosis.pattern = "copd | (exacerbation | obstructive) & pulmonary"
targets.diagnosis.review = "settled"
targets.diagnosis.reviewed_by = "AB"

targets.warning.text = "Hypercapnic respiratory failure"
targets.warning.pattern = "hypercapni* | respiratory & failure"
targets.warning.review = "guessed"

targets.disposition.text = "ward"
targets.disposition.review = "guessed"

targets.dont_miss.text = "Pulmonary embolism"
targets.dont_miss.pattern = "pulmonary & embolism | pe"
targets.dont_miss.review = "guessed"
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
- **`review` is `guessed` or `settled`.** Every target starts `guessed`,
  whoever wrote it; a clinician who agrees with it, or rewrites it, sets it
  to `settled` and puts their initials in `reviewed_by`. The `# guessed`
  comments become `review = "guessed"`.
- **`false` still says that none is expected,** where the kind allows it:
  `targets.warning = false`, with its own `review`.

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

- a target that is `guessed`, or missing for a kind a scorer reads;
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
- `deidentified`: who checked that it names no patient, and when;
- `review` and `reviewed_by`, as for targets: whether a clinician has read
  the vignette as it is sent, translation included.

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

## 6. Open

- Sign-off on §3's meanings, by whom, and how it is recorded.
- Whether reviews are per target, as proposed, or per case.
- Where `false` is allowed: today only for `warning`; `dont_miss` may want
  it.
