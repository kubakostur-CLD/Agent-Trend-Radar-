from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Item:
    """Pojedynczy element pobrany ze źródła, już w ujednoliconym formacie."""

    source: str            # id modułu, np. "wikipedia"
    platform: str          # grupa do liczenia platform, np. "wikipedia", "news"
    outlet: str            # nazwa wyświetlana, np. "Wikipedia PL", "Google News PL"
    title: str
    url: str
    region: str            # "PL" albo "GLOBAL"
    lang: str              # "pl", "en", ...
    engagement: float = 0.0          # surowa metryka (wyświetlenia, punkty, wyszukiwania...)
    metric_label: str = ""           # jednostka metryki do raportu
    rate: float | None = None        # tempo wzrostu wg źródła (np. pkt/h, wzrost dzień do dnia)
    published_at: datetime | None = None
    fetched_at: datetime = field(default_factory=utcnow)
    summary: str = ""
    related: list[str] = field(default_factory=list)   # powiązane tytuły (np. newsy przy trendzie)
    extra: dict = field(default_factory=dict)
    # Wypełniane w pipeline/normalize.py
    canonical_url: str = ""
    norm_engagement: float = 0.0     # percentyl w ramach (źródło, region), 0..1
    velocity: float = 0.0            # percentyl `rate` w ramach (źródło, region), 0..1


@dataclass
class Topic:
    """Grupa elementów o tym samym temacie, często z kilku platform."""

    items: list[Item]
    title: str = ""
    score: float = 0.0
    engagement: float = 0.0
    velocity: float = 0.0
    freshness: float = 0.0
    tracked: bool = False
    # Uzupełniane w etapie 4 (historia + Claude)
    status: str = ""
    days_seen: int = 0
    summary: str = ""
    why_viral: str = ""
    category: str = ""

    @property
    def platforms(self) -> set[str]:
        return {i.platform for i in self.items}

    @property
    def region(self) -> str:
        pl = sum(1 for i in self.items if i.region == "PL")
        return "PL" if pl * 2 >= len(self.items) else "GLOBAL"

    @property
    def is_mixed_region(self) -> bool:
        return len({i.region for i in self.items}) > 1


@dataclass
class SourceResult:
    name: str
    ok: bool
    count: int = 0
    seconds: float = 0.0
    error: str = ""
