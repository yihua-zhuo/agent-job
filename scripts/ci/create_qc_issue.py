#!/usr/bin/env python3
"""Create GitHub Issue on QC failure. Called by pipeline-qc.yml."""
import json, os, subprocess, sys
from datetime import datetime

path = os.environ.get('ARTIFACT_PATH', 'artifacts/qc-result.json')
if not os.path.exists(path):
    print("No QC result")
    sys.exit(0)

with open(path) as f:
    data = json.load(f)

if data.get('status') != 'fail':
    print(f"QC status={data.get('status')} — no issue needed")
    sys.exit(0)

blocking = data.get('details', {}).get('llm_parsed', {}).get('blocking', [])
run_id = os.environ.get('GITHUB_RUN_ID', 'N/A')

t = datetime.utcnow().isoformat()
blocks_str = '\n'.join(f'- {b}' for b in blocking) if blocking else '- (none)'

body = (
    f"**Pipeline Stage:** qc\n"
    f"**Status:** FAIL — quality gate rejected\n"
    f"**Triggered:** {t}\n\n"
    f"## Blocking Issues\n"
    f"{blocks_str}\n\n"
    f"_See pipeline-run: {run_id}_"
)

title = f"❌ QC Gate Failed — {datetime.utcnow().strftime('%Y-%m-%d %H:00')}"

# Ensure labels exist (--force is a no-op if already present).
for lbl in ('pipeline', 'qc', 'automated'):
    subprocess.run(['gh', 'label', 'create', lbl, '--force'], capture_output=True, text=True)

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
if result.returncode == 0:
    print('Issue created:', result.stdout.strip())
else:
    print('Error:', result.stderr)
    sys.exit(1)
