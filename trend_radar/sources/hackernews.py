"""Hacker News: strona główna (oficjalne API Firebase, bez klucza)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from ..models import Item, utcnow
from .base import Source, register

API = "https://hacker-news.firebaseio.com/v0"


@register("hackernews")
class HackerNewsSource(Source):
    def fetch(self) -> list[Item]:
        ids = self.http.get_json(f"{API}/topstories.json")[: self.cfg.get("top_n", 30)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            stories = list(pool.map(lambda i: self.http.get_json(f"{API}/item/{i}.json"), ids))
        now = utcnow()
        items = []
        for s in stories:
            if not s or s.get("type") != "story" or s.get("dead") or s.get("deleted"):
                continue
            created = datetime.fromtimestamp(s["time"], tz=timezone.utc)
            age_h = max((now - created).total_seconds() / 3600, 0.5)
            points = s.get("score", 0)
            discussion = f"https://news.ycombinator.com/item?id={s['id']}"
            items.append(
                Item(
                    source=self.name,
                    platform="hackernews",
                    outlet="Hacker News",
                    title=s.get("title", ""),
                    url=s.get("url") or discussion,
                    region="GLOBAL",
                    lang="en",
                    engagement=float(points + s.get("descendants", 0)),
                    metric_label="pkt+komentarzy",
                    rate=points / age_h,
                    published_at=created,
                    extra={"discussion": discussion, "points": points, "comments": s.get("descendants", 0)},
                )
            )
        return items
