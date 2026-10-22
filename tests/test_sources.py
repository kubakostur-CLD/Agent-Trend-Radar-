from datetime import date

import httpx
import respx

from trend_radar.http import Http
from trend_radar.sources.google_trends import parse_feed as parse_trends, parse_traffic
from trend_radar.sources.hackernews import HackerNewsSource
from trend_radar.sources.rss import parse_feed as parse_rss
from trend_radar.sources.wikipedia import WikipediaSource

from .conftest import fixture

WIKI = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/pl.wikipedia/all-access"


def http():
    return Http("TrendRadar-test/0.1", cache_dir=None, max_attempts=1)


def test_parse_traffic_formats():
    assert parse_traffic("2000+") == 2000
    assert parse_traffic("20 000+") == 20000
    assert parse_traffic("5K+") == 5000
    assert parse_traffic("1.5M+") == 1_500_000
    assert parse_traffic("") == 0


def test_google_trends_feed():
    items = parse_trends(fixture("google_trends_pl.xml"), "PL", "PL", "pl")
    assert [i.title for i in items] == ["orlen", "burza w Krakowie"]
    orlen = items[0]
    assert orlen.engagement == 20000
    assert orlen.related == ["Orlen obniża ceny paliw na stacjach"]
    assert orlen.extra["news"][0]["url"] == "https://example.pl/orlen-ceny-paliw"
    assert "geo=PL" in orlen.url
    assert items[1].extra["news"] == []


def test_google_news_feed_strips_publisher_and_counts_coverage():
    feed = {"name": "Google News PL", "region": "PL", "lang": "pl", "google_news": True}
    items = parse_rss(fixture("google_news_pl.xml"), feed)
    assert items[0].title == "Orlen obniża ceny paliw na stacjach"
    assert items[0].outlet == "Google News PL · Example PL"
    assert items[0].extra["coverage"] == 3
    # Pozycja w feedzie podnosi zaangażowanie: pierwszy element > ostatni.
    assert items[0].engagement > items[2].engagement


@respx.mock
def test_wikipedia_filters_and_detects_new_entries():
    respx.get(f"{WIKI}/2026/10/21").mock(return_value=httpx.Response(200, text=fixture("wiki_pl_day.json")))
    respx.get(f"{WIKI}/2026/10/20").mock(return_value=httpx.Response(200, text=fixture("wiki_pl_prev.json")))
    cfg = {
        "projects": [{"project": "pl.wikipedia", "region": "PL", "lang": "pl"}],
        "exclude_patterns": ["^(Specjalna)(:|_)", "^(Strona_główna)$", "^Zmarli_w_"],
    }
    items = WikipediaSource(cfg, http(), date(2026, 10, 22)).fetch()
    assert [i.title for i in items] == ["Orlen", "Kraków"]
    orlen, krakow = items
    assert orlen.extra["prev_views"] is None           # nowe wejście do top
    assert krakow.extra["prev_views"] == 14000
    assert orlen.rate > krakow.rate                     # większy wzrost dzień do dnia
    assert krakow.url == "https://pl.wikipedia.org/wiki/Krak%C3%B3w"


@respx.mock
def test_wikipedia_falls_back_when_yesterday_missing():
    respx.get(f"{WIKI}/2026/10/21").mock(return_value=httpx.Response(404))
    respx.get(f"{WIKI}/2026/10/20").mock(return_value=httpx.Response(200, text=fixture("wiki_pl_prev.json")))
    respx.get(f"{WIKI}/2026/10/19").mock(return_value=httpx.Response(404))
    cfg = {"projects": [{"project": "pl.wikipedia", "region": "PL", "lang": "pl"}]}
    items = WikipediaSource(cfg, http(), date(2026, 10, 22)).fetch()
    assert {i.title for i in items} == {"Kraków", "Polska"}
    assert items[0].extra["day"] == "2026-10-20"


@respx.mock
def test_hackernews_skips_dead_and_non_stories():
    api = "https://hacker-news.firebaseio.com/v0"
    respx.get(f"{api}/topstories.json").mock(return_value=httpx.Response(200, json=[1, 2, 3]))
    respx.get(f"{api}/item/1.json").mock(
        return_value=httpx.Response(200, json={"id": 1, "type": "story", "title": "Show HN: X", "score": 120, "descendants": 30, "time": 1792_000_000, "url": "https://x.dev"})
    )
    respx.get(f"{api}/item/2.json").mock(return_value=httpx.Response(200, json={"id": 2, "type": "job", "title": "Hiring", "time": 1792_000_000}))
    respx.get(f"{api}/item/3.json").mock(return_value=httpx.Response(200, json={"id": 3, "type": "story", "dead": True, "time": 1792_000_000}))
    items = HackerNewsSource({"top_n": 3}, http(), date(2026, 10, 22)).fetch()
    assert len(items) == 1
    assert items[0].engagement == 150
    assert items[0].extra["discussion"] == "https://news.ycombinator.com/item?id=1"
