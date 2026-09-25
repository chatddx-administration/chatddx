# Export and analysis: from a run to inspect, xlsx and R

This note charts how chatddx's runs leave chatddx: as inspect logs, as
spreadsheets, and as data for R. It supersedes the repl's `export` command
(`new-datamodel.md` §4), and settles how much analysis chatddx does itself.

Decided, as of this note:

- **One selection, one set of rows, many writers.** An export is a
  selection of trials by their parameters, read from the database once, and
  written as an inspect log, an xlsx workbook, or files for R.
- **A stateless command,** `chatddx export`, not a repl command. The repl's
  `export` goes.
- **Descriptive analysis in-house, inference in R.** chatddx summarizes;
  paired comparisons and models are R's.
- **The xlsx is a data handoff and a summary report,** not a review sheet.

## 1. Where things stand

```
Run, Score (database)
  └─ repl `export` (the cell held in the repl, and the identity)
       └─ cell_log(): one EvalLog per identity × cell
            ├─ a sample per draw; a seeded trial is one draw, its latest
            │  completed run, and the trial's other runs are left out
            ├─ metadata: the cell's variations, views, fingerprints, and
            │  the case's targets as they were at export
            └─ scored(): inspect re-scores with the registry's scorers
                 └─ .eval file ── inspect view / inspect score (judge) / samples_df
```

What that leaves out:

- **Scores made in inspect stay in the log.** The judge's scores exist only
  in `.eval` files, never as `Score` rows, so nothing but inspect sees them.
- **The selection is the repl's cell.** A log is "my runs of this cell";
  nothing selects by case tags or seeds, or across cells.
- **Targets are a snapshot.** A log holds the targets it was exported with.
  A target fixed afterwards reaches the database's scores, not the log's,
  until the log is exported again.
- **Tables need inspect.** `samples_df` reads logs, so a spreadsheet would
  wait on a log, and take inspect's shape.

## 2. The flow

```
selection ──> draws ──┬─> .eval       (inspect: viewer, re-scoring, judge)
(parameters)  (rows)  ├─> .xlsx       (people: data and summaries)
                      └─> .parquet    (R: arrow; .csv beside it)
                            ▲
inspect's scores ─────── imported as Score rows
```

### Selection: by parameters, not by what started the runs

A selection names what the trials are, never what initiated them: a batch,
the repl or a chat makes no difference (see `new-datamodel.md` §5, on the
batch as an initiator).

| Parameter | Selects |
|---|---|
| `--owner` | whose runs, and whose names and targets the export reads (their own, or else the archive's) |
| `--configuration`, `--stack` | cells, repeatable: each pair a cell; either alone, every cell that has it |
| `--tags`, `--case` | cases: any of the tags, or named cases |
| `--seeds` | trials with these seeds; `none` for unseeded ones |
| `--status` | completed, errored, or both (the default) |
| `--since`, `--until` | when the runs started |

- **A selection is resolved against the database as it is,** and the export
  records the selection it was made from, so that it can be made again.
- **Which run stands for a trial** is the writer's to say: the log keeps
  one per draw, as today; the tables keep every run, with a column saying
  which one the log would keep.

### Draws: the rows every writer shares

A draw is one run of a trial, with everything a row needs, read once:

- the factors: the cell's variation of each slice, by name and fingerprint,
  the stack and its parts, the case, its tags and language, and the seed;
- the run: its ids, status, validity, finish reason, error, start and end,
  tokens in and out, requests, and the client it ran on;
- the answer, and what each view reads from it;
- the case's targets, as the owner is held to them, and `missing` for a
  kind the case has none of (`clinical-input.md` §3);
- the scores: per scorer, the value, what it rests on, or why there is
  none, and what made it (scorer trail, blob, target, case row).

The inspect log is built from draws, and nothing else reads the database.

### Writers

- **`.eval`:** `cell_log` as it is, fed draws: one log per cell, a sample per
  draw, scored by inspect with the registry's scorers. It stays the way to
  inspect's viewer, to re-scoring without generating, and to the judge.
- **`.xlsx`:** a workbook for people who work in spreadsheets (§4).
- **`.parquet`, and `.csv` beside it:** for R (§5).

### inspect's scores come back

- **A score made in inspect is imported as a `Score` row,** by whoever
  imports it, from the log's sample and the scorer's options: the judge's
  value, its explanation, and the grader model. The scorer is registered
  like the others, with the judge's file as its function, so a score still
  names the code that made it.
- **Then every writer sees every score,** and `chatddx agreement` could
  read the database as well as logs.
- **Open:** a grader model's own run: whether the judge's requests are kept
  as runs, as `research-data-model.md`'s `judge_trial` would have it, so
  that a judge's cost and exchange are on record.

## 3. The command

```
chatddx export --owner alex --configuration plan --stack qwen3-8b-awq@pelle \
    --tags edn --seeds 1,2,3 --to eval,xlsx,parquet DIRECTORY
```

- **Stateless:** everything it needs is on the line, so it can be scripted
  and repeated, and a repl isn't needed to hold a cell.
- **It writes a manifest** beside what it writes: the selection, the
  command line, when, the chatddx revision, and each file's rows.
- **The repl's `export` goes.** The repl stays the place to run and look;
  `runs`, `replay`, `score` and the batch summary cover looking.
- **inspect is loaded only for `eval`,** as `agreement` loads it.
- **Needs:** openpyxl for xlsx, and pyarrow for parquet, which the
  `analysis` dependency group brings with pandas; they move to the
  dependencies of the export (a group of its own, or the main ones).

## 4. The workbook

For a data handoff and a summary report; nothing is read back from it.

| Sheet | Holds |
|---|---|
| `summary` | per cell and scorer: runs, mean, the confidence interval clustered by case, the runs without a value, and the rates of invalid, truncated and errored runs |
| `runs` | a row per draw: factors, run, views (joined into text), scores as a column per scorer |
| `scores` | a row per score, long: for filtering and pivots |
| `cases` | a row per case: tags, language, targets (`missing` where none), its `source`, and the vignette's file |
| `cells` | a row per cell: its variation of each slice, and the stack |
| `selection` | the manifest |
| `codebook` | each column of every sheet: what it holds, its type, its values |

- Long text (answers, vignettes) is cut at Excel's cell limit, and says so;
  the parquet files keep it whole.

## 5. R

- **Parquet, read with `arrow::read_parquet`:** types survive, and factors'
  levels travel as dictionary columns. The same tables as the workbook's
  `runs`, `scores`, `cases` and `cells`, one file each.
- **CSV beside it,** for whoever has no arrow; the codebook says each
  column's type.
- **Not `.rds`:** it would need a package of its own (pyreadr), and parquet
  does the same job for R and for everything else.
- **A starter script,** `analysis.R`, written with the files: it reads them,
  sets factor levels and reference cells from the codebook, and shows the
  paired comparison of two cells over their shared cases. It is a start,
  not the analysis.

## 6. What chatddx analyses itself

- **Descriptive, per cell and scorer:** runs, mean, and a confidence
  interval clustered by case, since a case's replicates aren't independent;
  the rates of invalid, truncated and errored runs; tokens and time. The
  `score` command and a batch's summary show the same, and the workbook's
  `summary` sheet holds it.
- **Not inference:** paired differences between cells, mixed models with
  the case as a random effect, factor effects and the like are done in R
  from the parquet files. `research-data-model.md` listed them as derived
  views; they move out of chatddx.
- **Why here:** numpy is already a dependency (through inspect), and a mean
  with its interval is what someone looking at a run needs; a model needs a
  statistician's choices, which R and its people are better at.
- **Open:** the interval: a cluster bootstrap, or a cluster-robust standard
  error (inspect's `stderr` takes a cluster); and whether `stderr` in the
  registry's metrics becomes that.

## 7. What changes elsewhere

- `new-datamodel.md` §4: `export` in the repl is replaced by this command;
  the log's layout stays.
- `new-datamodel.md` §11, "Later, from inspect": scores come back first.
- `research-data-model.md`'s derived views: descriptive ones stay in
  chatddx, inferential ones go to R.
