# Git Hooks Setup

This directory contains shared Git hooks for the project.

## Setup (one-time)

After cloning the repo, run:
```bash
git config core.hooksPath .githooks
```

## Available Hooks

- `pre-commit` — runs flake8 and mypy checks before commit (non-blocking)
- `pre-push` — runs flake8 and mypy before push (strict, will block on errors)

## Hooks are tracked

Hooks in this directory are committed to the repo and shared across the team.