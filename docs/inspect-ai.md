## How it fits chatddx

Not sure yet, ChatDDX uses a pattern based scoring mechanism while inspect-ai
uses LLMs to score LLMs which brings in a new class of challenges.

A provisional inspect-ai integration lives in `src/chatddx/logs/*` but it
relies on a scoring mechanism that has been scrapped.

A new implementation awaits in `docs/backlog/export.md` and until then all
inspect-ai related decisions are on hold.

The research document `docs/research/output-and-scorers.md` was meant to lay
the groundwork for an inspect-ai integration, but has stalled.
