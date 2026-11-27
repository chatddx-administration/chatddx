# What `portal` says

Written by `chatddx-dev index` from the messages said in `[parts.portal]`'s code in `settings.toml`, its tests left out, as `chatddx locale write` extracts them into the catalogs, sorted by file and then by message whatever its case:

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

## `frontend/src/islands/Home.svelte`

```
%(num)s token
```

```
%(num)s tokens
```

```
65-year-old man with sudden chest pain for 2 hours, radiating to the left arm, nausea, cold sweats. History of hypertension and type 2 diabetes.
```

```
<span class="gradient-text">Emergency</span> <span class="text-foreground">Differential Diagnostics</span>
```

```
<strong class="font-semibold text-foreground">Important:</strong> for testing only. It does not replace clinical judgment or medical consultation.
```

```
A case holds at most %(num)s character; this one has %(given)s.
```

```
A case holds at most %(num)s characters; this one has %(given)s.
```

```
Analyze
```

```
Case
```

```
Configuration
```

```
Current symptoms, duration, severity, and relevant medical history.
```

```
Describe the patient's symptoms and history for a differential and a management plan.
```

```
Enter nothing that could identify a patient. De-identifying a case is the responsibility of the clinician or researcher who enters it.
```

```
Model
```

```
No answer to show
```

```
no run was started
```

`in progress`

```
reading
```

`in progress`

```
saving
```

```
something went wrong
```

```
Symptoms & history
```

`in progress`

```
waiting
```

```
Written in
```

## `frontend/src/islands/scoring.ts`

```
Change what it is asked
```

```
Its request was written by hand, not from a recipe: it is changed in the Library.
```

## `frontend/src/lib/kinds.ts`

`kind`

```
appendix
```

`kind`

```
canary set
```

`kind`

```
case
```

`kind`

```
configuration
```

`kind`

```
engine
```

`kind`

```
expectation
```

`kind`

```
expectation schema
```

`kind`

```
facts
```

`kind`

```
few shot
```

`kind`

```
instructions
```

`kind`

```
judge
```

`kind`

```
model
```

`kind`

```
output
```

`kind`

```
passthrough
```

`kind`

```
prompt
```

`kind`

```
reasoning
```

`kind`

```
sampling
```

`kind`

```
scorer
```

`kind`

```
tool
```

`kind`

```
toolset
```

`kind`

```
translations
```

`kind`

```
trial
```

## `frontend/src/lib/scorer/JudgeEditor.svelte`

```
A scorer asks the version of a judge it names, so the scorers asking this one keep asking the version they ask until they are changed.
```

## `frontend/src/lib/scorer/JudgeFields.svelte`

```
Asked under the model
```

```
Request
```

```
Seeds, a call each
```

## `frontend/src/lib/scorer/JudgeTexts.svelte`

```
Instructions
```

```
its instructions
```

```
its prompt
```

```
Not now
```

```
Nothing changed yet.
```

```
Preview
```

```
Prompt
```

```
Save what it is asked
```

```
Saves %(parts)s as your own.
```

```
Texts
```

```
What %(judge)s is asked, written as you would have it. Saving keeps each text you change as a version of your own, the judge's request with them, and a judge of your own asked through it. The scorers asking %(judge)s keep asking the version they ask until they follow yours, from its page.
```

```
what it is told to answer
```

## `frontend/src/lib/scorer/ScorerViews.svelte`

```
%(judge)s: %(configuration)s under %(model)s, %(seeds)s
```

```
%(judge)s: %(configuration)s, %(seeds)s
```

```
%(metric)s, by a judge
```

```
%(num)s seed
```

```
%(num)s seeds
```

```
a new judge
```

```
a view
```

`a verdict`

```
at
```

```
Compared by
```

```
its judge
```

```
Judge
```

```
Label
```

```
Leave it out
```

```
line by line, as a list
```

```
Move it down
```

```
Move it up
```

```
Not now
```

```
Out of
```

```
Reads of the answer
```

```
Reads of what is expected
```

```
Verdict at
```

```
view %(n)s
```

## `frontend/src/lib/scorer/SelectorPicker.svelte`

`a selector`

```
%(label)s, typed
```

`a selector`

```
typed…
```

## `frontend/src/lib/scorer/TextSegments.svelte`

```
%(label)s, text %(n)s
```

```
Leave out %(name)s
```

## `frontend/src/lib/scorer/judging.ts`

```
%(configuration)s, as it is asked now
```

```
%(handle)s, the weights it holds
```

```
the weights it holds
```

## `frontend/src/lib/scorer/rewriting.ts`

```
%(judge)s's request
```

```
%(part)s: %(problem)s
```

```
its configuration: %(problem)s
```

```
the judge: %(problem)s
```

## `frontend/src/lib/scorer/scorers.ts`

```
%(output)s: %(selected)s
```

`an output`

```
text
```

```
the whole answer
```

## `frontend/src/lib/scorer/selectors.ts`

```
%(field)s where %(by)s is %(value)s › %(member)s
```

```
each of %(field)s
```

```
each of %(field)s › %(member)s
```

## `frontend/src/lib/scorer/texts.ts`

```
its tools' guidance
```

```
the answer
```

```
the answer's schema
```

```
the appendices
```

```
the vignette
```

```
what it is told to answer
```

```
what the view reads of the expectation
```

```
‹the answer's schema›
```

## `frontend/src/lib/thread/Changed.svelte`

`change`

```
added
```

```
Nothing of what it holds; only what is said of it, or its labels.
```

`change`

```
removed
```

## `src/chatddx/portal/cases.py`

```
pick one case or more to take for
```

## `src/chatddx/portal/fields.py`

`refusal`

```
%(field)s isn't JSON: %(error)s
```

```
%(model)s, an earlier engine
```

```
%(name)s, as it is held
```

```
%(name)s, in %(language)s
```

## `src/chatddx/portal/pages.py`

```
can't be done
```

```
Copy this and send it to drift@chatddx.com:
```

## `src/chatddx/portal/review.py`

`refusal`

```
no configuration can run %(case)s now
```

## `src/chatddx/portal/runs.py`

```
an earlier version
```

`a part of a response`

```
content
```

`a part of a response`

```
reasoning
```

`a part of a response`

```
tool call
```

```
tool call: %(name)s
```

## `src/chatddx/portal/scoring.py`

```
%(problems)s: create a new scorer to score with
```

```
%(thread)s, which it is forked from
```

```
latest version
```

`refusal`

```
scorer %(scorer)s has a newer version: look at it again
```

```
version %(at)s of %(last)s
```

```
view %(n)s
```

## `src/chatddx/portal/shelves.py`

```
A configuration with its cases and seeds fixed, so that its run can be repeated.
```

```
A configuration's texts in another language, so that a case is asked in its own language.
```

```
A function a model may call, such as a web search, to look up what it doesn't know.
```

```
A model that grades what no pattern can, asked the same way each time.
```

```
A vignette and the appendices sent with it, so that every model is asked the same.
```

`kind`

```
appendix
```

`kind`

```
canary set
```

`kind`

```
case
```

```
cases
```

`kind`

```
configuration
```

```
Configurations
```

`kind`

```
engine
```

```
Everything sent with a case, put together from parts, so that one can change while the rest hold still.
```

`kind`

```
expectation
```

`kind`

```
expectation schema
```

`kind`

```
facts
```

`kind`

```
few shot
```

```
Fixed probes sent with a run, to catch an engine that changed between runs.
```

```
For request options no other part covers, sent as written.
```

```
Grades answers against expectations, so that configurations can be compared by numbers.
```

```
How much the model thinks before it answers, which can change the answer.
```

`kind`

```
instructions
```

`kind`

```
judge
```

`kind`

```
model
```

```
Operations
```

`kind`

```
output
```

`kind`

```
passthrough
```

`kind`

```
prompt
```

`kind`

```
reasoning
```

`kind`

```
sampling
```

`kind`

```
scorer
```

```
Scoring
```

```
Shipped with the data sets by developers and ops, so that everyone picks from the same; read here, not written.
```

```
So that a run can be repeated: the same configuration, cases and seeds again.
```

```
So that answers can be compared, each graded against what a good answer holds.
```

```
So that every model is asked about the same patients, and graded against the same good answers.
```

```
So that what is sent to a model can be changed a part at a time, and the changes compared.
```

```
The first message, telling the model its role and its task.
```

```
The form expectations are written in, so that a scorer knows where to look.
```

```
The last message, which puts the case to the model and asks for an answer.
```

```
The shape an answer must take, so that it can be read and graded.
```

```
The tools a configuration offers and how to use them, so that a model can look things up.
```

```
To steer how freely the model picks its words, and how long it may answer.
```

`kind`

```
tool
```

`kind`

```
toolset
```

`kind`

```
translations
```

`kind`

```
trial
```

```
Trials
```

```
What a good answer to one case holds, so that answers to it can be graded.
```

```
Worked examples sent before the case, to show the model what is wanted.
```

## `src/chatddx/portal/starting.py`

`refusal`

```
%(name)s is out of date: update it on its page
```

## `src/chatddx/portal/templates/base.html`

```
Compose
```

```
language
```

```
Library
```

```
Pages
```

```
Review
```

```
runs
```

```
Scoring
```

```
Sign out
```

```
World
```

## `src/chatddx/portal/templates/begun.html`

```
a language tag, such as sv or pt-BR
```

```
A new %(kind)s
```

```
A new configuration
```

```
A new expectation
```

```
A new few shot
```

```
A new instructions
```

```
a new judge
```

```
A new output
```

```
A new passthrough
```

```
A new prompt
```

```
A new reasoning
```

```
A new sampling
```

```
A new scorer
```

```
A new toolset
```

```
A new translations
```

```
A new trial
```

```
A thread of your own, from what is given here.
```

```
Breadcrumb
```

```
Contents
```

`a language`

```
into
```

```
labels
```

```
language
```

```
name
```

```
Pick another
```

```
Show its texts
```

```
such as sv
```

`under the field language`

```
The text's, kept with it.
```

```
The texts of %(configuration)s, into %(language)s.
```

```
Translations are begun of a configuration's texts, into a language; its recipe holds them once it picks them, in the Library or in Compose.
```

```
What its views and resources are called, by position, kept with its first version.
```

```
Write it
```

`after the button Write it`

```
Writes a new thread of your own.
```

`after the button Write it`

```
Writes a new thread of your own; a translation left empty isn't kept.
```

## `src/chatddx/portal/templates/case.html`

```
%(owner)s shares it with you. Leaving takes it out of what you see, here and wherever it is offered, until %(owner)s shares it again.
```

```
%(owner)s's
```

```
a language tag, such as sv or pt-BR
```

```
About
```

```
appendices: %(appendices)s
```

```
Breadcrumb
```

```
cases
```

```
Changes
```

```
comma separated
```

```
Contents
```

```
Delete it
```

```
Description
```

```
Edit
```

```
fingerprint
```

```
id
```

```
It is the first.
```

`after the button Delete it`

```
It stays in the runs that used it, and you can restore it from the Library.
```

```
its replacement, at the current vignette: <span class="font-mono text-xs">%(replacement)s</span>
```

```
its vignette's text, on a page of its own
```

`under the field Language`

```
Its vignette's: its cases are sent in it.
```

```
Kind
```

```
language
```

```
Leave it
```

```
Left empty, it goes by its vignette's place.
```

```
logins, comma separated
```

```
name
```

```
newer version
```

```
Next version
```

```
none
```

```
Open the latest
```

```
owner
```

```
Previous version
```

```
Restore
```

```
Review it
```

```
Save what is said
```

```
Shared with
```

```
shared with you
```

```
source
```

```
Store its replacement
```

`a replacement`

```
stored
```

```
Tags
```

```
the one picked
```

```
version %(at)s of %(last)s
```

```
Version %(n)s
```

```
version %(n)s, %(at)s
```

```
Versions
```

```
write yours
```

```
You deleted it: nobody else sees it, and it isn't offered anywhere.
```

```
yours
```

## `src/chatddx/portal/templates/compare.html`

`between the last two names`

```
 and 
```

```
%(case)s: %(held)s of %(of)s
```

```
%(model)s, an earlier engine
```

```
A mean is over the %(num)s item every run holds, with how many of them it has a value for.
```

```
A mean is over the %(num)s items every run holds, with how many of them it has a value for.
```

```
Breadcrumb
```

```
By item, under %(view)s
```

```
Comparing runs
```

```
Held by only some
```

```
none yet
```

```
runs
```

```
Scores
```

```
Some ran under %(models)s at different engines: grouped under it, they aren't like for like.
```

```
To see how runs fare against each other, side by side over the items they all hold.
```

## `src/chatddx/portal/templates/error.html`

```
Back to where you were
```

```
can't be done
```

```
Copy this and send it to drift@chatddx.com:
```

```
newer version
```

```
not allowed
```

```
not found
```

```
Sign in
```

```
something went wrong
```

## `src/chatddx/portal/templates/fields.html`

```
%(field)s, read as
```

```
as JSON
```

```
as text
```

```
Left empty, it is none.
```

```
One a line, in order; none takes one out, and the last adds one.
```

```
One a line; an empty line is none.
```

```
Open the one picked
```

```
pick one
```

```
Whole numbers, one a line or apart by commas.
```

## `src/chatddx/portal/templates/home.html`

```
needs scripts
```

```
The home page's script isn't built.
```

## `src/chatddx/portal/templates/landing.html`

```
A case's vignette beside what a good answer to it holds, its diagnosis, the warnings it should raise, where the patient should go and what must not be missed, each in plain words and as a pattern a scorer can match.
```

```
A configuration that has changed since it ran, or whose runs aren't whole, says so, and Run brings the case up to date: three replicates and a repeat under each configuration.
```

```
A pattern too broad scores every answer well, one too narrow none. Measure takes a single pattern and shows how it has matched the answers it has read: what each of its alternatives found, and what it missed, most frequent first.
```

```
A research rig for emergency care
```

```
A run names the versions it ran under, so a result can always be traced back to what produced it.
```

```
A run of four cases: its model, engine, seed and the rig's build, what was noted of it, and each item's outcome, valid, salvaged or errored.
```

```
A run records what was planned, what was sent and what came back: the model, the engine, the seeds, the build of the rig itself, and every answer, whether valid, salvaged from a broken stream or failed.
```

```
A tour of the portal
```

```
A tour, with fictional cases
```

```
Asked the same question twice, a language model can answer differently, and a model behind an API can change overnight. Nor does it have what makes a colleague's judgement trustworthy: a reputation, insight into its own reasoning, and accountability when it's wrong.
```

```
Before it assists in emergency care, someone has to know how well it performs: on which cases, under which instructions, and how sure that knowledge is. ChatDDX is built to find out, and to hand over what it found with everything needed to check it.
```

```
Below the case, each configuration's score on it is plotted among every other case's under that configuration, field by field, and each replicate is a point that leads to its score.
```

```
cases
```

```
Cases arrive de-identified, from a known source or typed by a clinician, who de-identifies them. A vignette is sent only to endpoints cleared for it, and the record keeps it as a fingerprint.
```

```
ChatDDX measures how accurately large language models produce differential diagnoses and management plans from emergency-care case vignettes, and keeps what it measured so that others can rebuild it and examine it.
```

```
Clinicians and researchers
```

```
Clinicians review cases and write what is expected of them; researchers compose configurations, judges and scorers, and run them. The portal speaks English and Swedish.
```

```
Copyright Alexander Holmbäck and Olof Silfver, all rights reserved.
```

```
engines
```

```
Every exchange is recorded
```

```
Every expectation, prompt, instruction, sampling setting and scorer is kept in every version, each named by its digest. The Library shows what each version changed, and who changed it.
```

```
Everything that can change an answer or its score is a factor, pinned by its digest, the hash of what it holds, and referring to the factors it is made of by theirs.
```

```
expectations
```

```
Factors
```

```
How the case fares under every configuration
```

```
How the case fares: for each configuration, its score on the case plotted among every other case's under it, field by field.
```

```
How well does a language model reason about a patient?
```

```
Is the yardstick right?
```

```
Local or remote models
```

```
Log in
```

```
Measuring the possible warnings of a case: how often each alternative of the pattern matched, and the answers it missed, most frequent first.
```

```
model weights
```

```
Models run on the rig's own hosts with vLLM, or remotely behind OpenAI-compatible APIs, each pinned to the weights and engine it was served with.
```

```
Nothing is overwritten
```

```
Pages
```

```
Patient data on a path of its own
```

```
prompts
```

```
Review
```

```
sampling
```

```
scorers
```

```
seeds
```

```
The cage
```

```
The cases, answers and scores below are scripted: made up to show the portal at work, not results of any model.
```

```
The clinician tightens or widens it right where it is written, before asking how any model fared.
```

```
The environment a run took place in can then be rebuilt from the digests it names, and delivered with its results as a bundle anyone can check offline.
```

```
The Review page: a fictional case of abdominal pain, its vignette beside the expectation written for it, with the latest version's change to the disposition highlighted.
```

```
The versions of an expectation in the Library, each with its time, its author and its digest, below what the latest version changed.
```

```
This site holds fictional cases only.
```

```
What makes a result reproducible
```

```
What went wrong is noted rather than hidden, and the answers are scored by strict patterns or by a language model asked to judge.
```

```
Why measure
```

## `src/chatddx/portal/templates/library.html`

```
%(num)s of yours can't be used.
```

```
%(num)s of yours can't be used.
```

```
%(num)s of yours is out of date.
```

```
%(num)s of yours are out of date.
```

```
%(num)s shared with you
```

```
%(num)s shared with you
```

```
%(num)s yours
```

```
%(num)s yours
```

```
%(shown)s of %(of)s
```

`after a kind's word`

```
, loaded with data sets
```

`after a tag`

```
, picked
```

`after a kind's word`

```
, written in Review
```

```
A trial is begun of the cases picked on the <a href="/library?kind=case">case shelf</a>, with <span class="font-medium">Begin a trial of the picked</span>; or run a configuration on a case straight away in <a class="bench" href="/review">Review</a>.
```

`any owner`

```
any
```

```
Begin a trial of the picked
```

```
deleted
```

`after the tags picked`

```
each of them
```

```
Everything you work with, kept with every version, so that nothing is lost and every run can be traced to what it ran. Your own first.
```

```
Expectation schema
```

```
Find
```

```
Find by name, owner, tag or description
```

```
forked from %(origin)s
```

`after the button Begin a trial of the picked`

```
Its cases are the picked, and its language theirs.
```

```
Kinds
```

```
Kinds: %(kind)s
```

```
language
```

```
latest version
```

```
Library
```

```
loaded with data sets, or typed on Home
```

```
Loaded with data sets: read here, not written
```

```
name
```

```
None is begun here: a case comes from a data set, or is typed on Home.
```

```
none you see
```

```
one you don't see
```

```
Overview
```

```
owner
```

```
pick %(name)s
```

```
Pick every one shown
```

```
Pick none
```

```
Picked
```

```
Purpose
```

```
Restore
```

```
Run the picked
```

```
show every one
```

```
Tagged
```

```
Tags
```

```
Take for the picked
```

`after the button Take for the picked`

```
Takes the expectation shared with you, under the schema, for each picked case: yours stay as they are.
```

`after the button Run the picked`

```
together, as one start.
```

```
under %(schema)s
```

```
under any schema
```

```
Update all
```

```
Write a new one
```

```
Written in Review: read here, not written
```

## `src/chatddx/portal/templates/macros.html`

```
%(case)s in %(language)s
```

```
%(cases)s with %(configuration)s on %(model)s (%(seeds)s)
```

```
%(num)s %(language)s case
```

```
%(num)s %(language)s cases
```

```
%(num)s ahead
```

```
%(num)s ahead
```

```
%(num)s case
```

```
%(num)s cases
```

`outcome`

```
%(num)s completed
```

```
%(num)s completed
```

`outcome`

```
%(num)s errored
```

```
%(num)s errored
```

`outcome`

```
%(num)s invalid
```

```
%(num)s invalid
```

```
%(num)s missing
```

```
%(num)s missing
```

`outcome`

```
%(num)s salvaged
```

```
%(num)s salvaged
```

`outcome`

```
%(num)s stopped
```

```
%(num)s stopped
```

```
%(num)s to go
```

```
%(num)s to go
```

`outcome`

```
%(num)s unread
```

```
%(num)s unread
```

`outcome`

```
%(num)s valid
```

```
%(num)s valid
```

`a part replaced`

```
%(part)s: %(title)s
```

```
%(shown)s of %(of)s
```

```
%(status)s: %(why)s
```

```
<span class="font-medium">%(part)s</span>: yours keeps %(fork)s over %(base)s
```

```
can't be shown
```

```
can't be updated
```

```
can't be used
```

```
Compare
```

```
Compare %(run)s
```

`outcome`

```
completed
```

`outcome`

```
errored
```

`job`

```
failed
```

```
Find
```

```
Find by what it says
```

```
Finished
```

`job`

```
finished
```

`sampling`

```
greedy
```

```
greedy, %(num)s replicate
```

```
greedy, %(num)s replicates
```

```
halting
```

`outcome`

```
invalid
```

```
It asks a judge that is behind.
```

```
Its model, %(model)s, has a new version.
```

```
Its origin has a newer version.
```

```
Its origin is now made for %(now)s, where yours is made for %(was)s: updating moves yours to %(now)s.
```

```
Job
```

```
Left to score
```

```
Next
```

```
no
```

`a part replaced`

```
no %(part)s
```

```
No endpoint here serves its engine.
```

```
none
```

```
Nothing is saved yet
```

```
out of date
```

```
Outcomes
```

```
page %(at)s of %(of)s
```

`of a list`

```
Pages
```

```
paused
```

```
Previous
```

```
queued
```

```
Run
```

`outcome`

```
salvaged
```

```
Score again
```

```
seed %(seeds)s
```

```
seeds %(seeds)s
```

```
Started
```

`job`

```
stopped
```

`outcome`

```
stopped
```

```
Tabs
```

```
The facts about %(model)s were corrected where they change what it sends.
```

`after the button Compare`

```
the runs ticked, side by side over the cases they share
```

```
under way
```

`outcome`

```
unread
```

```
Update
```

`outcome`

```
valid
```

```
What it was made from has moved on
```

```
What you typed is kept below, and what was refused is marked there: set it right and send it again.
```

```
yes
```

```
Yours and its origin both change %(paths)s: updating keeps yours there.
```

## `src/chatddx/portal/templates/review.html`

```
<a class="begin" href="/cases/%(family)s#holds">Write yours</a> in the Library.
```

```
all
```

```
Brings the case as it is saved to three replicates and a repeat under each of your configurations: runs what has no runs or has changed, goes on with what stopped, and scores again what isn't scored against the expectation as it is
```

```
can't be checked
```

```
Case
```

```
cases
```

```
Change it
```

```
Delete
```

```
Deletes the appendix %(appendix)s: this case and those under it leave the list
```

```
Expectation
```

```
Expectation schemas
```

```
Filters
```

`after the button Move yours here`

```
from %(case)s, which it leaves: only if it still holds with this case's appendices
```

```
In sync
```

```
Languages
```

```
Measuring the expectation
```

```
Move yours here
```

```
Needs repairing
```

```
needs scripts
```

```
No case to review tagged %(tags)s.
```

```
No case to review.
```

```
none
```

```
none expected
```

```
none of yours
```

```
none you see
```

```
Review
```

`a button`

```
Run
```

```
Saving
```

```
Scores
```

```
shared with you
```

```
Show in the Library
```

```
Tags
```

```
Take %(thread)s
```

```
The vignette is also on <a href="/cases/%(family)s/vignette">a page of its own</a>.
```

```
yes
```

```
yours
```

## `src/chatddx/portal/templates/run.html`

```
%(model)s, an earlier engine
```

```
%(name)s, in %(language)s
```

```
%(num)s tool round before the last call.
```

```
%(num)s tool rounds before the last call.
```

```
%(sent)s in, %(got)s out
```

```
(cut short)
```

```
a language unknown
```

```
Breadcrumb
```

```
Case
```

```
cases
```

```
Checked now
```

```
Configuration
```

```
Engine
```

```
Findings
```

```
Finished
```

```
Halt
```

```
Items
```

```
Job
```

```
language
```

```
Left to score
```

```
Mean
```

```
Model
```

```
none yet
```

```
not scored
```

```
Nothing could be read.
```

```
Outcome
```

```
Recorded
```

```
Reload the page to see how far it has come.
```

```
Replicate
```

```
Response
```

```
Resume
```

`after the button Resume`

```
resuming sends what it lacks.
```

```
Rig
```

```
Run
```

```
Run again
```

```
runs
```

```
Score again
```

```
Scores
```

```
seeds
```

```
Started
```

```
Started with
```

```
the answer
```

```
Tokens
```

```
Trial
```

```
under way
```

```
unfinished
```

## `src/chatddx/portal/templates/runner.html`

```
%(num)s case
```

```
%(num)s cases
```

```
%(num)s seed
```

```
%(num)s seeds
```

```
a language unknown
```

```
at %(endpoint)s: %(concurrency)s at once, %(order)s
```

```
concurrency
```

`concurrency`

```
each endpoint's
```

`order`

```
each endpoint's
```

```
Left empty, each endpoint's execution; a shuffled order's seed is drawn. The trials run as one start, queued as your job.
```

```
order
```

`trials`

```
Run it
```

```
Run them
```

```
Run the picked
```

```
Score it once it is finished
```

```
version
```

```
version %(n)s, %(at)s
```

```
version of %(name)s
```

## `src/chatddx/portal/templates/runs.html`

```
%(num)s queued
```

```
%(num)s queued
```

```
%(num)s under way
```

```
%(num)s under way
```

```
all
```

```
All runs
```

```
Find
```

```
Find by configuration, part, case or model
```

```
Left to score
```

```
Newer
```

```
No worker is running, so nothing queued is taken.
```

```
Older
```

```
page %(at)s
```

`of a list`

```
Pages
```

```
Pause
```

```
paused
```

```
Pausing holds what is queued and queues the runs under way again after the items being sent. Stop takes what is queued out, its runs left unfinished to be resumed; once nothing is queued, Stop now halts the runs under way.
```

```
Resume
```

```
runs
```

```
show every one
```

```
Stop
```

```
Stop now
```

```
Your queue
```

```
Your runs, newest first, to follow what is under way and open what has finished.
```

## `src/chatddx/portal/templates/score.html`

```
%(num)s message
```

```
%(num)s messages
```

```
%(view)s for %(case)s
```

```
(cut short)
```

```
And %(count)s older.
```

```
Answer
```

```
At %(at)s: %(value)s
```

```
Breadcrumb
```

```
By %(judge)s, as its request is rebuilt from what it pins.
```

```
By %(scorer)s, replicate %(replicate)s.
```

```
can't be shown
```

```
Detail
```

```
Expectation
```

```
Metric
```

```
none
```

```
none yet
```

```
none, it is greedy
```

```
not scored by this scorer
```

```
Parameters
```

```
Picked from the answer
```

```
Picked from the expectation
```

```
Reading
```

```
Rebuilt now, this isn't the request that was sent: what it pins, or the code, has changed since.
```

```
Repeats
```

```
Replicate
```

```
Replicates
```

```
Request
```

```
Run
```

```
Score
```

```
Scored
```

```
Scored again now, this comes to %(value)s: the code scores it otherwise than when it was scored.
```

```
Seed
```

```
seed %(seeds)s
```

```
seeds %(seeds)s
```

```
Split
```

```
the answer
```

```
The same request in other runs of yours: the same skeleton, engine, cleanup and case, under the same seed.
```

```
under another scoring
```

```
Value
```

```
Verdict
```

## `src/chatddx/portal/templates/scoring.html`

```
%(case)s, replicate %(replicate)s
```

```
%(expected)s of the %(num)s case you see
```

```
%(expected)s of the %(num)s cases you see
```

```
<a class="bench" href="%(href)s">Compare them</a> over the cases they share.
```

```
a judge
```

```
a scorer
```

```
a scorer grading against %(schema)s
```

```
A scorer is <a class="begin" href="/library/new?kind=scorer">written in the Library</a>.
```

```
A seed gave none
```

```
A view reads a configuration's answers where its output's schema offers what the view picks; a case is graded only where you expect something of it, which is written in Review.
```

```
About
```

```
Agreement
```

```
an earlier version
```

```
Answer
```

```
Ask its latest version
```

```
Ask its latest version, in a scorer of your own
```

```
Asked by
```

```
Asked under
```

```
Case
```

```
Configurations left out
```

```
Configurations read
```

```
Coverage
```

```
Disagreements
```

```
Each compares what it picks from an answer with what it picks from the expectation, by a metric of %(code)s at version %(version)s, given %(params)s, holding %(resources)s.
```

```
Each compares what it picks from an answer with what it picks from the expectation, by a metric of %(code)s at version %(version)s, given %(params)s.
```

```
Each compares what it picks from an answer with what it picks from the expectation, by a metric of %(code)s at version %(version)s, holding %(resources)s.
```

```
Each compares what it picks from an answer with what it picks from the expectation, by a metric of %(code)s at version %(version)s.
```

```
Each one you see, yours first: the scorers by the expectation schema they grade against, the judges by the model they are asked under.
```

```
Expectation
```

```
Expected
```

```
Findings
```

`after the button Ask its latest version`

```
in %(scorer)s's %(views)s
```

`after the button Ask its latest version`

```
in %(scorer)s's %(views)s, forking it
```

```
in %(unit)s
```

```
Items judged
```

```
its page in the Library
```

```
Its request is a judge's configuration, written and saved in Compose; a scorer asks the version of a judge it names until it follows another, below.
```

```
Judge
```

```
Judges
```

```
Mean
```

```
Metric
```

```
needs scripts
```

```
No expectation of yours: %(num)s
```

```
No expectation of yours: %(num)s
```

```
none yet
```

```
none you see
```

```
Over the latest score of your runs under each scorer asking any version of it: an item's seeds agree when each gave the same value, which its view's metric reads of their verdicts.
```

```
Parameters
```

```
Read by
```

```
Read with
```

```
reading %(schema)s
```

```
Request
```

```
Run
```

```
Runs left to score are on <a class="bench" href="/runs?left=true">Runs</a>.
```

```
saved %(at)s by %(by)s
```

```
Scorer
```

```
Scorer · view
```

```
scorers
```

```
Scorers and judges
```

```
Scores
```

```
Scoring
```

```
Seeds, a call each
```

```
Served now at
```

```
Show
```

```
Slots
```

```
split %(split)s
```

```
Texts
```

```
the whole answer
```

```
the whole expectation
```

```
To choose from, several of yours: %(cases)s
```

`a model`

```
under %(model)s
```

```
Verdicts
```

```
View
```

```
Views
```

```
With its first seed and the answer as a placeholder, and the expectation as one: a view fills them with what it picks of each.
```

```
With its first seed and the answer as a placeholder, and what %(view)s picks of what is expected of %(case)s: a view fills them with what it picks of each.
```

```
Your runs scored by this version, newest first, each by the mean of its latest score under each view.
```

## `src/chatddx/portal/templates/sign-in.html`

```
Login
```

```
Password
```

```
Sign in
```

```
Wrong login or password.
```

```
You were signed in, but your browser didn't keep the session. A browser keeps it only where the portal is reached over HTTPS or at localhost, with cookies allowed: open the portal so and sign in again.
```

## `src/chatddx/portal/templates/starting.html`

```
Breadcrumb
```

```
Each trial's version at the endpoint serving its engine.
```

```
none
```

`trials`

```
Run it
```

```
Run them
```

```
Run trials
```

```
Trials
```

```
Trials are picked on the <a href="/library?kind=trial">trial tab</a> of the Library.
```

## `src/chatddx/portal/templates/taken.html`

```
%(owner)s's
```

```
Breadcrumb
```

```
none you see
```

```
Outcomes
```

```
shared by several, to take from one: %(owners)s
```

`expectations`

```
Taken
```

```
taken, into <a href="/threads/%(thread)s">your thread %(thread)s</a>
```

```
Under %(schema)s, for each picked case.
```

```
yours
```

## `src/chatddx/portal/templates/thread.html`

```
%(owner)s shares it with you. Leaving takes it out of what you see, here and wherever it is offered, until %(owner)s shares it again.
```

```
<a class="bench" href="/compose/%(thread)s">Open it in Compose</a>, where its texts and settings are written and saved
```

```
<a class="bench" href="/lab/run?trial=%(thread)s">Run it</a>
```

```
<a class="bench" href="/scoring/%(thread)s">Weigh it on Scoring</a>, beside the scorers and judges it works with and how they scored
```

```
a language tag, such as sv or pt-BR
```

`after the button Fork it as it is`

```
A thread of your own, starting from its latest version, which follows this one's changes when you ask.
```

```
About
```

`change`

```
added
```

```
Against version %(n)s, the one it was saved over.
```

```
Breadcrumb
```

```
Change it
```

```
Changes
```

```
comma separated
```

```
Contents
```

```
Delete it
```

```
Description
```

```
Edit
```

```
Findings
```

```
Fork it
```

```
Fork it as it is
```

```
Forked from
```

```
It is the first.
```

`after the button Delete it`

```
It stays in the runs that used it, and you can restore it from the Library.
```

```
Kind
```

```
labels
```

```
language
```

```
Leave it
```

```
Left empty, it goes by its title.
```

```
logins, comma separated
```

```
Make it the latest
```

```
name
```

```
newer version
```

```
Next version
```

```
none of yours
```

```
Nothing of what it holds; only what is said of it, or its labels.
```

```
one you don't see
```

```
Open the latest
```

```
owner
```

```
Previous version
```

```
Recipe
```

`change`

```
removed
```

```
Request
```

```
Restore
```

```
runs
```

```
Save it
```

```
Save what is said
```

```
saved %(at)s by %(by)s
```

`after the button Save it`

```
Saves a new version of it.
```

```
Shared with
```

```
shared with you
```

```
Tags
```

`under the field language`

```
The text's, kept with it.
```

```
version %(at)s of %(last)s
```

```
Version %(n)s
```

```
version %(n)s, %(at)s
```

```
Versions
```

```
What its views and resources are called, by position, kept with this edit.
```

```
World
```

```
You deleted it: nobody else sees it, and it isn't offered anywhere.
```

## `src/chatddx/portal/templates/translations.html`

```
<a href="%(tried)s">try it with the latest in Compose</a>
```

```
a language tag, such as sv or pt-BR
```

```
an earlier version
```

```
Another language
```

```
another, such as de
```

```
cases you see are in it
```

```
Held by %(configurations)s: what they send that it doesn't translate yet comes first.
```

`languages`

```
Into
```

```
it translates into it
```

```
Its leading or trailing whitespace isn't its source's.
```

```
Languages
```

```
Leave it out
```

```
No configuration you see holds it, so it is offered no text to translate.
```

```
none
```

```
Not sent by the configurations holding it
```

```
not translated yet
```

```
Save it
```

`after the button Save it`

```
Saves a new version of it; a translation left empty or out isn't kept.
```

```
started from “%(similar)s”
```

```
Translate into it
```

```
Translation
```

## `src/chatddx/portal/templates/updated.html`

```
A new version of each
```

```
Breadcrumb
```

```
Library
```

```
none
```

```
Not updated
```

```
now made for %(now)s, was %(was)s
```

```
Updated
```

```
What of yours was behind what it was made from, updated in this order so that what is read is updated before what reads it.
```

## `src/chatddx/portal/templates/vignette.html`

```
%(case)s: vignette
```

```
Breadcrumb
```

```
Its vignette, %(id)s in %(source)s.
```

```
the vignette
```

```
This isn't the text the case was made from any more.
```

## `src/chatddx/portal/templates/world.html`

```
%(concurrency)s, %(order)s, %(retries)s
```

```
%(gpu)s, compute capability %(capability)s, %(vram)s MiB, driver %(driver)s
```

```
%(name)s from %(provider)s
```

```
%(num)s at once
```

```
%(num)s at once
```

```
%(num)s retry
```

```
%(num)s retries
```

```
%(num)s token
```

```
%(num)s tokens
```

```
%(num)s vignette
```

```
%(num)s vignettes
```

```
%(repo)s at revision %(revision)s, %(num)s file
```

```
%(repo)s at revision %(revision)s, %(num)s files
```

```
%(rig)s at %(revision)s
```

```
%(total)s billion
```

```
%(total)s billion, %(active)s billion active
```

```
<span class="font-medium">%(judge)s</span> to %(handle)s
```

```
<span class="font-mono text-xs">%(path)s</span>, a vignette a <span class="font-mono text-xs">%(suffix)s</span> file
```

```
a remote API's model
```

```
Address
```

```
API
```

```
Arguments
```

```
as %(like)s
```

```
as many as are typed
```

```
Bindings
```

```
Canaries
```

```
Capacity
```

```
Chat template
```

```
Chat templates
```

```
Cleaned up by
```

```
Cleared for
```

```
Cleared for it
```

```
Configurations are made for
```

```
Context
```

```
Contract
```

```
default
```

```
Description
```

```
Directory
```

```
Endpoint
```

```
Endpoints
```

```
Engine
```

```
engines
```

```
Environment
```

```
Facts
```

```
Family
```

```
for %(handles)s
```

```
Handle
```

```
Handles
```

```
Hardware
```

```
History
```

```
Holds
```

```
Host
```

```
Hosts
```

```
its directory can't be read: %(why)s
```

```
its versions
```

```
Judges are bound
```

```
kept at <span class="font-mono text-xs">%(path)s</span> on %(host)s
```

```
Level
```

```
Licence
```

```
listening on %(bind)s
```

```
Model
```

```
Models
```

```
Names to pick a model by, which stay the same when ops put new weights under them.
```

```
no
```

```
no endpoint serves it
```

```
no endpoint serves its weights, so it can't be picked
```

```
no handle here holds it
```

```
none
```

```
none: a remote engine
```

```
none: it takes no secret
```

```
not sensitive
```

```
Output contracts
```

```
Parameters
```

```
pinned by
```

```
Quantization
```

```
Read from
```

```
Reasoning
```

```
Recommended sampling
```

```
refused: %(why)s
```

```
refused: %(why)s, so %(nearest)s is asked for instead
```

```
Runs by default
```

```
Runtime
```

```
Secret variable
```

```
sends %(sent)s
```

```
sensitive
```

```
Served by
```

```
serves %(model)s
```

```
So that a data set's configurations and judges run on models this portal serves.
```

```
Sources
```

```
taken
```

```
taken, adding nothing to the request
```

```
taken: %(note)s
```

```
Takes typed cases
```

```
texts typed into the database
```

```
The machines that run local engines, so that the files an engine pins can be found on them.
```

```
the model's %(config)s
```

```
The World
```

```
thinking budget
```

```
vLLM %(version)s on %(gpu)s
```

```
vLLM %(version)s, from <span class="font-mono text-xs">%(closure)s</span>
```

```
Weights
```

```
What answers requests, pinned by all that can change an answer, so that a run says exactly what answered it.
```

```
What is known about each model, so that a configuration asks it only for what it can do.
```

```
What the portal runs on that you don't write, so that every run can say what answered it and where its cases came from.
```

```
Where
```

```
Where each engine is reached, so that a run knows where to send, how much at once and which cases may go.
```

```
Where the vignettes come from, so that a sensitive one goes only where it is cleared; none is shown here.
```

```
World
```

```
yes
```

## `src/chatddx/portal/threads.py`

`refusal`

```
a fork is named
```

`refusal`

```
configuration %(thread)s is written by hand: it has no recipe to pick parts of
```

`purpose`

```
generation
```

`purpose`

```
judge
```

`refusal`

```
labels: %(refused)s
```

## `src/chatddx/portal/titles.py`

```
%(case)s (earlier)
```

```
%(case)s + %(num)s appendix
```

```
%(case)s + %(num)s appendices
```

```
%(case)s with %(appendices)s
```

```
expectation for %(case)s
```

## `src/chatddx/portal/translations.py`

```
%(configuration)s has no recipe whose texts to translate
```

```
translations hold a language or more: translate a text, or delete them
```
