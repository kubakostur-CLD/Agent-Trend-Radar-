from . import google_trends, hackernews, rss, wikipedia  # noqa: F401  (rejestracja modułów)
from .base import REGISTRY, Source, register

__all__ = ["REGISTRY", "Source", "register"]
