"""
Scoring: what a run's answer comes to, held to its case's targets.

A scorer reads one of the views an output declares, and a target the case
has for what it expects (new-datamodel.md §4): a scorer applies to a run
whose output offers its view and whose case has its target. `score` holds a
run to each scorer that applies, and history keeps what each made of it.
"""
