"""Safety Alert Region API client for getting region codes.

safekorea.go.kr was replatformed: the old /idsiSFK/sfk/cs/sua/web/*.do
endpoints now 302 to the new main page. The region dropdowns of the new
disaster-SMS page (/safekorea-kor/ctim/cmsg/calamitySms.do) are fed by
changeSidoList_new.do / changeSggList_new.do, which take a JSON body
(form-encoded POSTs get a 500). The site still rejects Python's default
TLS fingerprint, so keep curl_cffi with chrome impersonation.

Note the 2026 행정구역 codes: 전북특별자치도 is 5200000000 (4500000000
returns an empty list) and 전남광주통합특별시 (1200000000) exists alongside
the still-working 광주(2900000000)/전남(4600000000) codes.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List

from curl_cffi import requests as cffi_requests

_LOGGER = logging.getLogger(__name__)
_IMPERSONATE = "chrome"
_TIMEOUT = 15

_BASE = "https://www.safekorea.go.kr/safekorea-kor/ctim/cmsg"
_PAGE_URL = f"{_BASE}/calamitySms.do?menuSn=34"


class SafetyAlertRegionApiClient:
    """API client for Safety Alert region code retrieval."""

    def __init__(self, session=None) -> None:
        # session arg kept for backward compatibility; curl_cffi creates its own.
        self._session = session

    @staticmethod
    def _headers() -> Dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.safekorea.go.kr",
            "Referer": _PAGE_URL,
            "X-Requested-With": "XMLHttpRequest",
        }

    async def _post_json(self, url: str, payload: dict) -> list | None:
        try:
            async with cffi_requests.AsyncSession(impersonate=_IMPERSONATE) as s:
                r = await s.post(
                    url, json=payload, headers=self._headers(),
                    timeout=_TIMEOUT, verify=False,
                )
            if r.status_code != 200:
                _LOGGER.warning("Region API %s: HTTP %s", url, r.status_code)
                return None
            ctype = (r.headers.get("Content-Type") or "").lower()
            if "json" not in ctype:
                _LOGGER.warning(
                    "Region API %s returned non-JSON (content-type: %s)",
                    url, ctype,
                )
                return None
            data = r.json()
            return data if isinstance(data, list) else None
        except Exception as e:
            _LOGGER.warning("Region API %s failed: %s", url, e)
            return None

    async def async_get_sido_list(self) -> List[Dict[str, str]]:
        """Get list of sido (시도) regions.

        There is no JSON endpoint for the sido level — the options are
        rendered into the page HTML, so scrape them from there.
        """
        try:
            async with cffi_requests.AsyncSession(impersonate=_IMPERSONATE) as s:
                r = await s.get(_PAGE_URL, timeout=_TIMEOUT, verify=False)
            if r.status_code != 200:
                return []
            result = [
                {"code": code, "name": name}
                for code, name in re.findall(
                    r'<option value="(\d{10})">([^<]+)</option>', r.text)
            ]
        except Exception as e:
            _LOGGER.warning("Region API sido page failed: %s", e)
            return []
        result.sort(key=lambda x: x["name"])
        return result

    async def async_get_sgg_list(self, sido_code: str) -> List[Dict[str, str]]:
        """Get list of sgg (시군구) regions for a given sido."""
        data = await self._post_json(
            f"{_BASE}/changeSidoList_new.do", {"sbLawArea1": sido_code})
        if not data:
            return []
        result = [
            {"code": s.get("bdongCd", ""), "name": s.get("cbsAreaNm", "")}
            for s in data
        ]
        result.sort(key=lambda x: x["name"])
        return result

    async def async_get_emd_list(
        self, sido_code: str, sgg_code: str
    ) -> List[Dict[str, str]]:
        """Get list of emd (읍면동) regions for a given sido and sgg."""
        data = await self._post_json(
            f"{_BASE}/changeSggList_new.do",
            {"sbLawArea1": sido_code, "sbLawArea2": sgg_code})
        if not data:
            return []
        result = [
            {"code": e.get("bdongCd", ""), "name": e.get("cbsAreaNm", "")}
            for e in data
        ]
        result.sort(key=lambda x: x["name"])
        return result
