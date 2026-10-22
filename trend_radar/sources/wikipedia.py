"""Najczęściej oglądane artykuły Wikipedii (Wikimedia Analytics API, bez klucza)."""

from __future__ import annotations

import logging
import math
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import httpx

from ..models import Item
from .base import Source, register

log = logging.getLogger(__name__)

API = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{project}/all-access/{y}/{m:02d}/{d:02d}"


@register("wikipedia")
class WikipediaSource(Source):
    def fetch(self) -> list[Item]:
        top_n = self.cfg.get("top_n", 40)
        excludes = [re.compile(p) for p in self.cfg.get("exclude_patterns", [])]
        items: list[Item] = []
        for proj in self.cfg.get("projects", []):
            day, articles = self._latest_top(proj["project"])
            prev = dict(self._top(proj["project"], day - timedelta(days=1)) or [])
            lang_host = proj["project"].replace(".wikipedia", "")
            kept = 0
            for name, views in articles:
                if any(p.search(name) for p in excludes):
                    continue
                prev_views = prev.get(name)
                # Brak artykułu w wczorajszym top 1000 = nowe wejście, wzrost liczony od dołu listy.
                base = prev_views or (min(prev.values()) if prev else views)
                items.append(
                    Item(
                        source=self.name,
                        platform="wikipedia",
                        outlet=f"Wikipedia {lang_host.upper()}",
                        title=name.replace("_", " "),
                        url=f"https://{lang_host}.wikipedia.org/wiki/{quote(name)}",
                        region=proj.get("region", "GLOBAL"),
                        lang=proj.get("lang", lang_host),
                        engagement=float(views),
                        metric_label="wyświetleń",
                        rate=math.log2(max(views, 1) / max(base, 1)),
                        published_at=datetime(day.year, day.month, day.day, 23, 59, tzinfo=timezone.utc),
                        extra={"prev_views": prev_views, "day": day.isoformat()},
                    )
                )
                kept += 1
                if kept >= top_n:
                    break
        return items

    def _latest_top(self, project: str) -> tuple[date, list[tuple[str, int]]]:
        # Dane za wczoraj pojawiają się z kilkugodzinnym opóźnieniem, wtedy bierzemy przedwczoraj.
        for back in (1, 2, 3):
            day = self.run_date - timedelta(days=back)
            if (top := self._top(project, day)) is not None:
                return day, top
        raise RuntimeError(f"brak danych pageviews dla {project}")

    def _top(self, project: str, day: date) -> list[tuple[str, int]] | None:
        url = API.format(project=project, y=day.year, m=day.month, d=day.day)
        try:
            data = self.http.get_json(url)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        articles = data["items"][0]["articles"]
        return [(a["article"], int(a.get("views", a.get("views_ceil", 0)))) for a in articles]
