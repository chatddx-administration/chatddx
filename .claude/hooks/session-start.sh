#!/bin/bash
# Readies a Claude Code on the web session: PostgreSQL 16, the Python
# environment, the settings the nix devShell would source, and the branch.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# PostgreSQL 16 doesn't start with the container; tests connect as root.
if ! pg_isready -q; then
  service postgresql start > /dev/null
  for _ in $(seq 1 30); do pg_isready -q && break; sleep 1; done
fi

if ! su postgres -c "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname = 'root'\"" | grep -q 1; then
  su postgres -c "createuser --superuser root"
fi

if ! psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'chatddx'" | grep -q 1; then
  createdb chatddx
fi

# The Python environment, as uv.lock pins it.
export PATH="$HOME/.local/bin:$PATH"
UV_PYTHON=/usr/bin/python3.12 uv sync --frozen --all-groups --quiet

# The settings the devShell sources from .env.
if [ ! -f .env ]; then
  cp .env-example .env
fi

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    grep -E '^[A-Z_]+=' .env | sed 's/^/export /'
    echo "export VIRTUAL_ENV=\"$CLAUDE_PROJECT_DIR/.venv\""
    echo "export PATH=\"$CLAUDE_PROJECT_DIR/.venv/bin:\$HOME/.local/bin:\$PATH\""
  } >> "$CLAUDE_ENV_FILE"
fi

# The branch as the remote has it: fast-forwarded where nothing local is in
# the way, and said otherwise.
branch=$(git rev-parse --abbrev-ref HEAD)

if [ "$branch" != "HEAD" ] && git fetch --quiet origin "$branch" 2> /dev/null; then
  behind=$(git rev-list --count "HEAD..origin/$branch")
  ahead=$(git rev-list --count "origin/$branch..HEAD")

  if [ "$behind" -gt 0 ] && [ "$ahead" -eq 0 ] && git diff --quiet && git diff --cached --quiet; then
    git merge --quiet --ff-only "origin/$branch"
    echo "$branch: fast-forwarded $behind commits from origin"
  elif [ "$behind" -gt 0 ]; then
    echo "$branch: $behind behind and $ahead ahead of origin, or changed locally: not fast-forwarded"
  fi
else
  echo "$branch: not fetched from origin"
fi
