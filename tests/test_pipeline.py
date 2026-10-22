from trend_radar.config import ScoringConfig
from trend_radar.models import Topic
from trend_radar.pipeline.cluster import cluster
from trend_radar.pipeline.dedupe import dedupe
from trend_radar.pipeline.normalize import canonical_url, normalize, percentiles
from trend_radar.pipeline.score import rank

from .conftest import NOW, make_item


# --- normalizacja -----------------------------------------------------------

def test_canonical_url_strips_tracking_and_mobile():
    assert canonical_url("http://m.Example.com/a/b/?utm_source=x&id=7&fbclid=1#top") == "https://example.com/a/b?id=7"
    assert canonical_url("https://www.example.com/story/amp") == "https://example.com/story"


def test_percentiles_rank_and_ties():
    assert percentiles([10, 20, 30]) == [0.0, 0.5, 1.0]
    assert percentiles([5, 5]) == [0.5, 0.5]
    assert percentiles([7]) == [1.0]


def test_normalize_excludes_keywords_case_and_diacritics_insensitive(item):
    items = [item("Mecz Legii z Lechem"), item("Ceny paliw rosną")]
    kept = normalize(items, exclude_keywords=["LEGIA", "legii"])
    assert [i.title for i in kept] == ["Ceny paliw rosną"]


# --- deduplikacja -----------------------------------------------------------

def test_dedupe_same_url_within_source(item):
    a = item("Tytuł A", url="https://ex.com/1?utm_source=a", engagement=5)
    b = item("Zupełnie inny tytuł", url="https://www.ex.com/1", engagement=3)
    out = dedupe(normalize([a, b]))
    assert len(out) == 1 and out[0].title == "Tytuł A"


def test_dedupe_near_identical_titles_within_source_keeps_stronger(item):
    a = item("Orlen obniża ceny paliw na stacjach", engagement=1)
    b = item("Orlen obniża ceny paliw na stacjach!", engagement=9)
    out = dedupe(normalize([a, b]))
    assert len(out) == 1 and out[0].engagement == 9


def test_dedupe_keeps_same_story_on_different_platforms(item):
    a = item("Orlen obniża ceny paliw", platform="news", url="https://ex.com/1")
    b = item("Orlen obniża ceny paliw", platform="bluesky", url="https://ex.com/1")
    assert len(dedupe(normalize([a, b]))) == 2


# --- klastrowanie -----------------------------------------------------------

def test_cluster_joins_cross_platform_and_separates_unrelated(item):
    items = normalize([
        item("orlen", platform="google_trends", engagement=20000, related=["Orlen obniża ceny paliw na stacjach"]),
        item("Orlen", platform="wikipedia", engagement=42000),
        item("Orlen obniża ceny paliw na stacjach", platform="news", engagement=3),
        item("Sejm przyjął ustawę o szkolnictwie wyższym", platform="news", engagement=1),
        item("Burza w Krakowie zerwała dachy", platform="news", engagement=2),
    ])
    topics = cluster(items, threshold=0.5)
    by_title = {t.title: t for t in topics}
    assert by_title["Orlen"].platforms == {"google_trends", "wikipedia", "news"}
    assert len(topics) == 3


def test_cluster_requires_two_shared_words_for_longer_titles(item):
    items = normalize([
        item("Polska wygrywa z Niemcami w siatkówce", engagement=2),
        item("Polska podnosi stopy procentowe", engagement=1),
    ])
    assert len(cluster(items)) == 2


def test_cluster_matches_polish_inflection(item):
    items = normalize([
        item("Wybory prezydenckie we Francji", engagement=2),
        item("Kto wygra wyborach prezydenckich Francji?", engagement=1),
    ])
    assert len(cluster(items)) == 1


# --- scoring ----------------------------------------------------------------

def _topic(*items):
    return Topic(items=list(items), title=items[0].title)


def test_three_platforms_beat_one_with_equal_engagement(item):
    multi = _topic(*(item("Temat A", platform=p) for p in ("news", "wikipedia", "google_trends")))
    single = _topic(item("Temat B", platform="news"))
    for t in (multi, single):
        for i in t.items:
            i.norm_engagement = 0.8
    ranked = rank([single, multi], ScoringConfig(), now=NOW)
    assert ranked[0] is multi
    assert multi.score > single.score


def test_velocity_and_freshness_raise_score(item):
    from datetime import timedelta

    fast = _topic(item("Szybki", velocity=1.0))
    slow = _topic(item("Wolny", velocity=0.0, published_at=NOW - timedelta(days=3)))
    for t in (fast, slow):
        t.items[0].norm_engagement = 0.5
    rank([fast, slow], ScoringConfig(), now=NOW)
    assert fast.score > slow.score
    assert fast.freshness > slow.freshness


def test_tracked_keyword_bonus(item):
    a = _topic(item("Premiera nowego iPhone"))
    b = _topic(item("Premiera nowego Pixela"))
    for t in (a, b):
        t.items[0].norm_engagement = 0.5
    rank([a, b], ScoringConfig(), track_keywords=["iphone"], now=NOW)
    assert a.tracked and not b.tracked
    assert a.score > b.score


def test_single_word_title_does_not_absorb_common_word(item):
    # „Polska” z Wikipedii nie może wciągać każdego newsa ze słowem „Polska”.
    items = [item("Polska", platform="wikipedia", engagement=9)]
    items += [item(f"Polska {w} zmiany {i}", engagement=1) for i, w in enumerate(["podatki", "drogi", "szkoły", "sport"])]
    items += [item(f"Inny temat numer {i}", engagement=1) for i in range(20)]
    topics = cluster(normalize(items))
    polska = next(t for t in topics if t.title == "Polska")
    assert len(polska.items) == 1


def test_single_word_title_needs_match_in_title_not_related(item):
    items = normalize([
        item("komunikat", platform="google_trends", engagement=5, related=["Lalka bije rekordy w kinach"]),
        item("Lalka", platform="wikipedia", engagement=9),
    ])
    assert len(cluster(items)) == 2


def test_region_tie_is_global(item):
    t = Topic(items=[item("BioWare", platform="wikipedia", region="PL"), item("BioWare", platform="wikipedia", region="GLOBAL")])
    assert t.region == "GLOBAL"
