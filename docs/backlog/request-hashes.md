# Request hashes

Not built. A run keeps the exact bodies it sent and got back, byte for
byte, but nothing hashes them yet. This note gathers what was designed for
request hashes, and a proposal for building them. The design they come
from is `design/data-generation.md` §3.

## What they are for

Trail fingerprints identify what was authored. Request hashes identify
what was sent, and they belong to each run: a trial can be run on a later
client, or after an LLM's facts changed, and send something else.

- **An LLM's facts can change a request without moving any trail
  fingerprint.** That is by design, since an LLM is its snapshot, and the
  request hash catches it.
- **An output's views can change its fingerprint without changing a
  request.** Two outputs that differ only in their views send the same
  request, and read it differently.
- **Collapses show as equal hashes.** Two cells that resolve to the same
  request on one stack are one treatment. Resolution already names the
  intent a variation collapses into where the LLM's facts declare it (Qwen3
  has no effort levels, so reasoning `low` and `high` both resolve to
  thinking on). Equal skeleton hashes would show every other collapse, at
  no cost.

## The levels (`data-generation.md` §3.1)

| Level | Covers | Used for |
|---|---|---|
| Contribution | each slice's effect on the request once resolved for a given stack | comparing configurations: two contribution vectors that differ in one position give a single-factor contrast, and a position that collapses shows as equal |
| Skeleton | the request with the case left as a placeholder | equal skeletons on the same stack mean identical requests for every case, since the case reaches the request only through the instruction's `case` variable, which a template may place but never branch on |
| Request | each run's exact body | proving what was asked |

## Canonical form (`data-generation.md` §3.2)

- **JSON Canonicalization Scheme (RFC 8785), with one exception:** anything
  whose order carries meaning, such as a JSON Schema's `properties`, which
  a constrained decoder emits in that order, is encoded as ordered pairs
  first, so the sort can't reach it. Trail fingerprints already work this
  way.
- **Resolved values, not blanks:** resolution writes down every value it
  relied on.
- **Left out:** transport (timeouts, retries, streaming, headers, request
  ids, API keys), the seed, which is the trial's, and names, owners and
  tags. inspect-ai makes the same cut for its cache key.
- **Two hashes per request:** the hash of the exact bytes, which proves
  what was sent, and the canonical hash, which compares across client
  versions where the SDK serializes the same request differently.

## Rules that keep them securable (`data-generation.md` §3.3)

1. Every hash names its scheme and version: `cddx-request/1:sha256:…`, as
   trail fingerprints name `cddx-trail/1`.
2. Every hash is stored next to its canonical input, so it can be
   recomputed.
3. Every run keeps its raw request and response bytes (it does).
4. Identities are single, write-once fields.

## Proposal

- **Per run and request:** the exact-bytes hash and the canonical hash,
  stored beside the bytes the run already keeps.
- **Per resolved cell:** the skeleton hash, which `show` prints with the
  cell.
- **Collapses:** the repl's `reasoning` command, which already resolves
  every reasoning variation on each stack, marks as collapsed the cells
  whose skeletons are equal. `show` resolves one cell, and has nothing to
  compare it with.
- **Contribution hashes** wait until something compares configurations
  slice by slice.
