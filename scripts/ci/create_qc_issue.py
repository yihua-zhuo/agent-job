#!/usr/bin/env python3
"""Create GitHub Issue on QC failure. Called by pipeline-qc.yml."""
import json
import os
import subprocess
import sys
from datetime import UTC, datetime


def log(message):
    print(f"[qc-issue] {message}", flush=True)


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _stringify_issue(issue):
    if isinstance(issue, dict):
        return issue.get('msg') or issue.get('message') or issue.get('issue') or issue.get('description') or str(issue)
    return str(issue)

path = os.environ.get('ARTIFACT_PATH', 'artifacts/qc-result.json')
log(f"artifact_path={path}")
if not os.path.exists(path):
    print("No QC result")
    sys.exit(0)
log(f"artifact_bytes={os.path.getsize(path)}")

with open(path) as f:
    data = json.load(f)

status = data.get('status')
if status is None and data.get('verdict') == 'fail':
    status = 'fail'

if status != 'fail':
    print(f"QC status={status} — no issue needed")
    sys.exit(0)

llm_parsed = data.get('details', {}).get('llm_parsed', {})
blocking = (
    llm_parsed.get('blocking')
    or llm_parsed.get('critical')
    or data.get('blocking')
    or data.get('critical_issues')
    or data.get('out_of_sync')
    or []
)
blocking = _as_list(blocking)
log(f"status={status}")
log(f"artifact_keys={sorted(data.keys())}")
log(f"blocking_count={len(blocking)}")
run_id = os.environ.get('GITHUB_RUN_ID', 'N/A')
now = datetime.now(UTC)
t = now.isoformat()
blocks_str = '\n'.join(f'- {_stringify_issue(b)}' for b in blocking) if blocking else '- (none)'

body = (
    f"**Pipeline Stage:** qc\n"
    f"**Status:** FAIL — quality gate rejected\n"
    f"**Triggered:** {t}\n\n"
    f"## Blocking Issues\n"
    f"{blocks_str}\n\n"
    f"_See pipeline-run: {run_id}_"
)

title = f"❌ QC Gate Failed — {now.strftime('%Y-%m-%d %H:00')}"

# Ensure labels exist (--force is a no-op if already present).
for lbl in ('pipeline', 'qc', 'automated'):
    label_result = subprocess.run(['gh', 'label', 'create', lbl, '--force'], capture_output=True, text=True)
    log(f"label={lbl} returncode={label_result.returncode}")

# Fix #11: pass each label with its own --label flag so gh receives them correctly.
cmd = [
    'gh', 'issue', 'create',
    '--title', title,
    '--body', body,
    '--label', 'pipeline',
    '--label', 'qc',
    '--label', 'automated',
]
result = subprocess.run(cmd, capture_output=True, text=True)
log(f"gh_issue_create_returncode={result.returncode}")
if result.returncode == 0:
    print('Issue created:', result.stdout.strip())
else:
    print('Error:', result.stderr)
    sys.exit(1)
