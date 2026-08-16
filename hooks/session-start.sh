#!/usr/bin/env bash
# SessionStart: render (and bootstrap if needed) the memory projection.
# stdout becomes agent context — stay silent except the compact reminder
# and a damaged-store warning, both of which the agent SHOULD see.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
payload="$(cat)"
transcript="$(printf '%s' "$payload" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("transcript_path",""))')"
source_kind="$(printf '%s' "$payload" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("source",""))')"
[ -n "$transcript" ] || exit 0

export LEDGER_MEMORY_DIR="$(dirname "$transcript")/memory"
mkdir -p "$LEDGER_MEMORY_DIR"
out="$(python3 "$here/../bin/ledger-memory" render 2>&1)"
rc=$?
if [ $rc -ne 0 ]; then
    # any failure (damaged store, missing binary, etc.) must reach the
    # agent, not vanish into a log
    printf 'MEMORY WARNING: %s\n' "$out"
elif [ "$source_kind" = "compact" ]; then
    printf 'Compaction just ran. If working knowledge was lost from the summary, save what you still know: ledger-memory save <name> -m "<fact>" (see MEMORY.md header).\n'
fi
exit 0
