"""
The repl: run cases on a cell, and watch the LLM answer as it goes.

A cell is a configuration joined to a stack (new-datamodel.md §5), and the
repl holds one the way psql holds a database: `use` puts a configuration in
it, `on` a stack, `set` another variation of one of its slices, and `run`
runs it on a case. Every run is recorded: `runs` lists them, and
`replay` shows one again as it streamed. `save` keeps the cell as a
configuration of the identity's own.

`shell` holds the repl's state and what the identity calls things, `cell`
the cell, and `commands` names each command, what it takes and the
function that carries it out, one module to each group of them: `listing`,
`choosing`, `inspecting`, `running` and `reviewing`. `render` writes a run
out, and `cli` reads the lines.
"""
