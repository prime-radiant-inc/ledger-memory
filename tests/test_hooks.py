import json
import os
import subprocess
import tempfile
import unittest

HOOKS = os.path.join(os.path.dirname(__file__), "..", "hooks")


def run_hook(script, payload, env=None):
    p = subprocess.run([os.path.join(HOOKS, script)],
                       input=json.dumps(payload), capture_output=True,
                       text=True, env=env or os.environ.copy())
    return p


class TestSessionStart(unittest.TestCase):
    def setUp(self):
        self.proj = tempfile.mkdtemp(prefix="proj-")
        self.transcript = os.path.join(self.proj, "abc123.jsonl")

    def test_startup_bootstraps_and_renders_silently(self):
        p = run_hook("session-start.sh",
                     {"transcript_path": self.transcript, "source": "startup"})
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.strip(), "")      # stdout is context: stay silent
        self.assertTrue(os.path.exists(os.path.join(self.proj, "memory", "MEMORY.md")))

    def test_compact_injects_reminder(self):
        p = run_hook("session-start.sh",
                     {"transcript_path": self.transcript, "source": "compact"})
        self.assertEqual(p.returncode, 0)
        self.assertIn("save what you still know", p.stdout)

    def test_damaged_store_reports_instead_of_failing_silently(self):
        os.makedirs(os.path.join(self.proj, "memory", ".ledger.git"))
        with open(os.path.join(self.proj, "memory", "MEMORY.md"), "w") as f:
            f.write("store head: deadbeef00\n")
        p = run_hook("session-start.sh",
                     {"transcript_path": self.transcript, "source": "startup"})
        self.assertIn("damaged", p.stdout)          # surfaced as context, not swallowed

    def test_any_nonzero_rc_surfaces_as_warning(self):
        # no `ledger` reachable on PATH, and LEDGER_BIN unset: any failure
        # (not just the damaged-store exit code 2) must reach the agent
        env = {"PATH": "/usr/bin:/bin"}
        p = run_hook("session-start.sh",
                     {"transcript_path": self.transcript, "source": "startup"}, env=env)
        self.assertIn("MEMORY WARNING", p.stdout)
        self.assertIn("install.sh", p.stdout)        # the install hint


class TestPreToolGuard(unittest.TestCase):
    def setUp(self):
        self.proj = tempfile.mkdtemp(prefix="proj-")
        self.memdir = os.path.join(self.proj, "memory")
        os.makedirs(self.memdir)
        self.transcript = os.path.join(self.proj, "x.jsonl")

    def payload(self, command):
        return {"tool_name": "Bash", "tool_input": {"command": command},
                "transcript_path": self.transcript}

    def deny_reason(self, p):
        doc = json.loads(p.stdout)
        return doc["hookSpecificOutput"]["permissionDecision"], \
               doc["hookSpecificOutput"]["permissionDecisionReason"]

    def test_denies_raw_write_to_memory_store(self):
        p = run_hook("pre-tool-guard.py",
                     self.payload(f"ledger set foo status=current -m x --store {self.memdir}"))
        decision, reason = self.deny_reason(p)
        self.assertEqual(decision, "deny")
        self.assertIn("ledger-memory", reason)      # redirect names the wrapper

    def test_denies_raw_chit_write_to_memory_store(self):
        # The tool renamed to chit at v0.3.0; the renamed binary must not
        # walk past a guard that matches the old name only.
        p = run_hook("pre-tool-guard.py",
                     self.payload(f"chit set foo status=current -m x --store {self.memdir}"))
        decision, reason = self.deny_reason(p)
        self.assertEqual(decision, "deny")
        self.assertIn("ledger-memory", reason)

    def test_allows_reads_and_unrelated_commands(self):
        for cmd in (f"ledger show --store {self.memdir}",
                    f"ledger tail --raw --store {self.memdir}",
                    "ledger set foo status=done -m x",   # not the memory store
                    "ls -la"):
            p = run_hook("pre-tool-guard.py", self.payload(cmd))
            self.assertEqual(p.stdout.strip(), "", cmd)  # silence = allow



    def test_denies_raw_write_when_project_path_contains_ledger_memory(self):
        # the live-found bug: a store path containing "ledger-memory" (e.g. the
        # ledger-memory repo's own project dir) defeated the old allowlist
        proj = os.path.join(self.proj, "-Users-x-git-ledger-memory")
        memdir = os.path.join(proj, "memory")
        os.makedirs(memdir)
        p = run_hook("pre-tool-guard.py",
                     {"tool_name": "Bash",
                      "tool_input": {"command": f"ledger set probe status=current -m test --store {memdir}"},
                      "transcript_path": os.path.join(proj, "x.jsonl")})
        doc = json.loads(p.stdout)
        self.assertEqual(doc["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_allows_wrapper_even_under_ledger_memory_path(self):
        proj = os.path.join(self.proj, "-Users-x-git-ledger-memory")
        memdir = os.path.join(proj, "memory")
        os.makedirs(memdir)
        for cmd in (f"/x/bin/ledger-memory save k -m hi",
                    f"LEDGER_MEMORY_DIR={memdir} /x/bin/ledger-memory save k -m hi",
                    f"ledger-memory retract k -m 'wrong because {memdir}'"):
            p = run_hook("pre-tool-guard.py",
                         {"tool_name": "Bash", "tool_input": {"command": cmd},
                          "transcript_path": os.path.join(proj, "x.jsonl")})
            self.assertEqual(p.stdout.strip(), "", cmd)



    def test_denies_quoted_and_nested_raw_writes(self):
        # hotfix-review reproductions: quoting/nesting must not elude the deny
        memdir = self.memdir
        for cmd in ('"ledger" set probe status=current -m t --store ' + memdir,
                    'eval "ledger set probe status=current -m t --store ' + memdir + '"',
                    "bash -c 'ledger set probe status=current -m t --store " + memdir + "'",
                    "`ledger set probe status=current -m t --store " + memdir + "`"):
            p = run_hook("pre-tool-guard.py", self.payload(cmd))
            doc = json.loads(p.stdout)
            self.assertEqual(doc["hookSpecificOutput"]["permissionDecision"], "deny", cmd)

    def test_wrapper_call_with_ledger_verb_in_message_is_allowed(self):
        # regression from the 0.1.1 fix: dropping the allowlist blocked wrapper
        # calls whose message text mentions a raw-write phrase
        cmd = ('/x/bin/ledger-memory save probe -m '
               '"context: user asked to ledger set this on entry" --store ' + self.memdir)
        p = run_hook("pre-tool-guard.py", self.payload(cmd))
        self.assertEqual(p.stdout.strip(), "", cmd)



    def test_raw_write_mentioning_wrapper_name_in_message_is_denied(self):
        # re-review finding: prose mention of "ledger-memory" in a raw write's
        # own -m text must not vouch for it
        for cmd in ('ledger set foo -m "note: switch to ledger-memory going forward" --store ' + self.memdir,
                    'ledger note foo -m "see the ledger-memory docs for details" --store ' + self.memdir):
            p = run_hook("pre-tool-guard.py", self.payload(cmd))
            doc = json.loads(p.stdout)
            self.assertEqual(doc["hookSpecificOutput"]["permissionDecision"], "deny", cmd)

    def test_env_prefixed_wrapper_call_is_allowed(self):
        cmd = ("LEDGER_MEMORY_DIR=" + self.memdir +
               ' /x/bin/ledger-memory save k -m "will ledger set this later"')
        p = run_hook("pre-tool-guard.py", self.payload(cmd))
        self.assertEqual(p.stdout.strip(), "", cmd)



    def test_multiline_wrapper_call_with_ledger_verb_in_message_is_allowed(self):
        # newline is a statement separator: a wrapper call on its own line
        # must vouch for itself even with a raw-write phrase in its message
        cmd = ('echo hi\n/x/bin/ledger-memory save foo '
               '-m "will ledger set this later" --store ' + self.memdir)
        p = run_hook("pre-tool-guard.py", self.payload(cmd))
        self.assertEqual(p.stdout.strip(), "", cmd)

    def test_malformed_stdin_fails_open_silently(self):
        for garbage in ("not json", "", "[]", '"x"'):
            p = subprocess.run([os.path.join(HOOKS, "pre-tool-guard.py")],
                               input=garbage, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, garbage)
            self.assertEqual(p.stdout.strip(), "", garbage)
