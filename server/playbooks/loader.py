"""Playbook loader and matcher.

Playbooks are YAML files describing resolution intent + tool whitelists per
escalation level. The brain matches an incoming parsed issue to a playbook
and uses the playbook's intent + tool list to constrain the ReAct loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class EscalationLevel:
    intent: str
    tools: List[str]
    requires_human_approval: bool = False


@dataclass
class Playbook:
    id: str
    match_keywords: List[str]
    match_os: Optional[str]
    levels: Dict[str, EscalationLevel]


def load_playbook(path: Path) -> Playbook:
    raw = yaml.safe_load(path.read_text())
    levels: Dict[str, EscalationLevel] = {}
    for level_name, body in (raw.get("escalation") or {}).items():
        levels[level_name] = EscalationLevel(
            intent=body.get("intent", ""),
            tools=list(body.get("tools") or []),
            requires_human_approval=bool(body.get("requires_human_approval")),
        )
    return Playbook(
        id=raw["id"],
        match_keywords=list((raw.get("match") or {}).get("keywords") or []),
        match_os=(raw.get("match") or {}).get("os"),
        levels=levels,
    )


def load_all(playbook_dir: Path) -> List[Playbook]:
    return [load_playbook(p) for p in sorted(playbook_dir.rglob("*.yaml"))]


def match(playbooks: List[Playbook], issue_text: str, os_name: str) -> Optional[Playbook]:
    """Naive keyword + OS match. Replace with embeddings for v2."""
    text = issue_text.lower()
    best: Optional[Playbook] = None
    best_score = 0
    for pb in playbooks:
        if pb.match_os and pb.match_os.lower() != os_name.lower():
            continue
        score = sum(1 for kw in pb.match_keywords if kw.lower() in text)
        if score > best_score:
            best, best_score = pb, score
    return best
