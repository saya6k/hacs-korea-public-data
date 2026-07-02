"""TAGO(국토교통부) city-bus API client.

Parameter casing is inconsistent across TAGO operations and gets silently
ignored (not rejected) when wrong — verified live 2026-07-02:
- getSttnThrghRouteList requires lowercase `nodeid`; `nodeId` is silently
  ignored and returns the whole city's routes, unfiltered.
- getSttnAcctoArvlPrearngeInfoList requires camelCase `nodeId`; lowercase
  `nodeid` is silently ignored and returns an empty result.
Do not "fix" the casing below without re-verifying against a live response.
"""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from ..exceptions import KrTransientError, raise_for_result_code

_LOGGER = logging.getLogger(__name__)

STTN_BASE = "https://apis.data.go.kr/1613000/BusSttnInfoInqireService"
ARVL_BASE = "https://apis.data.go.kr/1613000/ArvlInfoInqireService"


def _items(data: dict) -> list[dict[str, Any]]:
    """Normalize a TAGO response body: single result is a dict, not a list."""
    body = data.get("response", {}).get("body", {})
    items = body.get("items")
    if not items:
        return []
    item = items.get("item") if isinstance(items, dict) else None
    if item is None:
        return []
    return item if isinstance(item, list) else [item]


async def _call(session: aiohttp.ClientSession, base_url: str, operation: str,
                 api_key: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    url = f"{base_url}/{operation}"
    query = {**params, "serviceKey": api_key, "_type": "json"}
    try:
        async with session.get(url, params=query,
                                timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                raise KrTransientError(f"{operation}: HTTP {r.status}")
            data = await r.json(content_type=None)
    except aiohttp.ClientError as err:
        raise KrTransientError(f"{operation}: {err}") from err

    header = data.get("response", {}).get("header", {})
    code = header.get("resultCode")
    if code not in ("00", "03"):
        raise_for_result_code(code, header.get("resultMsg", ""))
        raise KrTransientError(f"{operation}: resultCode {code} {header.get('resultMsg', '')}")
    return _items(data)


async def validate_bus_api(session: aiohttp.ClientSession, api_key: str) -> bool:
    """Lightweight connectivity/auth check against 정류소정보."""
    try:
        await _call(session, STTN_BASE, "getSttnNoList", api_key,
                    {"cityCode": 25, "numOfRows": 1})
        return True
    except Exception:
        return False


async def search_stops(session: aiohttp.ClientSession, api_key: str,
                        city_code: int, name: str) -> list[dict[str, Any]]:
    """정류소명(부분일치)으로 정류소 후보를 검색. [{nodeid, nodenm, nodeno, ...}]."""
    return await _call(session, STTN_BASE, "getSttnNoList", api_key,
                       {"cityCode": city_code, "nodeNm": name, "numOfRows": 30})


async def stop_routes(session: aiohttp.ClientSession, api_key: str,
                       city_code: int, node_id: str) -> list[dict[str, Any]]:
    """그 정류소를 지나는 노선 목록. [{routeid, routeno, routetp, ...}]."""
    return await _call(session, STTN_BASE, "getSttnThrghRouteList", api_key,
                       {"cityCode": city_code, "nodeid": node_id, "numOfRows": 100})


async def fetch_stop_arrivals(session: aiohttp.ClientSession, api_key: str,
                               city_code: int, node_id: str) -> list[dict[str, Any]]:
    """정류소의 전체 노선 도착예정정보(1회 호출, 노선 필터 없음).

    Caller filters by routeid client-side so N selected routes only cost
    one API call per poll (mirrors subway's bulk-fetch-then-filter).
    """
    return await _call(session, ARVL_BASE, "getSttnAcctoArvlPrearngeInfoList", api_key,
                       {"cityCode": city_code, "nodeId": node_id, "numOfRows": 50})
