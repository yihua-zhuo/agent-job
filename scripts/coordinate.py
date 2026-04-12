#!/usr/bin/env python3
"""
Multi-Agent Coordination Script
Orchestrates communication between coordinator, code_review, test, and QC agents
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

AGENTS = {
    "coordinator": "docs/agents/coordinator/coordinator_agent.py",
    "code_review": "docs/agents/code_review/review_agent.py",
    "test": "docs/agents/test/test_agent.py",
    "qc": "docs/agents/qc/qc_agent.py"
}

class AgentCoordinator:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.workflow_state: Dict = {}

    def send_task(self, agent: str, task: Dict) -> Dict:
        """Send task to specific agent"""
        script_path = self.workspace / AGENTS.get(agent, "")
        
        if not script_path.exists():
            return {"error": f"Agent {agent} not found"}
        
        try:
            result = subprocess.run(
                ["python3", str(script_path)],
                input=json.dumps(task),
                capture_output=True,
                text=True,
                timeout=300,
                cwd=self.workspace
            )
            
            return {
                "agent": agent,
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None
            }
        except subprocess.TimeoutExpired:
            return {"agent": agent, "error": "timeout", "success": False}

    def parallel_execute(self, tasks: List[Dict], agents: List[str]) -> List[Dict]:
        """Execute tasks in parallel across specified agents"""
        results = []
        
        for i, (task, agent) in enumerate(zip(tasks, agents)):
            task["task_id"] = f"task_{i:03d}"
            result = self.send_task(agent, task)
            results.append(result)
            self.workflow_state[task["task_id"]] = result
        
        return results

    def run_workflow(self, workflow: List[Dict]) -> Dict:
        """Run full development workflow"""
        stages = {
            "parsing": [],
            "testing": [],
            "reviewing": [],
            "qc": []
        }
        
        for step in workflow:
            stage = step.get("stage", "parsing")
            agent = step.get("agent", "coordinator")
            tasks = step.get("tasks", [])
            
            if stage == "parsing":
                results = self.parallel_execute(tasks, [agent])
                stages["parsing"].extend(results)
            elif stage == "testing":
                results = self.parallel_execute(tasks, [agent])
                stages["testing"].extend(results)
            elif stage == "reviewing":
                results = self.parallel_execute(tasks, [agent])
                stages["reviewing"].extend(results)
            elif stage == "qc":
                results = self.parallel_execute(tasks, [agent])
                stages["qc"].extend(results)
        
        return stages

    def generate_workflow_report(self, stages: Dict) -> str:
        """Generate human-readable workflow report"""
        report = ["## Multi-Agent Workflow Report\n"]
        
        for stage, results in stages.items():
            passed = sum(1 for r in results if r.get("success", False))
            total = len(results)
            status = "✓" if passed == total else "✗"
            report.append(f"- {status} {stage}: {passed}/{total} tasks succeeded")
        
        return "\n".join(report)

def main():
    coordinator = AgentCoordinator(Path("/home/node/.openclaw/workspace/dev-agent-system"))
    
    if len(sys.argv) > 1 and sys.argv[1] == "--workflow":
        workflow = [
            {"stage": "parsing", "agent": "coordinator", "tasks": [{"action": "parse", "description": "Build auth module"}]},
            {"stage": "testing", "agent": "test", "tasks": [{"action": "run_unit"}]},
            {"stage": "reviewing", "agent": "code_review", "tasks": [{"action": "review"}]},
            {"stage": "qc", "agent": "qc", "tasks": [{"action": "verify"}]}
        ]
        
        results = coordinator.run_workflow(workflow)
        print(coordinator.generate_workflow_report(results))
    elif len(sys.argv) > 2 and sys.argv[1] == "--send":
        agent_name = sys.argv[2]
        task_data = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
        result = coordinator.send_task(agent_name, task_data)
        print(json.dumps(result, indent=2))
    else:
        print("Usage:")
        print("  coordinate.py --workflow")
        print("  coordinate.py --send <agent> <task_json>")

if __name__ == "__main__":
    main()