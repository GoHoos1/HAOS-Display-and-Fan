from __future__ import annotations

import logging
import os
import time
from typing import Iterable

import requests


LOGGER = logging.getLogger(__name__)


class HomeAssistantApi:
    def __init__(self, token: str | None = None, base_url: str = "http://supervisor/core/api/", timeout: int = 5) -> None:
        self.token = token or os.environ.get("SUPERVISOR_TOKEN")
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self._cache: dict[str, tuple[float, str]] = {}

    @property
    def available(self) -> bool:
        return bool(self.token)

    def get_state(self, entity_id: str) -> str:
        if not self.token:
            return "--"
        cached = self._cache.get(entity_id)
        if cached and time.monotonic() - cached[0] < 5:
            return cached[1]
        try:
            response = requests.get(
                self.base_url + "states/" + entity_id,
                headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            LOGGER.debug("Home Assistant API request failed for %s: %s", entity_id, exc)
            return "--"
        if response.status_code != 200:
            LOGGER.debug("Home Assistant API returned %s for %s", response.status_code, entity_id)
            return "--"
        state = str(response.json().get("state", "--"))
        if state in {"unknown", "unavailable", ""}:
            state = "--"
        self._cache[entity_id] = (time.monotonic(), state)
        return state

    def warm_cache(self, entity_ids: Iterable[str]) -> None:
        for entity_id in set(entity_ids):
            self.get_state(entity_id)
