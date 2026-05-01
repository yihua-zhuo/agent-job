---
name: claude-code
description: "Delegate coding tasks to Claude Code CLI (Anthropic's autonomous coding agent). Use when: (1) User asks to delegate to Claude Code or codex, (2) Running Claude Code commands, (3) Autonomous coding agent tasks, (4) PR reviews, refactoring, feature development via CLI. Trigger phrases: 'run claude code', 'delegate to claude code', 'use codex', 'autonomous coding', 'claude-code print mode', 'spawn claude-code agent'."
---

# Claude Code — Delegation Skill

Use this skill when delegating coding tasks to Claude Code CLI.

## Quick Start

**Preferred — Print Mode (non-interactive, one-shot):**
```bash
claude -p "Your task description" --max-turns 10
```

**With working directory and tool restrictions:**
```bash
claude -p "Fix the auth bug in src/auth.py" --workdir /path/to/project --allowedTools "Read,Edit,Bash" --max-turns 10
```

## Two Modes

### Print Mode (`-p`) — PREFERRED for most tasks

- Non-interactive, exits when done
- No PTY needed, clean integration
- Supports `--output-format json` for structured output
- Skip all dialogs (workspace trust, permissions)

**Common use cases:**
```bash
# One-shot fix
claude -p "Add error handling to all API calls in src/" --max-turns 10

# JSON structured output
claude -p "List all functions in src/" --output-format json --json-schema '{"type":"object","properties":{"functions":{"type":"array","items":{"type":"string"}}}}' --max-turns 5

# Resume session
claude -p "Continue the refactor" --resume <session_id> --max-turns 10
```

### Interactive PTY Mode — Multi-turn sessions

Requires tmux orchestration:
```bash
# Start tmux session
tmux new-session -d -s claude-work -x 140 -y 40

# Launch Claude Code inside it
tmux send-keys -t claude-work 'cd /path/to/project && claude' Enter

# Handle trust dialog (first time only) — default "Yes" is correct
sleep 4 && tmux send-keys -t claude-work Enter

# Send task
tmux send-keys -t claude-work 'Refactor the auth module' Enter

# Monitor progress
sleep 15 && tmux capture-pane -t claude-work -p -S -50

# Exit when done
tmux send-keys -t claude-work '/exit' Enter
```

**When to use:** Multi-turn iterative work (refactor → review → fix → test cycle), human-in-the-loop decisions, exploratory sessions.

## Key Flags

| Flag | Use case |
|------|----------|
| `--max-turns N` | Prevent runaway loops (print mode only) |
| `--output-format json` | Structured output for parsing |
| `--resume <id>` | Continue a previous session |
| `--continue` | Resume most recent session in directory |
| `--dangerously-skip-permissions` | Auto-approve all tool use (CI/automation) |
| `--allowedTools "Read,Edit,Bash"` | Restrict capabilities to what task needs |
| `--model sonnet\|opus\|haiku` | Model selection |
| `--workdir /path` | Set working directory |
| `--bare` | Skip hooks/plugins/MCP discovery (fastest, needs API key) |

## Handling Permissions Dialog (Interactive Mode)

On first launch, Claude Code shows two dialogs:

**1. Workspace Trust (default "Yes" — just press Enter):**
```
❯ 1. Yes, I trust this folder
 2. No, exit
```

**2. Permissions bypass warning (default is WRONG — "No, exit"):**
```
❯ 1. No, exit ← DEFAULT IS WRONG!
 2. Yes, I accept
```
**Must navigate DOWN then Enter.**

```bash
# Robust pattern with permissions bypass
tmux send-keys -t claude-work 'claude --dangerously-skip-permissions "your task"' Enter
sleep 4 && tmux send-keys -t claude-work Enter  # trust dialog
sleep 3 && tmux send-keys -t claude-work Down && sleep 0.3 && tmux send-keys -t claude-work Enter  # permissions
```

## Print Mode Structured Output

```bash
# Analyze and get JSON result
claude -p 'Analyze auth.py for security issues' --output-format json --max-turns 5

# Parse session_id for resumption
claude -p 'Start refactoring' --output-format json --max-turns 10 > /tmp/session.json
session_id=$(python3 -c "import json; print(json.load(open('/tmp/session.json'))['session_id'])")

# Resume with session
claude -p 'Continue and add connection pooling' --resume $session_id --max-turns 5

# Piped input (analyze diff output)
git diff main...feature | claude -p 'Review this diff for bugs' --max-turns 1
```

## Environment Variables

| Variable | Effect |
|----------|--------|
| `ANTHROPIC_API_KEY` | API key (alternative to OAuth login) |
| `CLAUDE_CODE_EFFORT_LEVEL` | Default effort: low/medium/high/max/auto |
| `MAX_MCP_OUTPUT_TOKENS` | Cap MCP server output |

## PM Todo Mode

When the user says "delegate to claude code" or similar, use this skill. For simple tasks, prefer print mode with `--max-turns 10` or less. For complex multi-step tasks, use interactive tmux mode and monitor progress with `tmux capture-pane`.