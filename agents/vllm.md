# vLLM for chatddx

Sep 26, 2026

What vLLM does that chatddx has had to meet, why, and what to do about it.
The version is 0.24.0; what is said of its code is read from that tag, and
of xgrammar's from 0.2.8, the latest release vLLM 0.24.0 takes.

## gpt-oss writes newlines without end, held to a schema

### What we see

On malborg, gpt-oss-20b answering in native mode (`response_format` with a
JSON schema, as `plan` resolves to there) at times writes its answer and
then newlines, token after token, and never finishes. It showed in a batch:

```
alice plan×gpt-oss-20b@malborg> batch dutch-fall
case          tokens  outcome    disposition_mentions  reciprocal_rank  warning_mentions
DutchFall10w    1783  valid      1                     0                0
Dutchfall11w    2426  valid      1                     0                0
Dutchfall12w  ~13800
```

and Dutchfall12w counted on. Nothing but the context stops it: a request
without `max_tokens` may take all of `max-model-len` less its prompt
(131072 tokens on malborg, as its inventory has it), minutes of the GPU
spent on newlines.

### Why

A native request is held to its schema by a grammar, vLLM's structured
outputs: with the default backend (`auto`), xgrammar's, wherever xgrammar
can compile the schema. With a reasoning parser the grammar holds
only the answer: it starts once the parser sees gpt-oss's final channel
open (`<|channel|>final … <|message|>`), and the thinking before it is
free. Harmony doesn't write `response_format` into the prompt, so gpt-oss
knows the schema from chatddx's schema prompt alone; the grammar is what
holds it to it.

vLLM compiles the schema with `any_whitespace` on unless it is told
otherwise (`disable_any_whitespace`, below). xgrammar then lets
`[ \n\r\t]*`, any amount of whitespace, in at every separator of the
document: after `{` and `[`, around `:` and `,`, and before `}` and `]`.
xgrammar can bound it (`max_whitespace_cnt`); vLLM 0.24.0 passes no bound.
Until the document closes, the grammar masks every token it doesn't allow,
gpt-oss's own way of ending (`<|return|>`) among them. Once it closes, the
grammar allows a stop token and nothing else, not even whitespace: the
newlines can't come after the answer, only inside it.

So, most likely: gpt-oss has written the last value and would end, the
grammar holds its end back, and the likeliest token left is a newline,
which the grammar lets in. Each newline makes the next one likelier, and
the closing brace never comes. On screen the answer looks whole, with
newlines after it; in the stream, its last brace is missing. A run
chatddx stopped keeps its responses byte for byte
(`/api/runs/{run}/exchange`): where the last of the content before the
newlines is the last value (`]` or `"`), not `}`, this is it.

### What chatddx does about it

- A run is stopped where the model streams 100 tokens in a row with
  nothing but whitespace in them (`RUNAWAY` in `runtime/run.py`). Its
  stream is closed, and vLLM, hearing the client go, aborts the request.
- What came before stands as its answer: the JSON closed where it stops,
  a string it hadn't finished left out. It is judged, read and scored as
  any other, and the run is flagged, its error
  `stopped: nothing but whitespace for 100 tokens`. A batch says so on
  the case's line and goes on.
- The fake vLLM does it when told to (`chatddx fake-vllm --runaway`, or
  `FakeTransport(runaway=True)` in a test): it leaves a document's closing
  brace out, or ends a text, and goes on with newlines till `max_tokens`
  or its context runs out.

This is a net, not a fix: a runaway still costs 100 tokens, and its
answer is one chatddx closed.

### The fix: serve without free whitespace

`disable_any_whitespace` makes vLLM compile every JSON schema compact, with
no whitespace between its tokens. After the last value the grammar allows
only what closes the document or goes on with it, and nothing to run on
with. In vLLM 0.24.0:

- **It is the server's, not the request's.** The request's
  `structured_outputs` has a `disable_any_whitespace` of its own, but
  neither xgrammar nor guidance reads it: both read the engine's config.
  It can't be sent from a configuration; it goes in the serving.
- **It needs the backend named.** vLLM refuses it with `auto`
  ("disable_any_whitespace is only supported for xgrammar and guidance
  backends"). Named, xgrammar gives up `auto`'s fallback: a schema it
  can't compile is refused, not handed to guidance or outlines. Run each
  of the inventory's schemas through a batch once the serving has
  changed.

```
vllm serve … \
  --structured-outputs-config '{"backend": "xgrammar", "disable_any_whitespace": true}'
```

or, the same, `--structured-outputs-config.backend xgrammar
--structured-outputs-config.disable_any_whitespace true`.

It changes what the model is held to, so in the inventory it goes with the
serving's `args`, which are fingerprinted (`malborg.toml`):

```toml
[serving."gpt-oss-20b@malborg".args]
structured-outputs-config = { backend = "xgrammar", disable_any_whitespace = true }
```

The serving, and with it the stack, then has a fingerprint of its own, so
runs from before the change and after it don't pass for one another. It
does change more than the runaways: gpt-oss no longer lays its JSON out as
it would, and what it writes can shift. A batch on the same cell before
and after says by how much, and whether a run is still stopped for
whitespace.
