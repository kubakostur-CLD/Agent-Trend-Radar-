"""Grupowanie elementów w tematy.

Etap lokalny (bez LLM): każdy element to ważony zbiór słów kluczowych (tytuł z wagą 1,
powiązane nagłówki z wagą 0,5, ważenie IDF w ramach dzisiejszego zbioru). Klastrowanie jest
zachłanne od najmocniejszych elementów. Nowy element porównujemy tylko z pierwszymi
członkami klastra, żeby uniknąć łańcuchowego zlepiania niepowiązanych tematów.
Łączenie między językami (PL↔EN) robi w etapie 4 Claude.
"""

from __future__ import annotations

import math
from collections import Counter

from ..models import Item, Topic
from .text import keywords

ANCHORS = 3          # z iloma pierwszymi członkami klastra porównujemy nowy element
RELATED_WEIGHT = 0.5
COMMON_SHARE = 0.05
COMMON_MIN_COUNT = 5
TITLE_PRIORITY = {"wikipedia": 0, "google_trends": 1}


def _vector(it: Item) -> dict[str, float]:
    vec: dict[str, float] = {}
    for rel in it.related[:5]:
        for t in keywords(rel):
            vec[t] = RELATED_WEIGHT
    for t in keywords(it.title):
        vec[t] = 1.0
    return vec


def similarity(a: dict[str, float], b: dict[str, float], idf: dict[str, float], common_idf: float = 0.0) -> float:
    shared = a.keys() & b.keys()
    if not shared:
        return 0.0
    title_a = [t for t, w in a.items() if w == 1.0]
    title_b = [t for t, w in b.items() if w == 1.0]
    if min(len(title_a), len(title_b)) >= 2 and len(shared) < 2:
        # Dla dłuższych tytułów jedno wspólne słowo to za mało (np. samo „Polska”).
        return 0.0
    if len(shared) == 1:
        # Jednowyrazowy tytuł (np. hasło z Wikipedii) łączymy tylko przez rzadkie słowo,
        # które występuje w tytule drugiego elementu, a nie tylko w powiązanych nagłówkach.
        (t,) = shared
        if idf.get(t, 0) <= common_idf or min(a[t], b[t]) < 1.0:
            return 0.0
    num = sum(idf.get(t, 1.0) * min(a[t], b[t]) for t in shared)
    wa = sum(idf.get(t, 1.0) * w for t, w in a.items())
    wb = sum(idf.get(t, 1.0) * w for t, w in b.items())
    return num / max(min(wa, wb), 1e-9)


def pick_title(items: list[Item]) -> str:
    return min(items, key=lambda i: (TITLE_PRIORITY.get(i.platform, 9), -i.norm_engagement)).title


def cluster(items: list[Item], threshold: float = 0.5) -> list[Topic]:
    vectors = [_vector(i) for i in items]
    df = Counter(t for v in vectors for t in v)
    n = max(len(items), 1)
    idf = {t: math.log(1 + n / c) for t, c in df.items()}
    # Słowo obecne w co najmniej 5 elementach i ponad 5% wszystkich jest zbyt pospolite, żeby samo łączyło tematy.
    common_idf = math.log(1 + n / max(COMMON_MIN_COUNT, COMMON_SHARE * n))

    order = sorted(range(len(items)), key=lambda k: items[k].norm_engagement, reverse=True)
    clusters: list[list[int]] = []
    for k in order:
        best, best_sim = None, 0.0
        for ci, members in enumerate(clusters):
            s = max(similarity(vectors[k], vectors[m], idf, common_idf) for m in members[:ANCHORS])
            if s > best_sim:
                best, best_sim = ci, s
        if best is not None and best_sim >= threshold:
            clusters[best].append(k)
        else:
            clusters.append([k])

    topics = []
    for members in clusters:
        its = [items[m] for m in members]
        topics.append(Topic(items=its, title=pick_title(its)))
    return topics
