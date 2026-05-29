#!/usr/bin/env python3
"""Helpers for issues that implement a ``docs/dev-plan`` board.

The Super AI Chain dev-plan contract is document-first: read the global
README, read the matching template, then execute the target board document
step by step. These helpers keep that contract out of ad hoc prompt strings
and make it reusable across planning, implementation, and self-review.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SIBLING_DEV_PLAN_ROOT = Path("../super-chain-testnet/docs/dev-plan")

DEV_PLAN_REF_RE = re.compile(
    r"(?im)^\s*(?:dev[-_ ]?plan|board|plan[-_ ]?doc)\s*:\s*`?([^`\s]+docs/dev-plan/[^`\s]+\.md|docs/dev-plan/[^`\s]+\.md)`?\s*$"
)


@dataclass(frozen=True)
class DevPlanContext:
    root: Path
    readme: Path
    template: Path
    target: Path
    depth: str

    @property
    def target_display(self) -> str:
        try:
            return self.target.relative_to(Path.cwd()).as_posix()
        except ValueError:
            return self.target.as_posix()


def find_dev_plan_ref(issue: dict[str, Any]) -> str | None:
    """Return a target dev-plan markdown path from issue body/title, if present."""
    text = "\n".join(str(issue.get(k) or "") for k in ("title", "body"))
    match = DEV_PLAN_REF_RE.search(text)
    if not match:
        return None
    return match.group(1).strip()


def resolve_dev_plan_context(issue: dict[str, Any]) -> tuple[DevPlanContext | None, str]:
    """Resolve a dev-plan issue to README/template/target paths.

    Returns ``(None, "")`` when the issue is not a dev-plan issue. Returns
    ``(None, error)`` when it claims to be one but the referenced files cannot
    be resolved locally.
    """
    ref = find_dev_plan_ref(issue)
    if not ref:
        return None, ""

    root_override = os.environ.get("DEV_PLAN_ROOT")
    if root_override:
        root = Path(root_override)
        target = root / ref.split("docs/dev-plan/", 1)[-1]
    else:
        ref_path = Path(ref)
        if ref_path.is_absolute():
            target = ref_path
            marker = "docs/dev-plan"
            parts = target.as_posix().split(marker, 1)
            root = Path(parts[0]) / marker if len(parts) == 2 else target.parent
        else:
            target = Path.cwd() / ref_path
            root = Path.cwd() / "docs/dev-plan"

    if not target.exists() and not root_override and not Path(ref).is_absolute():
        sibling_root = (Path.cwd() / DEFAULT_SIBLING_DEV_PLAN_ROOT).resolve()
        sibling_target = sibling_root / ref.split("docs/dev-plan/", 1)[-1]
        if sibling_target.exists():
            root = sibling_root
            target = sibling_target

    readme = root / "README.md"
    if not target.exists():
        return None, f"dev_plan_target_missing:{target}"
    if not readme.exists():
        return None, f"dev_plan_readme_missing:{readme}"

    target_text = target.read_text(encoding="utf-8")
    depth = _detect_template_depth(target_text)
    template = root / f"_template-{depth}.md"
    if not template.exists():
        return None, f"dev_plan_template_missing:{template}"

    return DevPlanContext(root=root, readme=readme, template=template, target=target, depth=depth), ""


def _detect_template_depth(target_text: str) -> str:
    """Infer medium/deep template from the board metadata text."""
    if re.search(r"模板深度\s*\|\s*\*{0,2}深\*{0,2}", target_text):
        return "deep"
    if re.search(r"模板深度\s*\|\s*\*{0,2}中\*{0,2}", target_text):
        return "medium"
    if "## 10." in target_text or "## 9." in target_text:
        return "deep"
    return "medium"


def build_dev_plan_prompt_block(ctx: DevPlanContext) -> str:
    """Return concise prompt instructions for a resolved dev-plan board."""
    return f"""## Dev-Plan Contract
This issue implements a board from `docs/dev-plan`: `{ctx.target_display}`.

Before planning or editing code, follow this exact reading order:
1. `{ctx.readme.as_posix()}` in full.
2. `{ctx.template.as_posix()}` in full. Template depth: `{ctx.depth}`.
3. `{ctx.target.as_posix()}` in full.

Operational rules from the dev-plan:
- README §2 global constraints are mandatory.
- The target board is independently executable; do not rely on sibling board context except dependencies declared in its metadata.
- Implement the target board's §5 steps in order. After every completed Step, run the corresponding machine-checkable verification from §6 when available.
- Do not cross-board edit files unless the target board explicitly lists them. If a cross-board change looks required, stop and report the blocker instead of guessing.
- Keep acceptance criteria machine-verifiable. Prefer `verify/*.sh`, project test commands, and exact expected outputs over manual inspection.
- Completion requires code/scripts/docs from the target board, passing verification, and a completion summary suitable for the board's "完成后必做" section.
"""


def build_source_contract_text(ctx: DevPlanContext | None) -> str:
    """Return concrete text for the plan's Source Contract section."""
    if ctx is None:
        return "GitHub issue body and repository files inspected during planning."
    return (
        f"Dev-plan target: `{ctx.target.as_posix()}`\n"
        f"Template depth: `{ctx.depth}`\n"
        "Reading order followed:\n"
        f"1. `{ctx.readme.as_posix()}`\n"
        f"2. `{ctx.template.as_posix()}`\n"
        f"3. `{ctx.target.as_posix()}`"
    )
