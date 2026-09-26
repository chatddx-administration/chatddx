# The chatddx API

The API does over HTTP what the shell does (`repl.md`): choose a cell, see
how it resolves, run cases on it, one or a batch, and look back at the runs
and their scores. It is mounted at `/api/`, and `/api/docs` lists every
endpoint with what it takes and gives.

## Who you are

A request acts as the identity of the user signed in to its session, by
name, or as `guest` without one. Either is made the first time it is met.

A session's `POST` carries its CSRF token in `X-CSRFToken`: a run spends
what your secrets pay for. `GET /api/me` says who you are, and sets the
`csrftoken` cookie the token is read from.

A stack whose details name a `credential` is sent the secret of that name,
from your identity's secrets.

## The cell

The API holds no cell between requests: each request names its own, as
query parameters on a `GET` and in the JSON body of a `POST`.

- `configuration`: yours or the archive's, by name, or `OWNER/NAME` for one
  shared with you. Another's runs once it is saved as your own.
- `stack`
- `instruction`, `output`, `coercion`, `reasoning`, `sampling`, `toolset`:
  a variation held in place of the configuration's, as `set` holds one;
  `none` takes the toolset out.

## The shell's commands

| shell | API |
| --- | --- |
| `configurations`, `stacks`, `cases` | `GET /api/registry/{entity}`, any entity; `?tag=` keeps those with any of the tags |
| `use`, `on`, `cell`, `set` | the cell each request names |
| `show` | `GET /api/cell`: the cell, how it resolves, and which cases each scorer can hold it to |
| `show tag TAG...` | `GET /api/cell?tag=TAG&tag=...` |
| `show ENTITY` | `GET /api/cell/{entity}` |
| `show ENTITY NAME` | `GET /api/registry/{entity}/{name}`, and `?owner=` for one shared with you |
| `reasoning` | `GET /api/reasoning` |
| `scorers` | `GET /api/scorers` |
| `seed` | the `seed` of each run or batch |
| `run CASE [SEED]` | `POST /api/runs` |
| `batch TAG...` | `POST /api/batch` |
| `save NAME` | `POST /api/cell/save` |
| `runs [COUNT]` | `GET /api/runs?limit=&offset=` |
| `replay [RUN]` | `GET /api/runs/{run}/transcript` |
| `score [RUN]` | `POST /api/scores` |

A run or a trial is named by its id, or by its first letters, as `runs`
shows them. Beyond the shell, a run's record is at `/api/runs/{run}`, its
messages at `/messages`, and the bytes it sent and got back at
`/exchange`; a trial is at `/api/trials/{trial}`, with your runs of it; and
any branch's versions and your runs with it are at
`/api/registry/{entity}/{name}/versions` and `/runs`.

## Running

`POST /api/runs` runs the cell on a `case`, by name, or on a `vignette` of
your own, recorded as a case without a name. `POST /api/batch` runs it on
each case with any of its `tags`, one after another; a vignette under two
names runs once.

Each takes a `seed`: a whole number, `"none"` to run unseeded, or nothing,
for a seed drawn as the shell draws one, the same for every case of a
batch. A cell whose sampling is greedy (temperature 0) runs unseeded when
no seed is given, and is refused one given: a seed would change nothing.

Whatever stands in a run's way is said before anything is sent: a refused
cell (422, with its refusals), a missing secret (409), another's
configuration (403).

## Streaming

A run streams as server-sent events, each as it comes, whether Django
serves over ASGI or WSGI. Each event's `event:` is its `type`:

- `batch`: a batch, before its first run: its cases and its seed.
- `run`: a run, before anything is sent: its id, what runs, and its seed.
- `thinking`, `text`, `call`: what the model sends back, piece by piece.
  Pieces of one part share its `part` number.
- `result`: what a tool returned.
- `usage`: the tokens used, once an answer came.
- `warning`, `validity`, `views`: whether the model reasoned as asked,
  whether the answer holds to its schema, and what each view reads from it.
- `error`: why the run came to no answer, or wasn't recorded.
- `scores`, `recorded`: the run's scores, and its record.
- `summary`: a batch's scores, scorer by scorer, after its last run.

A client that goes away stops the run, which is recorded as stopped, and
the batch. `"stream": false` answers a run with its record instead.
`GET /api/runs/{run}/transcript` gives a run's events again.
