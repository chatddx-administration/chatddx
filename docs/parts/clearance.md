# Clearance: work in progress

Material for a future `docs/clearance.md`. Split out of the former `agents/wip-bookkeeping.md`. The stub that was
`docs/clearance.md` is folded into "What holds now", since clearance is still in progress. The interim table and the
gate are built; the clearance pipeline (a `clearance` schema and its grants) isn't. "Decided" means the user said so;
"Take" is the agent's recommendation and still open.

## Scope

Decided: clearance tracks sensitive sources, sensitive derived content and vetted endpoints, both engines and databases.
It is enforcement, not curation: sending sensitive content to an engine that isn't cleared, judge engines included, is
the system's one hard block (`docs/chatddx.md`, "Findings"). The factors and the ledger provide the means; the runner
enforces.

Decided: this plan also holds every concern about running real patient data until it is resolved (see "Before real
patient data").

Decided: the boundary is every destination of sensitive content, the vignette included: engines and judge engines, the
third parties tools send to, the database (records, the notification queue, a job's reasons, typed texts), the edges and
exports. The gate keeps deciding per run, from what the run pins, and covers every request a run sends; each other
destination is cleared as this plan builds it.

## What holds now

### Vetted endpoints

Until clearance has a database grant, a World inventory's `[cleared]` table says which sensitive sources each endpoint
may receive sensitive content from.

Decided: Kompismoln's endpoints, `qwen3-8b@pelle` and `gpt-oss-20b@malborg`, are cleared for the sample World's
vignettes, in `worlds/kompismoln/inventory.toml`. Kompismoln will need to be cleared for the sample World in the
clearance pipeline when it is up, as the table goes.

Before a run or a judged scoring writes anything, the gate refuses (`src/chatddx/runner/gate.py`):

- an endpoint serving another engine than the one asked for;
- a sensitive source of the cases the endpoint isn't cleared for;
- tools on a sensitive source;
- an endpoint whose credential names a secret that isn't set;
- an endpoint the inventory can't confirm serves its engine, for runs, canaries and judges alike.

The first three hold for as long as the World is as it is (`gate.bar`); the last two may pass later (`gate.admit` adds
them). The page that runs trials offers none `gate.bar` refuses, saying why in its place
(`src/chatddx/portal/starting.py`). The bench leaves a judged scorer that `bar` refuses out of what applies to a run.

### Sensitive sources

Every source, a directory or a database, is sensitive unless declared otherwise (`docs/surfaces/inventory.md`,
`Source`). The gate enforces it against the inventory's `[cleared]` table until the clearance pipeline replaces the
table. A `[cleared]` entry for a source that isn't sensitive clears nothing and is said so (`cleared.not_sensitive`,
`src/chatddx/inventory/check.py`).

### Completions derived from vignettes

- Which records are sensitive is in docs/parts/ledger.md, "Sensitive records". Compilations are components
  (`src/chatddx/factors/request.py:Compilation`), not records, and hold no case text.
- No policy has settled. Options: a database-level read restriction on sensitive tables; a destination check when
  records are exported.
- Part of it exists: the sensitive tables are in schema `ledger`, and at tier 1 `chatddx_reader` can read `factor` but
  not `ledger` (`src/chatddx/store/migrations/0005-t1-ledger.sql`), nor the typed texts in `source`
  (`0015-t1-source.sql`). Nothing uses the reader yet, and who gets it is open.

### Typed vignettes

- A clinician may type about a real patient on the portal's home page. The text is a vignette, kept in the store as a
  database source's, so the database holds vignettes now, not only what is derived from them.
- Each World clears its endpoints for `typed` as it does for its directory source: the test and sample Worlds clear
  their fakes, not the sample's remote engine nor the test World's `qwen3-bare@fake`. Decided: Kompismoln clears both
  its endpoints for `typed`, which is the clinicians' sandbox there, and no real patient data goes into it.
- Their fingerprints are plain, as the sample's, since nothing manages keys yet: a short text's hash can be guessed by
  anyone who reads the factors, the reader included, while the text itself is kept from them. Open: a keyed one.

### Tools

- A tool's arguments are written by the model from the case. A tool that sends them off the host (a web search; the
  sample's `chatddx.tools.web_search` goes to DuckDuckGo) sends sensitive content to a third party, so the hard block
  covers tools as it covers engines and judges.
- Tools are pinned by their entry point and the version of it chatddx ships (`Tool.entry_point`, `Tool.version`;
  `src/chatddx/tools/shipped.py:TOOLS`), and a run records the version that ran (`RunStarted.tool_code`). So the
  clearance pipeline can clear a tool by its entry point and version, with the endpoints it reaches. Nothing declares
  those yet; that belongs to clearance, not to the factor.
- Tool results come back from the third party and are stored in the ledger (`ToolRun.result`), next to the responses.
- The runner runs tools, and the gate refuses them on a sensitive source until a tool can be cleared. What ships a tool
  is in `docs/surfaces/factors.md` (`Tool`).

### Judges

- A judge's engine falls under the hard block: a judge prompt always holds a completion, which is sensitive. The scoring
  pass gates each judge's endpoint as a run's (`gate.bar` in `runner/score.py:judge_at`, `gate.admit` in
  `Runner.score`), and the gate refuses a judge reading the vignette or appendices.
- Judge calls record their endpoints, by judge, name and URL (`ScoreStarted.endpoints`,
  `src/chatddx/ledger/score.py:JudgeEndpoint`), as a run records its own (`RunStarted.endpoint`), so whether a judged
  scoring was cleared can be audited from the ledger as a run's can.

### A request's sensitive content

Where it is at each stage of a request, beyond the records above:

- **Fills and the rendered request**: in the runner's memory only. The ledger keeps the request's fingerprint
  (`Call.request`), not the request, nor the prompt's token ids.
- **The wire body**: sent to the endpoint the run's start record names, every tool round's and attempt's included.
- **Attempts**: only their count is kept. A refusal's body is kept as the call's response, the last attempt's only; an
  earlier attempt's is dropped (`src/chatddx/runner/send.py`).
- **A tool round**: the model's arguments go wherever the tool's code sends them; the results are kept in the ledger.
- **Live deltas and tool runs**: through the database's notification queue, as they come.
- **Rendered again**: an item's first request rendered with its real fills, in memory, and only compared with the call's
  fingerprint; nothing is sent (`chatddx.runner.prepare.rendered_again`).
- **Not sensitive**: the chunks, the recipe, the skeleton and the trial, which names its cases by fingerprint; a
  canary's request; the look's request, rendered with placeholders.

## What the code offers

- What the factors hold of a vignette, the sensitive fills they make, and that no component holds where an engine is:
  `docs/parts/factors.md` ("Sensitive content", "Engines and models").
- `RunStarted.endpoint` and `ScoreStarted.endpoints` (`src/chatddx/ledger/run.py:Endpoint`) record where a run's and a
  scoring's calls went, by the endpoint's name and URL.
- The old module had `EndpointBinding(engine, base_url, clearances)` and
  `CaseSourcePolicy(source, required_clearances)`, with a check that every endpoint reached by sensitive content held
  the clearances its sources require (`git show de843eb:src/chatddx/core/manifest.py`, around L1913 and L2258). That
  shape still fits: sources require clearances, endpoints hold them, and the gate refuses when one is missing.

## Takes

- Databases count as endpoints, because the ledger _is_ sensitive storage, and the `source` schema holds typed vignettes
  themselves. The Postgres instance holding them has to be vetted like an engine, and an export target (records leaving
  for publication) is another endpoint.
- Storage: schema `clearance`, append-only like the catalog (SELECT, INSERT for the writer; t2 insert-only triggers).
  Granting clearance is the action the hard block depends on, so possibly only a separate role (`chatddx_clearance`) may
  write it. That is the one place a new database role seems justified.

## Open

1. **What a grant keys on.** This blocks the schema. Endpoints live in the inventory: ops-authored TOML, mutable, no
   ids. Candidates:
   - the URL (simple, but a local host serves different engines over time, and one engine may have several hosts);
   - an inventory entry name (stable for humans, but the inventory isn't in the database, so no foreign key);
   - the engine digest plus URL (what the old `EndpointBinding` did).

   An endpoint has a name and binds one engine digest to a URL (`src/chatddx/inventory/inventory.py:EndpointSpec`), a
   remote engine's URL too. So a grant can key on the endpoint's name with the digest and URL it holds, as the old
   `EndpointBinding` did. Today `[cleared]` keys on the name alone, so renaming an endpoint drops its clearance without
   warning, and its runs appear under two names.

2. **Where vetting is declared.** Decided for now: in the inventory, as `[cleared]`. For the long term: the inventory
   keeps all location facts in one place, while a database grant (through the portal, logged) gives an audit trail and
   fits the append-only store.
3. **Who may grant clearance**, and whether that needs its own role.
4. **Sources.** Sources say only whether they are sensitive. Still unspecified: what clearance each requires beyond
   that.
5. **Edges as destinations.** The repl shows sensitive content at its terminal: `show case` prints the vignette and
   `run` streams the completion. The API sends it over the network to whoever signed in, but only from its own places,
   each with `Cache-Control: no-store`. The portal is an edge too: every page is `no-store`, the vignette has a page of
   its own, its fonts are served by the app so that a page fetches nothing from a third party, and copying an answer as
   text wasn't ported, since it puts sensitive content on the clipboard. The takes count a database and an export target
   as endpoints to vet, but nothing says whether an edge's client is one, nor who may read the vignette or a run's items
   through it. Open: whether edges are vetted like endpoints, by what (the edge, the person, or the client's address),
   and whether the repl falls under the same rule.
6. **A clearance withdrawn during a run.** The gate decides as a run starts and as it resumes, and as a judged scoring
   starts, so a run under way keeps sending after its endpoint's clearance is withdrawn. Asking the gate at every send,
   a round's, an attempt's and a judge call's, would stop it. Take: as is, since a dated grant tells whether a run was
   cleared when it started (see "When to build it").

## Before real patient data

The healthcheck at 08ae453 (`healthchecks/2026-10-14-08ae453.md`) lists what has to hold before real patient data, or
the public web, in its §4, by weight, and its bug 7. Each is restated here as the code stands since the worker took runs
out of the app, in the healthcheck's order, with where else it is tracked. Some of them a deployment can carry
(`docs/parts/deploy.md`); the code has to carry the rest.

1. **Signing in** can stall the app.
   - Each attempt runs argon2id with its defaults (t=3, 64 MiB, p=4; `src/chatddx/identity/identity.py:72`), and an
     unknown login pays the same through a dummy hash. Both sign-in routes are synchronous
     (`src/chatddx/api/people.py:103-114`, `src/chatddx/portal/pages.py:120-135`) and share anyio's 40 threads with
     every synchronous route. Nothing limits the attempts, nor a password's length. About 40 concurrent POSTs stall
     every page and hold about 2.5 GiB (the healthcheck's arithmetic, not measured).
   - Every request opens a Postgres connection before its token is checked (`src/chatddx/api/people.py:55-70`,
     `src/chatddx/portal/pages.py:68-78`), and a portal error page opens a second (`src/chatddx/portal/pages.py:100`).
   - Untracked elsewhere: the app's own limit, and the connection before the token. puts the portal on the public web
     before Keycloak.
   - The NixOS module's nginx limits sign-ins per address (`docs/parts/deploy.md`, "The NixOS module"); the app and the
     Kubernetes target don't.
2. **Connections** are unbounded.
   - There is no pool: each request opens its own (`src/chatddx/api/state.py:21-33`).
   - A run's event stream holds two for as long as it is open, the request's and its own
     (`src/chatddx/api/runs.py:215-229`, `src/chatddx/api/telling.py:166`), and each app one more for its listener
     (`src/chatddx/api/listening.py:114`).
   - A worker holds one, and two more and a thread for each job it holds (`src/chatddx/worker/worker.py:Worker._work`),
     up to `src/chatddx/settings.py:WORKER_JOBS` jobs. A run's job is held to its endpoint's capacity, but a scoring
     alone holds no slots (`src/chatddx/api/scores.py:45-47`), and a job asked to halt or at an endpoint the inventory
     doesn't name isn't counted (`src/chatddx/store/queue.py:311`), so a worker takes as many of those as it has room
     for.
   - The quotas read a count and then insert, so a burst can overshoot them: `TYPED_PER_DAY`
     (`src/chatddx/bench/cases.py:type_case`) and `RUNS_PER_DAY` (`src/chatddx/bench/runs.py:check_quota`). Scoring
     again has no quota, beyond one job per run at a time.
   - So one account can exhaust Postgres' default 100 connections, and replicas multiply what each process holds
     (`docs/parts/deploy.md`, "Containers for Kubernetes").
3. **Shutdown.** The worker resolved it: nothing in the app grows with each run, a stopping worker queues what it holds
   again, cutting what is under way at its deadline, a killed one's jobs are claimed again once lost, and a stopping
   server cuts its event streams off.
4. **Typed cases** are kept for good.
   - `source.text` is insert-only (`src/chatddx/store/migrations/0016-t2-source.sql`), only the admin can delete a text,
     and no route or command erases a text or its family.
   - A refused run leaves its text stored and counted against `TYPED_PER_DAY` (the healthcheck's bug 7): the home page
     stores the text (`frontend/src/islands/Home.svelte:78`) before it starts the run (:83-85). A retry of the same text
     reuses its family, but an edited text or a reloaded page makes a new one, and a job that fails in the worker leaves
     its text too.
   - Why a job failed is kept for good as well, since the writer can't delete from `worker.job`
     (`src/chatddx/store/migrations/0020-t1-worker.sql`), and it can quote what was sent (10).
   - The fingerprints are unkeyed, the typed text's (`src/chatddx/bench/cases.py:type_case`) and a run's
     (`src/chatddx/runner/rounds.py:152-161`); see "Typed vignettes".
   - Untracked elsewhere: how long a typed text is kept, and how it is erased.
5. **Headers.** There is no CSP, frame-ancestors, nosniff, Referrer-Policy or HSTS (`src/chatddx/api/app.py:app`,
   `src/chatddx/portal/app.py:app`). `/api/docs` and `/api/openapi.json` are public, and Swagger UI loads
   `swagger-ui-dist@5` from jsdelivr, with a floating major and no SRI, onto the session cookie's origin. With no inline
   script, `script-src 'self'` fits every portal page. The NixOS module's nginx sends HSTS, `nosniff`, `Referrer-Policy`
   and `frame-ancestors`, but no `script-src`, which would refuse Swagger UI's scripts; the app sends none, so the
   Kubernetes target has none (`docs/parts/deploy.md`, "The NixOS module").
6. **Engine errors** are stored verbatim: the engine's error response to a rejected request, as the call's response
   (`src/chatddx/runner/send.py:158-160`), with only `prompt_token_ids` stripped (`src/chatddx/ledger/call.py:47`), and
   the engine's message in `Call.error` (`src/chatddx/runner/wire.py:17-35`). An engine that echoes its input in an
   error puts vignette text in the store. They are served with a run's items only, which are no-store. Not checked
   against real vLLM.
7. **Digests** work as capabilities.
   - `GET /api/components/{digest}` checks no visibility (`src/chatddx/api/world.py:79-89`), by design: appendices and
     expectations aren't sensitive (`docs/chatddx.md`).
   - `Seen.variation` checks only a part's kind (`src/chatddx/bench/seen.py:Seen.variation`), so
     `/threads/{id}/variation` shows another person's unshared chunk, and `POST /runs` with `parts` runs one
     (`src/chatddx/api/runs.py:_new`). Untracked.
   - `/threads/{id}/proposal` returns appendix text without no-store, as `component`
     (`src/chatddx/api/threads.py:proposal`).
8. **Sessions** and people.
   - A password change leaves sessions open (`src/chatddx/store/people.py:87-94`), and so does signing in again.
   - Expired sessions are deleted only when a session opens (`People.open_session`).
   - `Role` is shown, never checked.
   - No command deactivates anyone, though `People` can (`src/chatddx/store/people.py:81-84`), and a deactivated
     person's queued jobs still run: the worker finds a job's owner by id, active or not
     (`src/chatddx/worker/worker.py:Worker._done`).
   - `chatddx person password` refuses an empty password; `People.set_password` doesn't.
   - Tracked in `docs/backlog.md` ("Administering people"), but for signing in again, the deactivated person's jobs and
     the empty password.
9. **Migrations** are known by name only (`src/chatddx/store/migrate.py:27-32`). Applied files were edited in place
   before 08ae453, and none has been since. Tracked: `docs/backlog.md` ("Migrations checked by content") keeps their
   checksums, before a shared database.
10. **Error text** goes to clients.
    - Any exception in a job becomes the job's `why` (`src/chatddx/worker/worker.py:Worker._work`), served by
      `GET /api/runs` and `GET /api/runs/{run}` (`src/chatddx/api/runs.py:246-257`), which aren't no-store, shown on the
      portal's runs pages, and told in a run's `error` event (`src/chatddx/api/telling.py:113-115`). The worker logs it
      with its traceback (:190). A scoring's refusal carries its exception's text in `run.scored`.
    - The gate's messages hold an `OSError` (`src/chatddx/runner/gate.py:44-48`), answered as a 422 and shown on the
      portal's error page.
    - `docs/migrations.md` ("Tier 1", `0020-t1-worker.sql`) says why a job failed can quote what it was sending; says
      nothing outside its no-store places carries any.
11. **Writes** are unlimited. Appendices, threads, forks, edits, components and scorings have no count or size limit,
    and the app none on a request's body; a typed text's size is checked only once its body is parsed
    (`src/chatddx/bench/cases.py:type_case`). The only limits are runs a day, items a run and seeds. Behind the NixOS
    module's nginx, a body is held to nginx's default, 1 MB.
12. **Proxies.** The engine client sends through urllib's default opener (`src/chatddx/runner/wire.py:112-116`), which
    follows `HTTP_PROXY` and `HTTPS_PROXY`, so vignette-bearing requests go through any proxy the environment names; so
    do confirming an endpoint (`src/chatddx/runner/wire.py:served`) and the web search tool
    (`src/chatddx/tools/web_search.py:23`). The NixOS module unsets them for its services (`docs/parts/deploy.md`, "The
    NixOS module"). Take: the client opens without proxies, rather than every deployment keeping them out of its
    environment.
13. **Raw errors** go to stderr and the edge as they are, sensitive or not. Errors for developers and ops are propagated
    raw (AGENTS.md, "Handling errors and warnings"), and the user decided they go to the edge anyway for now, though an
    engine's error, a judge's, or any exception raised while a vignette or a completion is in hand may quote it.
    Untracked elsewhere: holding them back from the edge. The user suggests a `@sensitive` decorator on every function
    that may handle sensitive content, so that its errors are handled otherwise.

## When to build it

Nothing built so far waits on it:

- The gate reads `Inventory.cleared` once per endpoint it admits (`gate.bar`), for runs and judges. A database grant
  changes that one read. The repl, the API and the portal also read `cleared` to show an endpoint's clearances
  (`src/chatddx/repl/listing.py`, `src/chatddx/repl/inspecting.py`, `src/chatddx/api/world.py`).
- A run and a scoring already record what a grant would key on (Open 1): the endpoint's name and URL
  (`RunStarted.endpoint`, `ScoreStarted.endpoints`) and, through the trial or the judge, the engine's digest. If grants
  are append-only and dated, whether a run was cleared at `RunStarted.at` is a query, so the pipeline adds no field to
  stored runs.

It becomes the next blocker at:

- tool rounds on a sensitive source: the gate refuses tools on a sensitive source until a tool can be cleared ("Tools").
  The runner's tests declare the test World's source not sensitive for them, and no configuration of the sample's holds
  a tool;
- the first real sensitive source, typed cases from clinicians included, or the first runs on `pelle` and `malborg`
  whose clearance should be auditable from the database rather than from the inventory's git history;
- a deployment: `docs/parts/deploy.md` is solidified only once this plan, "Before real patient data" included, is
  resolved.
