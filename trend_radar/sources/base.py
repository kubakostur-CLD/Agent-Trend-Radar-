"""Wspólny interfejs źródeł i rejestr modułów.

Nowe źródło: utwórz plik w `sources/`, dziedzicz po `Source`, zaimplementuj `fetch()`
i oznacz klasę dekoratorem `@register("nazwa")`. Nazwa jest kluczem w `config.yaml`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from ..http import Http
from ..models import Item

REGISTRY: dict[str, type[Source]] = {}


def register(name: str):
    def deco(cls: type[Source]) -> type[Source]:
        cls.name = name
        REGISTRY[name] = cls
        return cls

    return deco


class Source(ABC):
    name: str = ""

    def __init__(self, cfg: dict, http: Http, run_date: date):
        self.cfg = cfg
        self.http = http
        self.run_date = run_date

    @abstractmethod
    def fetch(self) -> list[Item]:
        """Pobiera elementy. Wyjątek oznacza awarię tylko tego źródła."""
