"""Usuwanie duplikatów.

Duplikat to ten sam materiał zgłoszony dwa razy przez to samo źródło, np. ten sam link
w Google News PL z dwóch wydawców albo prawie identyczny tytuł. Ten sam temat na różnych
platformach NIE jest duplikatem, bo to sygnał wieloplatformowości, który łączy cluster.py.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from ..models import Item
from .text import fold

TITLE_SIMILARITY = 92


def dedupe(items: list[Item]) -> list[Item]:
    kept: list[Item] = []
    seen_urls: dict[tuple[str, str], Item] = {}
    for it in sorted(items, key=lambda i: i.engagement, reverse=True):
        key = (it.source, it.canonical_url or it.url)
        if key in seen_urls:
            continue
        folded = fold(it.title)
        if any(
            k.source == it.source and k.region == it.region and fuzz.ratio(folded, fold(k.title)) >= TITLE_SIMILARITY
            for k in kept
        ):
            continue
        seen_urls[key] = it
        kept.append(it)
    return kept
