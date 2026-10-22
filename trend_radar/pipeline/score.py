"""Scoring tematów: liczba platform, zaangażowanie, tempo wzrostu, świeżość."""

from __future__ import annotations

import math
from datetime import datetime

from ..config import ScoringConfig
from ..models import Topic, utcnow
from .normalize import matches_any

MAX_PLATFORMS = 4        # od 4 platform w górę premia się nie zwiększa
FRESHNESS_HALF_LIFE_H = 24


def freshness(newest: datetime | None, now: datetime) -> float:
    if newest is None:
        return 0.5
    age_h = max((now - newest).total_seconds() / 3600, 0)
    return 0.5 ** (age_h / FRESHNESS_HALF_LIFE_H)


def score_topic(t: Topic, cfg: ScoringConfig, now: datetime, track_keywords: list[str] | None = None) -> float:
    w = cfg.weights
    p = min(len(t.platforms), MAX_PLATFORMS)
    platforms = (p - 1) / (MAX_PLATFORMS - 1)
    # Najsilniejszy element plus mała premia za liczbę elementów (np. wiele newsów o tym samym).
    t.engagement = min(1.0, max(i.norm_engagement for i in t.items) + 0.05 * math.log2(len(t.items)))
    t.velocity = max(i.velocity for i in t.items)
    dates = [i.published_at for i in t.items if i.published_at]
    t.freshness = freshness(max(dates) if dates else None, now)
    t.tracked = bool(track_keywords) and any(matches_any(i.title, track_keywords) for i in t.items)
    s = (
        w.get("platforms", 0) * platforms
        + w.get("engagement", 0) * t.engagement
        + w.get("velocity", 0) * t.velocity
        + w.get("freshness", 0) * t.freshness
        + (cfg.track_bonus if t.tracked else 0)
    )
    t.score = round(100 * s, 1)
    return t.score


def rank(topics: list[Topic], cfg: ScoringConfig, track_keywords: list[str] | None = None, now: datetime | None = None) -> list[Topic]:
    now = now or utcnow()
    for t in topics:
        score_topic(t, cfg, now, track_keywords)
    return sorted(topics, key=lambda t: t.score, reverse=True)
