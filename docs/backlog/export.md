# Export and analysis: from a run to inspect, xlsx and R

Not built. This note charts how chatddx's runs are to leave chatddx: as
inspect logs, as spreadsheets, and as data for R, and settles how much
analysis chatddx does itself. The repl's `export` command has been removed
in favour of it; the code that writes an inspect log
(`chatddx.logs.export`) stays, with no command in front of it.

Decided, as of this note:

- **One selection, one set of rows, many writers.** An export is a
  selection of trials by their parameters, read from the database once, and
  written as an inspect log, an xlsx workbook, or files for R.
- **A stateless command,** `chatddx export`, not a repl command.
- **Descriptive analysis in-house, inference in R.** chatddx summarizes;
  paired comparisons and models are R's.
- **The xlsx is a data handoff and a summary report,** not a review sheet.

## 1. Where things stand

The repl had `export [DIRECTORY]`: it wrote all the identity's runs of the
held cell as one inspect log, into DIRECTORY or `./logs`, scored by the
registry's scorers, and printed `inspect view --log-dir logs` to look
through it. It is gone; `cell_log` and `write` remain, used by the tests
and ready for `chatddx export`.

```
Run, Score (database)
  └─ cell_log(identity, configuration, stack, label)
       └─ one EvalLog per identity × cell
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

### The log's layout

`cell_log` writes an identity's runs of a cell as an inspect log
(`data-generation.md` §5, option C), a sample per draw of a case, laid out
so:

| Sample field | Holds |
|---|---|
| `id`, `epoch` | the case, by the name the exporter sees it by, or its short fingerprint; and the draw. A seeded trial is one draw, its latest run that completed standing for it, or its latest run. Its epoch is its seed's place among the seeds the log holds, from 1, so that an epoch is one seed across cases. A trial with no seed makes a draw of each of its runs, the epochs after the seeded ones. |
| `input` | what the LLM was first sent: the instructions, as the system message they went out as, and the case |
| `output.completion` | the answer as text: where inspect expects an answer, and where `react()` puts a submitted one. It is the `text` view where the output offers one, and a structured answer's JSON otherwise |
| `messages`, and a `ModelEvent` per request | the exchange as pydantic-ai kept it, thinking and tool calls included. Each event carries the request as it went, and the response, a streamed one joined into the completion its chunks make up, as inspect keeps one. The bytes themselves stay on the run. |
| `target` | the pattern of the case's `diagnosis` target, which `reciprocal_rank` and `first_mention` read |
| `metadata` | the cell's variation of each slice, its stack and the stack's parts, by name; the case, its language, the seed, the trial's and the run's ids, and the run's status, validity, finish reason and error; the answer, and what each view the output offers reads from it, as a scorer gets it; the case's targets, by kind, as the exporter is held to them (`research/output-and-scorers.md` §2); the fingerprints of the configuration, the stack, the case and the output; the client; each tool's blob |

- **A log is one task on one model:** its task is the cell's label, and its
  model the stack, `vllm/qwen3-8b-awq@pelle`. The served name is on each
  output. An errored run's sample carries its error, as inspect's own do.
- **A cell is the natural unit.** An inspect log is one task on one LLM,
  and a sample id appears once per epoch.
- **Analysis needs no join.** `samples_df` over logs gives one row per
  draw, with its variation per slice as `metadata_*` columns and its scores
  as `score_*` columns. That is the factor vector of
  `research/a-new-datamodel.md`, as a table. It takes pandas and pyarrow, which
  the `analysis` dependency group brings.

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
the repl or a chat makes no difference (`post-endgame.md`, on the batch
as a record; the seed is the de facto batch key).

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
  as runs, as `research/a-new-datamodel.md`'s `judge_trial` would have it, so
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
- **The repl is the place to run and look,** not to export: `runs`,
  `replay`, `score` and the batch summary cover looking.
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
  from the parquet files. `research/a-new-datamodel.md` listed them as derived
  views; they move out of chatddx.
- **Why here:** numpy is already a dependency (through inspect), and a mean
  with its interval is what someone looking at a run needs; a model needs a
  statistician's choices, which R and its people are better at.
- **Open:** the interval: a cluster bootstrap, or a cluster-robust standard
  error (inspect's `stderr` takes a cluster); and whether `stderr` in the
  registry's metrics becomes that.

## 7. What changes elsewhere

- `research/output-and-scorers.md` §2, "Later, from inspect": scores come
  back first.
- `research/a-new-datamodel.md`'s derived views: descriptive ones stay in
  chatddx, inferential ones go to R.
