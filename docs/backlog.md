# Backlog

Open work, each section what would fit in one PR. A section says its fix, what is decided about it and, when it waits,
what for; its items say what holds today. "Decided" means the user said so. "Take" is the agent's recommendation and
still open.

"Ready" can start now, "Waiting" waits for what it names, and "Olof's work" is a clinician's, not a PR. Work a part's
doc in docs/parts/ tracks is that doc's, not this document's.

## Contents

- [Ready](#ready)
  - [Differentiate start-up and runtime findings](#differentiate-start-up-and-runtime-findings)
  - [Canary sets in use](#canary-sets-in-use)
  - [Drift between runs](#drift-between-runs)
  - [Attestation within a run](#attestation-within-a-run)
  - [Aggregation](#aggregation)
  - [Export and publication](#export-and-publication)
  - [Scoring: coverage and judges](#scoring-coverage-and-judges)
  - [Unheeded reasoning](#unheeded-reasoning)
  - [Tool rounds](#tool-rounds)
  - [What reaches vLLM: argv and passthrough](#what-reaches-vllm-argv-and-passthrough)
  - [Facts: the checks](#facts-the-checks)
  - [Facts as an engine changes them](#facts-as-an-engine-changes-them)
  - [Stopping: halts, deadlines and time limits](#stopping-halts-deadlines-and-time-limits)
  - [Streams that miss nothing](#streams-that-miss-nothing)
  - [Concurrent writers](#concurrent-writers)
  - [The database repeats the rules](#the-database-repeats-the-rules)
  - [Compilations checked](#compilations-checked)
  - [A run names the skeleton its look gave](#a-run-names-the-skeleton-its-look-gave)
  - [Vignette identity: renames, repairs and rebinding](#vignette-identity-renames-repairs-and-rebinding)
  - [Titles](#titles)
  - [Languages](#languages)
  - [Translating JSON few-shot answers](#translating-json-few-shot-answers)
  - [Values the canonical form can't keep](#values-the-canonical-form-cant-keep)
  - [Migrations checked by content](#migrations-checked-by-content)
  - [Administering people](#administering-people)
  - [The repl's reach](#the-repls-reach)
  - [The repl's rendering](#the-repls-rendering)
  - [Unknown query parameters](#unknown-query-parameters)
  - [Loading data sets](#loading-data-sets)
  - [Exporting data sets](#exporting-data-sets)
  - [The data's stage, said in code](#the-datas-stage-said-in-code)
  - [Missing tests](#missing-tests)
  - [The archive's configuration under another name](#the-archives-configuration-under-another-name)
  - [Appendices without threads](#appendices-without-threads)
- [Waiting](#waiting)
  - [Splits beyond `lines@1`](#splits-beyond-lines1)
  - [Shipped code: scorers and tools](#shipped-code-scorers-and-tools)
  - [Engines that aren't vLLM](#engines-that-arent-vllm)
  - [Engine identity: hardware and model files](#engine-identity-hardware-and-model-files)
  - [Facts waiting on a model or a run](#facts-waiting-on-a-model-or-a-run)
  - [Claims: slots, turns and a lost endpoint](#claims-slots-turns-and-a-lost-endpoint)
  - [Garbage collection](#garbage-collection)
  - [Performance, once measured](#performance-once-measured)
  - [Execution settings as a component](#execution-settings-as-a-component)
  - [Chat templates as components](#chat-templates-as-components)
  - [Text cleanup steps](#text-cleanup-steps)
  - [The appendix layout as a part](#the-appendix-layout-as-a-part)
- [Olof's work](#olofs-work)
  - [The sample's judge](#the-samples-judge)

## Ready

### Differentiate start-up and runtime findings

As a consequence of the new error policy (AGENTS.md, "Handling errors and warnings"), a distinction between start-up and
runtime is necessary.

### Canary sets in use

Built: the sample World's endpoints name the `basics` canary set, so its runs send it at start and end; a scripted run's
fake answers its canaries outside the script (`src/chatddx/fake_vllm/script.py:Script.scripts`); and a run's canary set
is referenced from `ledger.run_stage` as its trial is (`0029-t0-ledger-canaries.sql`). What is left:

- **Kompismoln's endpoints name none**: `worlds/kompismoln/endpoints.toml` is written by `chatddx import-engine`, which
  knows no canary set, so one written in by hand goes at the next import. Take: the inventory names a canary set for
  every endpoint it includes, an endpoint's own taking its place.
- Canary calls emit no `Streamed`.
- **Judge engines are never probed.** Canary probes run on the run's engine only. Probing judge engines would put
  canaries in a score's start record, as in a run's; added with defaults, they keep every stored digest.

### Drift between runs

Built: `src/chatddx/ledger/run.py:check_drift` compares, between phases and runs of one trial at one endpoint, each
canary's answer (`canary.drift`) and prompt-token fingerprint (`canary.prompt_drift`), and the system fingerprints the
engine says (`engine.system_drift`), as findings. `check_run` compares a run's own phases, and a run's page the person's
earlier finished runs of its trial at its endpoint too (`src/chatddx/api/runs.py:_checked`).

Take: the group under a handle is where its canaries would be compared across its engines, which would give the group
the evidence it lacks; still a take.

- Nothing but a run's page compares runs: the portal's run page, scores and the breakdown don't say that a run's engine
  drifted from an earlier one's.

### Attestation within a run

Checking a run or a score holds every call to what it should have been: each later round's and each judge's request
rebuilt, in `src/chatddx/runner/prepare.py` since it needs the vignette, and the prompt-token and model checks for judge
and canary calls.

### Aggregation

What may be pooled and what aggregates scores: runs grouped by their recorded factors, the evidence of the observed ones
checked, before anything pools them. Nothing plans it yet.

### Export and publication

How records leave the store with the factors they reference, under a seal that covers the whole log, and with what an
analysis needs frozen: languages and titles. Nothing plans it yet.

- **Records aren't in bundles.** A bundle carries components only; how records travel with the factors they reference,
  for example for publication, isn't specified.

- How scores are aggregated and exported together with the factors and the ledger for publication.

### Scoring: coverage and judges

A scoring says which cases it lacks before it is run, calls its judges concurrently, and confirms their endpoints only
when an item needs a judge.

- **A scoring doesn't say which cases it lacks.** Only checking a score warns, once a run is scored under it.
- **Judge calls go one at a time**, and every judged scoring confirms its judges' endpoints, even when no item needs a
  judge; an endpoint that hangs holds it up to the confirmation's timeout.

### Unheeded reasoning

A finding for reasoning a parser missed, and the repl's word on it.

- **No word on reasoning that wasn't heeded**, and no `[thinking in content]`: the runner can't tell reasoning a parser
  missed.
- **No finding for reasoning that wasn't heeded**, as the old chatddx had.
- **What the old bench had and this one doesn't**: what a run left unheeded (the old `outcome.py:unheeded`); the old
  crossing of variations, which the portal is to start as several runs; and what holds a configuration, the portal's ,
  whose part for the repl `Seen.runs(reaching=…)` and `Seen.runs(scored_by=…)` cover.

### Tool rounds

Tool rounds that are consistent and can be shown: a malformed call answered or left out, the answer tool beside another
caught when the run is checked, and a source a scripted run can send tools on.

- `tool_calls` skips a malformed call, but `next_request` copies the response's `tool_calls` as they are, so the next
  request holds a call that no `tool` message answers.
- **The answer tool called beside a toolset tool** ends the item, and checking the run notes the other call; no engine
  under test does that. Checking the run doesn't refuse a turn that runs the other call, though the runner never writes
  one.
- The gate refuses tools on a sensitive source, and both Worlds' sources are sensitive, as a real one is, so no scripted
  run can send a tool round on their cases. The old chatddx's sample runs `broken` and `rich` searched the web. A take:
  a made-up source that isn't sensitive, once calibration wants a tool round to show, with the web patched in the
  process that runs the tools (`urllib.request.urlopen`, src/chatddx/tools/web_search.py).

### What reaches vLLM: argv and passthrough

What an engine's command line and a passthrough may hold, checked against pinned lists of vLLM 0.24's `serve` flags,
each with whether it takes a value, and its request keys (docs/vllm.md, item 12). The flag list also lets the fake take
the first entry off docs/vllm.md, "Not emulated".

Decided: a passthrough's refusals stay, and a key vLLM 0.24 doesn't take gets a warning lint, on local engines only.

Decided: the arguments that don't change what is computed, such as `--max-num-seqs`, `--gpu-memory-utilization` and
logging, are the endpoint's rather than the engine's: out of its digest, written with the endpoint by the engine import,
as its capacity is, and recorded with each run, as its execution settings are. Each flag in the list says which it is,
and one the list doesn't know stays in the engine.

- **Every argument is in the engine's digest**, so changing one that only tunes the server makes another engine: the
  endpoint serves it under another name, a set at the endpoint no longer finds its earlier runs, running them again is
  refused at the gate, and a judge at it is another judge. Batching arguments still change the arithmetic on an engine
  that isn't batch invariant, as execution settings do, so "Aggregation" groups by them.

- `argv` is checked without vLLM's list of flags: a bare argument after a flag that takes no value passes, and lints
  don't expand abbreviated flags.
- A passthrough refuses a fixed list of options and lets everything else through. Two other ways:
  - an allow list: a passthrough may set only known engine extras. Nothing unknown gets through, but every new option
    needs a code change, and remote engines accept other options than vLLM, so the list would depend on the engine.

### Facts: the checks

Checking pairs and loading facts warn where they now stay silent or warn wrongly: an unknown budget warned about,
unknown reasoning not, an unread recommendation found when facts load, a budget with reasoning off refused when
compiled, and a default that lands on a refusal refused when facts load.

- **A budget with reasoning off is compiled.** Qwen3's off with a budget turns thinking off and sets a thinking budget.
- **Unread recommendations.** A recommendation for a level that collapses, or lands on its nearest, is never compiled,
  and nothing reports it. Checking pairs still counts it as the model's.
- A `sampling.recommended` entry for a level that collapses, or lands on its nearest, is never asked for by
  `ModelFacts.recommended`, and nothing reports it.
- **An unknown budget passes the check.** A budget sent to a model whose budget is unknown isn't warned about, while
  compiling one beside a level is refused.
- An unknown budget passes `facts.budget_refused`, while compiling one beside a level refuses it (`check_budget`).
- Unknown reasoning fails `facts.reasoning_unmatched`: a model without writes at any level, or a skeleton using a level
  nothing is known about, gets the warning.
- **A refused default is accepted.** A default that lands on a refusal loads, and whether the model reasons by default
  is then unknown.
- A `default` that lands on a refusal loads, and `reasons_by_default` then says `None`.

### Facts as an engine changes them

Facts about a model on a runtime, and the defaults an engine's command line sets over the model's own. The command line
can be done now; facts keyed by runtime wait for a second runtime.

- **A model or a model on a runtime.** Some facts are really about a model on a runtime, such as harmony ignoring the
  response format. They live on the model for now; facts keyed by runtime can be added when a second runtime appears.

- **The context and the thinking budget from the command line.** Done for vLLM 0.24 where every engine serving a model
  says so: the context is the longest `--max-model-len` they serve, and a thinking budget is refused where none has
  `--reasoning-parser` or `--reasoning-config`.

- **Defaults from the command line.** An engine's own default chat template arguments and generation config change the
  model's defaults. Facts describe the model's own defaults, and only the grammar-before-reasoning lint accounts for the
  change.

- An engine's `--default-chat-template-kwargs` and `--generation-config` change the model's defaults; only
  `vllm.grammar_before_reasoning` accounts for the first.

### Stopping: halts, deadlines and time limits

Everything under way can be ended in time: a call waiting for its response's headers, a running tool, and a halted run,
which can resume.

- **A call still waiting for its engine to answer at all**, under an execution with no timeout, waits on after a halt;
  only a stream can be shut down. vLLM answers at once and streams after. A run takes its endpoint's execution, and no
  World's sets a timeout, so runs have none.
- **Tools have no time limit of their own**, and a halt waits for a tool that's running.
- `Toolbox.run` has no time limit.

### Streams that miss nothing

A stream that can't miss a row or an event, and a notification queue that a listener that stops reading can't hold up.

- **The rows' order is their writer's.** A stream reads the rows after the last it told; a row committed after one with
  a higher number would be missed until the stream starts again. One writer per run keeps the two orders alike: the
  queue holds one job open per run, and a log's rows are written one transaction after another. A repl scoring a run
  while the worker writes it doesn't.
- **What isn't a row is told only to those listening**, so a stream that joins after a scoring started misses
  `run.scoring`. Notes along the way are told with the finish row that holds them, not as they happen.
- **`NOTIFY`'s queue**: a payload waits in the database's notification queue, kept on disk, until every listener has
  read it, and a listener that stops reading holds the queue up for all. Deltas are sensitive, and pass through the
  database that holds the ledger's responses already.

### Concurrent writers

The rules hold with two writers at once: adopting a vignette, taking an expectation and saving a name.

Decided: the advisory locks edits take (`src/chatddx/store/catalog.py:Catalog._lock`) extend to adopting, on the
vignette's source and content; to taking an expectation, on the owner, the case and the schema; and to creating a named
thread, on the owner, the kind and the name.

- The database repeats the rules two writers could break but two: that no two families are bound to the same vignette,
  by id or by content, at once, and that a person owns at most one live expectation thread per case and expectation
  schema. So two people adopting the same vignette at the same moment can create two families, and two writes at the
  same moment can leave a person several expectations to choose from, which scoring then refuses.
- The rules are checked in Python on rows read inside the writing transaction; with two writers at once only tier 2
  holds. Two `adopt` calls for one vignette at the same moment can create two families.

- **An edit that names its head holds with several writers without the database repeating the rule** Every edit takes
  its thread's advisory lock (src/chatddx/store/catalog.py:Catalog._lock). The writer may not update the catalog's
  tables, so `FOR UPDATE` isn't open to it.

- **Two saves of one name at once** can both create a configuration, in the repl's `save`.
- **Taking counts shared threads, not owners**: a case with two threads shared by one owner is to choose from, and
  naming that owner doesn't pick between them. Only two writers at once can leave an owner two.

### The database repeats the rules

Deferred constraint triggers, as `component_ref_matches` is one, for what the code writes together: a thread's first
version, a family's first binding, and a log's start record.

Decided: a component's reference rows stay unchecked by the database until something other than `Store.add` writes
components, since a trigger would repeat each kind's reference paths in SQL.

- **A thread without versions** is possible in the database, and so is a family without bindings; the catalog writes
  each together with its first. A deferred constraint could rule them out at tier 2.
- A thread without edits is possible in SQL.
- The database doesn't check that a component has all its reference rows, only that the rows it has are right; the store
  writes them together.

### Compilations checked

A skeleton's provenance asked for, a compilation checked against its recipe, and an edit that keeps a skeleton's
compilation when one exists.

- Nothing checks that a compilation's recipe compiles to its skeleton.
- **Skeleton provenance.** Should a skeleton be accepted only with a compilation? Hand-written ones, such as judge
  prompts, are possible today. Decided: keep hand-written skeletons, configurations without a recipe that nothing
  varies, which only the store writes. Provenance is whether a compilation names the skeleton, a question a lint can ask
  once the catalog or ledger is queried for it.
- **A skeleton edit may leave out its compilation** even when one exists, and nothing can require it.

### A run names the skeleton its look gave

A run sends what was looked at, or is refused, and a variation is compiled against facts that say what its edit was
built on.

Decided: a run may name the digest of the skeleton its look gave, as an edit names its head, and is refused when the
variation compiles to another by then.

- **What a fork varies is compared by recipe.** A variation with a part replaced is compiled whole by the running code
  and against the facts as they are stored then, so after a change to the compiler, or a corrected fact, it can send
  otherwise than the edit it was built on where nothing was replaced, and what its fork varies doesn't say so.

- **The variation**: stated whole in each request, the configuration by id and its parts by digest, with nothing stored
  by looking.
- **A variation compiles against the current facts, a configuration against the facts it pinned**
  (`seen.py:compiled_with`). After a correction, `plan+prompt=x` sends another sampling than `plan`, without that being
  picked. Manageable: a variation whose model isn't replaced compiles against the configuration's pinned facts, one
  whose model is replaced against the new model's current ones.

### Vignette identity: renames, repairs and rebinding

What follows a vignette that exists twice in a source, matches several families, was bound before the current binding,
or was renamed in a data set.

- **Identical vignettes.** Two vignettes with the same content under different ids in one source look like a rename:
  adopting refuses the second, which a survey lists as new. Once the adopted id is gone, a survey reports both ids as
  renames of the same family.
- **Several matching families.** When bindings of several families match a case, the latest matching binding decides,
  which needn't be the latest family's.
- **A repair moves the current binding only.** Cases and appendices bound to an earlier binding of the family aren't
  rebuilt at the new place (src/chatddx/catalog/families.py).
- A case stored at a vignette's old place after a repair gets a replacement from `behind` that nothing has stored.
- **A rename isn't followed into the data.** After repair-data, loading says the old id is missing until the data set
  names the new one.

### Titles

Titles that take fewer queries, pair no versions, and are short for a variation.

Decided: a skeleton compiled from a variation of a configuration is titled by the variation's label, as its run is.

- **An unnamed fork's title can pair two versions.** When the origin has no name and has moved on, the title describes
  the origin's current head, while what the fork varies is measured from the base.
- **A variation nobody saved has a long title.** It is described by its whole recipe: "case · diagnoses-tool ·
  recommended · off · qwen3-8b@pelle", where the repl called it "diagnoses-tool+reasoning=off": the configuration it
  came from and the parts set over it. A run of one is named so and says what it varied, but its skeleton is still
  titled by its recipe.

### Following keeps a fork's renamed view

Following an origin keeps the label of a view the fork renamed, though its scorer is the origin's.

- **Following can drop a fork's renamed view.** Labels follow the views the proposal keeps, so a fork that only renamed
  a view, and follows an origin whose views it keeps, takes the origin's labels.

### Languages

Where a compiled skeleton's language comes from, said and kept; judges checked for one, as a notice, and judged in one;
what a person may correct; and a case of a regional tag of its configuration's language.

Decided: a person may correct the language of a text only their own threads hold; anything else stays curation's.

- **Not all a model reads is in the request's language.** Chat templates add English of their own (default system
  prompts, harmony's channel instructions, tool-call scaffolding), and reasoning is often English whatever the prompt.
  The same text also takes another number of tokens in Swedish than in English, so an analysis split by language says
  so; languages themselves are never compared, as their cases differ.
- **A language refused on a compiled skeleton is said to come from its recipe**, by
  `src/chatddx/catalog/language.py:check_language`, `0012`'s `language_compiled` trigger and the bench's
  `COMPILED_LANGUAGE`; a translated skeleton's comes from the language its compilation names.
- **Judges aren't checked for language.** A judge's language could be compared with the cases its scoring grades, the
  way lints check a trial's. An English judge grading Swedish answers may be intended, so it would be a notice rather
  than a warning.
- A case tagged `en-GB` on an `en` configuration is left out as untranslatable (`Seen.languages` compares tags whole);
  before, it ran with `language.mixed`.
- **A judge's translations are never used.** A judge configuration runs in no language, and nothing compiles one into a
  language, so the sample's Swedish of `output.verdict` and `output.grade` is unreachable. A judge in a language would
  have its configuration compiled into it, and pin that skeleton; it meets "Olof's work" (how a Swedish note is read
  against an English answer).

### Translating JSON few-shot answers

A few-shot answer in JSON translated by its texts, rather than whole and by hand.

- **Few-shot answers in JSON are translated whole.** An example is one text, so an assistant example that is a JSON
  answer is translated as one entry, by hand, keeping its property names and allowed values as they are.

### Values the canonical form can't keep

NUL and NaN refused where a component, a record or a typed text is built, rather than failing or changing when stored.

Decided: floats refuse NaN and infinity throughout, and strings refuse NUL, as typed text already does
(`src/chatddx/bench/cases.py`); nothing stored can hold either, so no stored digest changes.

- The database can't keep text holding a NUL character. A component or a typed text holding one is refused when it is
  built; a record holding one is built, and can't be stored.

- NaN and infinity pass validation, and the canonical form writes them as `null`. The stored component reads back with
  the field unset, under the same digest, and `Bundle.load` reports `bundle.recanonicalized`. The request still carries
  the NaN.

### Migrations checked by content

An applied migration's file known by its content too, before a shared database.

Decided: each applied file's sha256 is kept beside its name, and migrating refuses, naming the file, when an applied
file differs; a database migrated before that records its checksums on its first run after.

- **Migrations edited in place and stores reloaded** (O2) is open while no store holds data worth keeping. The deploy
  (`docs/parts/deploy.md`) closes it.

### Administering people

A command that changes a person, and a new password that ends the person's sessions. Three of docs/parts/clearance.md's
("Before real patient data", 8) would ride along: signing in again, a deactivated person's queued jobs, and
`People.set_password`'s empty password.

Decided: the commands stay the operators' tool, used by whoever holds the database; `Role.ADMIN` means something only
with an admin page in the portal, or with Keycloak.

- **A new password doesn't end sessions.** `chatddx person password` replaces the hash, and a session opened with the
  old password stays until it expires; only making the person inactive ends their sessions.
- **Nobody administers people through chatddx.** The admin role exists, but nothing asks for it, and the commands
  connect as `DB_USER`, so whoever reaches the database adds people.
- **No command changes a person**: their name, roles, or whether they are active (`People.update`).

### The repl's reach

The repl reaches what a calibration session needs: several seeds, a scorer picked and a run scored again, the endpoint a
judge is called at, and an unnamed thread by its id.

Decided: the repl doesn't reach every write, which the API and the portal do. Execution settings and the canary set
follow the bench, which takes them from the endpoint ("Canary sets in use").

- A thread with a title and no name can't be named.
- A run takes one seed, and no execution settings, canary set or text cleanup; `score` can't pick a scorer, score a run
  again, or name the endpoint a judge is called at, so a judge whose engine two endpoints serve bars its scorer.

### The repl's rendering

What the repl prints: tool calls apart, which runs were started together, aligned judge lines, and a prompt that
survives a dropped connection. Tool calls apart is a runner fix: the runner's `Delta` drops the streamed tool call's
`index` (`src/chatddx/runner/send.py:Delta`), and carrying it fixes the API's `item.delta` and the portal's live view
too.

- **Two tool calls in one response run together** on one line as they stream, as a call's first delta is taken as its
  name and the deltas don't say where the next begins; `replay` splits them.
- **`runs` doesn't show a start.** A translated run says the language it was sent in, the run of the configuration's own
  language from the same start says none, and nothing says the two were started together; the API's
  `GET /api/runs?with=` and a run's page in the portal do (`Bench.runs(started_with=…)`).
- **The judge lines aren't aligned**, as their labels differ in length; the labels of a scoring's judge calls are known
  when it starts, so their width could be too.

### Unknown query parameters

Routes refuse what they don't declare.

Decided: one dependency for the whole app, the portal's routes included, whose links and forms its own code builds,
refuses a parameter a route doesn't declare and a scalar given twice.

- **A query parameter a route doesn't name is ignored**, unless the query is a model (`Varying`), so a misspelt filter
  on `GET /api/runs` or `GET /api/threads` gives everything, and a part given twice in a variation's query counts the
  last. Take: one check for every route that refuses a parameter the route doesn't declare, and a scalar given twice.

### Loading data sets

Loading that can only verify, loads as someone other than the archive, from several sources, holds what has no table
yet, knows the leftovers meant to stay, and says why it skips a recipe.

- verifying that the store holds a data set, without writing anything, which a loading's validated lines only do inside
  a transaction that writes;
- importing a data set as someone other than the archive.
- Trials, executions, scorings and hand-written skeletons have no tables, and a data set has one expectation schema.

### Exporting data sets

What the archive or a person holds, written back into a data set's files, so that a change made in the portal can be
kept in git.

### The data's stage, said in code

Whether data is guessed or vetted, by whom and from where, loaded with it, so that a score can say what it rests on.

Decided: the stage is a catalog entry on what a data set loads: entries change no digest, a stage moves from guessed to
vetted without a new version, and a score reads the entries on its expectations and its judge.

### Missing tests

Tests for what only the test World reaches, and for the scripted runs' and the runner's untested paths. A scripted run
that sets a part is the portal's.

- **What only the test World reaches isn't all read.** No test reads the gate refusing `qwen3-bare@fake` for `typed`
  cases, the pair lints its records give (`vllm.*` on `qwen3-bare@fake` and `clamped`, `facts.output_refused`,
  `facts.reasoning_unmatched`, `facts.budget_refused`, `language.unknown`), `headed`'s tool guidance, the passthrough,
  or the vignettes' quirks under the cleanup steps. The lints are tested on synthetic registries, and two of the judge
  tests in src/chatddx/scorers/test/test_scorers.py use a synthetic judge.
- **`set` and `--again` have no test**, and no scripted run sets a part.
- `send` again after a worker's exception isn't tested.

### The archive's configuration under another name

A finding when a hand-made recipe compiles to a shared configuration's skeleton.

Decided: the save goes through, with an info finding naming the thread that already holds the skeleton, since no write
is refused on a lint.

- **The archive's configuration saved under another name** is saved with no finding: a hand-made recipe that is a shared
  configuration's, compiled to its skeleton, becomes a thread of the person's own, and only a look's `held_by` says so
  (src/chatddx/api/threads.py). An expectation the same as one the person holds is refused.

### Appendices without threads

An appendix as part of its case alone, with no thread of its own, removing as much of what a thread gives it as can go.

Decided: an appendix is never handled outside the case it goes with; Review writes and shows it there, and the Library
has no shelf of appendices and no page of one (src/chatddx/portal/shelves.py:IN_REVIEW).

- **An appendix is a thread** (src/chatddx/bench/model.py:KINDS), with an owner, versions, sharing and deletion of its
  own, which nothing but its case needs, and the API still lists and writes it as one.
- **Deleting a case's branch** in Review deletes the thread of the appendix it ends in, and Review lists a case only
  while each of its appendices heads a thread the person sees (src/chatddx/portal/review.py:_branches); the case stays
  among its family's cases, as a case is immutable, and the API still lists it.
- **A case's title names its appendices by their threads' names**, and `case_titled` looks them up by those names
  (src/chatddx/bench/seen.py:Seen.case_titled), so an appendix without a thread needs its name kept elsewhere.

## Waiting

### Splits beyond `lines@1`

Splits for answers written otherwise than as a list's lines, and for expectations written as free text. Waits for such
answers or expectations to turn up.

- **One split.** A free-text answer is broken into items only as the lines of a list (`lines@1`), so a scorer can't read
  one written otherwise, as prose or with items on one line.
- If expectations written as free text turn up, a view could split them too. Two ways:
  - a separate split for the expectation side, next to the output's. It is additive: with none as its default, every
    existing digest stays the same, and each side gets the split it needs.
  - one split for both sides. That changes the meaning of an existing field, so the scorer's schema version would have
    to go up, and the two sides rarely need the same split.

### Shipped code: scorers and tools

The interface between components and the code they pin: tools versioned as scorers are, resources a scorer can be given,
and how shipped code is found. Waits for a second calling convention for tools, a first kind of resource, or code from
another distribution.

- **The tool interface isn't versioned**, unlike the scorer's: keyword arguments in, text out.
- **Resources can't be picked yet.** A scorer's resources are plain strings, no kind of component holds one, and the
  scoring code isn't given them. None are offered until a kind of resource exists, with its pins and code that reads it.
- `Scorer.resources` are meant to be digests but are typed as plain strings.
- Today chatddx keeps the list of the code it ships in its code: `src/chatddx/scorers/shipped.py` and
  `src/chatddx/tools/shipped.py`, by the entry point a component names. Packaging metadata changes only when the package
  is installed again, and tests add tools of their own to the list for as long as they run
  (src/chatddx/runner/test/tools.py:shipped). Packaging entry points would fit code from other distributions, which
  nothing runs today.

### Engines that aren't vLLM

Stop assuming vLLM: ask for token ids only where an engine takes them, and lint what OpenAI's API refuses. Waits for the
first real remote endpoint that isn't vLLM; every remote engine in the Worlds is the fake.

Take: the engine says whether it takes token ids, so the choice is a factor a trial shows.

- **Every engine is asked for the prompt's token ids.** A remote engine that isn't vLLM may refuse the unknown option.
  Either the engine says whether it takes it, which changes the engine's digest, or the runner decides per call, which
  leaves the run without prompt-token fingerprints.

- `render` sends `return_token_ids` to every engine by default; a remote engine that isn't vLLM may refuse it.
- **Every engine is asked for the prompt's token ids**.
- **Tool parameters whose root isn't an object.** OpenAI's API is reported to refuse function parameters whose root
  isn't `type: object`. Unverified; a candidate lint for tools on a remote engine.
- **The key for the output limit is the sampling's.** `Sampling.max_tokens_key` picks `max_completion_tokens` or
  `max_tokens`, which the API an engine serves decides, not the experiment; Compose keeps it under Advanced. Its home is
  the engine, beside `api`: an engine field defaulting to `max_completion_tokens` keeps every engine's digest, and
  `render` would name the key, but the sampling field can't go without a way to read the chunks that set it.

### Engine identity: hardware and model files

An engine described well enough to tell apart, and its files checked against the hub. The hardware waits for the first
server on several GPUs, which the import refuses until then (`src/chatddx/importers/o11n.py`); the hub check likely
starts in o11n's report (Kompismoln/o11n, `nixos/vllm-report.py`).

- **Hardware has no GPU count,** so engines that split a model across GPUs can't be told apart by their hardware. Nor
  does it say the CPU, the RAM, the GPU's uuid, the machine's id or where it is.

- **Model files aren't checked against the hub.** huggingface_hub keeps the commit's file listing from the download
  (`<repo>/trees/<commit>.json`): the hub's SHA-256 of each LFS file and the git blob hash of the rest. The report could
  compare every file it hashes with it, offline. The import takes the host's hashes as they are.

### Facts waiting on a model or a run

Small edits to the facts, each waiting on something outside the code: `xhigh`, on a model that supports it; harmony's
tool choices, on a run at `gpt-oss-20b@malborg`.

- **xhigh can't be written.** It's a level, but no reasoning effort says it, so a model can only collapse or refuse it.
  Adding the effort is additive, if a model that supports it shows up.
- **Tool choice on harmony.** Named and required tool choices are unverified for gpt-oss. vLLM 0.24's gpt-oss tool
  parser accepts both, so the JSON-array grammar applies; whether harmony's output survives it isn't known.

### Claims: slots, turns and a lost endpoint

The repl's runs and the worker's judge calls hold slots at their endpoints; claims take turns per owner at each
endpoint, and "ahead" says what the turns make it; and a job at an endpoint the inventory lost waits rather than fails.
The slots and turns wait for endpoints that are shared and busy; the lost endpoint can go now.

- The repl sends in its own process, and its runs don't count against an endpoint's capacity. It could queue its runs
  and follow their events, or send in its own process but hold slots in the queue, as a worker claiming its own job.
  Take: as it is, and holding slots once endpoints are shared and busy.
- Decided: queue order, as built, then turns per owner at each endpoint once people wait on each other. Turns aren't
  built.
- **"Ahead" counts jobs, not items**, and the workers seen are counted for anyone's jobs, not the person's endpoints.
- **A job whose handle moved on** to another engine while it was queued fails at the gate and says to run it again; one
  whose handle was deleted, or that no endpoint here serves any more, fails saying to pick another.

### Garbage collection

Decided: it waits until storage cost or an erasure calls for it; until then the store keeps everything, as its tiers
mean it to. Erasing a typed text is docs/parts/clearance.md's ("Before real patient data", 4).

- Garbage collector for true deletions of non-referenced items.

### Performance, once measured

Paging in the store, and reads that don't repeat, once a measurement says they are slow. The transaction a start holds
open while the gate confirms its endpoint, a network wait, can go now.

Decided: a person's runs are read whole until that is slow, then paged in the store by a cursor, the last run's start.

- **A person's runs are all read**, filtered and then paged, and with `unscored`, what is left of each is worked out
  first. Take: as is until slow, then paging by a cursor, the last run's start.
- **A person's runs are all read**, and paged afterwards, in the API too (`Bench.runs`), and what is left to score is
  worked out for each of them, about 40 ms a run under five scorers. Page in the store once that is slow.
- **A case's language** is its family's, read from the families the person sees, in a few queries however many cases
  (`Seen.languages`, `Seen.findings`); a case of a family they don't see is read one at a time.
- **The facts are read from the store each time they are asked for** (`Seen.facts`), several times a look. That is cheap
  with a facts thread per model; cache them per request if it shows.
- **A start holds a transaction open while the gate confirms its endpoint**, once per language though every run of a
  start goes to one endpoint; a few seconds at most against an endpoint that answers. Confirming once, before the
  transaction, would remove most of it.
- `api/threads.py:thread_of` reads a compilation per configuration listed, for `translated`.
- **A start isn't a subject.** Its runs are tied by a `with` entry and found by a scan (`Seen.runs(started_with=…)`);
  the group that a run over mixed-language cases forms is known by an entry, as variants were known by a name, one level
  up. Small today, and the same shape.

### Execution settings as a component

Execution settings named and picked, as a kind the start record references by digest, outside the trial's digest. Waits
for the portal to offer them for picking.

- Today execution settings are a value inside each run's start record: recorded, sealed with the run's log, and compared
  by value. They have no digest, so the catalog can't name a set of settings (for example "sequential" or "8-way"), the
  portal can't offer them for picking, and finding the runs that used the same settings means comparing values across
  run records.

  Making them a component of a new kind, which the start record references by digest, would give them a name, a catalog
  thread and a foreign key like the pinned factors. They would still stay out of the trial's digest, so this changes how
  execution settings are stored, not what a trial means. The cost is a new kind (with the catalog's thread kinds and
  their migration) and a change to the run record.

- Whether execution settings become an object, which this take doesn't decide.

### Chat templates as components

A chat template held in the bundle, as a kind the engine references by digest. Waits for a need: a bundle read offline,
or the template's date check run off the host.

- Today a local engine pins its chat template by the file's hash, like the model files: a world input, fetched from
  wherever the inventory says it is. A bundle therefore holds the template's hash but not the template, and only a host
  with the file in hand can read it.

  Making the template a component of a new kind, holding the template's text, that the engine references by digest,
  would put it inside the bundle: it is small and not sensitive, so a bundle could rebuild the engine's prompt
  formatting offline. Lints could read it too, so the check for templates that read the current date would run when
  factors are linted, not only on a host. Engines sharing a template would share the component. It would move the
  template from world input to authored factor, and cost a new kind (with the catalog's thread kinds and their
  migration) and a change to the template check.

### Text cleanup steps

More cleanup steps, each a named function in `src/chatddx/factors/cases.py:_OPS`. Waits for a vignette that needs one:
29 of the Worlds' 110 vignette files hold spaces before a newline, and none a non-breaking space, a zero-width character
or a Unicode line break; Kompismoln's source is still to be checked.

- **Four cleanup steps exist.** Vignettes may also need non-breaking spaces turned into spaces, zero-width characters
  removed, Unicode line breaks turned into newlines, or trailing whitespace stripped.

### The appendix layout as a part

A part a variation can replace, when someone wants to vary it.

Decided: the layout then becomes a chunk kind of its own, so the part holds a digest like the others and no edge needs a
special case.

- **The appendix layout as a part** a variation replaces, when someone wants to vary it. It is a value rather than a
  chunk, so a part would hold one where the others hold a digest, at every edge.

## Olof's work

### The sample's judge

Olof's work, not a PR: his prompt replaces the sample's draft judge, measured by his grades of real answers, and his
notes revise the targets.

- **The sample's judge** is a draft over Olof's notes until his prompt replaces it, as an edit. His prompt settles which
  of his comment and answer it reads, how a Swedish note is read against an English answer, whether a verdict is pass or
  fail, a scale or one per aspect, how strict it is about extra or harmful advice, and the judge's engine and seeds. It
  is measured by real answers from pelle and malborg on `dutch-11`, `dutch-01` and `akm-01`, graded by Olof with a line
  on why. Open beside it: notes on more cases, and revising the targets where his notes disagree, as on `dutch-11`
  (shock, most likely sepsis, where the targets have an aortic aneurysm or a dissection).
