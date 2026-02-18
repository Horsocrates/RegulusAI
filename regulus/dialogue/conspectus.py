"""
Regulus AI - Conspectus
========================

Team Lead's running record — structured notes that accumulate through
the dialogue. The conspectus is the persistent memory layer: small,
structured, always current.

The full detail lives in the dialogue history; the conspectus holds
only what's needed for decisions and Worker handoff.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DomainSummary:
    """Compressed summary of a single domain's output."""
    domain: str = ""
    summary: str = ""
    confidence: Optional[int] = None
    flags: list[str] = field(default_factory=list)
    iterations: int = 0


@dataclass
class Conspectus:
    """Team Lead's running notes — the persistent memory of the dialogue."""

    original_question: str = ""
    erfragte: str = ""              # what form the answer must take
    root_question: str = ""         # the ONE question to answer
    question_set: list[dict] = field(default_factory=list)
    domain_summaries: dict[str, DomainSummary] = field(default_factory=dict)
    convergence_state: dict = field(default_factory=dict)
    attention_log: list[str] = field(default_factory=list)
    open_issues: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Render the conspectus as markdown for prompt injection."""
        parts = [f"# CONSPECTUS\n"]

        parts.append(f"## Original question\n{self.original_question}\n")

        if self.erfragte:
            parts.append(f"## Erfragte\n{self.erfragte}\n")

        if self.root_question:
            parts.append(f"## Root question\n{self.root_question}\n")

        if self.question_set:
            parts.append("## Active question set")
            for q in self.question_set:
                status = q.get("status", "pending")
                text = q.get("q", q.get("question", ""))
                parts.append(f"- {text} — status: {status}")
            parts.append("")

        if self.domain_summaries:
            parts.append("## Domain outputs (compressed)\n")
            for domain in sorted(self.domain_summaries.keys()):
                ds = self.domain_summaries[domain]
                parts.append(f"### {domain} summary")
                parts.append(ds.summary)
                if ds.confidence is not None:
                    parts.append(f"- Confidence: {domain}={ds.confidence}%")
                if ds.flags:
                    parts.append(f"- Flags: {', '.join(ds.flags)}")
                parts.append("")

        if self.convergence_state:
            parts.append("## Convergence state")
            for k, v in self.convergence_state.items():
                parts.append(f"- {k}: {v}")
            parts.append("")

        if self.attention_log:
            parts.append("## Attention log")
            for entry in self.attention_log:
                parts.append(f"- {entry}")
            parts.append("")

        if self.open_issues:
            parts.append("## Open issues")
            for issue in self.open_issues:
                parts.append(f"- {issue}")
            parts.append("")

        return "\n".join(parts)

    def update_from_tl_response(self, tl_text: str) -> None:
        """Parse <conspectus>...</conspectus> from TL output and update fields.

        The TL is expected to include a <conspectus> block in every response.
        This method extracts the block and parses its markdown sections to
        update the conspectus fields. If no block is found, the conspectus
        is left unchanged.
        """
        block = _extract_xml(tl_text, "conspectus")
        if not block:
            return

        # Parse markdown sections from the conspectus block
        sections = _parse_markdown_sections(block)

        if "original question" in sections:
            self.original_question = sections["original question"].strip()

        if "erfragte" in sections:
            self.erfragte = sections["erfragte"].strip()

        if "root question" in sections:
            self.root_question = sections["root question"].strip()

        if "active question set" in sections:
            self.question_set = _parse_question_set(
                sections["active question set"]
            )

        # Domain summaries: look for "D1 summary", "D2 summary", etc.
        for key, content in sections.items():
            m = re.match(r"(D\d)\s*summary", key, re.IGNORECASE)
            if m:
                domain = m.group(1).upper()
                confidence = _extract_confidence_from_text(content)
                self.domain_summaries[domain] = DomainSummary(
                    domain=domain,
                    summary=content.strip(),
                    confidence=confidence,
                )

        if "convergence state" in sections:
            self.convergence_state = _parse_key_value_lines(
                sections["convergence state"]
            )

        if "attention log" in sections:
            self.attention_log = _parse_list_items(
                sections["attention log"]
            )

        if "open issues" in sections:
            self.open_issues = _parse_list_items(
                sections["open issues"]
            )

    def save(self, run_dir: Path) -> None:
        """Save conspectus.md to the run directory."""
        path = run_dir / "conspectus.md"
        path.write_text(self.to_markdown(), encoding="utf-8")

    @classmethod
    def load(cls, run_dir: Path) -> "Conspectus":
        """Load conspectus from run directory (re-parse from markdown)."""
        path = run_dir / "conspectus.md"
        if not path.exists():
            return cls()
        c = cls()
        c.update_from_tl_response(
            f"<conspectus>\n{path.read_text(encoding='utf-8')}\n</conspectus>"
        )
        return c


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _extract_xml(text: str, tag: str) -> str:
    """Extract content between <tag>...</tag>. Returns empty string if not found."""
    pattern = re.compile(rf"<{tag}>(.*?)</{tag}>", re.DOTALL | re.IGNORECASE)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def _parse_markdown_sections(text: str) -> dict[str, str]:
    """Parse markdown text into {section_title_lowercase: content} dict.

    Splits on ## and ### headings.
    """
    sections: dict[str, str] = {}
    current_key = ""
    current_lines: list[str] = []

    for line in text.split("\n"):
        heading_match = re.match(r"^#{2,3}\s+(.+)$", line)
        if heading_match:
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = heading_match.group(1).strip().lower()
            current_lines = []
        else:
            current_lines.append(line)

    if current_key:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def _parse_question_set(text: str) -> list[dict]:
    """Parse bullet list of questions with status annotations."""
    questions = []
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("-"):
            continue
        line = line.lstrip("- ").strip()
        # Try to split on " — status:" or " - status:"
        status_match = re.search(r"\s*[—\-]\s*status:\s*(.+)$", line)
        if status_match:
            q_text = line[:status_match.start()].strip()
            status = status_match.group(1).strip()
        else:
            q_text = line
            status = "pending"
        questions.append({"q": q_text, "status": status})
    return questions


def _parse_list_items(text: str) -> list[str]:
    """Parse bullet list items into a list of strings."""
    items = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("-"):
            items.append(line.lstrip("- ").strip())
    return items


def _parse_key_value_lines(text: str) -> dict:
    """Parse '- key: value' lines into a dict."""
    result = {}
    for line in text.split("\n"):
        line = line.strip().lstrip("- ").strip()
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip()
            # Try to parse as int/float/list
            try:
                val = int(val)
            except (ValueError, TypeError):
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    pass
            result[key.strip()] = val
    return result


def _extract_confidence_from_text(text: str) -> Optional[int]:
    """Extract a confidence percentage from text like 'Confidence: D1=87%'."""
    match = re.search(r"[Cc]onfidence[:\s]*(?:D\d\s*=\s*)?(\d+)%?", text)
    if match:
        return int(match.group(1))
    return None
