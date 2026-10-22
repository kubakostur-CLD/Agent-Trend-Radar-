"""Orkiestracja jednego przebiegu: źródła → pipeline → raport."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .config import Config
from .http import Http
from .models import Item, SourceResult, Topic
from .pipeline.cluster import cluster
from .pipeline.dedupe import dedupe
from .pipeline.normalize import normalize
from .pipeline.report import render
from .pipeline.score import rank
from .sources import REGISTRY

log = logging.getLogger(__name__)


@dataclass
class RunOutput:
    items: list[Item]
    topics: list[Topic]
    results: list[SourceResult]
    markdown: str
    report_date: date


def collect(cfg: Config, http: Http, run_date: date, only: set[str] | None = None) -> tuple[list[Item], list[SourceResult]]:
    jobs = []
    for name, scfg in cfg.sources.items():
        if only and name not in only:
            continue
        if not only and not scfg.get("enabled", False):
            continue
        if name not in REGISTRY:
            log.error("Nieznane źródło w config.yaml: %s", name)
            continue
        jobs.append(REGISTRY[name](scfg, http, run_date))

    def run_one(src) -> tuple[list[Item], SourceResult]:
        t0 = time.monotonic()
        try:
            items = src.fetch()
            partial = getattr(src, "partial_errors", [])
            res = SourceResult(src.name, True, len(items), time.monotonic() - t0, "; ".join(partial))
            log.info("✅ %s: %d elementów (%.1fs)", src.name, len(items), res.seconds)
            return items, res
        except Exception as e:  # awaria źródła nie przerywa przebiegu
            log.error("❌ %s: %s: %s", src.name, type(e).__name__, str(e).splitlines()[0] if str(e) else "")
            log.debug("Szczegóły błędu %s", src.name, exc_info=True)
            return [], SourceResult(src.name, False, 0, time.monotonic() - t0, f"{type(e).__name__}: {e}"[:200])

    items: list[Item] = []
    results: list[SourceResult] = []
    with ThreadPoolExecutor(max_workers=max(len(jobs), 1)) as pool:
        for its, res in pool.map(run_one, jobs):
            items += its
            results.append(res)
    return items, results


def run(cfg: Config, run_date: date | None = None, only: set[str] | None = None) -> RunOutput:
    tz = ZoneInfo(cfg.general.timezone)
    now = datetime.now(tz)
    run_date = run_date or now.date()
    http = Http(
        cfg.user_agent,
        timeout=cfg.general.http_timeout,
        cache_dir=cfg.path(cfg.general.cache_dir),
        cache_ttl_minutes=cfg.general.cache_ttl_minutes,
    )
    try:
        raw, results = collect(cfg, http, run_date, only)
    finally:
        http.close()

    items = dedupe(normalize(raw, cfg.filters.exclude_keywords))
    log.info("Elementy: %d surowych → %d po normalizacji i deduplikacji", len(raw), len(items))
    topics = rank(cluster(items, cfg.scoring.cluster_threshold), cfg.scoring, cfg.filters.track_keywords)
    log.info("Tematy: %d", len(topics))

    md = render(topics, results, cfg, now, run_date.isoformat(), len(items))
    return RunOutput(items, topics, results, md, run_date)


def summary(results: list[SourceResult]) -> str:
    lines = ["Podsumowanie źródeł:"]
    for r in results:
        status = "OK " if r.ok else "BŁĄD"
        lines.append(f"  {status} {r.name:<15} {r.count:>4} el. {r.seconds:5.1f}s {r.error}")
    return "\n".join(lines)
