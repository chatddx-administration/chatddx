# ChatDDX

LLMs aren't deterministic like traditional programs: the same question can get a different answer, and a model behind an
API can change overnight. Nor do they have what makes a human's judgement trustworthy: reputation, introspection and
accountability. It can't be held to account when it's wrong. That poses a range of challenges for LLM assistance in
emergency care, starting with knowing how it performs, in a way others can reproduce and examine.

ChatDDX is a rig that measures how accurately LLMs produce differential diagnoses and management plans from
emergency-care case vignettes. Everything that can change an answer or its score (prompts, sampling, engines, model
weights, cases, seeds, expectations, scorers) is a factor, pinned by its digest. That way the environment of a run, "the
cage", can be rebuilt and delivered with its results.

It records each exchange and handles sensitive vignettes as a fingerprint to be resolved only at cleared endpoints.
There is a sandbox chat for "typed vignettes" where the clinicians are responsible for de-identification.

- Scoring can be done with pattern matching and LLM judges.
- Models run locally on vLLM or remotely behind OpenAI-compatible APIs. See [docs/chatddx.md](docs/chatddx.md).

## Developing

On a Linux machine, such as Ubuntu on WSL, with the development environment from Nix.

### Nix with flakes

```sh
nix --version
```

If Nix is missing, install [Lix](https://lix.systems/install/):
`curl -sSf -L https://install.lix.systems/lix | sh -s -- install`. On WSL, turn on systemd first: add `systemd=true`
under `[boot]` in `/etc/wsl.conf` and run `wsl --shutdown` from Windows.

Flakes must be enabled:

```sh
nix show-config | grep experimental-features   # should list flakes and nix-command
```

If they aren't:

```sh
mkdir -p ~/.config/nix && echo 'experimental-features = nix-command flakes' >> ~/.config/nix/nix.conf
```

### Git and the repository

```sh
git --version || sudo apt install -y git
git clone https://github.com/chatddx-administration/chatddx.git   # or git@github.com:… over SSH
cd chatddx
```

### The development shell

The shell reads `.env` when you enter it. `.env-devshell` has what it needs, with the database at `dev-db`'s socket:

```sh
cp .env-devshell .env
```

Enter the shell from the repository's root. The first time, it builds the Python environment, which takes a while:

```sh
nix develop
echo ${IN_NIX_SHELL:-outside}   # "impure" inside the shell, "outside" otherwise
exit                            # or Ctrl-D, back to your own shell
```

With [nix-direnv](https://github.com/nix-community/nix-direnv), `direnv allow` enters it whenever you `cd` in.

The commands below run inside the shell, from the repository's root: `.env` names the sample World by a path relative to
it.

### The database

Start the database and apply the migrations:

```sh
dev-db start
chatddx migrate
```

### Tests

```sh
pytest                  # everything
pytest -m "not slow"    # the quick run
pytest -n 4             # everything on 4 workers (pytest-xdist)
```

### Stamping

Each turn of an agent's ends with what it changed in the docs and the translations in the catalogs as stamps pending,
git conflicts to resolve. [docs/parts/dev.md](docs/parts/dev.md) says how to fetch a turn's end, stamp it and merge it.

### The sample world

`worlds/sample` serves two fake vLLM engines on this machine, and a stand-in for a remote one. Write the sample data
into the archive, then share it with alice and give her forks of her own:

```sh
chatddx sync-archive
```

```sh
chatddx person provision alice
```

In a second shell (`nix develop` there too), serve each endpoint's fake engine as its start-up says, till Ctrl-C:

```sh
chatddx fake-engines
```

Then, in the first:

```sh
curl -s http://127.0.0.1:12099/v1/models   # served under the engine's digest
chatddx repl alice
```

```text
use plan
run dutch-10
quit
```

The run streams the fake's answer, scores it and records it.

For runs to look at, with what can go wrong among them, run the sample World's scripted runs instead, without
`fake-engines` running (they serve their own fakes):

```sh
chatddx scripted-runs alice   # each once; --again runs them again, and names pick some
chatddx repl alice
```

```text
runs
replay
```

For a case to review as it would look after weeks of work, with its expectation in a dozen versions and some 40
evaluations scored against them, some faring better than others and a few broken (~80s):

```sh
chatddx scripted-review alice dutch-10   # --gatherings, --versions, --days and --seed shape it
```

For configurations as they would look after weeks of composing, each in a few versions and some 36 gatherings of them,
baselines on the World's baseline cases, reviews of a case and tries on a handful, some versions faring better than
others and a few broken (~90s):

```sh
chatddx scripted-compose alice   # --gatherings, --versions, --days and --seed shape it
```

### The portal

The portal is served with the API, and builds its frontend in `frontend/` with pnpm, which the shell has. With the
sample loaded and `chatddx fake-engines` running in a second shell, give alice a password and serve it:

```sh
chatddx person password alice
chatddx run --watch   # builds the frontend as it changes, till Ctrl-C
```

Then sign in as alice at http://localhost:8000, type a case and pick a model. `pnpm --dir frontend check` checks the
frontend's types.

### Kompismoln's hosts

On the Kompismoln VPN, ask pelle and malborg what they serve:

```sh
chatddx import-engine \
  http://pelle.via-pelle.int.kompismoln.se:12008 http://malborg.via-pelle.int.kompismoln.se:12008 \
  --engines worlds/kompismoln/engines.toml --endpoints worlds/kompismoln/endpoints.toml
git diff
```

No diff means the hosts still serve the engines `worlds/kompismoln` pins. Both are cleared for the sample's vignettes,
so a case can run on them:

```sh
chatddx sync-archive --world worlds/kompismoln
chatddx person provision alice
chatddx repl alice --world worlds/kompismoln
```

```text
use plan
set model qwen3-8b
run dutch-10
quit
```

## License

Copyright Alexander Holmbäck and Olof Silfver, all rights reserved. You may view, inspect and run ChatDDX free of charge
for evaluation, internal testing and non-commercial academic research. You may not copy, modify, publish, distribute,
sublicense or sell it, in whole or in part, without their written permission. It comes without warranty. See
[LICENSE](LICENSE).
