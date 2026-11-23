#!/usr/bin/env bash
# Usage: ./dev/check.sh [check]..., from the repository's root in the dev shell with its database
# up (dev-db start). Each check tests one thing and writes nothing git tracks; the checks
# named, or all of them, run side by side, and it fails, saying which did, if any does.
# What a check that runs says is also logged to dev/state/logs/<check>.log, as dev/write.sh moves it to logs/.
set -euo pipefail
. dev/settings.sh
. dev/stamped.sh

CHECKS=(openapi index stamps locale pending format python-lint python-tests frontend docs dev browser)

openapi() {
  chatddx openapi | cmp -s - frontend/openapi.json ||
    fail "frontend/openapi.json is behind the code: run chatddx openapi > frontend/openapi.json"
}

index() {
  chatddx-dev index --check
}

# Compromise: the prose is checked only against a commit known to be stamped, lest a guess
# refuse work for what a write would only stamp again.
stamps() {
  local base
  chatddx-dev stamp check
  base="$(stamped)"
  if [[ -n $base ]]; then
    chatddx-dev stamp docs --check "$base"
  else
    echo "stamps: no commit known to be stamped, as dev/stamped.sh tells, so the prose isn't checked" >&2
  fi
}

locale() {
  chatddx locale check
}

pending() {
  chatddx-dev stamp pending
  chatddx locale pending
}

format() {
  ruff format --check
  chatddx-dev stamp reflow --check
  shfmt --diff dev
  RUST_LOG=warn taplo fmt --check
}

python-lint() {
  ruff check
  basedpyright
}

frontend() {
  pnpm --dir frontend check
  timed pnpm --dir frontend test
}

docs() {
  chatddx-dev refcheck
}

dev() {
  shellcheck dev/*.sh dev/test/*.bats
  bats --print-output-on-failure dev/test
}

python-tests() {
  pytest -n 4 -p chatddx.test.budget
}

# Compromise: on their own, for the browser they start.
browser() {
  pnpm --dir frontend build
  pytest -m browser
}

# Duplication: dev/src/chatddx_dev/costs/__init__.py:Cost reads these columns, in this order; it
# spools them likewise only in a checkout, as told by dev/costs.tsv being there.
spooled() {
  local took
  [[ -n ${MACHINE_CLASS:-} && -f dev/costs.tsv ]] || return 0
  mkdir -p dev/state
  took="$(awk -v a="$1" -v b="$EPOCHREALTIME" 'BEGIN { printf "%.1f", b - a }')"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$MACHINE_CLASS" "$took" \
    "$2" "${CHATDDX_BESIDE:-0}" "$(git rev-parse --short HEAD 2>/dev/null)" "$3" >>dev/state/costs-spool.tsv
}

logged() {
  local rc=$?
  [[ -z $began ]] || spooled "$began" "$rc" "./dev/check.sh $check"
  exec >&- 2>&-
  wait "${teed[@]}"
}

timed() {
  local began="$EPOCHREALTIME" rc=0
  "$@" || rc=$?
  spooled "$began" "$rc" "$*"
  return "$rc"
}

fail() {
  echo "$1" >&2
  exit 1
}

# Optimization: a check that passes holds what it read as good in dev/state/<check>-good, and is
# skipped till that changes: what settings.toml's checks.inputs names for it, as a commit of the
# worktree would hold it, for stamps also the commit stamped against, and for docs also
# origin/main, which refcheck checks the commits the docs name against. Outside a git checkout,
# such as nix's, nothing is held.
# Duplication: the tree as dev/agent.sh's tree makes it, but for what checks write.
inputs() {
  local index tree paths
  index="$(mktemp)"
  if cp "$(git rev-parse --git-path index 2>/dev/null)" "$index" 2>/dev/null &&
    GIT_INDEX_FILE="$index" git add --all 2>/dev/null &&
    GIT_INDEX_FILE="$index" git rm -r --cached --quiet --ignore-unmatch dev/costs.tsv logs &&
    setting paths "checks.inputs.$1"; then
    tree="$(GIT_INDEX_FILE="$index" git write-tree)"
    {
      echo "${paths[*]}"
      git ls-tree "$tree" -- dev/check.sh dev/settings.sh "${paths[@]}"
    } | git hash-object --stdin
    [[ $1 != stamps ]] || stamped || true
    [[ $1 != docs ]] || git rev-parse --verify --quiet origin/main || true
  fi
  rm -f "$index"
}

# Optimization: checks named together run side by side, and what each says is said in
# order once all have run.
# Accommodating for bash, which ignores errexit wherever a status is tested: each check
# runs as a process of its own, so that it still stops at its first failure.
# Dependency: frontend's check and browser's build both write
# frontend/src/lib/api/schema.d.ts (pnpm types), so they run one after the other.
lane() {
  local check rc
  trap exit INT TERM
  for check in "$@"; do
    rc=0
    bash "${BASH_SOURCE[0]}" "$check" >"$said/$check.out" 2>"$said/$check.err" || rc=$?
    echo "$rc" >"$said/$check.rc"
  done
}

# Accommodating for a terminal, which interrupts only its foreground process group, and for
# bash, whose background commands ignore interrupts while job control is off: each lane
# runs as a job, a process group of its own without the terminal's input, and relay hands
# it what this gets, then waits for it to stop at the end of its check.
relay() {
  kill -"$1" -- "${lanes[@]/#/-}" 2>/dev/null || true
  wait
  trap - "$1"
  kill -"$1" $$
}

checks=("$@")
[[ ${#checks[@]} -gt 0 ]] || checks=("${CHECKS[@]}")
built=()
others=()
for check in "${checks[@]}"; do
  [[ " ${CHECKS[*]} " == *" $check "* ]] || fail "no check $check: ${CHECKS[*]}"
  case "$check" in
  frontend | browser) built+=("$check") ;;
  *) others+=("$check") ;;
  esac
done
if [[ ${#checks[@]} -eq 1 ]]; then
  check="${checks[0]}"
  good="dev/state/$check-good"
  log="dev/state/logs/$check.log"
  # Policy: a check skipped leaves its log as the run that passed wrote it, so that a log tells of a run.
  was="$(inputs "$check")"
  if [[ -n $was && $was == "$(cat "$good" 2>/dev/null)" ]]; then
    echo "• $check: unchanged since it passed ($good)" >&2
    exit
  fi
  mkdir -p dev/state/logs
  printf '%s %s ./dev/check.sh %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "$(git rev-parse --short HEAD 2>/dev/null)" "$check" >"$log"
  began=""
  teed=()
  exec > >(tee -a "$log")
  teed+=("$!")
  exec 2> >(tee -a "$log" >&2)
  teed+=("$!")
  trap logged EXIT
  echo "• $check" >&2
  began="$EPOCHREALTIME"
  "$check"
  if [[ -n $was && $was == "$(inputs "$check")" ]]; then
    echo "$was" >"$good"
  fi
  exit
fi
said="$(mktemp -d)"
trap 'rm -rf "$said"' EXIT
lanes=()
trap 'relay INT' INT
trap 'relay TERM' TERM
set -m
export CHATDDX_BESIDE=$((${#others[@]} - (${#built[@]} ? 0 : 1)))
if [[ ${#built[@]} -gt 0 ]]; then
  lane "${built[@]}" </dev/null &
  lanes+=("$!")
fi
for check in "${others[@]}"; do
  lane "$check" </dev/null &
  lanes+=("$!")
done
wait
failed=()
for check in "${checks[@]}"; do
  cat "$said/$check.err" >&2
  cat "$said/$check.out"
  [[ $(cat "$said/$check.rc") -eq 0 ]] || failed+=("$check")
done
[[ ${#failed[@]} -eq 0 ]] || fail "• failed: ${failed[*]}"
