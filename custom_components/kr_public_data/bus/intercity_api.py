"""Express/intercity bus (고속버스/시외버스) API client.

Both are same-day dispatch timetables (not live countdowns), verified live
2026-07-03. Base URL has NO "Service" suffix — e.g. `.../ExpBusInfo`, not
`.../ExpBusInfoService` — that mismatch was the actual cause of persistent
404s during initial investigation, not an approval/propagation issue (both
datasets showed [승인] the whole time). Response envelope matches the city
bus API exactly (`response.header.resultCode`), so this reuses bus.api's
HTTP/error-handling helper instead of duplicating it.
"""
from __future__ import annotations

from typing import Any

import aiohttp

from .api import _call

EXPRESS_BASE = "https://apis.data.go.kr/1613000/ExpBusInfo"
INTERCITY_BASE = "https://apis.data.go.kr/1613000/SuburbsBusInfo"

_SOURCES = {
    "express": {
        "base": EXPRESS_BASE,
        "terminal_op": "GetExpBusTrminlList",
        "dispatch_op": "GetStrtpntAlocFndExpbusInfo",
    },
    "intercity": {
        "base": INTERCITY_BASE,
        "terminal_op": "GetSuberbsBusTrminlList",  # sic — TAGO's own spelling
        "dispatch_op": "GetStrtpntAlocFndSuberbsBusInfo",
    },
}


async def search_terminals(session: aiohttp.ClientSession, api_key: str,
                            source: str, name: str) -> list[dict[str, Any]]:
    """터미널명(부분일치)으로 검색. [{terminalId, terminalNm, cityName?}]."""
    cfg = _SOURCES[source]
    return await _call(session, cfg["base"], cfg["terminal_op"], api_key,
                       {"terminalNm": name, "numOfRows": 30})


async def fetch_dispatches(session: aiohttp.ClientSession, api_key: str, source: str,
                            dep_terminal_id: str, arr_terminal_id: str) -> list[dict[str, Any]]:
    """출발-도착 터미널 구간의 당일 배차 전체(1회 호출, 노선당 여러 등급 혼재).

    depPlandTime 오름차순 정렬은 호출측(coordinator) 책임.
    """
    cfg = _SOURCES[source]
    return await _call(session, cfg["base"], cfg["dispatch_op"], api_key,
                       {"depTerminalId": dep_terminal_id, "arrTerminalId": arr_terminal_id,
                        "numOfRows": 200})


async def discover_queries(session: aiohttp.ClientSession, api_key: str,
                            dep_name: str, arr_name: str
                            ) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """dep_name/arr_name으로 검색할 땐 고속버스/시외버스를 구분하지 않고
    양쪽을 능동적으로 조회해 실제 배차가 있는 (source, depTerminalId,
    arrTerminalId) 조합을 전부 찾는다 — 같은 이름의 터미널이 한 소스 안에
    여러 개(예: "동서울" 4곳) 있어도 전부 시도해서 실제로 동작하는 것만
    골라낸다.

    하지만 고속버스/시외버스는 결제 플랫폼이 달라 사용자가 구분할 수 있어야
    하므로, 반환하는 dispatch 항목마다 어느 쪽에서 나왔는지 `_source`를
    붙여 등급 선택 단계에서 "일반 (시외버스)" 처럼 표시할 수 있게 한다.

    Returns (queries, all_dispatches) — queries는 이후 coordinator가 그대로
    재사용해 매 폴링마다 동일한 조합만 호출하도록 subentry.data에 저장된다.
    """
    queries: list[dict[str, str]] = []
    all_dispatches: list[dict[str, Any]] = []
    for source in _SOURCES:
        try:
            deps = await search_terminals(session, api_key, source, dep_name)
            arrs = await search_terminals(session, api_key, source, arr_name)
        except Exception:
            continue
        dep_ids = {c["terminalId"] for c in deps if c["terminalNm"] == dep_name}
        arr_ids = {c["terminalId"] for c in arrs if c["terminalNm"] == arr_name}
        for dep_id in dep_ids:
            for arr_id in arr_ids:
                try:
                    dispatches = await fetch_dispatches(session, api_key, source, dep_id, arr_id)
                except Exception:
                    continue
                if dispatches:
                    queries.append({"source": source, "depTerminalId": dep_id,
                                    "arrTerminalId": arr_id})
                    for d in dispatches:
                        all_dispatches.append({**d, "_source": source})
    return queries, all_dispatches
