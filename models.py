from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Resource:
    """A meeting/access/application item shown with a seminar."""

    label: str
    value: str


@dataclass
class Seminar:
    company: str = ""
    event_date: date | None = None
    start_time: str = ""
    end_time: str = ""
    location: str = ""
    meetings: list[str] = field(default_factory=list)
    applications: list[Resource] = field(default_factory=list)
    source_text: str = ""
    id: int | None = None

    @property
    def time_display(self) -> str:
        if self.start_time and self.end_time:
            return f"{self.start_time}–{self.end_time}"
        return self.start_time or "时间待补充"

