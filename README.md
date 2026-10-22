# 📡 Trend Radar

Agent, który raz dziennie zbiera trendy, memy i tematy na czasie (Polska i świat), grupuje je w tematy,
ocenia i wysyła zwięzły raport.

> Status: etap 2 z 5. Działają źródła Wikipedia, Hacker News, Google Trends (RSS) i Google News (RSS)
> oraz raport Markdown. Pełna dokumentacja po polsku powstanie w etapie 5.

## Szybki start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # uzupełnij TR_CONTACT
python -m trend_radar run --dry-run
pytest
```

Raport trafia do `reports/YYYY-MM-DD.md`. Źródła włączasz i wyłączasz w `config.yaml`.
