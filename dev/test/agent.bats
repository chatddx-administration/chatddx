#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

setup() {
  cd "$BATS_TEST_TMPDIR"
  export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
  export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
  export CALLS="$BATS_TEST_TMPDIR/calls"
  : >"$CALLS"
  unset CLAUDE_CODE_REMOTE CLAUDE_ENV_FILE FAIL WRITE_EXIT WRITE_TOUCH UNTRANSLATED

  mkdir bin
  printf '#!%s\necho "uv fails" >&2\nexit 1\n' "$BASH" >bin/uv
  printf '#!%s\n[ "$1 $2" = "locale pending" ] || exit 0\nprintf "%%s" "${UNTRANSLATED:-}"\n[ -z "${UNTRANSLATED:-}" ]\n' "$BASH" >bin/chatddx
  chmod +x bin/*
  export PATH="$BATS_TEST_TMPDIR/bin:$PATH"

  git init -q --bare -b main origin.git
  git clone -q origin.git repo 2>/dev/null
  cd repo
  mkdir dev
  cp "$BATS_TEST_DIRNAME/../agent.sh" "$BATS_TEST_DIRNAME/../settings.sh" dev/
  cp "$BATS_TEST_DIRNAME/../../settings.toml" .
  {
    echo "#!$BASH"
    cat <<'EOF'
echo "check $*" >>"$CALLS"
failed=()
mkdir -p dev/state/logs
for check in "$@"; do
  echo "$check said" >"dev/state/logs/$check.log"
  if [[ " ${FAIL:-} " == *" $check "* ]]; then
    echo "• $check"
    echo "FAILED $check broke" | tee -a "dev/state/logs/$check.log"
    failed+=("$check")
  fi
done
((${#failed[@]} == 0)) || { echo "• failed: ${failed[*]}"; exit 1; }
EOF
  } >dev/check.sh
  {
    echo "#!$BASH"
    cat <<'EOF'
echo "write $*" >>"$CALLS"
[[ -z ${WRITE_TOUCH:-} ]] || echo written >>written
echo "write said"
exit "${WRITE_EXIT:-0}"
EOF
  } >dev/write.sh
  chmod +x dev/check.sh dev/write.sh
  echo /dev/state/ >.gitignore
  : >.env-container
  git add -A
  git commit -q -m init
  git push -q origin main
  git switch -q -c feat
  git push -q -u origin feat 2>/dev/null
}

hook() {
  run bash -c 'printf "%s" "$2" | ./dev/agent.sh "$1"' _ "$1" "${2:-{\}}"
}

committed() {
  echo "$1" >>"$1"
  git add "$1"
  git commit -q -m "$1"
}

subject() { git log -1 --format=%s "${1:-HEAD}"; }
checked() { grep -c "^check" "$CALLS" || true; }
wrote() { grep -c "^write" "$CALLS" || true; }

@test "agent says how to use it" {
  run ./dev/agent.sh
  [ "$status" -eq 1 ]
  [[ $output == "usage: "* ]]
}

@test "session-start checks a fresh session and says nothing when it passes" {
  hook session-start '{"source":"startup"}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ "$(cat dev/state/session-start)" = fresh ]
  grep -qx "check openapi index stamps locale pending format python-lint frontend docs" "$CALLS"
}

@test "session-start refuses work for what fails, with what it said" {
  FAIL="format docs" hook session-start '{"source":"startup"}'
  [ "$status" -eq 0 ]
  [[ ${lines[0]} == "Work is refused, for formatting errors, broken references: tell the user so, with what follows,"* ]]
  [[ $output == *"FAILED format broke"* ]]
  [[ $output == *"FAILED docs broke"* ]]
  [ "$(cat dev/state/session-start)" = "fresh refused" ]
}

@test "session-start checks nothing on resume" {
  hook session-start '{"source":"resume"}'
  [ "$status" -eq 0 ]
  [ "$(checked)" -eq 0 ]
  [ -z "$(cat dev/state/session-start)" ]
}

@test "session-start refuses work in a container that fails to provision" {
  export CLAUDE_CODE_REMOTE=true
  hook session-start '{"source":"startup"}'
  [ "$status" -eq 0 ]
  [[ $output == *"Work is refused, for a container that fails to provision"* ]]
  [[ $output == *"uv fails"* ]]
  [ "$(cat dev/state/session-start)" = "fresh unprovisioned refused" ]
}

@test "turn-start holds the commit the turn starts at" {
  mkdir -p dev/state
  echo fresh >dev/state/session-start
  hook turn-start
  [ "$status" -eq 0 ]
  [ "$(cat dev/state/turn-start)" = "$(git rev-parse HEAD)" ]
  [ ! -e dev/state/session-start ]
  [ ! -e dev/state/refused ]
}

@test "turn-start keeps work refused that session-start refused" {
  mkdir -p dev/state
  echo "fresh refused" >dev/state/session-start
  hook turn-start
  [ "$status" -eq 0 ]
  [ -e dev/state/refused ]
}

@test "turn-start keeps work refused at a later turn while what refused it fails" {
  FAIL=index hook session-start '{"source":"startup"}'
  hook turn-start
  FAIL=index hook turn-start
  [ "$status" -eq 0 ]
  [[ $output == "Work is refused, for indexes behind the code"* ]]
  [ -e dev/state/refused ]
  echo change >file
  hook turn-end
  [ "$(wrote)" -eq 0 ]
}

@test "turn-start lets work on at a later turn once what refused it passes, and says so" {
  FAIL=index hook session-start '{"source":"startup"}'
  hook turn-start
  hook turn-start
  [ "$status" -eq 0 ]
  [[ $output == "Work isn't refused any more: "* ]]
  [ ! -e dev/state/refused ]
}

@test "turn-start provisions again at a later turn in a container that failed to" {
  export CLAUDE_CODE_REMOTE=true
  hook session-start '{"source":"startup"}'
  hook turn-start
  hook turn-start
  [ "$status" -eq 0 ]
  [[ $output == *"Work is refused, for a container that fails to provision"* ]]
  [ -e dev/state/refused ]
}

@test "turn-start moves a fresh session to the commit its prompt starts at" {
  export CLAUDE_CODE_REMOTE=true
  committed later
  mkdir -p dev/state
  echo fresh >dev/state/session-start
  hook turn-start "{\"prompt\":\"At $(git rev-parse --short HEAD~1), do it\"}"
  [ "$status" -eq 0 ]
  [ "$(subject)" = init ]
  [ "$(git branch --show-current)" = feat ]
  [[ $output == *"a container that fails to provision"* ]]
  [ -e dev/state/refused ]
}

@test "turn-start refuses work at a commit that isn't to be found" {
  export CLAUDE_CODE_REMOTE=true
  mkdir -p dev/state
  echo fresh >dev/state/session-start
  hook turn-start '{"prompt":"At deadbeef"}'
  [ "$status" -eq 0 ]
  [[ $output == *"deadbeef, the commit the prompt starts at, which isn't to be found"* ]]
  [ -e dev/state/refused ]
}

@test "turn-start fast-forwards to what was pushed to the branch" {
  export CLAUDE_CODE_REMOTE=true
  git clone -q ../origin.git ../other 2>/dev/null
  (cd ../other && git switch -q feat && committed pushed && git push -q origin feat)
  hook turn-start
  [ "$status" -eq 0 ]
  [ "$(subject)" = pushed ]
}

@test "turn-start fetches what the operator stamped, and lets go of what it no longer holds" {
  export CLAUDE_CODE_REMOTE=true
  git update-ref refs/stamped/gone HEAD
  git push -q origin HEAD:refs/stamped/feat refs/stamped/gone
  git update-ref -d refs/stamped/feat
  git push -q origin --delete refs/stamped/gone
  hook turn-start
  [ "$status" -eq 0 ]
  [ "$(git rev-parse refs/stamped/feat)" = "$(git rev-parse HEAD)" ]
  run ! git rev-parse --verify -q refs/stamped/gone
}

@test "session-start fetches what the operator stamped before it checks" {
  export CLAUDE_CODE_REMOTE=true
  git push -q origin HEAD:refs/stamped/feat
  hook session-start '{"source":"startup"}'
  [ "$status" -eq 0 ]
  [ "$(git rev-parse refs/stamped/feat)" = "$(git rev-parse HEAD)" ]
}

@test "turn-start tells what was pushed to a branch that went its own way" {
  export CLAUDE_CODE_REMOTE=true
  git clone -q ../origin.git ../other 2>/dev/null
  (cd ../other && git switch -q feat && committed pushed && git push -q origin feat)
  committed own
  hook turn-start
  [ "$status" -eq 0 ]
  [[ $output == "origin/feat has commits feat lacks, up to "*" pushed: commit what changed and merge origin/feat before going on." ]]
  [ "$(subject)" = own ]
  [ ! -e dev/state/refused ]
}

@test "turn-end does nothing while work is refused" {
  hook turn-start
  touch dev/state/refused
  committed work
  hook turn-end
  [ "$status" -eq 0 ]
  [ "$(wrote)" -eq 0 ]
}

@test "turn-end has the turn go on without the commit the turn started at" {
  hook turn-end
  [ "$status" -eq 2 ]
  [[ $output == "turn-end has no commit the turn started at:"* ]]
}

@test "turn-end does nothing when nothing changed" {
  hook turn-start
  hook turn-end
  [ "$status" -eq 0 ]
  [ "$(wrote)" -eq 0 ]
}

@test "turn-end writes and pushes" {
  hook turn-start
  committed work
  hook turn-end
  [ "$status" -eq 0 ]
  grep -qx "write " "$CALLS"
  [ "$(subject)" = work ]
  [ "$(git rev-parse origin/feat)" = "$(git rev-parse HEAD)" ]
}

@test "turn-end commits what it wrote as turn-end" {
  hook turn-start
  committed work
  WRITE_TOUCH=1 hook turn-end
  [ "$status" -eq 0 ]
  [ "$(subject)" = turn-end ]
  [ -z "$(git status --porcelain)" ]
  [ "$(git rev-parse origin/feat)" = "$(git rev-parse HEAD)" ]
}

@test "turn-end has the turn go on when write fails, with what it said" {
  hook turn-start
  committed work
  WRITE_EXIT=1 hook turn-end
  [ "$status" -eq 2 ]
  [[ ${lines[0]} == "./dev/write.sh fails, as below:"* ]]
  [ "${lines[1]}" = "write said" ]
}

@test "turn-end lets the turn end when it went on once already" {
  hook turn-start
  committed work
  WRITE_EXIT=1 hook turn-end '{"stop_hook_active":true}'
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "turn-end has the turn go on with messages untranslated" {
  hook turn-start
  committed work
  UNTRANSLATED="sv: 2 untranslated" hook turn-end
  [ "$status" -eq 2 ]
  [ "${lines[0]}" = "Translate the messages left untranslated before you end the turn:" ]
  [ "${lines[1]}" = "sv: 2 untranslated" ]
}

@test "turn-end pushes a branch rebased over what it pushed before" {
  hook turn-start
  committed work
  git push -q origin feat
  git commit -q --amend -m "work, reworded"
  hook turn-end
  [ "$status" -eq 0 ]
  [ "$(subject origin/feat)" = "work, reworded" ]
}

@test "turn-end pushes nothing over what was pushed meanwhile" {
  git clone -q ../origin.git ../other 2>/dev/null
  (cd ../other && git switch -q feat && committed pushed && git push -q origin feat)
  hook turn-start
  committed work
  hook turn-end
  [ "$status" -eq 2 ]
  [[ ${lines[0]} == "git push fails, as below:"* ]]
  [ "$(subject origin/feat)" = pushed ]
}

@test "hand-over hands nothing over while work is refused" {
  hook turn-start
  touch dev/state/refused
  run ./dev/agent.sh hand-over </dev/null
  [ "$status" -eq 0 ]
  [[ $output == "Work is refused this turn, so nothing is handed over"* ]]
}

@test "hand-over commits, pushes, checks and pushes the logs" {
  hook turn-start
  echo work >work
  run ./dev/agent.sh hand-over </dev/null
  [ "$status" -eq 0 ]
  [ "$output" = "Thanks for your hard work, have a good day!" ]
  [ "$(subject HEAD~1)" = hand-over ]
  [ "$(subject)" = "hand-over: logs" ]
  [ "$(git rev-parse origin/feat)" = "$(git rev-parse HEAD)" ]
  [ "$(cat logs/python-tests.log)" = "python-tests said" ]
  [ "$(sed -n 2,4p "$CALLS" | tr '\n' ' ')" = "check format python-lint frontend docs dev check python-tests check browser " ]
}

@test "hand-over tells what failed, from its log" {
  hook turn-start
  echo work >work
  FAIL=python-tests run ./dev/agent.sh hand-over </dev/null
  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "Handed over with failing Python tests, logged in logs/ and pushed:" ]
  [ "${lines[1]}" = "logs/python-tests.log:" ]
  [ "${lines[2]}" = "FAILED python-tests broke" ]
  [ "$(subject)" = "hand-over: logs" ]
}
