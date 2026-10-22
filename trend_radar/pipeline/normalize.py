"""Ujednolicenie elementów: kanoniczny URL, filtry słów, percentyle metryk w ramach źródła."""

from __future__ import annotations

from collections import defaultdict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..models import Item
from .text import fold

TRACKING_PARAMS = {"fbclid", "gclid", "igshid", "ref", "ref_src", "mc_cid", "mc_eid", "oc", "smid", "cmpid"}


def canonical_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url
    host = parts.netloc.lower()
    for prefix in ("www.", "m.", "mobile.", "amp."):
        if host.startswith(prefix):
            host = host[len(prefix):]
    path = parts.path.rstrip("/")
    if path.endswith("/amp"):
        path = path[:-4]
    query = urlencode(
        sorted((k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS)
    )
    return urlunsplit(("https", host, path, query, ""))


def percentiles(values: list[float]) -> list[float]:
    """Percentyl rangowy 0..1 (najwyższa wartość = 1). Remisy dostają ten sam percentyl."""
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [1.0]
    order = sorted(values)
    # Liczba wartości mniejszych + połowa remisów, przeskalowana do 0..1.
    result = []
    for v in values:
        lower = sum(1 for x in order if x < v)
        equal = sum(1 for x in order if x == v)
        result.append((lower + (equal - 1) / 2) / (n - 1))
    return result


def matches_any(text: str, words: list[str]) -> bool:
    t = fold(text)
    return any(fold(w) in t for w in words if w)


def normalize(items: list[Item], exclude_keywords: list[str] | None = None) -> list[Item]:
    exclude_keywords = exclude_keywords or []
    kept = []
    for it in items:
        it.title = " ".join(it.title.split())
        if not it.title or not it.url:
            continue
        if exclude_keywords and matches_any(it.title, exclude_keywords):
            continue
        it.canonical_url = canonical_url(it.url)
        kept.append(it)

    groups: dict[tuple[str, str], list[Item]] = defaultdict(list)
    for it in kept:
        groups[(it.source, it.region)].append(it)
    for group in groups.values():
        for it, p in zip(group, percentiles([i.engagement for i in group])):
            it.norm_engagement = p
        rated = [i for i in group if i.rate is not None]
        for it, p in zip(rated, percentiles([i.rate for i in rated])):
            it.velocity = p
    return kept
