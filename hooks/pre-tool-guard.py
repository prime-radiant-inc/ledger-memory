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

# A raw write is the bare `ledger` binary (optionally path-qualified, possibly
# quoted) followed eventually by a write verb. The ledger token must end at
# whitespace (after an optional closing quote) so that `ledger-memory save` —
# or any path merely *containing* "ledger-memory", such as this very project's
# own store path — can never match. (Found live: the old allowlist was
# `"ledger-memory" not in cmd`, which let every raw write through for any
# project whose path contains that substring.)
# A wrapper *invocation* is allowlisted first, as a token match — so a wrapper
# call whose message text happens to say "ledger set" is never denied. False
# positives block the primary write path and are the one failure this nudge
# must not have; false negatives (eval nesting, exotic quoting, a line that
# both invokes the wrapper and raw-writes) are the accepted cost of string
# matching and are backstopped by the MEMORY.md header, not this guard.
BOUNDARY = r"(?:^|[\s;&|(\"'`])"
# The allowlist requires the wrapper token at a command-start position
# (start of string, after a separator, or after env-var assignments) — a raw
# write whose -m message merely *mentions* "ledger-memory" in prose must not
# vouch for itself. The allowlist can be strict without risk: a wrapper call
# alone never matches RAW_WRITE (the binary token is ledger-memory, not
# ledger), so WRAPPER_CALL only decides the case where a real wrapper call's
# message text also contains a raw-write-looking phrase.
# newline is a shell statement separator, so it belongs in the class; a plain
# space does NOT — that's exactly what separates "wrapper call on its own
# line" (allow) from "prose mention of ledger-memory mid-sentence" (deny)
CMD_START = r"(?:^|[;&|(`\n\r]|\$\()"
WRAPPER_CALL = re.compile(
    rf"{CMD_START}\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*(?:\S*/)?ledger-memory[\"']?\s")
# Both names stay denied: the tool is `chit` from v0.3.0, but `ledger`
# binaries linger on machines and either one can write the store raw.
RAW_WRITE = re.compile(
    rf"{BOUNDARY}(?:\S*/)?(?:ledger|chit)[\"']?\s+(?:\S+\s+)*?(?:set|note|vocab|close|rollup|import|create)\b")

try:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = payload.get("tool_input", {}).get("command", "")
    transcript = payload.get("transcript_path", "")
    memdir = os.path.join(os.path.dirname(transcript), "memory") if transcript else ""

    if memdir and memdir in cmd and RAW_WRITE.search(cmd) \
            and not WRAPPER_CALL.search(cmd):
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
