"""CLI: python -m trend_radar run [--dry-run] [--date YYYY-MM-DD] [--sources a,b] [--config PATH]"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from .config import load_config
from .runner import run, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trend_radar", description="Trend Radar: codzienny raport trendów")
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="uruchom pełny przebieg")
    p_run.add_argument("--dry-run", action="store_true", help="raport na stdout, bez wysyłki i zapisu do bazy")
    p_run.add_argument("--date", type=date.fromisoformat, help="data raportu (domyślnie dziś)")
    p_run.add_argument("--sources", help="lista źródeł oddzielona przecinkami (nadpisuje enabled)")
    p_run.add_argument("--config", default="config.yaml")
    p_run.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    cfg = load_config(args.config)
    only = {s.strip() for s in args.sources.split(",")} if args.sources else None
    out = run(cfg, args.date, only)

    reports_dir = cfg.path(cfg.general.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{out.report_date.isoformat()}.md"
    path.write_text(out.markdown, encoding="utf-8")
    if args.dry_run:
        print(out.markdown)
    logging.info("Raport zapisany: %s", path)
    print(summary(out.results), file=sys.stderr)
    return 0 if any(r.ok for r in out.results) else 1


if __name__ == "__main__":
    sys.exit(main())
