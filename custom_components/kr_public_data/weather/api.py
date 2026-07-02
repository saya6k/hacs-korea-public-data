"""KMA Weather Warning API client."""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Any
import aiohttp
from . import (KMA_API_BASE, EVENT_TYPE_ADVISORY, EVENT_TYPE_CANCELLED,
               EVENT_TYPE_NONE, EVENT_TYPE_PRE_ADVISORY, EVENT_TYPE_PRE_WARNING,
               EVENT_TYPE_WARNING)
from ..exceptions import KrTransientError, raise_for_result_code

_LOGGER = logging.getLogger(__name__)

def _parse_dt(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(str(s), "%Y%m%d%H%M")
    except (ValueError, TypeError):
        return None

def _determine_type(item: dict[str, Any]) -> str:
    if str(item.get("command", "")) != "1":
        return EVENT_TYPE_NONE
    if str(item.get("cancel", "")) != "0":
        return EVENT_TYPE_CANCELLED
    ws = item.get("warnStress", 1)
    st = _parse_dt(item.get("startTime", ""))
    if st and st <= datetime.now():
        return EVENT_TYPE_ADVISORY if ws == 0 else EVENT_TYPE_WARNING
    return EVENT_TYPE_PRE_ADVISORY if ws == 0 else EVENT_TYPE_PRE_WARNING

async def validate_kma_api(api_key: str, area_code: str) -> bool:
    params = {"serviceKey": api_key, "numOfRows": "1", "pageNo": "1",
              "areaCode": area_code, "warningType": "1", "dataType": "json"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(KMA_API_BASE, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    return False
                d = await r.json(content_type=None)
                return d.get("response", {}).get("header", {}).get("resultCode") in ("00", "03")
    except Exception:
        return False

async def fetch_warning(session: aiohttp.ClientSession, api_key: str,
                        area_code: str, warning_type: int) -> dict[str, Any]:
    """Fetch one warning slot. Raises on failure — only a genuine "no active
    warning" response (resultCode 03 / empty items) maps to EVENT_TYPE_NONE,
    so an API outage can never masquerade as an all-clear."""
    params = {"serviceKey": api_key, "numOfRows": "10", "pageNo": "1",
              "areaCode": area_code, "warningType": str(warning_type), "dataType": "json"}
    try:
        async with session.get(KMA_API_BASE, params=params,
                               timeout=aiohttp.ClientTimeout(total=30)) as r:
            if r.status != 200:
                raise KrTransientError(f"기상특보 HTTP {r.status}")
            data = await r.json(content_type=None)
    except aiohttp.ClientError as err:
        raise KrTransientError(f"기상특보 연결 실패: {err}") from err
    hdr = data.get("response", {}).get("header", {})
    rc = hdr.get("resultCode")
    if rc == "03":  # NO_DATA — no warning active for this area/type
        return {"event_type": EVENT_TYPE_NONE, "raw": None}
    if rc != "00":
        raise_for_result_code(rc, hdr.get("resultMsg", ""))
        raise KrTransientError(
            f"기상특보 resultCode {rc}: {hdr.get('resultMsg', '')}")
    try:
        items = data["response"]["body"]["items"]["item"]
        if not items:
            return {"event_type": EVENT_TYPE_NONE, "raw": None}
        item = items[0] if isinstance(items, list) else items
        et = _determine_type(item)
        sdt = _parse_dt(item.get("startTime", ""))
        edt = _parse_dt(item.get("endTime", ""))
        return {"event_type": et, "start_time": sdt.isoformat() if sdt else None,
                "end_time": edt.isoformat() if edt else None,
                "start_time_dt": sdt, "end_time_dt": edt,
                "warn_stress": item.get("warnStress"), "raw": item}
    except (KeyError, IndexError, TypeError) as err:
        raise KrTransientError(f"기상특보 응답 형식 오류: {err}") from err
