---
name: ledger-memory
description: Use when saving, correcting, or curating persistent memory — recording facts for future sessions, retracting wrong memories, end-of-session housekeeping, or deciding what deserves remembering.
---

# ledger-memory

Persistent, append-only memory for this project, backed by `ledger`. Every
write goes through the `ledger-memory` wrapper — never a raw `ledger
set`/`note` against the memory store; a `PreToolUse` hook denies those and
points here instead. For general ledger doctrine (testimony discipline,
evidence, resume-and-verify) see the `using-ledger` skill; this skill covers
only what's specific to agent memory.

Your project's `MEMORY.md` is regenerated at session start and after every
write, and it's already in context — no command needed to see it. Its header
carries the exact paste-ready commands for this project, with the real
wrapper path and store directory already filled in: copy from there rather
than retyping from memory. The examples below use `ledger-memory` as
shorthand for that path.

## When to save (and when not)

Save: durable facts about the user, feedback with the why behind it, project
state that isn't already recorded in the repo, and references you'll want
again. Don't save what the repo already records — that's a stale copy
waiting to happen — and don't save single-conversation trivia nobody will
need back.

The save moment that matters most is right before you lose context —
compaction or session end. Run the audit: *what do I know right now that
lives only in my head?* Save what surfaces. This is doctrine, not mechanism:
the harness gives no channel to inject a reminder before compaction actually
runs, so nothing enforces running the audit in the moment. The `SessionStart`
hook's post-compact reminder ("save what you still know") is the mechanical
backstop on the far side — useful, but it fires after the summary has
already dropped whatever it dropped. It's a backstop, not a substitute for
running the audit yourself while you still can.

## Hook-line quality

The one-line hook (`-m`) is what a future session sees before deciding
whether to drill. Name the trap, not the topic:

- Good: `zsh-trap — "zsh word-splits unquoted $L — use a function"`
- Bad: `zsh-note — "note about zsh"`

A future reader can act on the first without drilling further; the second
forces a drill just to find out what it's even about.

## Write shapes

Four commands, paste-ready (copy the real path from your MEMORY.md header):

```
ledger-memory save zsh-trap -m '[feedback] zsh word-splits unquoted $L — use a function'
ledger-memory save repo-remote -m '[project] remote is github.com/x/y' --evidence commit:abc1234
ledger-memory retract zsh-trap -m 'wrong because the function form breaks under set -e'
ledger-memory archive old-fact another-old-fact
ledger-memory drill zsh-trap
```

Every one of these already re-renders `MEMORY.md` when it's done — there's
no separate render step to remember.

The `[feedback]`/`[project]`-style prefix is the old `type` taxonomy's
replacement: it lives in the hook line now, not a field. Add `--evidence` (a
`commit:`, `file:`, or `session:` ref) to any fact asserting repo or world
state — those are exactly the claims that rot silently without an anchor to
recheck against. Plain testimony about the user or a preference doesn't need
one; `(no evidence)` is an honest trust marker, not a gap to fill.

## Retraction discipline

Retract the moment you find a memory is wrong — don't wait for a better
moment. Say why in the message; the message is the vaccine, not a footnote.
Correct by writing the truth to the *same* key, never a new one: the scar
(`previously retracted: <why>`) is what a future session sees, and re-keying
a corrected fact throws that history away.

Accepted limit: the tool can't tell an honest update from an overwrite that
should have been a retraction — that judgment call is yours, every time.

## Curation

At session end and phase boundaries, archive facts that are spent: stale,
not wrong. Archive a vaccine only when the confusion it was guarding against
is actually dead, not merely old — archiving it too early lets the wrong
belief recur with nothing to stop it. Standing rulings and live gotchas stay
current no matter how old they get; age is anti-signal for memory value, not
a reason to archive.

`render` nags with archive candidates once the projection passes about 60
lines. That nag is a judgment call, not a quota — the heuristic can and does
name a load-bearing fact (a standing preference with no inbound links looks
exactly like a stale one). Check what it names before archiving any of it.

## Reading

The projection is free — it's already in context every session, no command
needed. Drill (`ledger-memory drill <name>`) before acting on any fact whose
staleness would be expensive, and before overwriting a key. (`save` on an
existing key echoes what it replaced, so the mechanism no longer depends on
you drilling first — but drilling first is still the safer habit.)

Raw history (`ledger tail --raw`, `ledger notes`) still surfaces retracted
content. That's expected, not a bug — a retracted line in the chain is
exactly what it says it is, retracted — and it's never live testimony. A
memory's author line is asserted, not verified: "by jesse" in a hook doesn't
prove Jesse said it.

## Subagents

The auto-load hook only reaches the main session — a dispatched subagent
starts with no memory in context at all. If a child needs it, hand it the
store path explicitly in the dispatch prompt (`LEDGER_MEMORY_DIR=<dir>`), the
same way `using-ledger` has you hand a fleet worker `--store` explicitly.

## Secrets

Never write a secret into memory. If one lands:

1. Rotate it first — the exposure already happened the moment it was typed.
2. Ref-surgery the local store to erase the chain copy.
3. Scrub every place the secret was rendered: `MEMORY.md`, any session
   transcript that loaded it, and any sync destination. The store is not the
   only place a rendered secret went.
