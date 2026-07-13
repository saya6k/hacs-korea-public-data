"""Subway (Seoul realtime arrivals) LLM tool."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from ..const import ENTRY_TRANSIT
from .base_tool import BaseKRTool
from .render import svg_table

_SUBWAY_ACCENT = "#0ea5e9"  # sky


def _seconds_to_min(seconds: Any) -> str:
    try:
        s = int(seconds or 0)
    except (TypeError, ValueError):
        return "-"
    if s <= 0:
        return "-"
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m"


class GetSubwayArrivalsTool(BaseKRTool):
    service = ENTRY_TRANSIT
    name = "get_subway_arrivals"
    description = (
        "Return upcoming Seoul subway arrivals at a configured station. "
        "Returns the next two trains per direction filter."
    )
    parameters = vol.Schema(
        {
            vol.Optional(
                "station",
                description=(
                    "Station name (Korean, e.g. '강남'). Omit to use the "
                    "first configured station."
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
        coords: dict[str, Any] = store.get("subway_coords") or {}
        if not coords:
            return self.error("등록된 지하철 역이 없습니다.")

        wanted = tool_input.tool_args.get("station")
        if wanted is None:
            station = next(iter(coords.keys()))
        elif wanted in coords:
            station = wanted
        else:
            return self.error(f"'{wanted}' 역이 등록되어 있지 않습니다.")

        coord = coords[station]
        if coord.data is None:
            return self.error("지하철 도착 데이터가 아직 준비되지 않았습니다.")

        arrivals: list[dict[str, Any]] = []
        for key, items in coord.data.items():
            for item in items:
                arrivals.append({
                    "line": item.get("line_name"),
                    "direction": key.split("_")[0],
                    "destination": item.get("destination"),
                    "arrival_message": item.get("arrival_message"),
                    "arrival_in_seconds": item.get("barvl_dt"),
                    "train_type": item.get("train_type"),
                })

        rows = [
            [
                a.get("line") or "",
                a.get("direction") or "",
                a.get("destination") or "",
                _seconds_to_min(a.get("arrival_in_seconds")),
                a.get("arrival_message") or "",
            ]
            for a in arrivals
        ]
        featured = svg_table(
            "지하철 도착 정보",
            ["노선", "방향", "행선", "도착", "안내"],
            rows,
            subtitle=f"{station}역",
            accent=_SUBWAY_ACCENT,
            empty_message="현재 도착 예정 정보가 없습니다.",
        )

        return self.envelope(
            station=station,
            arrivals=arrivals,
            featured_image=featured,
            instruction=(
                "Summarise the next subway arrivals naturally. The user is "
                "already shown a table; keep your reply short. Translate "
                "the Korean direction (상행/하행/내선/외선) and "
                "arrival_message. Convert arrival_in_seconds to minutes "
                "for the user."
            ),
        )
