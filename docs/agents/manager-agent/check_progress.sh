#!/bin/bash
# Manager Agent - CRM 项目进度检查脚本
# 每10分钟执行一次

LOG_FILE="/home/node/.openclaw/workspace/dev-agent-system/shared-memory/reports/manager_log.txt"
RESULTS_DIR="/home/node/.openclaw/workspace/dev-agent-system/shared-memory/results"
TASKS_DIR="/home/node/.openclaw/workspace/dev-agent-system/shared-memory/tasks"

mkdir -p "$(dirname "$LOG_FILE")"

echo "========================================" >> "$LOG_FILE"
echo "Manager Agent 检查 - $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# 检查 Phase 1 完成状态
echo "Phase 1 状态检查:" >> "$LOG_FILE"
for result in "$RESULTS_DIR"/*_result.json; do
    if [ -f "$result" ]; then
        echo "  ✅ $(basename "$result")" >> "$LOG_FILE"
    fi
done

# 检查 Phase 2 任务状态
echo "" >> "$LOG_FILE"
echo "Phase 2 任务状态:" >> "$LOG_FILE"
for task in "$TASKS_DIR"/*.json; do
    if [ -f "$task" ]; then
        echo "  📋 $(basename "$task")" >> "$LOG_FILE"
    fi
done

echo "" >> "$LOG_FILE"
echo "检查完成 - $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

exit 0
