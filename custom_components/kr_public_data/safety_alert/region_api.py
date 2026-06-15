"""Safety Alert Region API client for getting region codes.

safekorea.go.kr rejects Python's default TLS fingerprint and serves the
homepage HTML in place of the JSON endpoint. Use curl_cffi with chrome
impersonation, like the main DisasterSmsList endpoint.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List

from curl_cffi import requests as cffi_requests

_LOGGER = logging.getLogger(__name__)
_IMPERSONATE = "chrome"
_TIMEOUT = 15


class SafetyAlertRegionApiClient:
    """API client for Safety Alert region code retrieval."""

    BASE_URL = "https://www.safekorea.go.kr/idsiSFK/sfk/cs/sua/web"

    def __init__(self, session=None) -> None:
        # session arg kept for backward compatibility; curl_cffi creates its own.
        self._session = session

    @staticmethod
    def _headers() -> Dict[str, str]:
        return {
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.safekorea.go.kr",
            "Referer": "https://www.safekorea.go.kr/idsiSFK/neo/sfk/cs/sfc/dis/disasterMsgList.jsp",
            "X-Requested-With": "XMLHttpRequest",
        }

    async def _post_json(self, url: str, payload: dict) -> dict | None:
        try:
            async with cffi_requests.AsyncSession(impersonate=_IMPERSONATE) as s:
                r = await s.post(
                    url, json=payload, headers=self._headers(),
                    timeout=_TIMEOUT, verify=False,
                )
            if r.status_code != 200:
                _LOGGER.warning("Region API %s: HTTP %s", url, r.status_code)
                return None
            final_url = str(getattr(r, "url", "") or "")
            ctype = (r.headers.get("Content-Type") or "").lower()
            if "main.do" in final_url or "html" in ctype:
                _LOGGER.warning(
                    "Region API %s redirected to %s (content-type: %s)",
                    url, final_url or "<unknown>", ctype,
                )
                return None
            return json.loads(r.text)
        except Exception as e:
            _LOGGER.warning("Region API %s failed: %s", url, e)
            return None

    async def async_get_sido_list(self) -> List[Dict[str, str]]:
        """Get list of sido (시도) regions."""
        url = f"{self.BASE_URL}/Get_CBS_Sido_List.do"
        data = await self._post_json(url, {})
        if not data:
            return []
        result = [
            {
                "code": s.get("BDONG_CD", ""),
                "name": s.get("CBS_AREA_NM", ""),
                "id": s.get("CBS_AREA_ID", ""),
            }
            for s in data.get("cbs_sido_list", [])
        ]
        result.sort(key=lambda x: x["name"])
        return result

    async def async_get_sgg_list(self, sido_code: str) -> List[Dict[str, str]]:
        """Get list of sgg (시군구) regions for a given sido."""
        url = f"{self.BASE_URL}/Get_CBS_Sgg_List.do"
        payload = {"sgg_searchInfo": {"BDONG_CD": "", "bdong_cd": sido_code}}
        data = await self._post_json(url, payload)
        if not data:
            return []
        result = [
            {"code": s.get("BDONG_CD", ""), "name": s.get("CBS_AREA_NM", "")}
            for s in data.get("cbs_sgg_list", [])
        ]
        result.sort(key=lambda x: x["name"])
        return result

    async def async_get_emd_list(
        self, sido_code: str, sgg_code: str
    ) -> List[Dict[str, str]]:
        """Get list of emd (읍면동) regions for a given sido and sgg."""
        url = f"{self.BASE_URL}/Get_CBS_Emd_List.do"
        payload = {
            "emd_searchInfo": {
                "BDONG_CD": "",
                "area1_bdong_cd": sido_code,
                "area2_bdong_cd": sgg_code,
            }
        }
        data = await self._post_json(url, payload)
        if not data:
            return []
        result = [
            {"code": e.get("BDONG_CD", ""), "name": e.get("CBS_AREA_NM", "")}
            for e in data.get("cbs_emd_list", [])
        ]
        result.sort(key=lambda x: x["name"])
        return result
