#!/usr/bin/env python3
"""Create GitHub Issue on deploy failure. Called by pipeline-deploy.yml."""
import json, os, subprocess, sys
from datetime import datetime

path = os.environ.get('ARTIFACT_PATH', 'artifacts/deploy-result.json')

# Fix #10: surface read/parse errors explicitly instead of silently swallowing them.
try:
    with open(path) as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"Artifact not found at {path} — no issue created")
    sys.exit(0)
except json.JSONDecodeError as e:
    print(f"Failed to parse artifact JSON: {e}", file=sys.stderr)
    sys.exit(1)

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

# Ensure labels exist (--force is a no-op if already present).
for lbl in ('pipeline', 'deploy', 'automated'):
    subprocess.run(['gh', 'label', 'create', lbl, '--force'], capture_output=True, text=True)

# Fix #9: pass each label with its own --label flag so gh receives them correctly.
cmd = [
    'gh', 'issue', 'create',
    '--title', title,
    '--body', body,
    '--label', 'pipeline',
    '--label', 'deploy',
    '--label', 'automated',
]
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode == 0:
    print('Issue created:', result.stdout.strip())
else:
    print('Error:', result.stderr)
    sys.exit(1)
