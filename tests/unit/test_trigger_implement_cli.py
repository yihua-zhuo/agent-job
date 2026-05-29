import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "dev" / "trigger_implement.py"
SPEC = importlib.util.spec_from_file_location("trigger_implement", MODULE_PATH)
trigger_implement = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(trigger_implement)


class TriggerImplementCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._env_patch = patch.dict(os.environ, {}, clear=True)
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)

    def test_load_env_maps_dot_github_token_to_github_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(".GITHUB_TOKEN=from-dot-env\n", encoding="utf-8")

            trigger_implement.load_env(env_path)

        self.assertEqual(os.environ["GITHUB_TOKEN"], "from-dot-env")
        self.assertEqual(trigger_implement.get_token(), "from-dot-env")

    def test_load_env_does_not_override_existing_standard_token(self) -> None:
        os.environ["GITHUB_TOKEN"] = "already-set"
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(".GITHUB_TOKEN=from-dot-env\n", encoding="utf-8")

            trigger_implement.load_env(env_path)

        self.assertEqual(os.environ["GITHUB_TOKEN"], "already-set")

    def test_detect_repo_supports_https_and_ssh_remotes(self) -> None:
        cases = [
            ("https://github.com/acme/agent-job.git\n", ("acme", "agent-job")),
            ("git@github.com:acme/agent-job.git\n", ("acme", "agent-job")),
        ]
        for stdout, expected in cases:
            with self.subTest(stdout=stdout):
                completed = type("Completed", (), {"returncode": 0, "stdout": stdout})()
                with patch.object(trigger_implement.subprocess, "run", return_value=completed) as run_mock:
                    self.assertEqual(trigger_implement.detect_repo(), expected)
                    run_mock.assert_called_once()
                    call_args = run_mock.call_args
                    self.assertIn("git", call_args.args[0])
                    self.assertIn("remote", call_args.args[0])
                    self.assertIn("get-url", call_args.args[0])
                    self.assertIn("origin", call_args.args[0])

    def test_list_ready_sorts_oldest_first_and_filters_request(self) -> None:
        payload = {
            "items": [
                {"number": 42, "title": "newer"},
                {"number": 7, "title": "older"},
            ]
        }
        with patch.object(trigger_implement, "api", return_value=(200, json.dumps(payload).encode())) as api:
            issues = trigger_implement.list_ready("acme", "agent-job", "token")

        api.assert_called_once()
        self.assertEqual([issue["number"] for issue in issues], [7, 42])
        method, path, token = api.call_args.args
        self.assertEqual(method, "GET")
        self.assertEqual(token, "token")
        self.assertIn("/search/issues?", path)
        self.assertIn("label%3Aready", path)
        self.assertIn("-label%3Awip", path)

    def test_dispatch_posts_workflow_dispatch_payload(self) -> None:
        with patch.object(trigger_implement, "api", return_value=(204, b"")) as api:
            with redirect_stdout(io.StringIO()) as stdout:
                trigger_implement.dispatch("acme", "agent-job", "token", "master", 123)

        api.assert_called_once()
        method, path, token, body = api.call_args.args
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/repos/acme/agent-job/actions/workflows/implement-ready-issues.yml/dispatches")
        self.assertEqual(token, "token")
        self.assertEqual(body, {"ref": "master", "inputs": {"issue_number": "123"}})
        self.assertIn("dispatched: issue #123", stdout.getvalue())

    def test_api_url_error_exits_with_clear_message(self) -> None:
        err = trigger_implement.urllib.error.URLError("dns failed")
        with patch.object(trigger_implement.urllib.request, "urlopen", side_effect=err):
            with patch("sys.stderr", new_callable=io.StringIO) as stderr:
                with self.assertRaises(SystemExit) as raised:
                    trigger_implement.api("GET", "/search/issues?q=x", "token")

        self.assertEqual(raised.exception.code, 1)
        self.assertIn("GitHub API request failed: dns failed", stderr.getvalue())

    def test_main_list_mode_uses_dotenv_token_and_does_not_dispatch(self) -> None:
        completed = type(
            "Completed",
            (),
            {"returncode": 0, "stdout": "https://github.com/acme/agent-job.git\n"},
        )()
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            try:
                os.chdir(tmp)
                Path(".env").write_text(".GITHUB_TOKEN=from-dot-env\n", encoding="utf-8")
                argv = ["trigger_implement.py", "--list"]
                with patch.object(sys, "argv", argv):
                    with patch.object(trigger_implement.subprocess, "run", return_value=completed):
                        with patch.object(trigger_implement, "list_ready", return_value=[]) as list_ready:
                            with patch.object(trigger_implement, "dispatch") as dispatch:
                                with redirect_stdout(io.StringIO()) as stdout:
                                    rc = trigger_implement.main()
            finally:
                os.chdir(cwd)

        self.assertEqual(rc, 0)
        list_ready.assert_called_once_with("acme", "agent-job", "from-dot-env")
        dispatch.assert_not_called()
        self.assertIn("ready issues in acme/agent-job: 0", stdout.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
