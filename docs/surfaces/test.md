# `test`

Written by `chatddx-dev index` from `[parts.test]`'s code in `settings.toml`, an entry for each public name, sorted alphabetically whatever its case, so that a class's members follow it, a language's after another's:

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

## `added_alice` `@pytest.fixture(name="alice")`
`src/chatddx/test/helpers.py:added_alice`

* `conn: Connection`
* ∟`Person`

## `added_bob` `@pytest.fixture(name="bob")`
`src/chatddx/test/helpers.py:added_bob`

* `conn: Connection`
* ∟`Person`

## `alice_with_password` `@pytest.fixture(name="alice")`
`src/chatddx/test/helpers.py:alice_with_password`

* `conn: Connection`
* ∟`Person`

## `alices_bench` `@pytest.fixture(name="bench")`
`src/chatddx/test/helpers.py:alices_bench`

* `conn: Connection`
* `alice: Person`
* `world: Inventory`
* ∟`Bench`

## `autocommitted` `@pytest.fixture(name="autocommit")`
`src/chatddx/test/helpers.py:autocommitted`

* ∟`bool`

## `Budget`
`src/chatddx/test/budget.py:Budget`

* `took: defaultdict[str, float]`
* `shared: defaultdict[str, float]`
* `waited: defaultdict[str, float]`
* `slow: set[str]`
* `skipped: set[str]`
* `pending: list[tuple[str, tuple[str, float]]]`
* `last: str`
* `depth: int`

## `Budget.__init__`
`src/chatddx/test/budget.py:Budget.__init__`

## `Budget.pytest_fixture_setup` `@pytest.hookimpl(wrapper=True)`
`src/chatddx/test/budget.py:Budget.pytest_fixture_setup`

* `fixturedef: pytest.FixtureDef[object]`
* ∟`Generator[None, object, object]`

## `Budget.pytest_runtest_logreport`
`src/chatddx/test/budget.py:Budget.pytest_runtest_logreport`

* `report: pytest.TestReport`
* ∟`None`

## `Budget.pytest_runtest_makereport` `@pytest.hookimpl(wrapper=True)`
`src/chatddx/test/budget.py:Budget.pytest_runtest_makereport`

* `item: pytest.Item`
* ∟`Generator[None, pytest.TestReport, pytest.TestReport]`

## `Budget.pytest_runtest_teardown`
`src/chatddx/test/budget.py:Budget.pytest_runtest_teardown`

* `item: pytest.Item`
* `nextitem: pytest.Item | None`
* ∟`None`

## `Budget.pytest_terminal_summary`
`src/chatddx/test/budget.py:Budget.pytest_terminal_summary`

* `terminalreporter: pytest.TerminalReporter`
* ∟`None`

## `CASES`
`src/chatddx/test/world.py:CASES`

`CASES = load_cases(DATA)`

## `chosen`
`src/chatddx/test/helpers.py:chosen`

* `request: pytest.FixtureRequest`
* `otherwise: str`
* ∟`str`

## `CLINICIAN`
`src/chatddx/test/world.py:CLINICIAN`

`CLINICIAN = "clinician"`

## `committing_as_bob` `@pytest.fixture(name="as_bob")`
`src/chatddx/test/helpers.py:committing_as_bob`

* `monkeypatch: pytest.MonkeyPatch`
* ∟`None`

## `COMPARED`
`src/chatddx/test/world.py:COMPARED`

`COMPARED = ("instructed", "instructed-greedy", "guided")`

## `connect`
`src/chatddx/test/helpers.py:connect`

* `name: str`
* `admin: bool = False`
* ∟`Connection`

## `copied`
`src/chatddx/test/world.py:copied`

* `to: Path`
* `world: Path = TEST`
* ∟`Path`

## `Copies`
`src/chatddx/test/helpers.py:Copies`

* `AHEAD: int = 6`
* `admin: str`

## `Copies.__init__`
`src/chatddx/test/helpers.py:Copies.__init__`

## `Copies.close`
`src/chatddx/test/helpers.py:Copies.close`

* ∟`None`

## `Copies.forget`
`src/chatddx/test/helpers.py:Copies.forget`

* `template: str`
* ∟`None`

## `Copies.give_back`
`src/chatddx/test/helpers.py:Copies.give_back`

* `name: str`
* ∟`None`

## `Copies.take`
`src/chatddx/test/helpers.py:Copies.take`

* `template: str`
* ∟`str`

## `create_database`
`src/chatddx/test/helpers.py:create_database`

* `admin: str`
* `template: str | None = None`
* ∟`str`

## `curated_template` `@pytest.fixture(name="template")`
`src/chatddx/test/helpers.py:curated_template`

* `request: pytest.FixtureRequest`
* ∟`str`

## `DATA`
`src/chatddx/test/world.py:DATA`

`DATA = TEST / "_data"`

## `DATA_SETS`
`src/chatddx/test/test_worlds.py:DATA_SETS`

`DATA_SETS = {"test": DATA, "sample": SAMPLE, "kompismoln": KOMPISMOLN}`

## `drop_database`
`src/chatddx/test/helpers.py:drop_database`

* `admin: str`
* `name: str`
* ∟`None`

## `each` `@pytest.fixture(scope="module", params=sorted(DATA_SETS))`
`src/chatddx/test/test_worlds.py:each`

* `request: pytest.FixtureRequest`
* ∟`tuple[World, Plan]`

## `edit`
`src/chatddx/test/world.py:edit`

* `path: Path`
* `old: str`
* `new: str`
* ∟`None`

## `FACT_LINTS`
`src/chatddx/test/world.py:FACT_LINTS`

`FACT_LINTS = […]`

## `FACTOR_LINTS`
`src/chatddx/test/world.py:FACTOR_LINTS`

`FACTOR_LINTS = […]`

## `faked` `@contextmanager`
`src/chatddx/test/world.py:faked`

* `world: Inventory`
* `get: Resolver`
* `endpoint: str = QWEN`
* `delay: float = 0.0`
* `script: Script | None = None`
* ∟`Generator[None]`

## `few`
`src/chatddx/test/test_worlds.py:few`

* `data: Path`
* `to: Path`
* ∟`Path`

## `FILLS`
`src/chatddx/test/test_worlds.py:FILLS`

`FILLS: dict[SlotName, str] = {…}`

## `found_alice` `@pytest.fixture(name="alice")`
`src/chatddx/test/helpers.py:found_alice`

* `conn: Connection`
* ∟`Person`

## `found_alices_bench` `@pytest.fixture(name="bench")`
`src/chatddx/test/helpers.py:found_alices_bench`

* `conn: Connection`
* `world: Inventory`
* ∟`Bench`

## `free_ports`
`src/chatddx/test/world.py:free_ports`

* `n: int`
* ∟`list[int]`

## `free_world`
`src/chatddx/test/world.py:free_world`

* `world: Path = TEST`
* ∟`Inventory`

## `freed`
`src/chatddx/test/world.py:freed`

* `to: Path`
* `world: Path = TEST`
* ∟`Path`

## `GAP`
`src/chatddx/test/test_tests.py:GAP`

`GAP = re.compile(r"\S {2,}\S")`

## `git`
`src/chatddx/test/helpers.py:git`

* `root: Path`
* `*args: str`
* ∟`str`

## `GPT_OSS`
`src/chatddx/test/world.py:GPT_OSS`

`GPT_OSS = "gpt-oss@fake"`

## `GPT_OSS_ARTIFACT`
`src/chatddx/test/world.py:GPT_OSS_ARTIFACT`

`GPT_OSS_ARTIFACT = "gpt-oss-20b"`

## `GPT_OSS_MODEL`
`src/chatddx/test/world.py:GPT_OSS_MODEL`

`GPT_OSS_MODEL = "openai/gpt-oss-20b"`

## `INSTRUCTION`
`src/chatddx/test/helpers.py:INSTRUCTION`

`INSTRUCTION = …`

## `item`
`src/chatddx/test/test_budget.py:item`

* `nodeid: str`
* ∟`pytest.Item`

## `JUDGE`
`src/chatddx/test/world.py:JUDGE`

`JUDGE = "judge"`

## `KOMPISMOLN`
`src/chatddx/test/world.py:KOMPISMOLN`

`KOMPISMOLN = WORLDS / "kompismoln" / "_data"`

## `test_tests.LINES`
`src/chatddx/test/test_tests.py:LINES`

`LINES = re.compile(r"\n|\\n")`

## `world.LINES`
`src/chatddx/test/world.py:LINES`

`LINES = "lines"`

## `LINES_GUIDED`
`src/chatddx/test/world.py:LINES_GUIDED`

`LINES_GUIDED = "lines-guided"`

## `LINES_INSTRUCTED`
`src/chatddx/test/world.py:LINES_INSTRUCTED`

`LINES_INSTRUCTED = "lines-instructed"`

## `LINTS`
`src/chatddx/test/world.py:LINTS`

`LINTS = [*FACTOR_LINTS, *FACT_LINTS]`

## `Loaded` `(NamedTuple)`
`src/chatddx/test/helpers.py:Loaded`

* `name: str`
* `said: list[str]`

## `loaded`
`src/chatddx/test/world.py:loaded`

What sync-archive and then person provision say, as a deploy and an operator
run them, the giftbag left out unless asked for.

* `conn: Connection`
* `plan: Plan`
* `cases: dict[str, DataCase]`
* `source: DirectorySource`
* `user: Person`
* `giftbag: bool = False`
* ∟`list[str]`

## `made`
`src/chatddx/test/test_budget.py:made`

* `budget: Budget`
* `nodeid: str`
* `when: Literal["setup", "call", "teardown"]`
* `duration: float`
* ∟`pytest.TestReport`

## `MARGIN`
`src/chatddx/test/budget.py:MARGIN`

`MARGIN = 3.0`

## `MISTRAL`
`src/chatddx/test/world.py:MISTRAL`

`MISTRAL = "mistral@fake"`

## `MISTRAL_ARTIFACT`
`src/chatddx/test/world.py:MISTRAL_ARTIFACT`

`MISTRAL_ARTIFACT = "mistral-7b"`

## `MISTRAL_MODEL`
`src/chatddx/test/world.py:MISTRAL_MODEL`

`MISTRAL_MODEL = "test/mistral-7b"`

## `MISTRAL_SMALL`
`src/chatddx/test/test_sample.py:MISTRAL_SMALL`

`MISTRAL_SMALL = "mistralai/Mistral-Small-3.2-24B-Instruct-2506"`

## `MODELS`
`src/chatddx/test/world.py:MODELS`

`MODELS = (QWEN_MODEL, GPT_OSS_MODEL, MISTRAL_MODEL)`

## `NATIVE`
`src/chatddx/test/world.py:NATIVE`

`NATIVE = "native"`

## `NATIVE_TOOLS`
`src/chatddx/test/world.py:NATIVE_TOOLS`

`NATIVE_TOOLS = "native-tools"`

## `needs_git`
`src/chatddx/test/helpers.py:needs_git`

`needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="no git")`

## `NOW`
`src/chatddx/test/helpers.py:NOW`

`NOW = datetime(2026, 1, 1, tzinfo=UTC)`

## `OFF`
`src/chatddx/test/world.py:OFF`

`OFF = "off"`

## `one_attempt`
`src/chatddx/test/helpers.py:one_attempt`

* `at: datetime`
* `until: datetime | None = None`
* ∟`tuple[Attempt, ...]`

## `parsed` `@pytest.fixture(scope="session")`
`src/chatddx/test/test_tests.py:parsed`

* ∟`list[tuple[Path, ast.Module]]`

## `PASSWORD`
`src/chatddx/test/helpers.py:PASSWORD`

`PASSWORD = "correct horse battery staple"`

## `pytest_configure`
`src/chatddx/test/budget.py:pytest_configure`

* `config: pytest.Config`
* ∟`None`

## `QUICK`
`src/chatddx/test/budget.py:QUICK`

`QUICK = 1 / 8`

## `QWEN`
`src/chatddx/test/world.py:QWEN`

`QWEN = "qwen3@fake"`

## `QWEN_ARTIFACT`
`src/chatddx/test/world.py:QWEN_ARTIFACT`

`QWEN_ARTIFACT = "qwen3-8b-awq"`

## `QWEN_BARE`
`src/chatddx/test/world.py:QWEN_BARE`

`QWEN_BARE = "qwen3-bare@fake"`

## `QWEN_BARE_ARTIFACT`
`src/chatddx/test/world.py:QWEN_BARE_ARTIFACT`

`QWEN_BARE_ARTIFACT = "qwen3-8b-bare"`

## `QWEN_MODEL`
`src/chatddx/test/world.py:QWEN_MODEL`

`QWEN_MODEL = "Qwen/Qwen3-8B-AWQ"`

## `registry` `@pytest.fixture(name="reg")`
`src/chatddx/test/helpers.py:registry`

* ∟`Registry`

## `REMOTE`
`src/chatddx/test/world.py:REMOTE`

`REMOTE = "unknown@remote"`

## `SAMPLE`
`src/chatddx/test/world.py:SAMPLE`

`SAMPLE = WORLDS / "sample" / "_data"`

## `sample_plan`
`src/chatddx/test/test_sample.py:sample_plan`

* ∟`Plan`

## `sampled_template` `@pytest.fixture(name="template")`
`src/chatddx/test/helpers.py:sampled_template`

* `sampled: Loaded`
* ∟`str`

## `SHARING`
`src/chatddx/test/test_tests.py:SHARING`

`SHARING = re.compile(r"(^|\.)(test_\w+|conftest)$")`

## `SHIPPED`
`src/chatddx/test/helpers.py:SHIPPED`

`SHIPPED = "chatddx.scorers.metrics:score"`

## `skeleton`
`src/chatddx/test/helpers.py:skeleton`

* `plan: Plan`
* `recipe: str`
* ∟`Skeleton`

## `SKIPPED`
`src/chatddx/test/test_the_test_world.py:SKIPPED`

`SKIPPED = […]`

## `SRC`
`src/chatddx/test/test_tests.py:SRC`

`SRC = settings.PROJECT_ROOT / "src"`

## `summary`
`src/chatddx/test/test_budget.py:summary`

* `budget: Budget`
* `config: pytest.Config`
* ∟`list[str]`

## `TARGETS_SCHEMA`
`src/chatddx/test/test_sample.py:TARGETS_SCHEMA`

`TARGETS_SCHEMA = json.loads((SAMPLE / "schemas" / "targets.json").read_text())`

## `templated` `@contextmanager`
`src/chatddx/test/helpers.py:templated`

* `copies: Copies`
* `of: str | None = None`
* ∟`Generator[str]`

## `TEST`
`src/chatddx/test/world.py:TEST`

`TEST = WORLDS / "test"`

## `test_a_case_s_notes_keep_their_author_comment_and_answer_not_a_language`
`src/chatddx/test/test_sample.py:test_a_case_s_notes_keep_their_author_comment_and_answer_not_a_language`

* ∟`None`

## `test_a_name_tests_share_is_spelled_once_in_world_py`
`src/chatddx/test/test_tests.py:test_a_name_tests_share_is_spelled_once_in_world_py`

* `parsed: list[tuple[Path, ast.Module]]`
* ∟`None`

## `test_a_sync_binds_each_world_s_endpoints_and_prunes_other_world_s_engines` `@pytest.mark.slow`
`src/chatddx/test/test_worlds.py:test_a_sync_binds_each_world_s_endpoints_and_prunes_other_world_s_engines`

* `db: str`
* `tmp_path: Path`
* `monkeypatch: pytest.MonkeyPatch`
* `capsys: pytest.CaptureFixture[str]`
* ∟`None`

## `test_a_test_matches_a_table_s_cells_not_its_padding` `@pytest.mark.slow`
`src/chatddx/test/test_tests.py:test_a_test_matches_a_table_s_cells_not_its_padding`

* `parsed: list[tuple[Path, ast.Module]]`
* ∟`None`

## `test_a_test_takes_what_it_shares_from_helpers_not_a_test_or_a_conftest` `@pytest.mark.slow`
`src/chatddx/test/test_tests.py:test_a_test_takes_what_it_shares_from_helpers_not_a_test_or_a_conftest`

* `parsed: list[tuple[Path, ast.Module]]`
* ∟`None`

## `test_a_worker_s_tests_are_weighed_as_they_would_be_alone`
`src/chatddx/test/test_budget.py:test_a_worker_s_tests_are_weighed_as_they_would_be_alone`

* `pytestconfig: pytest.Config`
* ∟`None`

## `test_each_endpoint_serves_the_engine_planned_under_its_name`
`src/chatddx/test/test_worlds.py:test_each_endpoint_serves_the_engine_planned_under_its_name`

* `each: tuple[World, Plan]`
* ∟`None`

## `test_each_fake_answers_each_skeleton_or_refuses_it_as_vllm_would`
`src/chatddx/test/test_worlds.py:test_each_fake_answers_each_skeleton_or_refuses_it_as_vllm_would`

* `each: tuple[World, Plan]`
* ∟`None`

## `test_every_target_s_pattern_reads` `@pytest.mark.parametrize("data", sorted(set(DATA_SETS.values())), ids=lambda p: p.name)`
`src/chatddx/test/test_worlds.py:test_every_target_s_pattern_reads`

* `data: Path`
* ∟`None`

## `test_every_world_in_the_repository_is_checked`
`src/chatddx/test/test_worlds.py:test_every_world_in_the_repository_is_checked`

* ∟`None`

## `test_kompismoln_s_data_is_the_sample_s_without_its_appendices_under_its_own_tags`
`src/chatddx/test/test_sample.py:test_kompismoln_s_data_is_the_sample_s_without_its_appendices_under_its_own_tags`

* ∟`None`

## `test_kompismoln_s_facts_are_the_bundled_ones_as_its_engines_serve_them`
`src/chatddx/test/test_sample.py:test_kompismoln_s_facts_are_the_bundled_ones_as_its_engines_serve_them`

* ∟`None`

## `test_kompismoln_s_sources_are_the_sample_s`
`src/chatddx/test/test_sample.py:test_kompismoln_s_sources_are_the_sample_s`

* ∟`None`

## `test_only_a_test_far_off_the_cut_is_marked_or_unmarked`
`src/chatddx/test/test_budget.py:test_only_a_test_far_off_the_cut_is_marked_or_unmarked`

* `pytestconfig: pytest.Config`
* ∟`None`

## `test_padding_is_told_from_a_line_s_indent_and_an_f_string_s_values`
`src/chatddx/test/test_tests.py:test_padding_is_told_from_a_line_s_indent_and_an_f_string_s_values`

* ∟`None`

## `test_the_budget_says_so_when_no_test_ran`
`src/chatddx/test/test_budget.py:test_the_budget_says_so_when_no_test_ran`

* `pytestconfig: pytest.Config`
* ∟`None`

## `test_the_sample_holds_olof_s_notes_on_three_cases_as_written`
`src/chatddx/test/test_sample.py:test_the_sample_holds_olof_s_notes_on_three_cases_as_written`

* ∟`None`

## `test_the_sample_loads_with_its_world_s_fakes`
`src/chatddx/test/test_sample.py:test_the_sample_loads_with_its_world_s_fakes`

* `conn: Connection`
* `sampled: Loaded`
* ∟`None`

## `test_the_sample_s_cases_are_81_english_and_18_swedish`
`src/chatddx/test/test_sample.py:test_the_sample_s_cases_are_81_english_and_18_swedish`

* ∟`None`

## `test_the_sample_s_texts_are_english_and_translated_into_swedish`
`src/chatddx/test/test_sample.py:test_the_sample_s_texts_are_english_and_translated_into_swedish`

* ∟`None`

## `test_the_sample_s_translations_carry_its_recipes_into_swedish`
`src/chatddx/test/test_sample.py:test_the_sample_s_translations_carry_its_recipes_into_swedish`

* ∟`None`

## `test_the_sample_uses_every_table_a_data_set_and_a_world_hold`
`src/chatddx/test/test_sample.py:test_the_sample_uses_every_table_a_data_set_and_a_world_hold`

* ∟`None`

## `test_the_sample_world_holds_the_vignettes_at_7893656_but_akm_06_s_amended`
`src/chatddx/test/test_sample.py:test_the_sample_world_holds_the_vignettes_at_7893656_but_akm_06_s_amended`

* ∟`None`

## `test_the_targets_schema_takes_the_old_chatddx_s_target_kinds`
`src/chatddx/test/test_sample.py:test_the_targets_schema_takes_the_old_chatddx_s_target_kinds`

* ∟`None`

## `test_the_test_world_plans_and_loads_as_designed` `@pytest.mark.slow`
`src/chatddx/test/test_the_test_world.py:test_the_test_world_plans_and_loads_as_designed`

* `conn: Connection`
* ∟`None`

## `test_the_test_world_s_vignettes_hold_what_their_ids_say`
`src/chatddx/test/test_the_test_world.py:test_the_test_world_s_vignettes_hold_what_their_ids_say`

* ∟`None`

## `test_what_tests_share_is_written_once`
`src/chatddx/test/test_tests.py:test_what_tests_share_is_written_once`

* `parsed: list[tuple[Path, ast.Module]]`
* ∟`None`

## `test_what_the_fake_writes_holds_to_each_data_set_s_schemas` `@pytest.mark.parametrize("path", …)`
`src/chatddx/test/test_worlds.py:test_what_the_fake_writes_holds_to_each_data_set_s_schemas`

* `path: Path`
* ∟`None`

## `TOOL_ANSWER`
`src/chatddx/test/world.py:TOOL_ANSWER`

`TOOL_ANSWER = "tool-answer"`

## `TYPED`
`src/chatddx/test/helpers.py:TYPED`

`TYPED = "A 54-year-old woman with sudden breathlessness after a long flight."`

## `UNCONSTRAINED`
`src/chatddx/test/test_worlds.py:UNCONSTRAINED`

`UNCONSTRAINED = ("harmony", "mistral")`

## `UNKNOWN_MODEL`
`src/chatddx/test/world.py:UNKNOWN_MODEL`

`UNKNOWN_MODEL = "unknown"`

## `WAITED`
`src/chatddx/test/budget.py:WAITED`

`WAITED = frozenset({"db"})`

## `WORD`
`src/chatddx/test/test_tests.py:WORD`

`WORD = re.compile(r"[a-z]+")`

## `WORLD`
`src/chatddx/test/test_tests.py:WORLD`

`WORLD = SRC / "chatddx" / "test" / "world.py"`

## `world_facts`
`src/chatddx/test/world.py:world_facts`

* `world: Path = TEST`
* ∟`Facts`

## `world_plan`
`src/chatddx/test/world.py:world_plan`

* `world: Path = TEST`
* `data: Path = DATA`
* ∟`Plan`

## `WORLDS`
`src/chatddx/test/world.py:WORLDS`

`WORLDS = settings.PROJECT_ROOT / "worlds"`

## `ZERO`
`src/chatddx/test/helpers.py:ZERO`

`ZERO = "sha256:" + "0" * 64`
