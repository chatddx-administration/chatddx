# `runner`

Written by `chatddx-dev index` from `[parts.runner]`'s code in `settings.toml`, an entry for each public name, sorted alphabetically whatever its case, so that a class's members follow it, a language's after another's:

Python:

```
## `<name>` `@<decorator>` `[<type parameters>]` `(<bases>)`
`<file>:<qualified name>`

* `<parameter or field>: <type> = <default>`
* ∟`<return type>`

Raises:
1. `<exception>`: `<arguments>` (from `<exception caught>`, through `<private helper>`, in a `ValidationError`)

Finds:
1. `<code>`: `<message>` (`<level>`, from `<exception caught>`, through `<private helper>`)
```

- A constant or a type alias is its definition instead of bullets; a class and its `__init__` leave out ∟, and a method its instance; `*`: the parameters after it are keyword-only, `/`: those before it positional-only.
- Raises and Finds are the function's own and its private helpers', in the order the code reaches them, each once, a `Whoops` left out; what a public function it calls raises is in that function's entry.
- Text is quoted, a value in it as `{<expression>}`, and an argument that isn't text is as written; a finding is a warning unless it gives its level.

- A stamp pending is a git conflict, from `<<<<<<< signed` to `=======` as last stamped and on to the `>>>>>>>` closing it as written now, till it is stamped.

## `admit`
`src/chatddx/runner/gate.py:admit`

* `inventory: Inventory`
* `get: Resolver`
* `endpoint: str`
* `trial: Trial`
* `judged: tuple[Judge, str] | None = None`
* `timeout: float = 10.0`
* ∟`str | None`

Raises:
1. `Refused`: `"endpoint {endpoint!r} needs the secret in ${credential}, which isn't set"` (through `_secret`)
2. `Self`: `"endpoint %(endpoint)s can't be confirmed: %(error)s", endpoint=repr(endpoint), error=str(e)` (from `(StructuralError, OSError)`, through `raw`)
3. `Self`: `"endpoint %(endpoint)s can't be confirmed: it serves nothing at %(url)s, not %(expected)s", endpoint=repr(endpoint), url=url, expected=expected` (through `raw`)
4. `Self`: `"endpoint %(endpoint)s can't be confirmed: it serves %(served)s at %(url)s, not %(expected)s", endpoint=repr(endpoint), served=", ".join(listed), url=url, expected=expected` (through `raw`)

## `assemble`
`src/chatddx/runner/wire.py:assemble`

* `chunks: Iterable[Chunk]`
* ∟`dict[str, JsonValue]`

## `bar`
`src/chatddx/runner/gate.py:bar`

* `inventory: Inventory`
* `get: Resolver`
* `endpoint: str`
* `trial: Trial`
* `judged: tuple[Judge, str] | None = None`
* ∟`None`

Raises:
1. `Refused`: `"judge {judge.digest} reads the {' and '.join(read)}, which no judge is given"`
2. `Refused`: `str(e)` (from `LookupError`)
3. `Refused`: `"endpoint {endpoint!r} serves engine {spec.engine}, the {whose}'s is {engine}"`
4. `Refused`: `"endpoint %(endpoint)s isn't cleared for source %(sources)s, which is sensitive", endpoint=repr(endpoint), sources=", ".join(uncleared)`
5. `Refused`: `"the configuration's tools would get content from source %(sources)s, which is sensitive, and tools can't be cleared yet", sources=", ".join(sensitive)`

## `CanaryEnded` `@dataclass(frozen=True)`
`src/chatddx/runner/events.py:CanaryEnded`

* `call: CanaryCall`

## `Chunk`
`src/chatddx/runner/wire.py:Chunk`

`type Chunk = dict[str, JsonValue]`

## `chunks`
`src/chatddx/runner/wire.py:chunks`

* `lines: Iterable[bytes]`
* ∟`Iterator[Chunk]`

Raises:
1. `ValueError`: `"a chunk that isn't a JSON object: {data[:200]!r}"`
2. `Rejected`: `200, chunk`
3. `Unfinished`: `"the stream ended before [DONE]"`

## `converse`
`src/chatddx/runner/rounds.py:converse`

* `url: str`
* `body: Mapping[str, JsonValue]`
* `toolbox: Toolbox | None`
* `*`
* `execution: Execution`
* `secret: str | None`
* `on_delta: Callable[[Delta], None]`
* `on_tool: Callable[[ToolRun], None]`
* `halt: Halt | None = None`
* `started_at: datetime | None = None`
* ∟`Exchange`

## `Delta` `@dataclass(frozen=True)`
`src/chatddx/runner/send.py:Delta`

* `kind: Literal["reasoning", "content", "tool_call"]`
* `text: str`
* `tokens: int`

## `events`
`src/chatddx/runner/wire.py:events`

* `lines: Iterable[bytes]`
* ∟`Iterator[str]`

## `Exchange` `@dataclass(frozen=True)`
`src/chatddx/runner/rounds.py:Exchange`

* `call: Call`
* `turns: tuple[Turn, ...] = ()`
* `stopped: bool = False`

## `grade`
`src/chatddx/runner/score.py:grade`

* `conn: Connection`
* `inventory: Inventory`
* `by: Person`
* `run: UUID`
* `scoring: Scoring`
* `registry: Registry`
* `execution: Execution | None`
* ∟`"Grading"`

Raises:
1. `ValueError`: `"run {run} hasn't finished"`
2. `ValueError`: `"judge calls are sent one at a time yet"`

## `Grading`
`src/chatddx/runner/score.py:Grading`

## `Grading.__init__`
`src/chatddx/runner/score.py:Grading.__init__`

* `store: Store`
* `ran: Run`
* `started: ScoreStarted`
* `scorer: Scorer`
* `views: Metrics`
* `loaded: Registry`
* `expected: dict[str, JsonValue]`
* `judging: dict[str, _Judging]`
* `trial: Trial`

## `Grading.finish`
`src/chatddx/runner/score.py:Grading.finish`

* ∟`tuple[Score, list[Finding]]`

Raises:
1. `ValueError`: `"score {self.score} is finished"`

## `Grading.score` `@property`
`src/chatddx/runner/score.py:Grading.score`

* ∟`UUID`

## `Grading.send`
`src/chatddx/runner/score.py:Grading.send`

* `on_event: Callable[[ScoreEvent], None] | None = None`
* `halt: Halt | None = None`
* ∟`None`

Raises:
1. `KeyboardInterrupt`

Finds:
1. `answer.salvaged`: `"cut short, and read with its structure closed"` (`info`, through `Grading._grade`)
2. `answer.salvaged`: `"cut short, and read with its structure closed; the call ended with: %(error)s"` (`info`, through `Grading._grade`)
3. `{code}`: `message` (through `Grading._grade`)

## `Grading.started` `@property`
`src/chatddx/runner/score.py:Grading.started`

* ∟`ScoreStarted`

## `Halt`
`src/chatddx/runner/send.py:Halt`

## `Halt.__init__`
`src/chatddx/runner/send.py:Halt.__init__`

## `Halt.is_set`
`src/chatddx/runner/send.py:Halt.is_set`

* ∟`bool`

## `Halt.set`
`src/chatddx/runner/send.py:Halt.set`

* ∟`None`

## `Halt.wait`
`src/chatddx/runner/send.py:Halt.wait`

* `timeout: float`
* ∟`bool`

## `Halt.watching` `@contextmanager`
`src/chatddx/runner/send.py:Halt.watching`

* `interrupt: Callable[[], None]`
* ∟`Generator[None]`

## `ItemEnded` `@dataclass(frozen=True)`
`src/chatddx/runner/events.py:ItemEnded`

* `item: RunItem`

## `Items`
`src/chatddx/runner/prepare.py:Items`

* `trial: Trial`
* `skeleton: Skeleton`

## `Items.__init__`
`src/chatddx/runner/prepare.py:Items.__init__`

* `conn: Connection`
* `inventory: Inventory`
* `get: Resolver`
* `trial: str`

## `Items.case`
`src/chatddx/runner/prepare.py:Items.case`

* `case: str`
* `layout: AppendixLayout`
* ∟`Prepared`

## `Items.item`
`src/chatddx/runner/prepare.py:Items.item`

* `key: ItemKey`
* ∟`PreparedItem`

## `ItemScored` `@dataclass(frozen=True)`
`src/chatddx/runner/events.py:ItemScored`

* `item: ScoreItem`

## `ItemStarted` `@dataclass(frozen=True)`
`src/chatddx/runner/events.py:ItemStarted`

* `key: ItemKey`
* `seed: int`

## `judge_at`
`src/chatddx/runner/score.py:judge_at`

* `inventory: Inventory`
* `get: Resolver`
* `trial: Trial`
* `judge: str`
* `engine: str`
* ∟`str`

Raises:
1. `Refused`: `str(e)` (from `LookupError`)

## `JudgeAnswered` `@dataclass(frozen=True)`
`src/chatddx/runner/events.py:JudgeAnswered`

* `key: ItemKey`
* `view: int`
* `call: JudgeCall`
* `verdict: JsonValue | None`

## `JudgeAsked` `@dataclass(frozen=True)`
`src/chatddx/runner/events.py:JudgeAsked`

* `key: ItemKey`
* `scorer: str`
* `view: int`
* `judge: str`
* `seed_index: int`

## `load`
`src/chatddx/runner/rounds.py:load`

* `skeleton: Skeleton`
* `get: Resolver`
* ∟`Toolbox | None`

## `NO_EXPECTATION`
`src/chatddx/runner/score.py:NO_EXPECTATION`

`NO_EXPECTATION: JsonValue = {"reason": "no expectation"}`

## `Noted` `@dataclass(frozen=True)`
`src/chatddx/runner/events.py:Noted`

* `finding: Finding`

## `Outcome`
`src/chatddx/runner/outcome.py:Outcome`

`Outcome`

## `outcome`
`src/chatddx/runner/outcome.py:outcome`

* `skeleton: Skeleton`
* `item: RunItem`
* ∟`tuple[Outcome, str | None]`

## `post`
`src/chatddx/runner/wire.py:post`

* `url: str`
* `body: Mapping[str, JsonValue]`
* `*`
* `secret: str | None = None`
* `timeout: float | None = None`
* ∟`Stream`

Raises:
1. `Rejected`: `e.code, _parsed(e.read())` (from `urllib.error.HTTPError`)

## `PreparedItem` `@dataclass(frozen=True)`
`src/chatddx/runner/prepare.py:PreparedItem`

* `key: ItemKey`
* `seed: int`
* `vignette: Fingerprint`
* `body: dict[str, JsonValue]`
* `findings: tuple[Finding, ...]`

## `Refused` `(Worded)`
`src/chatddx/runner/gate.py:Refused`

## `Rejected` `(Exception)`
`src/chatddx/runner/wire.py:Rejected`

* `status: int`
* `body: dict[str, JsonValue] | None`

## `Rejected.__init__`
`src/chatddx/runner/wire.py:Rejected.__init__`

* `status: int`
* `body: dict[str, JsonValue] | None`

## `rendered_again`
`src/chatddx/runner/prepare.py:rendered_again`

* `conn: Connection`
* `inventory: Inventory`
* `run: Run`
* ∟`dict[ItemKey, str | None]`

## `request`
`src/chatddx/runner/wire.py:request`

* `url: str`
* `body: Mapping[str, JsonValue]`
* `secret: str | None = None`
* ∟`urllib.request.Request`

## `RunEvent`
`src/chatddx/runner/events.py:RunEvent`

`type RunEvent = ItemStarted | Streamed | ToolRan | ItemEnded | CanaryEnded | Noted`

## `Runner`
`src/chatddx/runner/run.py:Runner`

## `Runner.__init__`
`src/chatddx/runner/run.py:Runner.__init__`

* `conn: Connection`
* `inventory: Inventory`
* `by: Person`

Raises:
1. `ValueError`: `"the runner needs a connection in autocommit mode"`

## `Runner.resume`
`src/chatddx/runner/run.py:Runner.resume`

* `run: UUID`
* ∟`"Running"`

Raises:
1. `ValueError`: `"run {run} is finished"`
2. `ValueError`: `"run {run} was sent to no endpoint, so it can't resume"`
3. `Self`: `"endpoint %(endpoint)s takes %(num)s at once, the execution sends %(sends)s", endpoint=repr(endpoint), num=spec.capacity, sends=execution.concurrency` (through `Runner._admitted`)
4. `ValueError`: `"endpoint {endpoint.name!r} is at {url} now, and run {run} was sent to {endpoint.url}"`

Finds:
1. `run.resumed`: `"resumed after %(done)s of %(num)s items by %(now)s, where %(then)s started it"` (through `_resumed`)
2. `run.resumed`: `"resumed after %(done)s of %(num)s items"` (`info`, through `_resumed`)

## `Runner.score`
`src/chatddx/runner/run.py:Runner.score`

* `run: UUID`
* `scoring: Scoring`
* `registry: Registry`
* `execution: Execution | None = None`
* ∟`Grading`

## `Runner.start`
`src/chatddx/runner/run.py:Runner.start`

* `trial: Trial`
* `registry: Registry`
* `endpoint: str`
* `execution: Execution | None = None`
* `canaries: CanarySet | None = None`
* `verify_at: tuple[Phase, ...] = PHASES`
* ∟`"Running"`

Raises:
1. `Self`: `"endpoint %(endpoint)s takes %(num)s at once, the execution sends %(sends)s", endpoint=repr(endpoint), num=spec.capacity, sends=execution.concurrency` (through `Runner._admitted`)

## `Running`
`src/chatddx/runner/run.py:Running`

## `Running.__init__`
`src/chatddx/runner/run.py:Running.__init__`

* `conn: Connection`
* `inventory: Inventory`
* `registry: Registry`
* `started: RunStarted`
* `url: str`
* `secret: str | None`
* `toolbox: Toolbox | None`
* `items: Sequence[RunItem] = ()`
* `canaries: Sequence[CanaryCall] = ()`
* `findings: Sequence[Finding] = ()`

## `Running.cut`
`src/chatddx/runner/run.py:Running.cut`

Hangs up the calls in flight and records none of them, so that a resume sends
them again.

* ∟`None`

## `Running.finish`
`src/chatddx/runner/run.py:Running.finish`

* ∟`list[Finding]`

Raises:
1. `ValueError`: `"run {self.run} is finished"`

## `Running.run` `@property`
`src/chatddx/runner/run.py:Running.run`

* ∟`UUID`

## `Running.send`
`src/chatddx/runner/run.py:Running.send`

* `on_event: Callable[[RunEvent], None] | None = None`
* `halt: Halt | None = None`
* ∟`None`

Raises:
1. `KeyboardInterrupt` (through `Running._probe`)

Finds:
1. `case.unreadable`: `str(e)` (from `(LookupError, StructuralError)`, through `Running._prepared`)

## `Running.started` `@property`
`src/chatddx/runner/run.py:Running.started`

* ∟`RunStarted`

## `Running.stop`
`src/chatddx/runner/run.py:Running.stop`

* ∟`None`

## `ScoreEvent`
`src/chatddx/runner/events.py:ScoreEvent`

`type ScoreEvent = ItemScored | JudgeAsked | Streamed | JudgeAnswered | Noted`

## `send`
`src/chatddx/runner/send.py:send`

* `url: str`
* `body: Mapping[str, JsonValue]`
* `*`
* `execution: Execution | None = None`
* `secret: str | None = None`
* `on_delta: Callable[[Delta], None] | None = None`
* `backoff: float = 1.0`
* `halt: Halt | None = None`
* `started_at: datetime | None = None`
* ∟`Call`

Raises:
1. `Stopped`: `call(None, STOPPED)`
2. `Stopped`: `call(stream.status, STOPPED)`

## `served`
`src/chatddx/runner/wire.py:served`

* `url: str`
* `*`
* `secret: str | None = None`
* `timeout: float | None = None`
* ∟`list[str]`

## `STOPPED`
`src/chatddx/runner/send.py:STOPPED`

`STOPPED = "stopped"`

## `Stopped` `(Exception)`
`src/chatddx/runner/send.py:Stopped`

* `call: Call`

## `Stopped.__init__`
`src/chatddx/runner/send.py:Stopped.__init__`

* `call: Call`

## `STREAM`
`src/chatddx/runner/send.py:STREAM`

`STREAM: dict[str, JsonValue] = {…}`

## `Stream`
`src/chatddx/runner/wire.py:Stream`

## `Stream.__enter__`
`src/chatddx/runner/wire.py:Stream.__enter__`

* ∟`Self`

## `Stream.__exit__`
`src/chatddx/runner/wire.py:Stream.__exit__`

* `_type: type[BaseException] | None`
* `_value: BaseException | None`
* `_traceback: TracebackType | None`
* ∟`None`

## `Stream.__init__`
`src/chatddx/runner/wire.py:Stream.__init__`

* `response: HTTPResponse`

## `Stream.__iter__`
`src/chatddx/runner/wire.py:Stream.__iter__`

* ∟`Iterator[Chunk]`

## `Stream.close`
`src/chatddx/runner/wire.py:Stream.close`

* ∟`None`

## `Stream.interrupt`
`src/chatddx/runner/wire.py:Stream.interrupt`

* ∟`None`

## `Stream.status` `@property`
`src/chatddx/runner/wire.py:Stream.status`

* ∟`int`

## `Streamed` `@dataclass(frozen=True)`
`src/chatddx/runner/events.py:Streamed`

* `key: ItemKey`
* `delta: Delta`

## `Toolbox` `@dataclass(frozen=True)`
`src/chatddx/runner/rounds.py:Toolbox`

* `functions: Mapping[str, Callable[..., object]]`
* `parameters: Mapping[str, Validator]`
* `answer: str | None`
* `max_rounds: int`
* `code: tuple[ToolCode, ...]`

## `Toolbox.pending`
`src/chatddx/runner/rounds.py:Toolbox.pending`

* `call: Call`
* ∟`tuple[ToolCall, ...]`

## `Toolbox.run`
`src/chatddx/runner/rounds.py:Toolbox.run`

* `call: ToolCall`
* ∟`ToolRun`

Raises:
1. `ToolStopped`: `ToolRun(id=call.id, name=call.name, started_at=started, finished_at=_now(), result=f'error: {STOPPED}', error=STOPPED)`

## `ToolRan` `@dataclass(frozen=True)`
`src/chatddx/runner/events.py:ToolRan`

* `key: ItemKey`
* `run: ToolRun`

## `ToolStopped` `(Exception)`
`src/chatddx/runner/rounds.py:ToolStopped`

* `run: ToolRun`

## `ToolStopped.__init__`
`src/chatddx/runner/rounds.py:ToolStopped.__init__`

* `run: ToolRun`

## `Unfinished` `(ConnectionError)`
`src/chatddx/runner/wire.py:Unfinished`

## `usage`
`src/chatddx/runner/outcome.py:usage`

* `item: RunItem`
* ∟`tuple[int, int]`

## `used`
`src/chatddx/runner/outcome.py:used`

* `call: Call`
* ∟`tuple[int, int]`
