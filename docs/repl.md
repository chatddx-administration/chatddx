# The chatddx shell

The chatddx shell, the repl, is where you run clinical cases through a
language model and see what comes back. You pick what to ask and which
model to ask, run one case or a whole set of them, and every answer is
recorded and scored as it arrives.

This manual goes through the shell command by command. The examples use
the fake model (`@fake`), which answers every case the same way, so you can
try everything without a GPU.

## Starting

The shell runs as an identity: a name that owns your runs and your saved
settings. Create yours once, which also loads the shared inventory of
models, settings and cases:

```
chatddx init-data alice
```

Then start the shell:

```
chatddx repl alice
```

To try it without a GPU, start the fake model in another terminal first:

```
chatddx fake-vllm
```

The shell greets you with its prompt:

```
alice #13530>
```

`alice` is who you are, and `#13530` is the seed the shell drew for you (see
`seed` below). As you choose what to run, the prompt grows to show it.

## A few words first

- **Configuration:** what to ask and how. The instruction, the kind of
  answer wanted (free text, a list of diagnoses, a management plan),
  whether the model should think first, and how it samples its words. A
  configuration names no model.
- **Stack:** which model answers, on which machine: `qwen3-8b-awq@pelle` is
  Qwen3-8B on the machine called pelle.
- **The cell:** the configuration and the stack you have chosen, together.
  Every run uses the cell.
- **Case:** a clinical vignette, with what it is expected to yield: its
  targets. Each target is a few plain words saying what is expected, and a
  pattern the scorers look for in an answer. Either can be missing.
- **Run:** one answer to one case from the cell, recorded with everything
  that was sent and received.
- **Trial:** the cell, a case and a seed together. Running the same trial
  twice gives two runs of one trial.

## Getting around

### `help`

Lists every command, with the words it takes. A word in brackets is
optional; `TAG...` means one tag or several.

### `configurations`

Lists the configurations you can use: yours, and the archive's (the shared
inventory). Each row shows what the configuration is made of.

```
alice #13530> configurations
 configuration    instruction  output           coercion  reasoning  sampling     toolset  owner
 diagnoses        ddx          diagnoses        native    default    recommended  —        archive
 free-text        ddx          free-text        auto      default    recommended  —        archive
 plan             ddx          management-plan  native    default    recommended  —        archive
 ...
```

### `stacks`

Lists the models you can run on, and where each is served.

```
alice #13530> stacks
 stack                 llm           machine  endpoint                     owner
 qwen3-8b-awq@fake     qwen3-8b-awq  fake     http://localhost:12099/v1/   archive
 qwen3-8b-awq@pelle    qwen3-8b-awq  pelle    http://pelle.km:12009/v1/    archive
 ...
```

### `cases`

Lists the cases you can run, and how many there are.

```
alice #13530> cases
DutchFall10w  Dutchfall11w  ...  casesfromedn1  ...  openxddx-case_9
99 cases
```

Press Tab at any point to complete a command, or a name after it: a
configuration after `use`, a case after `run`, a tag after `batch` or
`show tag`.

## Choosing what to run

### `use CONFIGURATION`

Puts a configuration in the cell.

```
alice #13530> use plan
cell: plan × ?
alice plan #13530>
```

The `?` says the cell still needs a stack. A configuration someone else
shares with you is named with its owner first: `use bob/bobs-plan`. You can
look at it, but it runs only after you save it as your own (`save`).

### `on STACK`

Puts a stack in the cell.

```
alice plan #13530> on qwen3-8b-awq@fake
cell: plan × qwen3-8b-awq@fake
alice plan×qwen3-8b-awq@fake #13530>
```

### `cell CONFIGURATION STACK`

Both at once.

```
alice #13530> cell free-text qwen3-8b-awq@fake
cell: free-text × qwen3-8b-awq@fake
```

### `set SLICE VARIATION`

Changes one part of the cell's configuration, leaving the rest as it is.
The parts, called slices, are `instruction`, `output`, `coercion`,
`reasoning`, `sampling` and `toolset`. For example, to have the model
answer without thinking first:

```
alice plan×qwen3-8b-awq@fake #13530> set reasoning off
cell: plan+reasoning=off × qwen3-8b-awq@fake
```

The prompt shows what you changed (`+reasoning=off`). `set toolset none`
takes the tools away. Choosing a configuration again with `use` or `cell`
forgets what you set.

### `show`

Shows the cell, and what each slice turns into on this model: the settings
that will actually be sent, and the prompt text the model will read. Last
comes a table of the scorers: for each, whether this kind of answer gives
it anything to read, and how many cases have the target it needs. Nothing
is sent.

```
alice plan×qwen3-8b-awq@fake #13530> show
cell: plan × qwen3-8b-awq@fake
 slice        variation          on the stack
 stack        qwen3-8b-awq@fake  qwen3-8b-awq, served as Qwen/Qwen3-8B-AWQ at http://localhost:12099/v1/
 instruction  ddx                filled: output_guidance
 output       management-plan    a schema; views: differential, warning, disposition, critical
 coercion     native             response_format: guided decoding holds the answer to the schema; ...
 reasoning    default            the LLM's default, 'on': chat_template_kwargs.enable_thinking=true
 sampling     recommended        recommended for 'on': temperature=0.6 top_p=0.95 top_k=20 ...
 toolset      —
system
Fill in the management plan for the case.
user
‹case›
 scorer                view          target       of 99 cases
 disposition_mentions  disposition   disposition  99 have it
 first_mention         text          diagnosis    the output offers no such view
 reciprocal_rank       differential  diagnosis    99 have it
 warning_mentions      warning       warning      99 have it
```

If the model can't do what a slice asks, `show` says so in red, with the
reason: that cell is refused, and nothing can be run on it until it is
changed.

In the scorers' table, a case whose target has no pattern counts as
missing, and the table names it: `1 have it; missing: case-2`. A pattern
that doesn't parse is named in red. Cases with missing targets can still
be run; the scorers that need the missing target just leave them out.

### `show tag TAG...`

The same, with the scorers' table counting only the cases with any of the
tags: the cases `batch` would run.

```
alice plan×qwen3-8b-awq@fake #13530> show tag edn
...
 scorer                view          target       of 20 cases tagged edn
 disposition_mentions  disposition   disposition  20 have it
 first_mention         text          diagnosis    the output offers no such view
 reciprocal_rank       differential  diagnosis    20 have it
 warning_mentions      warning       warning      20 have it
```

### `show ENTITY [NAME]`

Shows any part of the inventory, by kind and name, and what came of your
runs with it. Without a name, it shows the cell's own. For a case, that is
its vignette, each kind of target, and your scores on it. Each target shows
its words and its pattern, and `missing` where either, or the whole target,
isn't there:

```
alice #5> show case DutchFall10w
case DutchFall10w, archive's  e647d6
 vignette                     Main complaint: abdominal pain in upper abdomen ...
 language                     en
 targets.diagnosis.text       missing
 targets.diagnosis.pattern    biliary & (colic | stone*)
 targets.warning.text         missing
 targets.warning.pattern      dissection | cholangitis | cholecystitis | pancreatitis | perforat*
 targets.disposition.text     missing
 targets.disposition.pattern  discharge* | home | outpatient | observation
 targets.dont_miss            missing
 tags                         dutch-fall
2 runs of yours with it
 scorer           runs  mean  stderr  without a value
 first_mention    2     —     —       2
 reciprocal_rank  2     0     0
```

A case that expects no warning says `none expected` instead. A pattern that
doesn't parse is shown with the reason, in red.

The kinds are `case`, `configuration`, `stack`, the six slices, `llm`,
`machine`, `os`, `serving`, `client`, `tool` and `scorer`.

### `reasoning`

Shows, in one table, what every reasoning setting becomes on every model:
the switch or effort that gets sent, the sampling it brings with it, or why
a model refuses it (gpt-oss can't stop thinking, for example). The cell's
current choices are marked with `▸`.

## Running

### `seed [SEED]`

The shell holds a seed, shown in the prompt after `#`. Every run sends it
to the model, which uses it for the random choices it makes while writing.
The same seed on the same cell and case asks for the same answer again, so
a seeded run can be repeated, and it is recorded with its seed.

- `seed` draws a new random seed.
- `seed 42` holds 42.
- `seed none` stops seeding: runs are then unrepeatable draws.

```
alice free-text×qwen3-8b-awq@fake #42> seed
seed: #88645
alice free-text×qwen3-8b-awq@fake #88645> seed none
seed: none: runs go unseeded
alice free-text×qwen3-8b-awq@fake #none>
```

Draw a new seed whenever you want fresh answers rather than a repeat of
ones you already have: running a batch twice under the same seed asks the
same questions the same way twice.

A cell whose sampling is greedy (temperature 0) always gives the model's
single most likely answer, and a seed changes nothing. The shell refuses to
run it with a seed and asks for `seed none`, so that no run claims a seed
it didn't use.

### `run CASE [SEED]`

Runs one case on the cell. The answer streams as it is written: the
model's thinking first, labelled, then the answer. Then come the tokens it
used, what each view reads from the answer, and the scores.

```
alice free-text×qwen3-8b-awq@fake #42> run DutchFall10w
trial: free-text × qwen3-8b-awq@fake × DutchFall10w (seed 42)
[thinking] I am the fake vLLM, and nothing here reads the case. ...
Fake diagnosis A
Fake diagnosis B
Fake diagnosis C
(285 in, 44 out)
differential
  1. Fake diagnosis A
  2. Fake diagnosis B
  3. Fake diagnosis C
scores
  first_mention    —      never named
  reciprocal_rank  0      not listed
recorded as run 1 of trial ab260a9c
```

A seed after the case is used for this run alone, and the shell keeps its
own: `run DutchFall10w 7`.

When the answer should follow a structure (a management plan, a list of
diagnoses), the shell also says whether it did: `valid`, or `invalid` with
what is wrong. A model that fails, a server that errors, or an answer that
can't be read is said in red, and the run is recorded all the same.

A model that runs away, writing nothing but whitespace token after token
as gpt-oss can once its answer is done, is stopped after 100 tokens of it
and said in red: `stopped: nothing but whitespace for 100 tokens`. The run
is recorded with what came before, `invalid` where the answer should
follow a structure. `chatddx fake-vllm --runaway` makes the fake model run
away after every answer, to try it.

Press Ctrl-C to stop a run while it streams. What came so far is recorded,
as stopped.

### `batch TAG...`

Runs the cell on every case with any of the tags, one after another, each
on a line of its own. The token count climbs while the case runs; then the
line fills in with how it went and each score. The batch ends with a
summary per scorer.

```
alice free-text×qwen3-8b-awq@fake #5> batch edn
batch: free-text × qwen3-8b-awq@fake × 20 cases tagged edn, seed 5
case            tokens  outcome    first_mention  reciprocal_rank
casesfromedn1       44  completed  —              0
casesfromedn10      44  completed  —              0
...
 scorer           runs  mean  stderr  without a value
 first_mention    20    —     —       20
 reciprocal_rank  20    0     0
```

- **Tags** say which set a case belongs to: `dutch-fall`, `edn` and
  `openxddx` in the inventory. `batch edn dutch-fall` runs both sets.
- **The outcome** is `completed`, `valid` or `invalid` (for structured
  answers), or `errored`, with the error at the end of the line. A case
  whose model runs away is stopped, as `run` stops it, and the batch goes
  on.
- **A blank score** means the case has no target for that scorer; `—`
  means the scorer found nothing to score.
- **The seed** is the shell's, the same for every case, and shown in the
  first line. A single `run CASE` afterwards, under the same seed, repeats
  what the batch did for that case.
- **Ctrl-C once** lets the case under way finish, and then stops; the line
  says so. **Ctrl-C again** stops that case too, recorded as stopped.
- The same vignette under two names is run once.

## Looking back

### `runs [COUNT]`

Lists your latest runs, the last 20, or as many as you say: when, what ran
(cell, case and seed), how it went, and the scores.

```
alice #5> runs 2
 run       when              trial     what ran                                      outcome    scores
 84cc62dd  2026-09-25 17:32  c7789eaa  free-text × qwen3-8b-awq@fake × casesfromedn9  completed  first_mention —
                                       (seed 5)                                                 reciprocal_rank 0
 98f5106b  2026-09-25 17:32  1948eb05  free-text × qwen3-8b-awq@fake × casesfromedn8  completed  first_mention —
                                       (seed 5)                                                 reciprocal_rank 0
```

### `replay [RUN]`

Shows a run again as it streamed, with when it ran and on which build of
chatddx. Without a run, the latest; otherwise the first letters of its id
from `runs` are enough: `replay 84cc`.

## Scoring

A run is scored as soon as it is recorded. The scorers compare what the
answer says with the case's targets.

### `scorers`

Lists the scorers, what part of an answer each reads, which target it
compares that to, and whether the cell's output offers what it reads.

```
alice #5> scorers
 scorer                function         reads         held to      metrics      owner    the cell
 disposition_mentions  mentions         disposition   disposition  mean stderr  archive  —
 first_mention         first_mention    text          diagnosis    mean stderr  archive  offers it
 reciprocal_rank       reciprocal_rank  differential  diagnosis    mean stderr  archive  offers it
 warning_mentions      mentions         warning       warning      mean stderr  archive  —
```

- `reciprocal_rank`: 1 if the diagnosis is first in the differential, 1/2
  if second, and so on; 0 if it isn't there.
- `first_mention`: in the first sentence or line of the answer that names
  the diagnosis, how many characters come before it; none if it is never
  named.
- `warning_mentions`, `disposition_mentions`: 1 if the warning, or where
  the patient goes, names what the case expects; 0 if not.

### `score [RUN]`

Scores whatever hasn't been scored as the scorers and targets are now. A
target changed in the inventory makes earlier runs of that case waiting to
be scored again; `score` catches them up, and ends with each scorer's
summary. With a run, it shows that run's scores.

```
alice #5> score
nothing to score
```

## Keeping and sharing

### `save NAME`

Keeps the cell's configuration, with whatever you changed with `set`, as a
configuration of your own under NAME. The pieces it uses become yours too.

```
alice free-text×qwen3-8b-awq@fake #5> save my-free-text
saved as my-free-text: created 87f14d
yours now too: instruction ddx, output free-text, coercion auto, reasoning default, sampling recommended
cell: my-free-text × qwen3-8b-awq@fake
```

## Leaving

`quit`, `exit` or Ctrl-D. Ctrl-C at the prompt clears the line; during a
command it ends the command, not the shell.

The lines you type are kept in `~/.chatddx_history` (or the file given with
`--history`), so the arrow keys bring them back next time. The shell also
reads lines from a pipe, which is handy for a fixed routine:

```
printf 'cell plan qwen3-8b-awq@pelle\nseed\nbatch edn\n' | chatddx repl alice
```
