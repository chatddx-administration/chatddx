# What `factors` says

Written by `chatddx-dev index` from the messages said in `[parts.factors]`'s code in `settings.toml`, its tests left out, as `chatddx locale write` extracts them into the catalogs, sorted by file and then by message whatever its case:

````
## `<file>`

`<its context>`

```
<the message, as written>
```

```
<its plural>
```
````

- A message said in no context has none before it, and one not counted no plural after it.
- A stamp pending is a git conflict, from `<<<<<<< signed` to `=======` as last stamped and on to the `>>>>>>>` closing it as written now, till it is stamped.

## `src/chatddx/factors/base.py`

`refusal`

```
%(value)s is not a language tag such as 'sv' or 'pt-BR'
```

`refusal`

```
duplicates are not allowed
```

`refusal`

```
U+0000 can't be stored
```

## `src/chatddx/factors/cases.py`

`case.drift`

```
the vignette at the source differs from the case's
```

## `src/chatddx/factors/facts.py`

`refusal`

```
no default reasoning level is known
```

`refusal`

```
no sampling is recommended for reasoning %(level)s
```

`refusal`

```
nothing is known about a thinking budget
```

`refusal`

```
nothing is known about reasoning %(level)s
```

## `src/chatddx/factors/lint.py`

`expectation.unchecked`

```
a $ref in the schema can't be resolved: %(ref)s
```

`engine.closure`

```
closure %(closure)s is not a Nix store path
```

`model.revision`

```
revision %(revision)s is not a commit and can move
```

`judge.greedy_seeds`

```
the judge is greedy, so its %(num)s seeds send the same request
```

```
the judge is greedy, so its %(num)s seeds send the same request
```

`language.unknown`

```
the language of %(unknown)s of %(num)s cases is unknown
```

```
the language of %(unknown)s of %(num)s cases is unknown
```

`schema.ref_unverified`

```
the parameters of tool %(tool)s have $ref, which this engine isn't known to resolve
```

`language.mixed`

```
the request is %(language)s, but %(num)s of %(cases)s cases is %(languages)s
```

```
the request is %(language)s, but %(num)s of %(cases)s cases are %(languages)s
```

`language.unknown`

```
the request's language is unknown
```

`schema.ref_unverified`

```
the schema has $ref, which this engine isn't known to resolve; inline_refs@1 removes them
```

`trial.engine_unmatched`

```
the skeleton is worked out for %(worked)s, but the engine serves %(serves)s
```

`judge.model_unmatched`

```
the skeleton is worked out for %(worked)s, but the judge's model is %(serves)s
```

`view.unreachable`

```
view %(view)s picks %(selector)s from the expectation, but its schema has no %(selector)s
```

`vllm.temperature_clamped`

```
vLLM 0.24 raises temperature %(temperature)s to 0.01
```

`vllm.thinking_budget_refused`

```
vLLM 0.24 refuses thinking_token_budget without --reasoning-parser or --reasoning-config
```

`vllm.tools_refused`

```
vLLM 0.24 refuses tool_choice %(choice)s without --enable-auto-tool-choice and --tool-call-parser; for harmony and Mistral models it goes out unconstrained instead
```

`vllm.native_tools_uncallable`

```
with tool_choice auto, vLLM 0.24 constrains the whole answer to response_format, so no tool can be called
```

`vllm.grammar_before_reasoning`

```
without --reasoning-parser, vLLM 0.24 constrains the answer from its first token, so a model can't reason first
```

## `src/chatddx/factors/request.py`

`refusal`

```
%(contract)s contracts need json_schema
```

`refusal`

```
%(insert)s is inserted in both the instructions and the prompt
```

`refusal`

```
%(kind)s cannot use inserts %(inserts)s
```

`refusal`

```
%(model)s: %(refused)s
```

`refusal`

```
%(prompt)s prompt in a %(recipe)s recipe
```

`refusal`

```
%(purpose)s requests cannot use slots %(slots)s
```

`refusal`

```
%(purpose)s requests need slots %(slots)s
```

`refusal`

```
%(ref)s is outside the schema
```

`refusal`

```
%(ref)s refers to itself
```

`refusal`

```
%(ref)s refers to nothing
```

`refusal`

```
a reasoning level is worked out from the model's facts, so it comes without an effort or chat template arguments
```

`refusal`

```
a recommended sampling is worked out from the facts about the recipe's model, which has none
```

`refusal`

```
a tool needs a function with a name, not %(tool)s
```

`refusal`

```
inserts used more than once: %(inserts)s
```

`refusal`

```
no translation into %(into)s for %(texts)s
```

`refusal`

```
no translations into %(into)s
```

`refusal`

```
only an output with a schema can show it
```

`refusal`

```
passthrough may not set %(keys)s
```

`refusal`

```
reasoning %(level)s is worked out from the facts about the recipe's model, which has none
```

`refusal`

```
schema ops need a schema
```

`refusal`

```
slots used more than once: %(slots)s
```

`refusal`

```
the answer tool %(tool)s has the name of a tool in the toolset
```

`refusal`

```
tools must be a list
```

`refusal`

```
whitespace isn't translated
```

## `src/chatddx/factors/select.py`

`refusal`

```
%(text)s: a JSON Pointer starts with /
```

`refusal`

```
%(text)s: a selector is a JSON Pointer or a JSONPath query starting with $
```

`refusal`

```
%(text)s: ~ must be followed by 0 or 1
```
