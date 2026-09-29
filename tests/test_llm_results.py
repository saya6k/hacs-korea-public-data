"""LLM result contracts; run with HA 2026.10+ and pytest installed."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from homeassistant.helpers import llm

from custom_components.kr_public_data.const import DOMAIN
from custom_components.kr_public_data.llm.kma_weather_tool import GetKMAWeatherForecastTool
from custom_components.kr_public_data.llm.safety_alert_tool import GetSafetyAlertsTool
from custom_components.kr_public_data.llm.tools import TOOLS_BY_ETYPE


def test_all_tools_report_missing_data_as_errors():
    hass = SimpleNamespace(data={})
    for factories in TOOLS_BY_ETYPE.values():
        for factory in factories:
            tool = factory(hass, "test")
            result = asyncio.run(
                tool.async_call(
                    hass, llm.ToolInput(tool_name=tool.name, tool_args={"range": "week"}), None
                )
            )
            assert isinstance(result, llm.ToolResult), tool.name
            assert result.error, tool.name
            assert result.data["error"], tool.name
            assert tool.integration == DOMAIN
            assert tool.title
            assert tool.annotations == llm.ToolAnnotations(
                read_only=True, destructive=False, idempotent=True, open_world=False
            )


def test_empty_alerts_are_success_with_featured_image():
    store = {
        "coordinators": {"seoul": SimpleNamespace(data={"alerts": []})},
        "regions": [{"code": "seoul", "name": "Seoul"}],
    }
    hass = SimpleNamespace(data={DOMAIN: {"test": store}})
    tool = GetSafetyAlertsTool(hass, "test")
    result = asyncio.run(
        tool.async_call(hass, llm.ToolInput(tool_name=tool.name, tool_args={}), None)
    )
    assert not result.error
    assert result.data["total_active"] == 0
    assert result.data["results"] == []
    assert result.data["featured_image"].startswith("data:image/svg+xml;base64,")


def test_weather_preserves_native_card_payload():
    store = {
        "coordinator": SimpleNamespace(
            data={
                "Seoul": {
                    "daily_forecasts": [{"datetime": "2026-09-29", "temperature": 20}],
                    "temperature": 21,
                }
            }
        )
    }
    hass = SimpleNamespace(data={DOMAIN: {"test": store}})
    tool = GetKMAWeatherForecastTool(hass, "test")
    result = asyncio.run(
        tool.async_call(hass, llm.ToolInput(tool_name=tool.name, tool_args={"range": "week"}), None)
    )
    assert isinstance(result, llm.ToolResult)
    assert not result.error
    assert result.data["source"] == "kma"
    assert result.data["forecast"]
    assert result.data["current_temperature"] == "21°C"
