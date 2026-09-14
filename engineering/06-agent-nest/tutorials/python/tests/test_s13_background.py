"""s13 background-task mechanism tests.

Replaces the legacy `test_s_full_background.py`, which tested the removed
`agents/s_full.py`. The canonical s13 chapter implements the same mechanism
with `start_background_task` / `collect_background_results` / `should_run_background`.
"""

import importlib.util
import os
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "s13_background_tasks" / "code.py"


def load_s13_module(temp_cwd: Path):
    fake_anthropic = types.ModuleType("anthropic")

    class FakeAnthropic:
        def __init__(self, *args, **kwargs):
            self.messages = types.SimpleNamespace(create=None)

    fake_dotenv = types.ModuleType("dotenv")
    setattr(fake_anthropic, "Anthropic", FakeAnthropic)
    setattr(fake_dotenv, "load_dotenv", lambda override=True: None)

    previous_anthropic = sys.modules.get("anthropic")
    previous_dotenv = sys.modules.get("dotenv")
    previous_cwd = Path.cwd()
    spec = importlib.util.spec_from_file_location("s13_under_test", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)

    sys.modules["anthropic"] = fake_anthropic
    sys.modules["dotenv"] = fake_dotenv
    try:
        os.chdir(temp_cwd)
        os.environ.setdefault("MODEL_ID", "test-model")
        spec.loader.exec_module(module)
        return module
    finally:
        os.chdir(previous_cwd)
        if previous_anthropic is not None:
            sys.modules["anthropic"] = previous_anthropic
        else:
            sys.modules.pop("anthropic", None)
        if previous_dotenv is not None:
            sys.modules["dotenv"] = previous_dotenv
        else:
            sys.modules.pop("dotenv", None)


class BackgroundTaskTests(unittest.TestCase):
    def test_should_run_background_explicit_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = load_s13_module(Path(tmp))
            self.assertTrue(
                module.should_run_background("bash", {"command": "ls", "run_in_background": True})
            )

    def test_should_run_background_slow_heuristic(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = load_s13_module(Path(tmp))
            self.assertTrue(module.should_run_background("bash", {"command": "pip install x"}))
            self.assertFalse(module.should_run_background("bash", {"command": "ls"}))
            self.assertFalse(module.should_run_background("read_file", {"path": "a.txt"}))

    def test_background_task_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            module = load_s13_module(Path(tmp))
            block = SimpleNamespace(
                id="tu_1",
                name="bash",
                input={"command": "echo hello", "run_in_background": True},
            )
            bg_id = module.start_background_task(block)
            self.assertTrue(bg_id.startswith("bg_"))

            notifications = []
            deadline = time.time() + 10
            while time.time() < deadline:
                notifications = module.collect_background_results()
                if notifications:
                    break
                time.sleep(0.05)
            self.assertTrue(notifications, "background task did not complete in time")
            self.assertIn(bg_id, notifications[0])
            self.assertIn("completed", notifications[0])


if __name__ == "__main__":
    unittest.main()
