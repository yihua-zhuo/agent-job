#!/usr/bin/env python3
"""Create GitHub Issue on code-review critical findings. Called by pipeline-code-review.yml."""
import json, os, subprocess, sys
from datetime import datetime

path = os.environ.get('ARTIFACT_PATH', 'artifacts/code-review-result.json')
if not os.path.exists(path):
    print("No code-review result")
    sys.exit(0)

with open(path) as f:
    data = json.load(f)

status = data.get('status', '')
llm_parsed = data.get('details', {}).get('llm_parsed', {})
critical = llm_parsed.get('critical', [])
warnings = llm_parsed.get('warnings', [])

if status != 'fail' or not critical:
    print("No critical issues — no issue needed")
    sys.exit(0)

run_id = os.environ.get('GITHUB_RUN_ID', 'N/A')
t = datetime.utcnow().isoformat()

issues_md = []
for i, c in enumerate(critical):
    dim = c.get('dim', '')
    line = c.get('line', '')
    msg = c.get('msg', '')
    loc = f'line {line}' if line else 'N/A'
    issues_md.append(f'{i+1}. **[{dim.upper()}]** {msg} (at {loc})')

issues_str = '\n'.join(issues_md)
warnings_str = '\n'.join(f'- {w}' for w in warnings[:5]) if warnings else 'None'

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

title = f"🔴 Code Review Critical — {datetime.utcnow().strftime('%Y-%m-%d %H:00')}"
cmd = [
    'gh', 'issue', 'create',
    '--title', title,
    '--body', body,
    '--label', 'pipeline', 'code-review', 'automated'
]
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode == 0:
    print('Issue created:', result.stdout.strip())
else:
    print('Error:', result.stderr)
    sys.exit(1)
