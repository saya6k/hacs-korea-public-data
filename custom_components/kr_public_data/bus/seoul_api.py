"""Seoul city bus (TOPIS, ws.bus.go.kr) API client.

Not part of the apis.data.go.kr/1613000 TAGO family (which excludes Seoul
entirely — verified live: cityCode 11 absent from getCtyCodeList). This is
a separate legacy service; verified live 2026-07-03 that the same
data.go.kr-issued service_key already used for TAGO authenticates here too,
with no additional 활용신청 needed. Unlike TAGO, a single
getStationByUid call already returns both the 1st and 2nd upcoming bus per
route at that stop — no separate "다음/다다음" derivation needed.
"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from ..exceptions import KrQuotaError, KrTransientError

_LOGGER = logging.getLogger(__name__)

BASE = "http://ws.bus.go.kr/api/rest"


def _items(data: dict) -> list[dict[str, Any]]:
    items = data.get("msgBody", {}).get("itemList")
    if not items:
        return []
    return items if isinstance(items, list) else [items]


async def _call(session: aiohttp.ClientSession, operation: str, api_key: str,
                 params: dict[str, Any]) -> list[dict[str, Any]]:
    url = f"{BASE}/{operation}"
    query = {**params, "serviceKey": api_key, "resultType": "json"}
    try:
        async with session.get(url, params=query,
                                timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                raise KrTransientError(f"{operation}: HTTP {r.status}")
            data = await r.json(content_type=None)
    except aiohttp.ClientError as err:
        raise KrTransientError(f"{operation}: {err}") from err

    header = data.get("msgHeader", {})
    code = header.get("headerCd")
    if code not in ("0", "4"):  # 0=success, 4=no matching data
        msg = header.get("headerMsg", "")
        # headerCd 7 is an overloaded auth-error bucket; this specific
        # message is ws.bus.go.kr's rate-limit/quota response within it.
        if code == "7" and "REQUESTS EXCEEDS" in msg.upper():
            raise KrQuotaError(f"{operation}: {msg}")
        raise KrTransientError(f"{operation}: headerCd {code} {msg}")
    return _items(data)


async def validate_seoul_bus_api(session: aiohttp.ClientSession, api_key: str) -> bool:
    try:
        await _call(session, "stationinfo/getStationByName", api_key, {"stSrch": "강남역"})
        return True
    except Exception:
        return False


async def search_stops(session: aiohttp.ClientSession, api_key: str,
                        name: str) -> list[dict[str, Any]]:
    """정류소명(부분일치)으로 검색. [{stId, stNm, arsId, ...}]."""
    return await _call(session, "stationinfo/getStationByName", api_key, {"stSrch": name})


async def fetch_stop_arrivals(session: aiohttp.ClientSession, api_key: str,
                               ars_id: str) -> list[dict[str, Any]]:
    """정류소의 전체 노선 도착정보(1회 호출). 노선당 1st/2nd 버스 정보 포함."""
    return await _call(session, "stationinfo/getStationByUid", api_key, {"arsId": ars_id})
