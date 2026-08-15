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

    def test_allows_reads_and_unrelated_commands(self):
        for cmd in (f"ledger show --store {self.memdir}",
                    f"ledger tail --raw --store {self.memdir}",
                    "ledger set foo status=done -m x",   # not the memory store
                    "ls -la"):
            p = run_hook("pre-tool-guard.py", self.payload(cmd))
            self.assertEqual(p.stdout.strip(), "", cmd)  # silence = allow
