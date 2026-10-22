"""Google Trends „Trending now” przez publiczny RSS.

Oficjalne API Google Trends jest zamkniętą alfą, więc używamy kanału RSS
`trends.google.com/trending/rss?geo=XX`. Nie jest to udokumentowane API, dlatego parser
szuka elementów po nazwie lokalnej (bez przywiązania do przestrzeni nazw) i pomija
pola, których brakuje.
"""

from __future__ import annotations

import re
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

from defusedxml import ElementTree as ET

from ..models import Item, utcnow
from .base import Source, register

FEED = "https://trends.google.com/trending/rss?geo={geo}"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(el, name: str):
    return next((c for c in el if _local(c.tag) == name), None)


def _text(el, name: str) -> str:
    c = _child(el, name)
    return (c.text or "").strip() if c is not None else ""


def parse_traffic(raw: str) -> float:
    """'2000+' -> 2000, '200K+' -> 200000, '1 000+' -> 1000, '2M+' -> 2e6."""
    s = raw.replace("\xa0", "").replace(" ", "").replace(",", "").replace("+", "").upper()
    m = re.match(r"([\d.]+)([KM]?)", s)
    if not m:
        return 0.0
    return float(m.group(1)) * {"": 1, "K": 1e3, "M": 1e6}[m.group(2)]


def parse_feed(xml: str, geo: str, region: str, lang: str, source: str = "google_trends") -> list[Item]:
    root = ET.fromstring(xml)
    now = utcnow()
    items = []
    for it in root.iter():
        if _local(it.tag) != "item":
            continue
        title = _text(it, "title")
        if not title:
            continue
        traffic = parse_traffic(_text(it, "approx_traffic"))
        published = None
        if pub := _text(it, "pubDate"):
            try:
                published = parsedate_to_datetime(pub)
            except (TypeError, ValueError):
                pass
        news = [c for c in it if _local(c.tag) == "news_item"]
        related = [_text(n, "news_item_title") for n in news if _text(n, "news_item_title")]
        news_links = [
            {"title": _text(n, "news_item_title"), "url": _text(n, "news_item_url"), "source": _text(n, "news_item_source")}
            for n in news
            if _text(n, "news_item_url")
        ]
        age_h = max((now - published).total_seconds() / 3600, 1.0) if published else 12.0
        items.append(
            Item(
                source=source,
                platform="google_trends",
                outlet=f"Google Trends {geo}",
                title=title,
                url=f"https://trends.google.com/trends/explore?q={quote_plus(title)}&geo={geo}&date=now%201-d",
                region=region,
                lang=lang,
                engagement=traffic,
                metric_label="wyszukiwań",
                rate=traffic / age_h,
                published_at=published,
                related=related,
                extra={"news": news_links},
            )
        )
    return items


@register("google_trends")
class GoogleTrendsSource(Source):
    def fetch(self) -> list[Item]:
        items: list[Item] = []
        for g in self.cfg.get("geos", []):
            xml = self.http.get_text(FEED.format(geo=g["geo"]))
            items += parse_feed(xml, g["geo"], g.get("region", "GLOBAL"), g.get("lang", "en"), self.name)
        return items
