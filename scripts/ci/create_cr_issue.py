#!/usr/bin/env python3
"""Create GitHub Issue on code-review critical findings. Called by pipeline-code-review.yml."""
import json
import os
import subprocess
import sys
from datetime import UTC, datetime


def log(message):
    print(f"[code-review-issue] {message}", flush=True)


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _issue_fields(issue):
    if isinstance(issue, dict):
        msg = issue.get('msg') or issue.get('message') or issue.get('issue') or issue.get('description') or str(issue)
        return {
            'dim': issue.get('dim') or issue.get('category') or 'critical',
            'line': issue.get('line', ''),
            'msg': msg,
        }
    return {'dim': 'critical', 'line': '', 'msg': str(issue)}

path = os.environ.get('ARTIFACT_PATH', 'artifacts/code-review-result.json')
log(f"artifact_path={path}")
if not os.path.exists(path):
    print("No code-review result")
    sys.exit(0)
log(f"artifact_bytes={os.path.getsize(path)}")

with open(path) as f:
    data = json.load(f)

status = data.get('status') or ('fail' if data.get('verdict') == 'fail' else '')
llm_parsed = data.get('details', {}).get('llm_parsed', {})
critical = [_issue_fields(c) for c in _as_list(llm_parsed.get('critical') or data.get('critical_issues'))]
warnings = [_issue_fields(w) for w in _as_list(llm_parsed.get('warnings') or data.get('suggestions'))]
log(f"status={status}")
log(f"artifact_keys={sorted(data.keys())}")
log(f"critical_count={len(critical)}")
log(f"warning_count={len(warnings)}")

if status != 'fail' or not critical:
    print("No critical issues — no issue needed")
    sys.exit(0)

run_id = os.environ.get('GITHUB_RUN_ID', 'N/A')
now = datetime.now(UTC)
t = now.isoformat()

issues_md = []
for i, c in enumerate(critical):
    dim = c['dim']
    line = c['line']
    msg = c['msg']
    loc = f'line {line}' if line else 'N/A'
    issues_md.append(f'{i+1}. **[{dim.upper()}]** {msg} (at {loc})')

issues_str = '\n'.join(issues_md)

# Fix #8: surface count of omitted warnings.
MAX_WARNINGS = 5
shown_warnings = warnings[:MAX_WARNINGS]
omitted = len(warnings) - len(shown_warnings)
warnings_str = '\n'.join(f'- {w["msg"]}' for w in shown_warnings) if shown_warnings else 'None'
if omitted > 0:
    warnings_str += f'\n- _…and {omitted} more warning(s) not shown_'

body = (
    f"**Pipeline Stage:** code-review\n"
    f"**Status:** FAIL — {len(critical)} critical issue(s) found\n"
    f"**Triggered:** {t}\n\n"
    f"## Critical Issues\n"
    f"{issues_str}\n\n"
    f"## Warnings\n"
    f"{warnings_str}\n\n"
    f"_See pipeline-run: {run_id}_"
)

title = f"🔴 Code Review Critical — {now.strftime('%Y-%m-%d %H:00')}"

# Ensure labels exist (--force is a no-op if already present).
for lbl in ('pipeline', 'code-review', 'automated'):
    label_result = subprocess.run(['gh', 'label', 'create', lbl, '--force'], capture_output=True, text=True)
    log(f"label={lbl} returncode={label_result.returncode}")

# Fix #7: pass each label with its own --label flag so gh receives them correctly.
cmd = [
    'gh', 'issue', 'create',
    '--title', title,
    '--body', body,
    '--label', 'pipeline',
    '--label', 'code-review',
    '--label', 'automated',
]
result = subprocess.run(cmd, capture_output=True, text=True)
log(f"gh_issue_create_returncode={result.returncode}")
if result.returncode == 0:
    print('Issue created:', result.stdout.strip())
else:
    print('Error:', result.stderr)
    sys.exit(1)
