"""Disaster message coordinator - resilient to intermittent SSL errors."""
from __future__ import annotations
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from . import DISASTER_SCAN_INTERVAL
from .api import fetch_disaster_messages
from ..resilience import ResilientCoordinator

_LOGGER = logging.getLogger(__name__)


def filter_messages(msgs, sido="", sgg="", legacy=""):
    """Filter messages by region.

    sido+sgg: match parts like "서울특별시 종로구"; sido-wide ("서울특별시 전체")
    and nationwide ("전국") messages also match. sido alone (sgg=""): match
    any district within that sido (whole-sido subentry). legacy: plain
    substring filter kept for entries created before per-district subentries.
    """
    if sido:
        sido_short = sido[:2]
        out = []
        for m in msgs:
            area = m.get("area") or ""
            for part in area.split(","):
                part = part.strip()
                if "전국" in part or (
                        sido_short in part
                        and (not sgg or sgg in part or "전체" in part)):
                    out.append(m)
                    break
        return out
    if legacy:
        return [m for m in msgs if legacy in (m.get("area") or "")]
    return msgs


class DisasterCoordinator(ResilientCoordinator):
    # safetydata.go.kr flaps often; a blip must not read as "no alerts".
    stale_tolerance = 5

    def __init__(self, hass, api_key):
        super().__init__(hass, _LOGGER, name="disaster",
                         update_interval=timedelta(seconds=DISASTER_SCAN_INTERVAL))
        self._api_key = api_key

    async def _fetch(self):
        return await fetch_disaster_messages(self._api_key, count=30)
