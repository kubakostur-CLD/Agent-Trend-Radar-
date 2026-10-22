"""Agregatory newsów i dowolne feedy RSS/Atom z config.yaml."""

from __future__ import annotations

import calendar
import re
from datetime import datetime, timezone
from html import unescape

import feedparser

from ..models import Item
from .base import Source, register

LI_RE = re.compile(r"<li\b", re.I)
TAG_RE = re.compile(r"<[^>]+>")


def parse_feed(text: str, feed: dict, source: str = "rss") -> list[Item]:
    parsed = feedparser.parse(text)
    entries = parsed.entries
    google_news = feed.get("google_news", False)
    n = len(entries)
    items = []
    for rank, e in enumerate(entries):
        title = unescape(e.get("title", "")).strip()
        outlet = feed["name"]
        if google_news:
            # Tytuły Google News mają postać „Tytuł - Wydawca”.
            src = (e.get("source") or {}).get("title")
            if src and title.endswith(f" - {src}"):
                title = title[: -len(src) - 3]
                outlet = f"{feed['name']} · {src}"
        if not title:
            continue
        published = None
        if e.get("published_parsed"):
            published = datetime.fromtimestamp(calendar.timegm(e.published_parsed), tz=timezone.utc)
        description = e.get("summary", "")
        # W Google News opis to lista artykułów o tej samej historii: ich liczba mierzy zasięg.
        coverage = len(LI_RE.findall(description)) if google_news else 0
        engagement = coverage if coverage else 1.0
        summary = "" if google_news else TAG_RE.sub("", unescape(description)).strip()[:280]
        items.append(
            Item(
                source=source,
                platform="news",
                outlet=outlet,
                title=title,
                url=e.get("link", ""),
                region=feed.get("region", "GLOBAL"),
                lang=feed.get("lang", "en"),
                # Pozycja w feedzie też jest sygnałem: wyżej = ważniejsze.
                engagement=float(engagement) + (n - rank) / max(n, 1),
                metric_label="artykułów" if google_news else "",
                published_at=published,
                summary=summary,
                extra={"coverage": coverage, "rank": rank + 1},
            )
        )
    return items


@register("rss")
class RssSource(Source):
    def fetch(self) -> list[Item]:
        items: list[Item] = []
        errors = []
        for feed in self.cfg.get("feeds", []):
            try:
                items += parse_feed(self.http.get_text(feed["url"]), feed, self.name)
            except Exception as e:  # pojedynczy feed nie zatrzymuje pozostałych
                errors.append(f"{feed['name']}: {e}")
        if errors and not items:
            raise RuntimeError("; ".join(errors))
        self.partial_errors = errors
        return items
