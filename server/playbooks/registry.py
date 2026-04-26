"""In-memory playbook registry with naive keyword/OS matching."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from server.playbooks.loader import Playbook, load_all


class PlaybookRegistry:
    def __init__(self, playbooks: List[Playbook]) -> None:
        self._playbooks = playbooks

    @classmethod
    def load(cls, root: Path) -> "PlaybookRegistry":
        return cls(load_all(root))

    def match(self, issue_text: str, *, os_name: str) -> Optional[Playbook]:
        text = issue_text.lower()
        best: Optional[Playbook] = None
        best_score = 0
        for pb in self._playbooks:
            if pb.match_os and pb.match_os.lower() != os_name.lower():
                continue
            score = sum(1 for kw in pb.match_keywords if kw.lower() in text)
            if score > best_score:
                best, best_score = pb, score
        return best
