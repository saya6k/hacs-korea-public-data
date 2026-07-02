"""City bus (전국 TAGO + 서울 TOPIS) LLM tool."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from ..const import ENTRY_BUS
from .base_tool import BaseKRTool
from .render import svg_table

_BUS_ACCENT = "#16a34a"  # green


def _seconds_to_min(seconds: Any) -> str:
    try:
        s = int(seconds or 0)
    except (TypeError, ValueError):
        return "-"
    if s <= 0:
        return "곧 도착"
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m"


def _tago_arrivals(info: dict, data: dict) -> list[dict[str, Any]]:
    arrivals = []
    for route in info["routes"]:
        for idx, item in enumerate(data.get(route["routeId"], [])):
            stops = item.get("arrprevstationcnt")
            arrivals.append({
                "route_no": route["routeNo"],
                "order": "다음" if idx == 0 else "다다음",
                "vehicle_type": item.get("vehicletp") or "",
                "note": f"{stops}정류장 전" if stops is not None else "",
                "arrival_in_seconds": item.get("arrtime"),
            })
    return arrivals


def _seoul_arrivals(info: dict, data: dict) -> list[dict[str, Any]]:
    arrivals = []
    for route in info["routes"]:
        item = data.get(route["routeId"])
        if not item:
            continue
        for idx in range(2):
            n = idx + 1
            if not item.get(f"vehId{n}"):
                continue
            arrivals.append({
                "route_no": route["routeNo"],
                "order": "다음" if idx == 0 else "다다음",
                "vehicle_type": "",
                "note": item.get("adirection") or "",
                "arrival_in_seconds": item.get(f"traTime{n}"),
            })
    return arrivals


class GetCityBusArrivalsTool(BaseKRTool):
    service = ENTRY_BUS
    name = "get_city_bus_arrivals"
    description = (
        "Return upcoming city bus arrivals at a configured stop (nationwide "
        "TAGO data plus Seoul via TOPIS). Returns up to the next two buses "
        "per configured route."
    )
    parameters = vol.Schema(
        {
            vol.Optional(
                "stop",
                description=(
                    "Bus stop name (Korean, e.g. '대전역'). Omit to use the "
                    "first configured stop."
                ),
            ): str,
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        store = self.store
        by_name: dict[str, Any] = store.get("city_bus_by_name") or {}
        if not by_name:
            return self.error("등록된 버스 정류장이 없습니다.")

        wanted = tool_input.tool_args.get("stop")
        if wanted is None:
            stop = next(iter(by_name.keys()))
        elif wanted in by_name:
            stop = wanted
        else:
            return self.error(f"'{wanted}' 정류장이 등록되어 있지 않습니다.")

        info = by_name[stop]
        coord = info["coordinator"]
        if coord.data is None:
            return self.error("버스 도착 데이터가 아직 준비되지 않았습니다.")

        arrivals = (_seoul_arrivals(info, coord.data) if info["kind"] == "seoul"
                    else _tago_arrivals(info, coord.data))

        rows = [
            [
                a["route_no"],
                a["order"],
                _seconds_to_min(a.get("arrival_in_seconds")),
                a.get("note") or "",
                a.get("vehicle_type") or "",
            ]
            for a in arrivals
        ]
        featured = svg_table(
            "버스 도착 정보",
            ["노선", "구분", "도착", "비고", "차량"],
            rows,
            subtitle=stop,
            accent=_BUS_ACCENT,
            empty_message="현재 도착 예정 정보가 없습니다.",
        )

        return self.envelope(
            stop=stop,
            arrivals=arrivals,
            featured_image=featured,
            instruction=(
                "Summarise the next bus arrivals naturally. The user is "
                "already shown a table; keep your reply short. Convert "
                "arrival_in_seconds to minutes. A route with no '다다음' "
                "entry only has one bus currently tracked — don't invent one."
            ),
        )
