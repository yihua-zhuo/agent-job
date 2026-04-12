#!/usr/bin/env python3
"""Coordinator script - parses tasks and dispatches to appropriate agents"""

import json
import sys
from pathlib import Path

def parse_task_description(description: str) -> dict:
    """Parse natural language task into structured format using M2.7 model"""
    
    prompt = f"""Parse this development task into structured format:
Task: {description}

Output JSON with:
- task_id: unique identifier
- type: feature|bugfix|refactor|docs
- priority: high|medium|low  
- components: list of code components needed
- tests_needed: list of test types required
- review_scope: areas requiring review
- estimated_steps: number of steps to complete"""

    # In production, this would call MiniMax-M2.7 API
    # For now, return structured template
    return {
        "task_id": "task_001",
        "type": "feature",
        "priority": "medium",
        "components": ["src/module.py"],
        "tests_needed": ["unit", "integration"],
        "review_scope": ["code_quality", "security"],
        "estimated_steps": 5
    }

def main():
    if len(sys.argv) > 1:
        description = " ".join(sys.argv[1:])
        result = parse_task_description(description)
        print(json.dumps(result, indent=2))
    else:
        print("Usage: python3 scripts/coordinator.py parse <task description>")

if __name__ == "__main__":
    main()