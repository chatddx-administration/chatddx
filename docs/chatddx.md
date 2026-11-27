# The ChatDDX Rig - requirements and design notes

## Purpose

ChatDDX is a system to measure how accurately LLMs generate differential diagnoses and management plans from
emergency-care case vignettes.

The rig provides:

- an environment that can be provably reconstructed (the "cage").
- means to record each exchange within the cage: what was planned, what was sent and what came back.
- first principles for sensitive data so that policies governing this data can be enforced.

It must be possible to deliver the cage together with the results, for scientific rigor.

## The cage

Everything that can change an answer or its score is a :Factor: prompts, sampling, engines, model weights, cases, seeds,
expectations, scorers. A factor is pinned in a :Component, an immutable set of parameters identified by its :Digest, the
hash of its canonical form, that refers to other components by theirs (`src/chatddx/factors/base.py:Component`). A run
or a score names what it ran under by digest, along with the rig's own build (`src/chatddx/rig.py:rig`), so that its
cage can be rebuilt from them, and a :Bundle carries a set of components and everything they reference, to be checked
offline. The ledger keeps whole what can't be made again, the responses, the tools' results, the times and the values,
and a vignette or a request only as a :Fingerprint (docs/parts/ledger.md).

## Requirements

- Simple and reliable scoring methods are needed to produce clean, easily processed outputs, which will require strict
  and simple pattern matching.
- Due to the sensitive nature of patient data passing through the orchestrator, a separate path is needed where data can
  be passed along revealing just enough for the orchestrator to fulfill its duty. Cases enter the system de-identified,
  from a predefined source or typed directly into a chat (:Typed case). De-identification is the clinician's duty.
- Nothing can be expected of the vignettes: They may or may not include labs and imaging results, and may even lack
  basic details such as age or sex. The source exposes no revision identifier.
- Portal interfaces for managing instructions, few-shots, prompts, output, sampling, reasoning, passthrough,
  translations, toolsets, recipes, appendices, expectations, trials, scorers, judges, scorings and starting and
  monitoring runs.
- Engines, models, canary sets, expectation schemas and scoring code are authored by ops or developers and shipped. A
  scorer is put together by researchers in the portal.
- A self-contained bundle that can be verified offline.
- Scripts that can read the World to import factor parameters.
- Import scripts that fingerprint World inputs (model files, closure, chat template, vignettes) into factors.

### Intended evolution of configurations

The researchers will want to iterate and continuously refine configurations according to the following workflow.

1. Chunks are added by hand-edits
2. Successful variations are saved as configurations proper
3. Unsuccessful variations are deleted
4. A configuration with several successful variations branch out
5. Unsuccessful configurations are deleted

What a configuration and a variation are, and how a variation is kept, is the catalog's.

## The parts

The rig's modules, from the World a deployment is described in to a run's score. A part's doc, if it has one, is in
docs/parts/, and a module's public surface is in docs/surfaces/.

1. `inventory`: a :World, the directory one deployment is described in, with its :Inventory of vignette sources,
   endpoints and hosts. `importers` writes a World's engines from o11n's reports, and `facts` holds the :Facts about
   models.
2. `factors`: every kind of :Component, the rules that keep each one valid, and the functions that compile, render and
   read them. It imports nothing else of chatddx, and the rest builds on it.
3. `store`: what is kept, in PostgreSQL 16: components by digest, the ledger's records, the catalog's rows, people,
   typed vignettes and the worker's queue. `curation` loads a data set into it as the :Archive's.
4. `catalog` and `identity`: how people name, own, share and follow what the store holds, and who a :Person is.
5. `bench`: what one person sees and does, whatever the :Edge: the `api`, the `portal`, with `locale` for its languages,
   and the `repl`.
6. `worker` and `runner`: the worker claims the runs queued for it; the runner sends a run's items and canaries to its
   endpoint, refusing sensitive content where it isn't cleared (`src/chatddx/runner/gate.py:bar`), runs its `tools`, and
   writes the run and its scores.
7. `ledger`: each run and score as a log of records, only added to, sealed when it finishes, and checked against the
   factors it names.
8. `scorers`: the scoring code chatddx ships, pinned by a :Scorer, which grades answers against expectations by pattern
   or by asking a :Judge.

Beside them, `cli` is the `chatddx` command, `settings` the project-wide source of truth, `rig` the rig's own build and
`whoops` the error a person is told of. `fake_vllm` stands in for vLLM 0.24 where none runs, and `scripted` runs the
scripted runs it answers. `test` and `conftest` are what the tests share, `stamp` writes what is stamped, and `refcheck`
checks what the docs refer to.

## How it runs

`chatddx portal` serves the portal and the API under `/api/`, and `chatddx worker` beside it sends and scores the runs
queued; `chatddx run` serves both with a worker in the same process, for development. Both connect to PostgreSQL 16 as
the :Writer, migrated by `chatddx migrate` as the :Admin (database). Engines are local vLLM servers on the inventory's
hosts or remote OpenAI-compatible APIs, each served at an :Endpoint, and `chatddx fake-engines` stands in for a World's
on one machine. A host runs the rig from the NixOS module (`nix/module.nix`); containers for a Kubernetes cluster are in
docs/parts/deploy.md.

## People and their edges

Clinicians, researchers, ops and developers each author some kinds of component (docs/glossary.md, "People"), and reach
the rig through an :Edge. Clinicians and researchers work in the portal, whose pages are in docs/parts/portal.md ("Its
pages"); ops and developers write a World's files and run the `chatddx` command; scripts use the API, documented at
`/api/docs`; and `chatddx repl` is a shell over a World for one person.

## Release

The project is ready to be released when docs/parts/deploy.md ("the last wip") is done.

## Vignettes and anything made from them are sensitive

The vignette and content produced from it: fills, requests and responses, tool arguments and results, judge requests and
responses, an engine's error that echoes a request; are all sensitive. Every part in the system that touches this data
must mention "sensitive" in the docs in preparation for the clearance pipeline (docs/parts/clearance.md). Typed cases
included. Clearance and sensitivity are considered a moving target until release: own store as cleared by definition,
and errors as an exception until the clearance pipeline exists.

In short: Sensitive content may go only where it is cleared to go, so sending it to an engine that isn't cleared, judge
engines included, must be refused, and so must storing it, showing it at an edge, handing it to a tool's third party or
exporting it where it isn't.

## Findings

A finding is a non-catastrophic inconsistency discovered at start-up or runtime (docs/backlog.md, "Differentiate
start-up and runtime findings"). They are a separate layer on top of ordinary exceptions to isolate rig-level
irregularities from application-level exceptions, and are listed separately in the generated surfaces at
docs/surfaces/*. All findings are listed in docs/glossary.md, "Findings".

## Where things are written

- This document: what the rig is for, and what holds across it.
- docs/glossary.md: every term, one line each (`grep '^:Term' docs/glossary.md`).
- docs/parts/: a part's doc, at whatever stage it is (AGENTS.md, "Development stages"), beside a module's surface in
  docs/surfaces/ and the indexes of its comments in docs/comments/, of its whoopses and asserts in docs/whoopses/ and of
  what it says to a person in docs/catalog/, which `chatddx-dev index` writes from the code.
- docs/parts/bench.md: the bench, which every edge goes through.
- docs/backlog.md: open work, a section for each pull request.
- docs/migrations.md: the database's migrations, by schema and tier.
- docs/vllm.md: vLLM, and what the fake pins of it.
- docs/reduce.md: continuous surface reduction, when asked to `reduce <thing>`.
- docs/nixos-test-procedure.md: testing the NixOS module from a cloud session.
