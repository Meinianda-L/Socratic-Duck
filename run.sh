#!/usr/bin/env bash
set -e

THIS_FILE="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$0")"
ROOT="$(cd "$(dirname "$THIS_FILE")" && pwd)"
TUI="$ROOT/ui-tui"

if [ "${1:-}" = "setup" ]; then
  exec python3 -m tui_gateway.setup
fi

if [ "${1:-}" = "build" ]; then
  echo "Building ink engine..."
  (cd "$TUI/packages/hermes-ink" && node ../../node_modules/.bin/esbuild src/entry-exports.ts --bundle --platform=node --format=esm --packages=external --outdir=dist)
  mkdir -p "$TUI/node_modules/@hermes/ink/dist"
  cp "$TUI/packages/hermes-ink/dist/entry-exports.js" "$TUI/node_modules/@hermes/ink/dist/"
  echo "Done."
  exit 0
fi

if [ ! -f "$TUI/node_modules/@hermes/ink/dist/entry-exports.js" ]; then
  echo "Building ink engine..."
  (cd "$TUI/packages/hermes-ink" && node ../../node_modules/.bin/esbuild src/entry-exports.ts --bundle --platform=node --format=esm --packages=external --outdir=dist)
  mkdir -p "$TUI/node_modules/@hermes/ink/dist"
  cp "$TUI/packages/hermes-ink/dist/entry-exports.js" "$TUI/node_modules/@hermes/ink/dist/"
fi

[ -f "$TUI/node_modules/esbuild/bin/esbuild" ] || (cd "$TUI/node_modules/esbuild" && node install.js 2>/dev/null || true)

if [ -f "$ROOT/.env" ]; then
  set -a; source "$ROOT/.env"; set +a
fi

export SOCRATIC_ROOT="$ROOT"
export SOCRATIC_CWD="$ROOT"
export SOCRATIC_PYTHON="$(which python3)"
export SOCRATIC_MOUSE_TRACKING="${SOCRATIC_MOUSE_TRACKING:-on}"

cd "$TUI"
exec node node_modules/tsx/dist/cli.mjs src/entry.tsx
