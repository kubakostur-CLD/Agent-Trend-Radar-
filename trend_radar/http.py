"""Wspólny klient HTTP: User-Agent, retry z backoffem, cache na dysku, robots.txt."""

from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}


class Http:
    def __init__(
        self,
        user_agent: str,
        timeout: float = 20,
        cache_dir: Path | None = None,
        cache_ttl_minutes: int = 30,
        max_attempts: int = 4,
    ):
        self.user_agent = user_agent
        self.client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            follow_redirects=True,
        )
        self.cache_dir = cache_dir
        self.cache_ttl = cache_ttl_minutes * 60
        self.max_attempts = max_attempts
        self._robots: dict[str, RobotFileParser] = {}
        self._robots_lock = threading.Lock()

    def close(self) -> None:
        self.client.close()

    # --- cache -------------------------------------------------------------

    def _cache_path(self, url: str) -> Path | None:
        if not self.cache_dir or self.cache_ttl <= 0:
            return None
        return self.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + ".body")

    def _cache_get(self, url: str) -> str | None:
        p = self._cache_path(url)
        if p and p.exists() and time.time() - p.stat().st_mtime < self.cache_ttl:
            return p.read_text(encoding="utf-8")
        return None

    def _cache_put(self, url: str, body: str) -> None:
        p = self._cache_path(url)
        if p:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")

    # --- requests ----------------------------------------------------------

    def get_text(self, url: str, params: dict | None = None, use_cache: bool = True) -> str:
        full_url = f"{url}?{urlencode(params)}" if params else url
        if use_cache and (cached := self._cache_get(full_url)) is not None:
            return cached
        for attempt in range(1, self.max_attempts + 1):
            try:
                resp = self.client.get(full_url)
            except httpx.TransportError as e:
                if attempt == self.max_attempts:
                    raise
                self._sleep(attempt, None, f"{type(e).__name__} dla {full_url}")
                continue
            if resp.status_code in RETRY_STATUSES and attempt < self.max_attempts:
                self._sleep(attempt, resp.headers.get("Retry-After"), f"HTTP {resp.status_code} dla {full_url}")
                continue
            resp.raise_for_status()
            if use_cache:
                self._cache_put(full_url, resp.text)
            return resp.text
        raise RuntimeError("unreachable")

    def get_json(self, url: str, params: dict | None = None, use_cache: bool = True):
        return json.loads(self.get_text(url, params, use_cache))

    def _sleep(self, attempt: int, retry_after: str | None, reason: str) -> None:
        delay = min(30.0, 2 ** attempt + random.random())
        if retry_after and retry_after.isdigit():
            delay = min(120.0, float(retry_after))
        log.warning("%s, ponawiam za %.1fs (próba %d/%d)", reason, delay, attempt, self.max_attempts)
        time.sleep(delay)

    # --- robots.txt --------------------------------------------------------

    def allowed_by_robots(self, url: str) -> bool:
        """Sprawdza robots.txt dla stron pobieranych spoza oficjalnych API."""
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        with self._robots_lock:
            rp = self._robots.get(origin)
            if rp is None:
                rp = RobotFileParser()
                try:
                    resp = self.client.get(origin + "/robots.txt")
                    if resp.status_code >= 400:
                        # Brak robots.txt (4xx) oznacza brak ograniczeń, ale 5xx traktujemy ostrożnie.
                        rp.parse([] if resp.status_code < 500 else ["User-agent: *", "Disallow: /"])
                    else:
                        rp.parse(resp.text.splitlines())
                except httpx.HTTPError:
                    rp.parse(["User-agent: *", "Disallow: /"])
                self._robots[origin] = rp
        return rp.can_fetch(self.user_agent, url)
