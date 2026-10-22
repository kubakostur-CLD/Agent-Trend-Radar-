"""Pełny przebieg na zamockowanych źródłach: raport powstaje, awaria źródła jest izolowana."""

from datetime import date

import httpx
import respx

from trend_radar.config import Config
from trend_radar.runner import run

from .conftest import fixture

WIKI = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/pl.wikipedia/all-access"


def make_cfg(tmp_path) -> Config:
    return Config(
        general={"cache_dir": str(tmp_path / "cache"), "reports_dir": str(tmp_path / "reports")},
        sources={
            "wikipedia": {"enabled": True, "projects": [{"project": "pl.wikipedia", "region": "PL", "lang": "pl"}],
                          "exclude_patterns": ["^(Specjalna)(:|_)", "^(Strona_główna)$", "^Zmarli_w_"]},
            "hackernews": {"enabled": True, "top_n": 5},
            "google_trends": {"enabled": True, "geos": [{"geo": "PL", "region": "PL", "lang": "pl"}]},
            "rss": {"enabled": True, "feeds": [
                {"name": "Google News PL", "url": "https://news.google.com/rss?hl=pl", "region": "PL", "lang": "pl", "google_news": True}
            ]},
            "reddit": {"enabled": False},
        },
    )


@respx.mock
def test_full_run_with_failing_source(tmp_path):
    respx.get(f"{WIKI}/2026/10/21").mock(return_value=httpx.Response(200, text=fixture("wiki_pl_day.json")))
    respx.get(f"{WIKI}/2026/10/20").mock(return_value=httpx.Response(200, text=fixture("wiki_pl_prev.json")))
    respx.get("https://hacker-news.firebaseio.com/v0/topstories.json").mock(return_value=httpx.Response(404))
    respx.get("https://trends.google.com/trending/rss?geo=PL").mock(return_value=httpx.Response(200, text=fixture("google_trends_pl.xml")))
    respx.get("https://news.google.com/rss?hl=pl").mock(return_value=httpx.Response(200, text=fixture("google_news_pl.xml")))

    out = run(make_cfg(tmp_path), run_date=date(2026, 10, 22))

    status = {r.name: r.ok for r in out.results}
    assert status == {"wikipedia": True, "hackernews": False, "google_trends": True, "rss": True}
    top = out.topics[0]
    assert top.title == "Orlen"
    assert top.platforms == {"wikipedia", "google_trends", "news"}
    md = out.markdown
    assert "## 🔥 TOP" in md and "**Orlen** 🇵🇱" in md
    assert "| hackernews | ❌" in md
    assert "[Wikipedia](https://pl.wikipedia.org/wiki/Orlen)" in md
