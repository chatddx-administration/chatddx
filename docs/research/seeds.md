# Seeds

Why chatddx seeds its runs by default, what that costs, and what was learned
in building it. What is built is in `datamodel.md` §8 and `repl.md`; what a
seed can say of a batch is in `design/post-endgame.md`.

## What was decided

A run is seeded unless someone says otherwise. The repl holds a seed, drawn
at random as it starts and shown in its prompt (`alice
plan×qwen3-8b-awq@pelle #48213>`). Every run sends it; `seed` draws a fresh
one, `seed N` holds N, and `seed none` runs unseeded; `run CASE SEED` is
that run's alone. So runs under one seed line up across cases, and a run
under a seed already used is another run of the same trial. Refreshing the
seed is one word, so a held seed never quietly turns replicates into
repeats.

## Why seed by default

From vLLM's main branch at the time of writing:

- **Only a seed can repeat a run.** With batch invariance on, vLLM itself
  warns that "random sampling without an explicit seed may not be batch
  invariant". A seed is necessary, not sufficient: the same hardware, vLLM
  version, request and batch invariance are needed too
  (`design/data-generation.md` §1).
- **Unseeded isn't independent either.** An unseeded request draws from
  the server's own generator, seeded once at start (`--seed`, 0 by
  default), so what it draws depends on the server's history, which
  nothing records.
- **A seeded draw is a trial of its own,** and a seed run again is a check
  that it holds, or a retry of one that errored. Unseeded runs of a cell on
  a case all fall into one trial, though each is a different draw.

## What it costs

- **Throughput.** vLLM gives a seeded request a generator of its own
  (`torch.Generator`). On CUDA, one seeded request in a step sends the
  whole step from FlashInfer's top-k and top-p kernel to PyTorch's, and
  draws its noise in a Python loop per seeded request. To be measured
  alongside batch invariance's own cost (`design/data-generation.md` §6).
- **Trials grow with seeds,** one per seed, cell and case: a held seed adds
  one trial per case, not per run.
- **Greedy sampling ignores the seed.** A seeded run at temperature 0, or
  top-k 1, would claim a reproducibility the seed has no part in, and a
  second seed would repeat it rather than replicate it. So the repl
  refuses it, and says `seed none` runs it unseeded.
- **One seed across cells correlates them.** The same seed reuses the same
  noise, which helps a paired comparison of two cells on one LLM, and is
  why replicates need seeds of their own.

## Learned in building it

- **Greedy is known only from what resolution writes:** a temperature of 0
  or a top-k of 1, the variation's own or the LLM's generation config as
  its facts declare it. A server whose own defaults are greedy goes
  unseen.
- **Five digits read well and collide sooner:** two sessions drawing the
  same seed on the same cell and case make a repeat where a replicate was
  meant, about one chance in 100,000 per pair.
- **Tests hold the seed:** the repl takes one, or none, so a test's output
  doesn't change with a draw. The fake vLLM reads a seed back in its
  thinking, and ignores it otherwise.
- **A replicate is a fresh seed,** and the cases run again under it.
