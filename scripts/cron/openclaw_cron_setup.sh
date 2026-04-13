#!/usr/bin/env bash
# Register each pipeline role as an OpenClaw cron job.
#
# OpenClaw cron fires an agent turn. The agent's prompt tells it to shell
# out to pipeline.py <step>, wait for exit, read the resulting envelope
# from shared-memory/results/<step>-result.json, and answer with a one-line
# status summary. The agent's ``exec`` tool does the actual work.
#
# Re-run is idempotent: we delete jobs by name first, then recreate them.
#
# Schedule shape ("always has new work to do"):
#   research   every 30m — generates new tasks
#   task        every 15m — consumes the oldest unclaimed task
#   manager     every 10m — heartbeat snapshot
#   test        every 15m — fast feedback
#   code-review hourly    — gated on test
#   qc          every 2h  — gated on review
#   orchestrator daily 02 — full serial run
#   deploy      daily 03  — gated on qc green today

set -euo pipefail

REPO=/home/node/.openclaw/workspace/dev-agent-system
AGENT=main
TIMEOUT=900
THINKING=low

# Prompt template — the agent runs pipeline.py for the given step and
# reports the status stored in the envelope. We pass --tools exec,read to
# make sure the agent can actually run the shell command and read the JSON.
prompt_for() {
  local step="$1"
  cat <<EOF
You are triggered by OpenClaw cron as the ${step} agent. Execute exactly one task:

1. Run this shell command (use your exec tool):
     cd ${REPO} && python3 scripts/cron/pipeline.py ${step}
2. Read the envelope file: ${REPO}/shared-memory/results/${step}-result.json
3. Reply with ONLY a JSON object: {"step": "${step}", "status": "<envelope.status>", "brief": "<one-line summary of envelope.details>"}

Do not commit, push, or modify source files. If the envelope file is missing after the run, reply with status="error".
EOF
}

# Remove any prior jobs we own (match by name prefix so we stay idempotent
# without clobbering unrelated jobs like "CRM Manager Check").
remove_existing() {
  local name="$1"
  local ids
  ids=$(openclaw cron list --json 2>/dev/null \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print('\n'.join(j['id'] for j in d.get('jobs',[]) if j.get('name')=='${name}'))")
  for id in $ids; do
    openclaw cron rm "$id" >/dev/null 2>&1 || true
    echo "  removed prior job $id ($name)"
  done
}

register() {
  local name="$1"      # pipeline-<step>
  local step="$2"      # step name fed to pipeline.py
  local schedule="$3"  # --every value OR --cron expression
  local schedule_kind="$4"  # "every" or "cron"

  remove_existing "$name"

  local schedule_flag=("--$schedule_kind" "$schedule")
  openclaw cron add \
    --name "$name" \
    "${schedule_flag[@]}" \
    --agent "$AGENT" \
    --session isolated \
    --message "$(prompt_for "$step")" \
    --timeout-seconds "$TIMEOUT" \
    --thinking "$THINKING" \
    --tools "exec,read,write" \
    --no-deliver \
    --json >/dev/null
  echo "  + registered $name ($schedule_kind=$schedule) -> pipeline.py $step"
}

echo "=== OpenClaw cron setup ==="
register "pipeline-research"     research     "30m" "every"
register "pipeline-task"         task         "15m" "every"
register "pipeline-manager"      manager      "10m" "every"
register "pipeline-test"         test         "15m" "every"
register "pipeline-code-review"  code-review  "0 * * * *"    "cron"
register "pipeline-qc"           qc           "20 */2 * * *" "cron"
register "pipeline-orchestrator" orchestrator "0 2 * * *"    "cron"
register "pipeline-deploy"       deploy       "10 3 * * 1-5" "cron"

echo
echo "Current pipeline-* jobs:"
openclaw cron list --json | python3 -c "
import json, sys
jobs = json.load(sys.stdin).get('jobs', [])
for j in jobs:
    if j['name'].startswith('pipeline-'):
        sch = j['schedule']
        s = f\"every {sch['everyMs']//60000}m\" if sch['kind']=='every' else f\"cron {sch.get('expr','?')}\"
        print(f\"  {j['name']:<28s} {s:<20s} enabled={j['enabled']}\")
"
