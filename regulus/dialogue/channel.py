"""
Regulus AI - Dialogue Channel
==============================

Append-only JSONL logger for the two-agent dialogue audit trail.
Every message between orchestrator, Team Lead, and Worker is recorded
as a single JSON line in dialogue.jsonl.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Optional


class DialogueChannel:
    """Append-only JSONL logger for dialogue messages."""

    def __init__(self, run_dir: Path):
        self.log_path = run_dir / "dialogue.jsonl"
        self._file: Optional[IO] = None

    def open(self) -> "DialogueChannel":
        self._file = open(self.log_path, "a", encoding="utf-8")
        return self

    def log(
        self,
        sender: str,
        receiver: str,
        msg_type: str,
        content: str,
        domain: Optional[str] = None,
        **meta,
    ) -> None:
        """Log a single dialogue message as a JSON line.

        Args:
            sender: "orchestrator" | "team_lead" | "worker"
            receiver: "team_lead" | "worker" | "orchestrator"
            msg_type: "init" | "instruction" | "domain_output" |
                      "reflect" | "feedback" | "final"
            content: Message text (truncated to 2000 chars in log)
            domain: Optional domain code ("D1"..."D5", "INIT", etc.)
            **meta: Extra fields (verdict, confidence, tokens, etc.)
        """
        if self._file is None:
            return

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "from": sender,
            "to": receiver,
            "type": msg_type,
            "domain": domain,
            "content": content[:2000],
            **meta,
        }
        self._file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None

    def __enter__(self) -> "DialogueChannel":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()
