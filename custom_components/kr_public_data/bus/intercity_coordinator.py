"""Intercity/express bus (시외/고속버스) departure coordinator.

Unlike city bus arrival data, this is a same-day dispatch timetable, not a
live countdown. "다음/다다음" here means the next two scheduled departures
(by depPlandTime) that haven't passed yet, per selected grade (등급).
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .intercity_api import fetch_dispatches
from ..resilience import ResilientCoordinator

_LOGGER = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
INTERCITY_BUS_SCAN_INTERVAL = 300  # same-day schedule, doesn't need live-arrival cadence


def _parse_plandtime(value) -> datetime | None:
    """Handles both the 12-digit (YYYYMMDDHHmm, express) and 14-digit
    (YYYYMMDDHHMMSS, intercity) forms seen live — only minute precision
    matters here, so seconds (if present) are ignored."""
    s = str(value)
    if len(s) < 12:
        return None
    try:
        return datetime.strptime(s[:12], "%Y%m%d%H%M").replace(tzinfo=KST)
    except ValueError:
        return None


class IntercityBusCoordinator(ResilientCoordinator):
    """One coordinator per O-D pair subentry - fetches today's full dispatch list.

    queries is a list of {"source", "depTerminalId", "arrTerminalId"} — one
    entry per (system, terminal-variant) combination that discover_queries()
    found actually has dispatches. Usually just one, but a route name can
    resolve to more than one working combination (e.g. duplicate express
    terminal variants, or both 고속버스 and 시외버스 serving the same names),
    in which case all are polled together.

    grades is a list of "source:gradeNm" composite keys (e.g. "express:우등")
    — 고속버스/시외버스 are booked on different platforms, so they must stay
    distinguishable even though search/discovery treats them uniformly.
    """
    stale_tolerance = 3  # same-day schedule, less time-critical than live arrivals

    def __init__(self, hass: HomeAssistant, api_key: str,
                 queries: list[dict[str, str]], grades: list[str]) -> None:
        name_key = f"{queries[0]['depTerminalId']}_{queries[0]['arrTerminalId']}" if queries else "empty"
        super().__init__(hass, _LOGGER, name=f"intercity_bus_{name_key}",
                         update_interval=timedelta(seconds=INTERCITY_BUS_SCAN_INTERVAL))
        self._api_key = api_key
        self._queries = queries
        self._session = async_get_clientsession(hass)
        self.grades = grades  # ["source:gradeNm", ...]

    async def _fetch(self):
        raw = []
        for q in self._queries:
            items = await fetch_dispatches(self._session, self._api_key, q["source"],
                                           q["depTerminalId"], q["arrTerminalId"])
            raw.extend({**item, "_source": q["source"]} for item in items)
        now = datetime.now(KST)
        result = {}
        for grade_key in self.grades:
            source, grade = grade_key.split(":", 1)
            upcoming = []
            for item in raw:
                if item.get("_source") != source or item.get("gradeNm") != grade:
                    continue
                dt = _parse_plandtime(item.get("depPlandTime"))
                if dt and dt >= now:
                    upcoming.append((dt, item))
            upcoming.sort(key=lambda pair: pair[0])
            result[grade_key] = upcoming[:2]
        return result
