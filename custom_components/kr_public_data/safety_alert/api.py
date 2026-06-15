"""Safety Alert API.

safekorea.go.kr replaced its old JSON endpoint
(/idsiSFK/sfk/cs/sua/web/DisasterSmsList.do — now silently redirects to main.do)
with the server-rendered listing page at
/safekorea-kor/ctim/cmsg/calamitySms.do, where the SMS records live in the
HTML response itself. We warm the session by GETing main.do so the elevisor
WAF hands out cookies, then GET the listing page (with sbLawArea1/2 region
filters) and parse out each <li> in the message list.

If we still get redirected to main.do or get a non-listing page back, we
surface the rejection rather than silently returning nothing.
"""
from __future__ import annotations
import logging
import re
from typing import Dict, Any, Optional, List

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests

from .exceptions import SafetyAlertConnectionError

_LOGGER = logging.getLogger(__name__)
_IMPERSONATE = "chrome"
_TIMEOUT = 15

_BASE = "https://www.safekorea.go.kr"
_WARMUP_URL = f"{_BASE}/safekorea-kor/main/main.do"
_LIST_URL = f"{_BASE}/safekorea-kor/ctim/cmsg/calamitySms.do"

_ONSUBMIT_ID = re.compile(r"onSubmit\(['\"]([^'\"]+)['\"]\)")


def _label_value(infolist, label: str) -> str:
    """Return the text following <span>{label} : </span> in a brd-infolist block."""
    for p in infolist.find_all("p"):
        span = p.find("span")
        if span and label in span.get_text():
            text = p.get_text(" ", strip=True)
            # strip the "label :" prefix
            return re.sub(rf"^{re.escape(label)}\s*:?\s*", "", text).strip()
    return ""


def _parse_list_html(html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    # Each message is an <li> inside the listing whose <div class="brd-context"> wraps the title + meta.
    items = []
    for li in soup.select("li"):
        ctx = li.find("div", class_="brd-context")
        if not ctx:
            continue
        title_a = ctx.select_one("h3.title-text a")
        info = ctx.find("div", class_="brd-infolist")
        if not title_a or not info:
            continue
        msg = title_a.get_text(" ", strip=True)
        sn = ""
        if title_a.has_attr("href"):
            m = _ONSUBMIT_ID.search(title_a["href"])
            if m:
                sn = m.group(1)
        items.append({
            "MD101_SN": sn,
            "MSG_CN": msg,
            "DST_SE_NM": _label_value(info, "재해구분"),
            "EMRG_STEP_NM": _label_value(info, "긴급단계"),
            "RCV_AREA_NM": _label_value(info, "송출지역"),
            "CRT_DT": _label_value(info, "발송일시"),
            "MSG_SE_NM": _label_value(info, "긴급단계"),
        })
    return items


class SafetyAlertApiClient:
    def __init__(self, session=None) -> None:
        # session arg kept for backward compatibility; curl_cffi creates its own.
        self._session = session

    async def async_get_safety_alerts(
        self, area_code: str = "1100000000",
        area_code2: Optional[str] = None,
        area_code3: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = {
            "menuSn": "34",
            "currentPage": "1",
            "readYn": "Y",
            "firstYn": "N",
            "sbLawArea1": area_code or "",
            "sbLawArea2": area_code2 or "",
            "sbLawArea3": area_code3 or "",
        }
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": _WARMUP_URL,
            "Upgrade-Insecure-Requests": "1",
        }
        try:
            async with cffi_requests.AsyncSession(impersonate=_IMPERSONATE) as s:
                # Warmup: pick up elevisor / JSESSIONID cookies.
                await s.get(_WARMUP_URL, timeout=_TIMEOUT, verify=False)
                r = await s.get(
                    _LIST_URL, params=params, headers=headers,
                    timeout=_TIMEOUT, verify=False,
                )

            if r.status_code != 200:
                raise SafetyAlertConnectionError(f"HTTP {r.status_code}")

            final_url = str(getattr(r, "url", "") or "")
            if "main.do" in final_url and "calamitySms.do" not in final_url:
                raise SafetyAlertConnectionError(
                    f"endpoint redirected to {final_url}; request rejected"
                )

            html = r.text or ""
            if "calamitySms" not in html and "재해구분" not in html:
                preview = html[:200].replace("\n", " ")
                raise SafetyAlertConnectionError(
                    f"unexpected response shape; body starts with: {preview!r}"
                )

            items = _parse_list_html(html)
            return {
                "disasterSmsList": items,
                "rtnResult": {"totCnt": len(items)},
            }
        except SafetyAlertConnectionError:
            raise
        except Exception as e:
            raise SafetyAlertConnectionError(str(e)) from e
