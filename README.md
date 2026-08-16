# ledger-memory

`ledger-memory` is a Claude Code plugin that gives an agent persistent,
append-only memory backed by [`ledger`](https://github.com/prime-radiant-inc/ledger),
replacing the old per-project markdown-file memory system. Facts are ledger
keys with a status field (`current`, `retracted`, `archived`), so retracting
a wrong fact leaves a permanent vaccine instead of silently deleting it, and
a generated `MEMORY.md` projection — never the store itself — is what
actually loads into an agent's context. See the [design
spec](https://github.com/prime-radiant-inc/ledger/blob/main/docs/superpowers/specs/2026-08-15-ledger-memory-design.md)
for the full rationale and the [spike
eval](https://github.com/prime-radiant-inc/ledger/blob/main/research/ledger-memory-spike-eval.md)
(8/8 agents, zero tool errors) that shaped the final write path.

## Requirements

`ledger` v0.1.0+ on PATH:

```
curl -fsSL https://github.com/prime-radiant-inc/ledger/releases/latest/download/install.sh | bash
```

or

```
brew install prime-radiant-inc/tap/ledger
```

## Install

Install like any Claude Code plugin — via your plugin marketplace or
`/plugin` (see the Claude Code docs).

## How it works

Each project gets one bare ledger store under its Claude Code project
directory:

```
~/.claude/projects/<project-slug>/memory/
  .ledger.git      # bare store — never hand-edited
  MEMORY.md        # generated projection — never hand-edited
```

`MEMORY.md` is composed fresh from the store on every session start and
after every write; it's what the harness actually loads into an agent's
context, not the store itself.

Every memory is a key with one field, `status`. A `save` sets `current` and
renders as a fact line. A `retract` sets `retracted` and renders as a
vaccine — "retracted: \<hook\> — wrong because \<why\>" — kept visible until
it's archived, so a future session can't quietly re-derive the same wrong
conclusion. If a key ever carried a retraction and gets saved again, the new
fact renders with a scar ("previously retracted: \<why\>") so a
stale-informed re-assert can't erase the warning. `archive` sets `archived`
and drops a fact (or a spent vaccine) out of the projection without deleting
it from the chain — this, not rollup, is memory's curation primitive;
`ledger-memory drill <name>` reads the full history back.

Writes only ever happen through the `ledger-memory` wrapper — never a raw
`ledger set`/`note` against the store (a `PreToolUse` hook enforces this,
see below). The full write surface is `save`, `retract`, `archive`,
`render`, `drill`:

```
ledger-memory save zsh-trap -m '[feedback] zsh word-splits unquoted $L — use a function'
ledger-memory save repo-remote -m '[project] remote is github.com/x/y' --evidence commit:abc1234
ledger-memory retract zsh-trap -m 'wrong because the function form breaks under set -e'
```

See the `ledger-memory` skill for the full write shapes and doctrine —
retraction discipline, curation, evidence, secrets.

## Hooks

- **SessionStart** (`startup`, `resume`, `clear`, `compact`, `fork`): renders
  the projection, bootstrapping the store on first run. Silent on a normal,
  healthy render. After a `compact` source, it adds one line of context
  reminding the agent to save anything the compaction summary might have
  lost. If the store looks damaged (present but unreadable, or empty while
  `MEMORY.md` still claims a head), it surfaces a warning instead of failing
  silently.
- **PreToolUse** (Bash): denies raw `ledger` write verbs (`set`, `note`,
  `vocab`, `close`, `rollup`, `import`, `create`) aimed at the memory store,
  redirecting to the wrapper. Reads (`show`, `notes`, `tail`, `status`) pass
  through untouched. Documented limitation: the check is a substring match
  against the memory directory's absolute path in the command text, so a
  write that reaches the same store via a relative path or a prior `cd`
  isn't caught. This is a best-effort nudge, not a sandbox — the primary
  defense is the `MEMORY.md` header itself, which tells the agent to use the
  wrapper.

## Uninstall

Removing the plugin removes the wrapper and hooks; it does not touch the
memory store. `~/.claude/projects/<project-slug>/memory/` is a plain git
repository — it survives plugin removal, and nothing about it depends on the
plugin being installed to stay readable.
