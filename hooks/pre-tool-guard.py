#!/usr/bin/env python3
"""PreToolUse guard: the memory ledger's only write path is the wrapper.

Known limitation (accepted, no behavior change intended): the match below is
a substring check against the memory dir's absolute path in the command
text. It misses writes that reach the same store via a relative path or a
prior `cd`, e.g. `cd memory && ledger set ...`. This guard is a best-effort
nudge, not a sandbox — the primary defense is the MEMORY.md header (which
tells the agent to use the wrapper), and the deny reason here exists to
educate, not to guarantee containment. Closing the relative-path gap would
need real shell parsing / cwd tracking, which isn't worth the complexity for
a nudge whose backstop is documentation, not enforcement.

The same looseness also produces false positives: a command that merely
mentions the memory dir's path anywhere and separately contains a write verb
anywhere is denied even when the write targets something else entirely.
Accepted for the same reason — this is a fail-open nudge, not enforcement.
"""
import json
import os
import re
import sys

# A raw write is the bare `ledger` binary (optionally path-qualified) followed
# eventually by a write verb. The ledger token must end at whitespace so that
# `ledger-memory save` — or any path merely *containing* "ledger-memory",
# such as this very project's own store path — can never match. (Found live:
# the old allowlist was `"ledger-memory" not in cmd`, which let every raw
# write through for any project whose path contains that substring.)
RAW_WRITE = re.compile(
    r"(?:^|[\s;&|(])(?:\S*/)?ledger\s+(?:\S+\s+)*?(?:set|note|vocab|close|rollup|import|create)\b")

try:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = payload.get("tool_input", {}).get("command", "")
    transcript = payload.get("transcript_path", "")
    memdir = os.path.join(os.path.dirname(transcript), "memory") if transcript else ""

    if memdir and memdir in cmd and RAW_WRITE.search(cmd):
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason":
                "Raw ledger writes to the memory store bypass rendering, scars, and "
                "evidence carry-forward. Use the wrapper: ledger-memory save/retract/"
                "archive (see MEMORY.md header). Reads (show/notes/tail/status) are fine.",
        }}))
except Exception:
    pass  # fail open: a PreToolUse hook must never crash and block the tool
sys.exit(0)
