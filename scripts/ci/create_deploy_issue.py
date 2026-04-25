#!/usr/bin/env python3
"""Create GitHub Issue on deploy failure. Called by pipeline-deploy.yml."""
import json, os, subprocess, sys
from datetime import datetime

path = os.environ.get('ARTIFACT_PATH', 'artifacts/deploy-result.json')
try:
    with open(path) as f:
        data = json.load(f)
except:
    data = {}

if data.get('status') != 'fail':
    print("Deploy did not fail — no issue needed")
    sys.exit(0)

tail = data.get('details', {}).get('tail', [])
output = '\n'.join(tail[-20:]) if tail else 'No output'
run_id = os.environ.get('GITHUB_RUN_ID', 'N/A')
t = datetime.utcnow().isoformat()

body = (
    f"**Pipeline Stage:** deploy\n"
    f"**Status:** FAIL\n"
    f"**Triggered:** {t}\n\n"
    f"Deploy script returned non-zero.\n\n"
    f"## Output\n"
    f"```\n"
    f"{output}\n"
    f"```\n\n"
    f"_See pipeline-run: {run_id}_"
)

title = f"❌ Deploy Failed — {datetime.utcnow().strftime('%Y-%m-%d')}"
cmd = [
    'gh', 'issue', 'create',
    '--title', title,
    '--body', body,
    '--label', 'pipeline', 'deploy', 'automated'
]
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode == 0:
    print('Issue created:', result.stdout.strip())
else:
    print('Error:', result.stderr)
    sys.exit(1)
