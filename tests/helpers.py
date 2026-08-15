import json
import os
import shutil
import subprocess
import tempfile
import unittest

WRAPPER = os.path.join(os.path.dirname(__file__), "..", "bin", "ledger-memory")


class WrapperTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ledger-memory-test-")
        self.memdir = os.path.join(self.tmp, "memory")
        os.makedirs(self.memdir)
        self.env = dict(os.environ,
                        LEDGER_MEMORY_DIR=self.memdir,
                        LEDGER_MEMORY_AS="test-session")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def wrap(self, *args, expect=0, env=None):
        p = subprocess.run(["python3", WRAPPER, *args],
                           capture_output=True, text=True, env=env or self.env)
        self.assertEqual(p.returncode, expect,
                         f"{args}: rc={p.returncode}\nstdout={p.stdout}\nstderr={p.stderr}")
        return p

    def ledger(self, *args):
        """Raw ledger call for test setup/verification only — never the write path under test."""
        return subprocess.run([os.environ.get("LEDGER_BIN", "ledger"), *args],
                              cwd=self.memdir, capture_output=True, text=True)

    def projection(self):
        with open(os.path.join(self.memdir, "MEMORY.md")) as f:
            return f.read()
