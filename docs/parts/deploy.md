# Deploy: work in progress

How chatddx is to run outside a development shell: a NixOS module whose systemd services run it on a host, and
containers for a Kubernetes cluster. The NixOS module is built; the containers aren't. "Decided" means the user said so;
"Take" is the agent's recommendation and still open.

## Start with this

1. **Decided: deploy is the last wip.** It can be solidified only once every other wip is resolved, and
   `docs/parts/clearance.md` above all: a deployment is where real patient data first arrives, and what has to hold
   before then is listed there ("Before real patient data").
2. **Decided, built: `chatddx run` and `chatddx portal`.** `chatddx run` is what `chatddx portal` was, the portal, the
   API and a worker in one process, with `--watch`, as the convenience for development. `chatddx portal` now serves the
   portal and the API with no worker, so that the NixOS module's systemd services each run a command of their own (see
   "Services and commands").
3. **Decided: two targets**, a NixOS module (see "The NixOS module") and containers for a Kubernetes cluster (see
   "Containers for Kubernetes"). Decided: the containers serve real patient data, on Kubernetes inside Karolinska's
   network, and that is the deployment; the NixOS module serves Kompismoln's chatddx and chatddx-dev, which sign people
   in and hold fictional cases only (see "On Kompismoln").

## What holds now

- **The flake** (`flake.nix`) has `packages.default`, the Python environment with `chatddx` on its PATH, and
  `packages.frontend`, the portal's build, which a deployment points `CHATDDX_PORTAL_ASSETS` at portal;
  `nixosModules.default`, and its tests in `checks` (see "The NixOS module"). It has no image, and nothing builds it but
  a person. CI runs the flake's checks on each push to main (docs/parts/dev.md, "CI").
- **What serves**, by command (`src/chatddx/cli.py`):

  | Command                | Serves                                                                                                                                    |
  | ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
  | `chatddx run`          | the portal at `/` and the API at `/api/`, with a worker on a thread of its process; `--watch` builds the frontend with pnpm as it changes |
  | `chatddx portal`       | the portal at `/` and the API at `/api/`, with no worker; `chatddx worker` runs beside it                                                 |
  | `chatddx api`          | the API at `/api/`, with no worker; `chatddx worker` runs beside it                                                                       |
  | `chatddx worker`       | the queue for a World, until SIGTERM or SIGINT; what it holds then is queued again                                                        |
  | `chatddx migrate`      | the migrations, as the admin, up to a tier                                                                                                |
  | `chatddx fake-engines` | the World's fake engines, for development                                                                                                 |

- **Stopping a worker**: its items and scorings under way go on for `settings.WORKER_DEADLINE` (60 s), which is to be
  "within the stop timeout of the service that runs the worker" (`src/chatddx/settings.py`). systemd's default stop
  timeout is 90 s; Kubernetes' default grace period is 30 s.
- **Several processes may serve one database**: workers take turns to claim, and a run's events reach every app through
  `LISTEN`/`NOTIFY` (`src/chatddx/api/listening.py`). Sessions are in the database.
- **What a process reads from its environment**: `DB_HOST`, `DB_NAME`, `DB_USER` and `DB_ADMIN` (`settings.database`);
  `HOST`, where to listen; `CHATDDX_WORLD`, `CHATDDX_PORTAL_ASSETS` and `CHATDDX_REVISION`; and each endpoint's secret,
  under the variable its `credential` names, read in `src/chatddx/runner/gate.py` and `src/chatddx/scripted/fakes.py`,
  not through `chatddx.settings`.
- **The database**: `src/chatddx/store/setup.sql` makes the admin `chatddx`, the writer `chatddx_writer` and the
  database. Development connects on a socket with peer authentication, OS users mapped to roles (AGENTS.md,
  "Environment"). `settings.database` names a host, a user and a database only, so a password or TLS can come only from
  libpq's own `PG*` variables.
- **A World is a directory**: its inventory, its facts, and a directory source's vignettes (`worlds/sample/vignettes`),
  which are sensitive unless declared otherwise (`docs/surfaces/inventory.md`, `Source`). Every process but `migrate`
  reads one.
- **Where it is to run**: decided, the HTTP server, the API and the worker as separate systemd services on NixOS, with
  the module's stop timeout above the worker's deadline, which is the worker's own. What the HTTP server is was left
  open: the portal's pages served apart from the API, or a proxy in front of both.
- **Identity**: "The deployment is to sit behind Keycloak", which isn't decided further. Take: a proxy in front, such as
  oauth2-proxy, passes the login in a header the app believes from it alone, mapped onto `person.login`, and Keycloak's
  own tokens are bearers for scripts when they come. Whether roles then come from Keycloak's realm roles instead of the
  column isn't decided.

## What a deployment runs

- **The app**: one Python process (uvicorn), the portal's pages at `/`, rendered on the server with Jinja2, and the API
  at `/api/`. They are one FastAPI app, not two services: the portal mounts the API (`src/chatddx/portal/app.py:app`),
  calls its route functions, and shares its `__Host-` session cookie and its same-origin check. `chatddx api` serves the
  API alone, without the pages.
- **The frontend's build**: static files, hashed JS and CSS, fonts and Vite's manifest, built by Nix
  (`packages.frontend`). There is no Node at run time: the islands are Svelte compiled for the browser, with no
  server-side rendering, and pnpm and Node only build them (`--watch` runs `vite build --watch`). The app serves them at
  `/static/`, and reads the manifest to name them in its pages, so it needs `CHATDDX_PORTAL_ASSETS` even when a proxy
  serves the files.
- **Workers**: `chatddx worker`, one or more, which send queued runs and score them, judges included.
- **Engines**, which both reach: the worker to send, and the app to confirm an endpoint before it starts a run
  (`src/chatddx/runner/gate.py:admit`, a request with the endpoint's secret). vLLM runs on the inference hosts, outside
  the module; `chatddx fake-engines` could stand in on a demo host.
- **PostgreSQL 16**: the database, the admin and the writer, and `LISTEN`/`NOTIFY` for a run's events and for waking
  workers.
- **Migrations**: `chatddx migrate`, once, as the admin, before the app and the workers start.
- **The archive's sync**: `chatddx sync-archive`, once, as the writer, after the migrations and before the app and the
  workers start, which don't wait on it succeeding. It runs again when a deploy changes its unit, the package with it;
  after a change to the World's data alone, `systemctl restart chatddx-sync-archive`.
- **The World**: a directory both read, with sensitive vignettes in it.
- **Secrets**: the endpoints' credentials, which both the app and the workers need, and the database's, beyond peer
  authentication.
- **In front**: TLS and a reverse proxy, and later Keycloak.
- **The operator's commands**, not services: `chatddx person add`, `password` and `provision`, `import-engine` and
  `repl`, with the same World and database as the services.
- **Something on a schedule**, once there is a command for it: purging expired sessions (`docs/parts/clearance.md`,
  "Before real patient data", Sessions).

## Services and commands

Decided, built: each service runs one command, with no flag that changes what it serves. `chatddx portal` serves the app
without a worker (`src/chatddx/cli.py:_portal`), as `chatddx api` serves the API.

| Service                                        | Command                |
| ---------------------------------------------- | ---------------------- |
| the app, the portal with the API               | `chatddx portal`       |
| the API alone, where nothing serves the portal | `chatddx api`          |
| each worker                                    | `chatddx worker`       |
| the migrations, before the others start        | `chatddx migrate`      |
| the archive's sync, after the migrations       | `chatddx sync-archive` |

Take: "the HTTP server" of the worker's decision is the proxy in front of the app, since the portal and the API are one
app on one origin.

## The NixOS module

Built: `nix/module.nix`, the flake's `nixosModules.default`, as `services.chatddx`. Decided: the module closes over this
flake (`lib.modules.importApply`), whose packages and revision are its defaults, so that it needs no `specialArgs`, and
a system that has the flake under another name (Kompismoln's `chatddx-dev`) gets that flake's. `nix/test.nix`, the
flake's `checks.<system>.module`, boots it in a VM.

- **Options**: `package` and `frontend`, the flake's; `revision`, the flake's, as `CHATDDX_REVISION`; `admin`; `world`;
  `listen`; `workers`; `environmentFile`; `database` (`createLocally`, `host`, `name`, `tier`); and `nginx` (`enable`,
  `hostName`, `signInRate`).
- **Services**, under `chatddx.target` (see "Services and commands"):
  - `chatddx-migrate`, a oneshot as the admin, after `postgresql.target`. The others require it, so a switch that
    changes it restarts them after it;
  - `chatddx-portal`, `chatddx portal` as the writer;
  - `chatddx-worker-1` and on, `chatddx worker` as the writer, with `TimeoutStopSec` at 90 s, above `WORKER_DEADLINE`.
- **Users**: the system users `admin`, `chatddx` unless the host names another, and `chatddx_writer`, named as the
  roles, so that NixOS' default `local all all peer` needs no map. The module declares the admin a system user in a
  group of its name, which merges with the host's own declaration of the same user, with its id and home (Kompismoln's
  principal, see "On Kompismoln").
- **The database**, with `createLocally`, the default: `services.postgresql`, the database owned by the admin
  (`ensureDBOwnership`, so it is named as the admin), the admin with `createrole` for tier 1's reader, and the writer.
  Without `createdb`, which only the tests use. The module leaves PostgreSQL's version to the host, whose cluster is
  tied to its own, and warns when it is neither 16 nor 17. Decided: 17 is accepted, as Kompismoln's hosts serve it
  (o11n's `nixos/postgresql.nix`).
- **The operator's `chatddx`**, on the system's PATH: the services' environment, and the secrets when it can read them;
  run as root, it runs as the writer, or as the admin for `migrate`.
- **Secrets**: `environmentFile`, read by systemd for the portal and the workers. A path in the store is refused
  (`types.externalPath`).
- **The World**: a path in the store is refused too, as the store is readable by every user of the host. The services
  can't see /home (`ProtectHome`).
- **nginx**, with `nginx.enable`:
  - HTTPS, from ACME unless the host gives a certificate, and everything proxied to the app, `/static/` included;
  - HSTS, `nosniff`, `Referrer-Policy: same-origin` and `frame-ancestors 'none'`;
  - sign-ins (`POST /sign-in`, `POST /api/session`) limited per address to `signInRate`, 10 a minute, with a burst of 5,
    and 429 beyond;
  - nginx's default limit on a request's body, 1 MB;
  - a run's event stream unbuffered, as the API asks with `X-Accel-Buffering: no`.
- **Hardening**: every service sandboxed (`ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `PrivateDevices`, no
  capabilities, `@system-service` system calls, `UMask=0077` and the like), and `http_proxy`, `https_proxy` and
  `all_proxy`, in either case, unset for them even when the host sets them for every service.
- **The test**: PostgreSQL 17; the admin a user of the test's own, `chatddx-test`, with a home (0750), as an org
  declares it; the sample World copied out of the store into that home, reached through the admin's group, which the
  writer is in; the portal on `[::1]:8000`; and the World's secret in a file. That the migrations run as the admin, and
  that the writer reads the World and `nobody` doesn't; the archive's sync after the migrations; through the operator's
  command, a provision and a password; then the fake engines. Through nginx, with a certificate made for the test: a
  typed case run by the portal, sent and scored by a worker; the headers; a 429 among sign-ins sent at once. Last, a
  worker that doesn't see a proxy set for every service. It passed by emulation in a cloud session before the admin
  option; decided since, a cloud session doesn't run it, the person does, on a host with KVM
  (`docs/nixos-test-procedure.md`, "Who runs what").
- **The evaluation**: `nix/module-eval.nix`, the flake's `checks.<system>.module-eval`, evaluates the module without
  building or booting: the default and an org's admin, workers, a database elsewhere, ordering, the sandbox's settings,
  PostgreSQL's versions, the database's name, and paths in the store refused. A cloud session runs it, `pytest` against
  PostgreSQL 17 and the host flow (`docs/nixos-test-procedure.md`).
- Open:
  - static files from nginx rather than the app, left with caching the build;
  - a `script-src` and `/api/docs` (`docs/parts/clearance.md`, "Before real patient data", Headers);
  - a timer that purges expired sessions, once there is a command for it;
  - whether the module also serves an inference host's vLLM from an endpoint's start-up, as `fake-engines` serves a fake
    from it, or that stays with the hosts' own NixOS containers.

## On Kompismoln

Built, in use: two apps of Kompismoln's org run this repository's `main` with the World `worlds/kompismoln`, and their
runs on the sample's vignettes go to pelle and malborg. Decided: neither is the deployment, both sign people in and hold
fictional cases only, so "Before real patient data" (`docs/parts/clearance.md`) doesn't hold them back.

- **chatddx**, at chatddx.com on helsinki, for the people who use the rig. It replaced the Django app of the same name,
  whose database was dumped and dropped first, and it started with an empty store.
- **chatddx-dev**, at chatddx-dev.kompismoln.se on stationary, for testing and development. Its store has been dropped
  and loaded again when a stored kind's version went up; since a bump adds the kind's upgrade from the version before
  (docs/parts/factors.md, "Components"), what it holds can be kept.

Each locks this repository in the org's flake, as its own input, `chatddx` or `chatddx-dev`, so a deploy takes the
revision its input is locked to.

- **Where it is**: Kompismoln's org (`Kompismoln/org`), in `apps/chatddx.nix`, the app file of both apps in its
  `org.toml`, which o11n's app-scheduler role imports on the app's hosts. It adapts the org's app to `services.chatddx`;
  o11n has nothing of chatddx's.
- **What the org gives**: the app's principal, `chatddx` or `chatddx-dev`, a system user with an id, a home in
  `/var/lib/<app>`, kept across stationary's ephemeral root, and a loopback address of its own (`bindAddress`). Decided:
  the principal is the admin (`admin`, and the database of its name). The writer is in its group (`principal.members`),
  to read the World in its home. `www.chatddx.com` redirects to chatddx.com (the org's `altpoints`).
- **What the app file adds**: `listen` on the principal's address; nginx for the app's endpoint; o11n's
  `nixos/nginx.nix` (ACME, the firewall) and `nixos/postgresql.nix` (PostgreSQL 17, its directory kept across the
  ephemeral root, a daily dump into the home); and `chatddx-worlds`, a oneshot before `chatddx-migrate` that copies the
  repository's `worlds/` into the home, since `worlds/kompismoln` refers to the sample's vignettes and `_data`.
- **One chatddx to a database server**: the migrations name the writer's and the reader's roles, which are the server's,
  not the database's. chatddx and chatddx-dev are on different hosts.
- **Shared engines**: both send to pelle and malborg, and each holds an endpoint to its capacity on its own, so an
  endpoint can take up to twice its capacity at once. Decided: accepted, as chatddx-dev is for testing.

## Containers for Kubernetes

- **The image**: Take: built by Nix (`dockerTools.streamLayeredImage`) from `packages.default` and `packages.frontend`,
  so that it holds the flake's closure and nothing else, with `CHATDDX_REVISION` set from the flake's revision. One
  image; each workload names its command (see "Services and commands").
- **Workloads**:
  - a Deployment for `chatddx portal`, with a Service and an Ingress, the event stream unbuffered there too;
  - a Deployment for `chatddx worker`, with `terminationGracePeriodSeconds` above `WORKER_DEADLINE`, since the default
    is shorter;
  - a Job for `chatddx migrate` before each release, as the admin.
- **The database**: peer authentication doesn't reach across pods, so the roles sign in with a password or a certificate
  over TCP. `settings.database` passes neither (see "What holds now"). Take: `chatddx.settings` names what libpq takes
  (`PGPASSFILE`, `PGSSLMODE` and the like), as the project's source of truth, rather than leaving it to libpq's
  environment. In the cluster (an operator such as CloudNativePG) or outside it is open.
- **Connections**: replicas multiply what each process holds, with no pool (`docs/parts/clearance.md`, "Before real
  patient data", Connections), against Postgres' `max_connections`.
- **The World**: not in the image, which a registry holds. Take: the inventory and facts as a ConfigMap; a directory
  source's vignettes on a volume only the workloads mount; endpoint secrets as a Secret, under the names the inventory
  gives.
- **Egress**: Take: a NetworkPolicy that lets the pods reach Postgres and the inventory's endpoints only, so that the
  network holds what the gate holds (`docs/parts/clearance.md`, "Vetted endpoints").
- **Probes**: the app has no health route, and the worker no HTTP at all. The app answers HEAD with 405, as FastAPI adds
  no HEAD to a GET route, so a probe has to GET. Open: a route for readiness, and whether the worker's beats
  (`settings.WORKER_BEAT`) can serve as its liveness.
- **Reaching the inference hosts**: pelle and malborg are on Kompismoln's VPN (README, "Kompismoln's hosts"). Open: how
  the cluster's pods reach them.
- Open: where the manifests live and what writes them (plain YAML in the repository, Helm, or Nix).

## Open

- Keycloak in front: which target runs it, and how it hands the app a login.
- CI: whether a deployment takes only a revision CI passed, and what builds the image. The checks, the VM test included,
  run on each push to main on a self-hosted Forgejo runner (docs/parts/dev.md, "CI"); the options for one with KVM on
  one of Kompismoln's hosts are in o11n's `agents/wip-self-hosted-kvm.md`.
