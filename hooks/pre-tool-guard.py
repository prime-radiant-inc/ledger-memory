#!/usr/bin/env python3
"""PreToolUse guard: the memory ledger's only write path is the wrapper."""
import json
import os
import re
import sys

WRITE_VERBS = r"(set|note|vocab|close|rollup|import|create)"

payload = json.load(sys.stdin)
if payload.get("tool_name") != "Bash":
    sys.exit(0)
cmd = payload.get("tool_input", {}).get("command", "")
transcript = payload.get("transcript_path", "")
memdir = os.path.join(os.path.dirname(transcript), "memory") if transcript else ""

if memdir and memdir in cmd and re.search(rf"\bledger\b(?:\s+\S+)*?\s+{WRITE_VERBS}\b", cmd) \
        and "ledger-memory" not in cmd:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason":
            "Raw ledger writes to the memory store bypass rendering, scars, and "
            "evidence carry-forward. Use the wrapper: ledger-memory save/retract/"
            "archive (see MEMORY.md header). Reads (show/notes/tail/status) are fine.",
    }}))
sys.exit(0)
