#!/usr/bin/env python3
"""
Unit tests for Git and GitHubClient classes in claude_code_review.py.

Run with:
    python -m pytest test_claude_code_review.py -v
    # or
    python -m unittest test_claude_code_review -v
"""

from __future__ import annotations

import http.client
import json
import os
import subprocess
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, Mock, call, patch

# ---------------------------------------------------------------------------
# Import the module under test.
# Assumes both files live in the same directory; adjust sys.path if needed.
# ---------------------------------------------------------------------------
import sys
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).parent))

from claude_code_review import (
    Git,
    GitHubClient,
    ReviewIssue,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _make_http_response(body: Any, status: int = 200) -> MagicMock:
    """Return a context-manager mock that mimics urllib's http.client.HTTPResponse."""
    raw = json.dumps(body).encode() if body is not None else b""
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read.return_value = raw
    mock_resp.status = status
    return mock_resp


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ===========================================================================
# Git — low-level execution
# ===========================================================================

class TestGitRun(unittest.TestCase):
    """Git.run / Git.run_safe — subprocess dispatch."""

    def setUp(self) -> None:
        self.git = Git(remote="origin")

    @patch("claude_code_review.subprocess.run")
    def test_run_returns_stdout(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _completed(stdout="abc123\n")
        result = self.git.run(["git", "rev-parse", "HEAD"])
        self.assertEqual(result, "abc123\n")
        mock_run.assert_called_once_with(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        )

    @patch("claude_code_review.subprocess.run")
    def test_run_raises_on_nonzero_by_default(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")
        with self.assertRaises(subprocess.CalledProcessError):
            self.git.run(["git", "bad-command"])

    @patch("claude_code_review.subprocess.run")
    def test_run_safe_returns_none_on_error(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")
        self.assertIsNone(self.git.run_safe(["git", "remote", "get-url", "origin"]))

    @patch("claude_code_review.subprocess.run")
    def test_run_safe_returns_stdout_on_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _completed(stdout="main\n")
        self.assertEqual(self.git.run_safe(["git", "branch", "--show-current"]), "main\n")


# ===========================================================================
# Git — repository info
# ===========================================================================

class TestGitRemoteUrl(unittest.TestCase):
    def setUp(self) -> None:
        self.git = Git(remote="origin")

    @patch.object(Git, "run_safe", return_value="git@github.com:acme/repo.git\n")
    def test_remote_url_uses_instance_remote_by_default(self, mock_run_safe: MagicMock) -> None:
        url = self.git.remote_url()
        mock_run_safe.assert_called_once_with(["git", "remote", "get-url", "origin"])
        self.assertEqual(url, "git@github.com:acme/repo.git\n")

    @patch.object(Git, "run_safe", return_value=None)
    def test_remote_url_returns_none_when_command_fails(self, _: MagicMock) -> None:
        self.assertIsNone(self.git.remote_url())

    @patch.object(Git, "run_safe", return_value="git@github.com:acme/repo.git\n")
    def test_remote_url_accepts_explicit_remote(self, mock_run_safe: MagicMock) -> None:
        self.git.remote_url("upstream")
        mock_run_safe.assert_called_once_with(["git", "remote", "get-url", "upstream"])


class TestGitInferGithubRepo(unittest.TestCase):
    def setUp(self) -> None:
        self.git = Git(remote="origin")

    @patch.object(Git, "remote_url", return_value="git@github.com:acme/myrepo.git\n")
    def test_ssh_url_without_dot_git(self, _: MagicMock) -> None:
        self.assertEqual(self.git.infer_github_repo(), "acme/myrepo")

    @patch.object(Git, "remote_url", return_value="https://github.com/acme/myrepo.git\n")
    def test_https_url_with_dot_git(self, _: MagicMock) -> None:
        self.assertEqual(self.git.infer_github_repo(), "acme/myrepo")

    @patch.object(Git, "remote_url", return_value="https://github.com/acme/myrepo\n")
    def test_https_url_without_dot_git(self, _: MagicMock) -> None:
        self.assertEqual(self.git.infer_github_repo(), "acme/myrepo")

    @patch.object(Git, "remote_url", return_value="http://github.com/acme/myrepo.git")
    def test_http_url(self, _: MagicMock) -> None:
        self.assertEqual(self.git.infer_github_repo(), "acme/myrepo")

    @patch.object(Git, "remote_url", return_value="https://gitlab.com/acme/myrepo.git")
    def test_non_github_url_returns_none(self, _: MagicMock) -> None:
        self.assertIsNone(self.git.infer_github_repo())

    @patch.object(Git, "remote_url", return_value=None)
    def test_no_remote_url_returns_none(self, _: MagicMock) -> None:
        self.assertIsNone(self.git.infer_github_repo())

    @patch.object(Git, "remote_url", return_value="git@github.com:acme/myrepo.git")
    def test_passes_explicit_remote_through(self, mock_remote_url: MagicMock) -> None:
        self.git.infer_github_repo(remote="upstream")
        mock_remote_url.assert_called_once_with("upstream")


# ===========================================================================
# Git — revision resolution
# ===========================================================================

class TestGitRevisionExists(unittest.TestCase):
    def setUp(self) -> None:
        self.git = Git()

    @patch("claude_code_review.subprocess.run")
    def test_returns_true_on_zero_exit(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _completed(returncode=0)
        self.assertTrue(self.git.revision_exists("main"))

    @patch("claude_code_review.subprocess.run")
    def test_returns_false_on_nonzero_exit(self, mock_run: MagicMock) -> None:
        mock_run.return_value = _completed(returncode=128)
        self.assertFalse(self.git.revision_exists("nonexistent-branch"))


class TestGitResolveRevision(unittest.TestCase):
    def setUp(self) -> None:
        self.git = Git(remote="origin")

    def _patch_exists(self, existing: set[str]) -> MagicMock:
        return patch.object(Git, "revision_exists", side_effect=lambda r: r in existing)

    def test_commit_hash_resolved_directly(self) -> None:
        sha = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
        with self._patch_exists({sha}):
            self.assertEqual(self.git.resolve_revision(sha), sha)

    def test_short_hash_resolved_directly(self) -> None:
        sha = "abc1234"
        with self._patch_exists({sha}):
            self.assertEqual(self.git.resolve_revision(sha), sha)

    def test_branch_name_prefers_remote_qualified(self) -> None:
        with self._patch_exists({"origin/develop"}):
            self.assertEqual(self.git.resolve_revision("develop"), "origin/develop")

    def test_branch_name_falls_back_to_bare_name(self) -> None:
        with self._patch_exists({"develop"}):
            self.assertEqual(self.git.resolve_revision("develop"), "develop")

    def test_main_falls_back_to_master(self) -> None:
        with self._patch_exists({"origin/master"}):
            self.assertEqual(self.git.resolve_revision("main"), "origin/master")

    def test_master_falls_back_to_main(self) -> None:
        with self._patch_exists({"origin/main"}):
            self.assertEqual(self.git.resolve_revision("master"), "origin/main")

    def test_raises_value_error_when_nothing_found(self) -> None:
        with self._patch_exists(set()):
            with self.assertRaises(ValueError):
                self.git.resolve_revision("ghost-branch")

    def test_custom_remote_used_in_candidates(self) -> None:
        with self._patch_exists({"upstream/feature"}):
            result = self.git.resolve_revision("feature", remote="upstream")
        self.assertEqual(result, "upstream/feature")

    def test_no_duplicates_in_candidate_traversal(self) -> None:
        """resolve_revision must not check the same candidate twice."""
        calls: list[str] = []

        def exists(r: str) -> bool:
            calls.append(r)
            return r == "origin/main"

        with patch.object(Git, "revision_exists", side_effect=exists):
            self.git.resolve_revision("main")

        self.assertEqual(len(calls), len(set(calls)), "duplicate candidates checked")


# ===========================================================================
# Git — fetch / commit operations
# ===========================================================================

class TestGitFetch(unittest.TestCase):
    def setUp(self) -> None:
        self.git = Git(remote="origin")

    @patch.object(Git, "run")
    def test_fetch_calls_git_fetch_with_refs(self, mock_run: MagicMock) -> None:
        self.git.fetch("master", "develop")
        mock_run.assert_called_once_with(
            ["git", "fetch", "--quiet", "--no-write-fetch-head", "origin", "master", "develop"]
        )

    @patch.object(Git, "run")
    def test_fetch_with_no_refs_does_nothing(self, mock_run: MagicMock) -> None:
        self.git.fetch()
        mock_run.assert_not_called()


class TestGitCurrentHead(unittest.TestCase):
    @patch.object(Git, "run", return_value="deadbeef1234567890\n")
    def test_strips_trailing_newline(self, _: MagicMock) -> None:
        git = Git()
        self.assertEqual(git.current_head(), "deadbeef1234567890")


class TestGitCommitHash(unittest.TestCase):
    @patch.object(Git, "run", return_value="cafebabe\n")
    def test_strips_newline(self, mock_run: MagicMock) -> None:
        git = Git()
        result = git.commit_hash("origin/master")
        self.assertEqual(result, "cafebabe")
        mock_run.assert_called_once_with(["git", "log", "-1", "--format=%H", "origin/master"])


class TestGitChangedFiles(unittest.TestCase):
    def setUp(self) -> None:
        self.git = Git()

    @patch.object(Git, "run", return_value="src/a.py\nsrc/b.py\n")
    def test_returns_list_of_files(self, _: MagicMock) -> None:
        files = self.git.changed_files("base_sha", "head_sha")
        self.assertEqual(files, ["src/a.py", "src/b.py"])

    @patch.object(Git, "run", return_value="")
    def test_returns_empty_list_when_no_changes(self, _: MagicMock) -> None:
        self.assertEqual(self.git.changed_files("a", "b"), [])

    @patch.object(Git, "run", return_value="  src/spaced.py  \n")
    def test_strips_whitespace_from_filenames(self, _: MagicMock) -> None:
        self.assertEqual(self.git.changed_files("a", "b"), ["src/spaced.py"])

    @patch.object(Git, "run")
    def test_passes_correct_diff_filter(self, mock_run: MagicMock) -> None:
        mock_run.return_value = ""
        self.git.changed_files("base", "head")
        args = mock_run.call_args[0][0]
        self.assertIn("--diff-filter=ACMRTUX", args)
        self.assertIn("--name-only", args)


# ===========================================================================
# Git — current_branch
# ===========================================================================

class TestGitCurrentBranch(unittest.TestCase):
    def setUp(self) -> None:
        self.git = Git()
        # Always clear relevant env vars before each test
        for key in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME", "GITHUB_REF"):
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME", "GITHUB_REF"):
            os.environ.pop(key, None)

    def test_prefers_github_head_ref(self) -> None:
        os.environ["GITHUB_HEAD_REF"] = "feature/my-branch"
        self.assertEqual(self.git.current_branch(), "feature/my-branch")

    def test_falls_back_to_github_ref_name(self) -> None:
        os.environ["GITHUB_REF_NAME"] = "release/1.0"
        self.assertEqual(self.git.current_branch(), "release/1.0")

    def test_strips_refs_heads_prefix(self) -> None:
        os.environ["GITHUB_REF"] = "refs/heads/hotfix/urgent"
        self.assertEqual(self.git.current_branch(), "hotfix/urgent")

    @patch.object(Git, "run_safe", return_value="local-branch\n")
    def test_falls_back_to_git_command(self, _: MagicMock) -> None:
        self.assertEqual(self.git.current_branch(), "local-branch")

    @patch.object(Git, "run_safe", return_value=None)
    def test_returns_empty_string_when_all_fail(self, _: MagicMock) -> None:
        self.assertEqual(self.git.current_branch(), "")


# ===========================================================================
# Git — diff_for_file
# ===========================================================================

class TestGitDiffForFile(unittest.TestCase):
    @patch.object(Git, "run_safe", return_value="@@ -1,3 +1,4 @@\n+new line\n")
    def test_returns_diff_output(self, mock_run_safe: MagicMock) -> None:
        git = Git()
        diff = git.diff_for_file("base", "head", "src/main.py")
        self.assertIn("+new line", diff)
        mock_run_safe.assert_called_once_with(["git", "diff", "base", "head", "--", "src/main.py"])

    @patch.object(Git, "run_safe", return_value=None)
    def test_returns_empty_string_when_command_fails(self, _: MagicMock) -> None:
        git = Git()
        self.assertEqual(git.diff_for_file("a", "b", "missing.py"), "")


# ===========================================================================
# GitHubClient — request / HTTP layer
# ===========================================================================

class TestGitHubClientRequest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = GitHubClient(token="tok_test", repo="acme/myrepo")

    @patch("claude_code_review.urlopen")
    def test_get_constructs_correct_url(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _make_http_response({"id": 1})
        self.client.get("/pulls/1")
        req: Request = mock_urlopen.call_args[0][0]
        self.assertEqual(req.full_url, "https://api.github.com/repos/acme/myrepo/pulls/1")
        self.assertEqual(req.get_method(), "GET")

    @patch("claude_code_review.urlopen")
    def test_get_with_params_adds_query_string(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _make_http_response([])
        self.client.get("/pulls", {"state": "open", "head": "acme:feat"})
        req: Request = mock_urlopen.call_args[0][0]
        self.assertIn("state=open", req.full_url)
        self.assertIn("head=acme", req.full_url)

    @patch("claude_code_review.urlopen")
    def test_authorization_header_sent(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _make_http_response({})
        self.client.get("/pulls/1")
        req: Request = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_header("Authorization"), "Bearer tok_test")

    @patch("claude_code_review.urlopen")
    def test_post_sends_json_body(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _make_http_response({"id": 99})
        self.client.post("/issues/1/comments", {"body": "hello"})
        req: Request = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(json.loads(req.data), {"body": "hello"})

    @patch("claude_code_review.urlopen")
    def test_patch_sends_json_body(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _make_http_response({"id": 99})
        self.client.patch("/issues/comments/42", {"body": "updated"})
        req: Request = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_method(), "PATCH")
        self.assertEqual(json.loads(req.data), {"body": "updated"})

    @patch("claude_code_review.urlopen")
    def test_delete_uses_delete_method(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _make_http_response(None)
        self.client.delete("/pulls/comments/7")
        req: Request = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_method(), "DELETE")

    @patch("claude_code_review.urlopen")
    def test_returns_none_for_empty_response_body(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _make_http_response(None)
        result = self.client.delete("/pulls/comments/7")
        self.assertIsNone(result)

    @patch("claude_code_review.urlopen")
    def test_github_api_version_header_present(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _make_http_response({})
        self.client.get("/pulls/1")
        req: Request = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_header("X-github-api-version"), "2022-11-28")


# ===========================================================================
# GitHubClient — PR number resolution
# ===========================================================================

class TestGitHubClientPrNumberFromEvent(unittest.TestCase):
    def setUp(self) -> None:
        self.client = GitHubClient(token="t", repo="o/r")

    def test_returns_none_when_env_var_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(self.client.pr_number_from_event())

    def test_reads_top_level_number(self) -> None:
        event = {"number": 42, "pull_request": {"number": 99}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(event, fh)
            path = fh.name
        try:
            with patch.dict(os.environ, {"GITHUB_EVENT_PATH": path}):
                self.assertEqual(self.client.pr_number_from_event(), 42)
        finally:
            os.unlink(path)

    def test_falls_back_to_pull_request_number(self) -> None:
        event = {"pull_request": {"number": 7}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(event, fh)
            path = fh.name
        try:
            with patch.dict(os.environ, {"GITHUB_EVENT_PATH": path}):
                self.assertEqual(self.client.pr_number_from_event(), 7)
        finally:
            os.unlink(path)

    def test_returns_none_when_no_pr_in_event(self) -> None:
        event = {"action": "push"}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(event, fh)
            path = fh.name
        try:
            with patch.dict(os.environ, {"GITHUB_EVENT_PATH": path}):
                self.assertIsNone(self.client.pr_number_from_event())
        finally:
            os.unlink(path)

    def test_returns_none_for_corrupted_json(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write("not json {{{")
            path = fh.name
        try:
            with patch.dict(os.environ, {"GITHUB_EVENT_PATH": path}):
                self.assertIsNone(self.client.pr_number_from_event())
        finally:
            os.unlink(path)

    def test_returns_none_for_nonexistent_path(self) -> None:
        with patch.dict(os.environ, {"GITHUB_EVENT_PATH": "/does/not/exist.json"}):
            self.assertIsNone(self.client.pr_number_from_event())


class TestGitHubClientPrNumberFromBranch(unittest.TestCase):
    def setUp(self) -> None:
        self.client = GitHubClient(token="t", repo="acme/repo")

    @patch.object(GitHubClient, "get", return_value=[{"number": 5}])
    def test_returns_first_open_pr(self, mock_get: MagicMock) -> None:
        result = self.client.pr_number_from_branch("feature/x")
        self.assertEqual(result, 5)
        mock_get.assert_called_once_with("/pulls", {"state": "open", "head": "acme:feature/x"})

    @patch.object(GitHubClient, "get", return_value=[])
    def test_returns_none_when_no_matching_pr(self, _: MagicMock) -> None:
        self.assertIsNone(self.client.pr_number_from_branch("orphan-branch"))

    @patch.object(GitHubClient, "get", return_value=None)
    def test_handles_none_response_gracefully(self, _: MagicMock) -> None:
        self.assertIsNone(self.client.pr_number_from_branch("branch"))


class TestGitHubClientResolvePrNumber(unittest.TestCase):
    def setUp(self) -> None:
        self.client = GitHubClient(token="t", repo="o/r")

    @patch.object(GitHubClient, "pr_number_from_event", return_value=10)
    @patch.object(GitHubClient, "pr_number_from_branch")
    def test_prefers_event_number(self, mock_branch: MagicMock, _: MagicMock) -> None:
        result = self.client.resolve_pr_number("some-branch")
        self.assertEqual(result, 10)
        mock_branch.assert_not_called()

    @patch.object(GitHubClient, "pr_number_from_event", return_value=None)
    @patch.object(GitHubClient, "pr_number_from_branch", return_value=20)
    def test_falls_back_to_branch_lookup(self, mock_branch: MagicMock, _: MagicMock) -> None:
        result = self.client.resolve_pr_number("my-branch")
        self.assertEqual(result, 20)
        mock_branch.assert_called_once_with("my-branch")

    @patch.object(GitHubClient, "pr_number_from_event", return_value=None)
    @patch.object(GitHubClient, "pr_number_from_branch", return_value=None)
    def test_returns_none_when_both_fail(self, *_: MagicMock) -> None:
        self.assertIsNone(self.client.resolve_pr_number("branch"))


# ===========================================================================
# GitHubClient — PR head SHA
# ===========================================================================

class TestGitHubClientGetPrHeadSha(unittest.TestCase):
    def setUp(self) -> None:
        self.client = GitHubClient(token="t", repo="o/r")

    @patch.object(GitHubClient, "get", return_value={"head": {"sha": "abc123"}})
    def test_returns_sha(self, mock_get: MagicMock) -> None:
        sha = self.client.get_pr_head_sha(1)
        self.assertEqual(sha, "abc123")
        mock_get.assert_called_once_with("/pulls/1")

    @patch.object(GitHubClient, "get", return_value={})
    def test_returns_none_when_missing(self, _: MagicMock) -> None:
        self.assertIsNone(self.client.get_pr_head_sha(1))

    @patch.object(GitHubClient, "get", return_value=None)
    def test_handles_none_response(self, _: MagicMock) -> None:
        self.assertIsNone(self.client.get_pr_head_sha(1))


# ===========================================================================
# GitHubClient — upsert_summary_comment
# ===========================================================================

class TestGitHubClientUpsertSummaryComment(unittest.TestCase):
    MARKER = GitHubClient.REVIEW_MARKER

    def setUp(self) -> None:
        self.client = GitHubClient(token="t", repo="o/r")

    @patch.object(GitHubClient, "post")
    @patch.object(GitHubClient, "patch")
    @patch.object(GitHubClient, "get", return_value=[])
    def test_creates_new_comment_when_none_exists(
        self, _get: MagicMock, mock_patch: MagicMock, mock_post: MagicMock
    ) -> None:
        self.client.upsert_summary_comment(pr_number=3, body="new body")
        mock_post.assert_called_once_with("/issues/3/comments", {"body": "new body"})
        mock_patch.assert_not_called()

    @patch.object(GitHubClient, "post")
    @patch.object(GitHubClient, "patch")
    @patch.object(
        GitHubClient,
        "get",
        return_value=[{"id": 55, "body": f"{GitHubClient.REVIEW_MARKER}\nold content"}],
    )
    def test_patches_existing_comment(
        self, _get: MagicMock, mock_patch: MagicMock, mock_post: MagicMock
    ) -> None:
        self.client.upsert_summary_comment(pr_number=3, body="updated body")
        mock_patch.assert_called_once_with("/issues/comments/55", {"body": "updated body"})
        mock_post.assert_not_called()

    @patch.object(GitHubClient, "post")
    @patch.object(GitHubClient, "patch")
    @patch.object(
        GitHubClient,
        "get",
        return_value=[{"id": 1, "body": "unrelated comment"}],
    )
    def test_ignores_unrelated_comments(
        self, _get: MagicMock, mock_patch: MagicMock, mock_post: MagicMock
    ) -> None:
        self.client.upsert_summary_comment(pr_number=3, body="body")
        mock_post.assert_called_once()
        mock_patch.assert_not_called()


# ===========================================================================
# GitHubClient — dismiss_previous_review_comments
# ===========================================================================

class TestGitHubClientDismissPreviousReviewComments(unittest.TestCase):
    MARKER = GitHubClient.REVIEW_MARKER

    def setUp(self) -> None:
        self.client = GitHubClient(token="t", repo="o/r")

    @patch.object(GitHubClient, "delete")
    @patch.object(
        GitHubClient,
        "get",
        return_value=[
            {"id": 10, "body": f"{GitHubClient.REVIEW_MARKER}\nstale issue"},
            {"id": 11, "body": "unrelated review comment"},
            {"id": 12, "body": f"{GitHubClient.REVIEW_MARKER}\nanother stale issue"},
        ],
    )
    def test_deletes_only_marker_comments(self, _get: MagicMock, mock_delete: MagicMock) -> None:
        self.client.dismiss_previous_review_comments(pr_number=5)
        self.assertEqual(mock_delete.call_count, 2)
        mock_delete.assert_any_call("/pulls/comments/10")
        mock_delete.assert_any_call("/pulls/comments/12")

    @patch.object(GitHubClient, "delete")
    @patch.object(GitHubClient, "get", return_value=[])
    def test_no_calls_when_no_comments(self, _get: MagicMock, mock_delete: MagicMock) -> None:
        self.client.dismiss_previous_review_comments(pr_number=5)
        mock_delete.assert_not_called()

    @patch.object(GitHubClient, "delete", side_effect=Exception("network error"))
    @patch.object(
        GitHubClient,
        "get",
        return_value=[{"id": 7, "body": GitHubClient.REVIEW_MARKER}],
    )
    def test_silently_swallows_delete_errors(self, _get: MagicMock, _delete: MagicMock) -> None:
        # Should not raise even if delete fails
        self.client.dismiss_previous_review_comments(pr_number=5)


# ===========================================================================
# GitHubClient — post_review_with_inline_comments
# ===========================================================================

class TestGitHubClientPostReviewWithInlineComments(unittest.TestCase):
    def setUp(self) -> None:
        self.client = GitHubClient(token="t", repo="o/r")

    def _make_issues(self, specs: list[dict]) -> list[ReviewIssue]:
        return [
            ReviewIssue(
                file=s.get("file", "src/a.py"),
                line=s.get("line", 10),
                severity=s.get("severity", "warning"),
                message=s.get("message", "some issue"),
            )
            for s in specs
        ]

    @patch.object(GitHubClient, "post")
    def test_posts_single_review_with_inline_comments(self, mock_post: MagicMock) -> None:
        issues = self._make_issues([
            {"file": "a.py", "line": 5, "severity": "warning", "message": "use f-string"},
            {"file": "b.py", "line": 12, "severity": "critical", "message": "null deref"},
        ])
        self.client.post_review_with_inline_comments(
            pr_number=1, commit_sha="sha123", issues=issues, summary_body="summary"
        )
        mock_post.assert_called_once()
        path, payload = mock_post.call_args[0]
        self.assertEqual(path, "/pulls/1/reviews")
        self.assertEqual(payload["commit_id"], "sha123")
        self.assertEqual(len(payload["comments"]), 2)

    @patch.object(GitHubClient, "post")
    def test_review_event_is_request_changes_when_critical_issues_exist(self, mock_post: MagicMock) -> None:
        issues = self._make_issues([{"severity": "critical", "line": 1}])
        self.client.post_review_with_inline_comments(1, "sha", issues, "summary")
        _, payload = mock_post.call_args[0]
        self.assertEqual(payload["event"], "REQUEST_CHANGES")

    @patch.object(GitHubClient, "post")
    def test_review_event_is_comment_when_no_critical_issues(self, mock_post: MagicMock) -> None:
        issues = self._make_issues([{"severity": "warning", "line": 3}])
        self.client.post_review_with_inline_comments(1, "sha", issues, "summary")
        _, payload = mock_post.call_args[0]
        self.assertEqual(payload["event"], "COMMENT")

    @patch.object(GitHubClient, "post")
    def test_issues_without_line_numbers_are_excluded_from_inline(self, mock_post: MagicMock) -> None:
        issues = self._make_issues([
            {"line": "", "severity": "info"},
            {"line": 0, "severity": "warning"},
            {"line": "abc", "severity": "warning"},
            {"line": 7, "severity": "critical"},
        ])
        self.client.post_review_with_inline_comments(1, "sha", issues, "summary")
        _, payload = mock_post.call_args[0]
        # Only line=7 is a valid positive integer string
        self.assertEqual(len(payload["comments"]), 1)
        self.assertEqual(payload["comments"][0]["line"], 7)

    @patch.object(GitHubClient, "post")
    def test_inline_comment_body_contains_severity_and_message(self, mock_post: MagicMock) -> None:
        issues = self._make_issues([{"line": 10, "severity": "critical", "message": "do not do this"}])
        self.client.post_review_with_inline_comments(1, "sha", issues, "summary")
        _, payload = mock_post.call_args[0]
        comment_body = payload["comments"][0]["body"]
        self.assertIn("Critical", comment_body)
        self.assertIn("do not do this", comment_body)
        self.assertIn(GitHubClient.REVIEW_MARKER, comment_body)

    @patch.object(GitHubClient, "post")
    def test_inline_comment_path_and_side_set_correctly(self, mock_post: MagicMock) -> None:
        issues = self._make_issues([{"file": "src/main.py", "line": 42, "severity": "warning"}])
        self.client.post_review_with_inline_comments(1, "sha", issues, "summary")
        _, payload = mock_post.call_args[0]
        comment = payload["comments"][0]
        self.assertEqual(comment["path"], "src/main.py")
        self.assertEqual(comment["side"], "RIGHT")

    @patch.object(GitHubClient, "post")
    def test_empty_issues_list_posts_review_with_no_inline_comments(self, mock_post: MagicMock) -> None:
        self.client.post_review_with_inline_comments(1, "sha", [], "all good")
        _, payload = mock_post.call_args[0]
        self.assertEqual(payload["comments"], [])
        self.assertEqual(payload["event"], "COMMENT")

    @patch.object(GitHubClient, "post")
    def test_summary_body_is_included_in_review_payload(self, mock_post: MagicMock) -> None:
        self.client.post_review_with_inline_comments(1, "sha", [], "my summary text")
        _, payload = mock_post.call_args[0]
        self.assertEqual(payload["body"], "my summary text")


# ===========================================================================
# Integration-style: Git + GitHubClient wired together
# ===========================================================================

class TestGitAndGitHubClientIntegration(unittest.TestCase):
    """
    Verify that the inferred repo name from Git flows correctly into
    GitHubClient requests — simulating what CodeReviewOrchestrator does.
    """

    @patch("claude_code_review.urlopen")
    @patch.object(Git, "remote_url", return_value="git@github.com:corp/service.git\n")
    def test_inferred_repo_used_in_api_url(self, _remote: MagicMock, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _make_http_response([{"number": 3}])
        git = Git(remote="origin")
        repo = git.infer_github_repo()
        self.assertEqual(repo, "corp/service")

        client = GitHubClient(token="tok", repo=repo)
        client.pr_number_from_branch("my-feat")

        req: Request = mock_urlopen.call_args[0][0]
        self.assertIn("corp/service", req.full_url)

    @patch("claude_code_review.urlopen")
    @patch.object(Git, "revision_exists", side_effect=lambda r: r == "origin/main")
    @patch.object(Git, "run", return_value="deadbeef\n")
    def test_resolve_then_commit_hash_pipeline(
        self, mock_run: MagicMock, _exists: MagicMock, _urlopen: MagicMock
    ) -> None:
        git = Git(remote="origin")
        resolved = git.resolve_revision("main")
        self.assertEqual(resolved, "origin/main")
        sha = git.commit_hash(resolved)
        self.assertEqual(sha, "deadbeef")


# ===========================================================================
# Edge cases / regression guards
# ===========================================================================

class TestGitEdgeCases(unittest.TestCase):
    def setUp(self) -> None:
        self.git = Git()

    @patch.object(Git, "remote_url", return_value="  git@github.com:acme/repo.git  ")
    def test_infer_github_repo_trims_whitespace(self, _: MagicMock) -> None:
        # Ensure leading/trailing whitespace in remote URL doesn't cause parse failure
        self.assertEqual(self.git.infer_github_repo(), "acme/repo")

    @patch.object(Git, "run", return_value="\n\n  src/a.py  \n  src/b.py\n\n")
    def test_changed_files_filters_blank_lines(self, _: MagicMock) -> None:
        files = self.git.changed_files("a", "b")
        self.assertNotIn("", files)
        self.assertEqual(len(files), 2)

    def test_resolve_revision_40_char_hash_treated_as_commit(self) -> None:
        sha = "a" * 40
        with patch.object(Git, "revision_exists", return_value=True) as mock_exists:
            result = self.git.resolve_revision(sha)
        # For a commit hash, only the hash itself should be checked (no remote/ prefix)
        mock_exists.assert_called_once_with(sha)
        self.assertEqual(result, sha)


class TestGitHubClientEdgeCases(unittest.TestCase):
    def setUp(self) -> None:
        self.client = GitHubClient(token="t", repo="o/r")

    @patch.object(GitHubClient, "get", return_value=[{"number": "7"}])
    def test_pr_number_from_branch_coerces_string_to_int(self, _: MagicMock) -> None:
        result = self.client.pr_number_from_branch("branch")
        self.assertEqual(result, 7)
        self.assertIsInstance(result, int)

    @patch.object(GitHubClient, "post")
    def test_post_review_line_zero_excluded(self, mock_post: MagicMock) -> None:
        """line=0 should NOT produce an inline comment (not a valid diff line)."""
        issues = [ReviewIssue(file="f.py", line=0, severity="warning", message="zero line")]
        self.client.post_review_with_inline_comments(1, "sha", issues, "summary")
        _, payload = mock_post.call_args[0]
        self.assertEqual(payload["comments"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
