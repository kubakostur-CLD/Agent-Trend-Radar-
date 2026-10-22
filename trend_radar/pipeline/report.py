"""Budowa raportu Markdown z listy tematów."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..config import Config
from ..models import Item, SourceResult, Topic

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
PLATFORM_NAMES = {
    "wikipedia": "Wikipedia",
    "hackernews": "Hacker News",
    "google_trends": "Google Trends",
    "news": "News",
    "bluesky": "Bluesky",
    "mastodon": "Mastodon",
    "youtube": "YouTube",
    "reddit": "Reddit",
    "kym": "Know Your Meme",
}
STATUS_ICONS = {"new": "🆕", "rising": "📈", "ongoing": "♻️", "fading": "📉"}


@dataclass
class Sections:
    top: list[Topic]
    memes: list[Topic]
    poland: list[Topic]
    world: list[Topic]
    emerging: list[Topic]
    meme_section_active: bool = False
    extra: dict = field(default_factory=dict)


def build_sections(ranked: list[Topic], cfg: Config) -> Sections:
    r = cfg.report
    top = ranked[: r.top_n]
    rest = [t for t in ranked if t not in top]
    memes = [t for t in ranked if t.category == "mem"][: r.section_n]
    poland = [t for t in rest if t.region == "PL"][: r.section_n]
    world = [t for t in rest if t.region != "PL"][: r.section_n]
    shown = set(map(id, top + poland + world))
    emerging = sorted(
        (t for t in ranked if id(t) not in shown and t.velocity >= cfg.scoring.emerging_min_velocity),
        key=lambda t: (t.velocity, t.score),
        reverse=True,
    )[: r.emerging_n]
    return Sections(top, memes, poland, world, emerging, meme_section_active=any(t.category for t in ranked))


def plural(n: int, one: str, few: str, many: str) -> str:
    """Polska odmiana: 1 artykuł, 2 artykuły, 5 artykułów, 22 artykuły."""
    if n == 1:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def fmt_num(x: float) -> str:
    return f"{int(round(x)):,}".replace(",", " ")


def metric(it: Item) -> str:
    if it.platform == "news":
        cov = it.extra.get("coverage", 0)
        return f"{cov} {plural(cov, 'artykuł', 'artykuły', 'artykułów')}" if cov else f"#{it.extra.get('rank', '?')} w feedzie"
    if it.platform == "hackernews":
        return f"{it.extra.get('points', 0)} pkt, {it.extra.get('comments', 0)} kom."
    if it.platform == "wikipedia" and it.extra.get("prev_views") is None:
        return f"{fmt_num(it.engagement)} {it.metric_label}, nowość w top"
    if it.metric_label:
        plus = "+" if it.platform == "google_trends" else ""
        return f"{fmt_num(it.engagement)}{plus} {it.metric_label}"
    return ""


def signals(t: Topic) -> list[str]:
    """Najmocniejszy element z każdej platformy, w formie „Wikipedia PL: 12 345 wyświetleń”."""
    best: dict[str, Item] = {}
    for it in t.items:
        if it.platform not in best or it.norm_engagement > best[it.platform].norm_engagement:
            best[it.platform] = it
    out = []
    for it in sorted(best.values(), key=lambda i: -i.norm_engagement):
        m = metric(it)
        out.append(f"{it.outlet}: {m}" if m else it.outlet)
    return out


def links(t: Topic, limit: int) -> list[tuple[str, str]]:
    """Linki źródłowe: najpierw po jednym z każdej platformy, potem kolejne."""
    result: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    def add(label: str, url: str) -> None:
        if url and url not in seen_urls and len(result) < limit:
            seen_urls.add(url)
            result.append((label, url))

    by_platform: dict[str, list[Item]] = {}
    for it in sorted(t.items, key=lambda i: -i.norm_engagement):
        by_platform.setdefault(it.platform, []).append(it)
    for its in by_platform.values():
        it = its[0]
        add(PLATFORM_NAMES.get(it.platform, it.outlet) if it.platform != "news" else it.outlet.split(" · ")[-1], it.url)
        if it.platform == "hackernews":
            add("dyskusja HN", it.extra.get("discussion", ""))
        if it.platform == "google_trends" and it.extra.get("news"):
            n = it.extra["news"][0]
            add(n.get("source") or "news", n["url"])
    for its in by_platform.values():
        for it in its[1:]:
            add(it.outlet.split(" · ")[-1], it.url)
    return result


def topic_line_title(t: Topic) -> str:
    icons = []
    if t.status in STATUS_ICONS:
        icons.append(STATUS_ICONS[t.status] + (f" {t.days_seen} dni" if t.status == "ongoing" else ""))
    if t.tracked:
        icons.append("⭐")
    flag = "🇵🇱🌍" if t.is_mixed_region else ("🇵🇱" if t.region == "PL" else "🌍")
    return " ".join([*icons, f"**{t.title}**", flag])


def render(
    ranked: list[Topic],
    results: list[SourceResult],
    cfg: Config,
    generated_at: datetime,
    report_date: str,
    n_items: int,
) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES), trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
    env.globals.update(
        signals=signals,
        links=lambda t: links(t, cfg.report.links_per_topic),
        title=topic_line_title,
        platform_count=lambda t: len(t.platforms),
        plural=plural,
        cell=lambda text: text.splitlines()[0].replace("|", "\\|") if text else "",
    )
    return env.get_template("report.md.j2").render(
        s=build_sections(ranked, cfg),
        results=results,
        ok_count=sum(r.ok for r in results),
        report_date=report_date,
        generated_at=generated_at.strftime("%Y-%m-%d %H:%M %Z"),
        n_items=n_items,
        n_topics=len(ranked),
    )
