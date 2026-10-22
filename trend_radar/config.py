from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class GeneralConfig(BaseModel):
    timezone: str = "Europe/Warsaw"
    report_hour: int = 8
    user_agent: str = "TrendRadar/0.1 (contact: {contact})"
    reports_dir: str = "reports"
    db_path: str = "data/trends.sqlite"
    cache_dir: str = ".cache"
    cache_ttl_minutes: int = 30
    http_timeout: float = 20


class ReportConfig(BaseModel):
    top_n: int = 10
    section_n: int = 7
    emerging_n: int = 5
    links_per_topic: int = 4


class FiltersConfig(BaseModel):
    exclude_keywords: list[str] = Field(default_factory=list)
    track_keywords: list[str] = Field(default_factory=list)


class ScoringConfig(BaseModel):
    weights: dict[str, float] = Field(
        default_factory=lambda: {"platforms": 0.35, "engagement": 0.30, "velocity": 0.20, "freshness": 0.15}
    )
    track_bonus: float = 0.10
    cluster_threshold: float = 0.5
    emerging_min_velocity: float = 0.7


class Config(BaseModel):
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    # Konfiguracja źródeł jest dowolnym słownikiem, każdy moduł czyta swoje klucze.
    sources: dict[str, dict] = Field(default_factory=dict)
    base_dir: Path = Path(".")

    @property
    def user_agent(self) -> str:
        contact = os.getenv("TR_CONTACT") or "unknown"
        return self.general.user_agent.format(contact=contact)

    def path(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else self.base_dir / p


def load_config(path: str | Path = "config.yaml") -> Config:
    path = Path(path).resolve()
    load_dotenv(path.parent / ".env")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Config(**data, base_dir=path.parent)
