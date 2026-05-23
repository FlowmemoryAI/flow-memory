"""Privacy controls for memory events."""

from __future__ import annotations

import re
from dataclasses import dataclass

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_TOKEN_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s]+")


@dataclass
class MemoryPrivacyFilter:
    redact_emails: bool = True
    redact_secrets: bool = True

    def redact(self, text: str) -> str:
        if self.redact_emails:
            text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
        if self.redact_secrets:
            text = _TOKEN_RE.sub(lambda m: f"{m.group(1)}=[REDACTED_SECRET]", text)
        return text
