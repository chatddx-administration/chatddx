# What `plan` says

Written by `chatddx-dev index` from the messages said in `[parts.plan]`'s code in `settings.toml`, its tests left out, as `chatddx locale write` extracts them into the catalogs, sorted by file and then by message whatever its case:

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

## `frontend/src/lib/plan/DiagnosisCard.svelte`

```
Critical
```

`probability`

```
High
```

`probability`

```
Low
```

`probability`

```
Medium
```

## `frontend/src/lib/plan/ManagementPlan.svelte`

```
Acute warning
```

```
Differential diagnoses
```

```
Medical sources
```

```
This information is for educational and reference purposes only and does not replace clinical judgment.
```

## `frontend/src/lib/plan/ManagementSection.svelte`

```
Disposition
```

```
Empirical treatment
```

```
Management
```

```
Workup
```

## `frontend/src/lib/plan/labs.ts`

```
Blood gas
```

```
Cardiac markers
```

```
Coagulation
```

```
Complete blood count
```

```
Electrolytes
```

```
Glucose/Metabolism
```

```
Inflammatory markers
```

```
Liver function
```

```
Renal function
```

```
Thyroid
```
