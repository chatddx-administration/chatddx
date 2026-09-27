# The chatddx datamodel

This document describes the underlying data structure of ChatDDX.

For using it, see `portal.md` (admin interface), `repl.md` (the shell),
`inventory.md` (the files that seed the database) or
`api.md` (how external tools may connect).

## 1. The classes of data

ChatDDX have two classes of data, both immutable and append-only: Repo and
History. History is the laboratory ledger that logs experimental runs,
conversations and scores. Repo is a collection of 16 versioned controlling factors:
```
case
client
coercion
configuration
instruction
llm
machine
os
output
reasoning
sampling
scorer
serving
stack
tool
toolset
```

Their integrity is assured by fingerprinted Trails (data) and associated Branches (metadata).

A Branch is called "branch" because it behaves like a git branch, with a timeline
attached to its name. So there's a head (canon), and it can be commited to, but it can't
be changed.

## 2. Guiding principles
We want to be able to generate thousands of experiments on whatever inference server we
come by, and find which factors improve their capability in speed and accuracy.
Each experiment reproducible, tomorrow or in five years, so that we can begin to lay the foundation
of knowledge about what an LLM can be trusted with and what it shouldn't.

This is a challenge, in particular grouping controlling factors in such a way that they
represent something meaningful *and* can be reliably applied across models and machines.
Due to the chaotic ecosystem that is LLMs 2026, the path ChatDDX took is a patchwork of
careful compromises to cater to our context specifically: Producing accurate management plans
for emergency healthcare on local, open weight models. This document describes every part
in detail and how they fit together.
