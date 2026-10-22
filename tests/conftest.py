from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from trend_radar.models import Item

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def make_item(title: str, platform: str = "news", source: str | None = None, **kw) -> Item:
    defaults = dict(
        source=source or platform,
        platform=platform,
        outlet=platform,
        title=title,
        url=kw.pop("url", f"https://example.com/{abs(hash((title, platform)))}"),
        region="PL",
        lang="pl",
        published_at=NOW - timedelta(hours=2),
    )
    defaults.update(kw)
    it = Item(**defaults)
    it.canonical_url = it.url
    return it


@pytest.fixture
def item():
    return make_item
