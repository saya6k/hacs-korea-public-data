"""City bus device helpers."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from custom_components.kr_public_data.const import DOMAIN


@callback
def bus_stop_device_id(hass: HomeAssistant, entry: ConfigEntry, sub_id: str | None,
                       info: dict) -> str:
    """Register the 정류장 hub device and return its id, for use as via_device_id.

    `info` is the stop's entry in store["stop_subs"] (nodeId / nodeName / kind).
    The hub holds no entities of its own — it exists so every route served at the
    stop nests under one device. It has to be registered here rather than handed
    to the entity platform as a DeviceInfo, because its id must be known *before*
    the route devices that reference it are built.
    """
    seoul = info["kind"] == "seoul"
    prefix = "seoul_bus_stop" if seoul else "city_bus_stop"
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=sub_id,
        identifiers={(DOMAIN, f"{prefix}_{info['nodeId']}")},
        translation_key="bus_stop",
        translation_placeholders={"stop": info["nodeName"]},
        manufacturer="서울시 TOPIS" if seoul else "국토교통부(TAGO)",
        model="버스 정류장",
        entry_type=DeviceEntryType.SERVICE,
    ).id


@callback
def intercity_bus_section_device_id(hass: HomeAssistant, entry: ConfigEntry,
                                    sub_id: str | None, dep_name: str,
                                    arr_name: str) -> str:
    """Register the 구간 hub device and return its id, for use as via_device_id.

    고속버스 and 시외버스 are booked on different platforms and stay separate
    devices (see intercity_bus_route_device), but they are the same 구간 to the
    user — this hub is what puts them side by side.
    """
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=sub_id,
        identifiers={(DOMAIN, f"intercity_bus_section_{dep_name}_{arr_name}")},
        translation_key="intercity_bus_section",
        translation_placeholders={"departure": dep_name, "arrival": arr_name},
        manufacturer="국토교통부(TAGO)", model="버스 구간",
        entry_type=DeviceEntryType.SERVICE,
    ).id


def city_bus_route_device(node_id: str, node_name: str, route_id: str, route_no: str,
                          via_device_id: str) -> DeviceInfo:
    """One device per (stop, route); both arrival sensors live under it."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"city_bus_{node_id}_{route_id}")},
        translation_key="bus_route",
        translation_placeholders={"stop": node_name, "route": route_no},
        manufacturer="국토교통부(TAGO)", model="시내버스 도착정보",
        entry_type=DeviceEntryType.SERVICE,
        via_device_id=via_device_id,
    )


def seoul_bus_route_device(ars_id: str, stop_name: str, route_id: str, route_no: str,
                           via_device_id: str) -> DeviceInfo:
    """One device per (Seoul stop, route); both arrival sensors live under it."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"seoul_bus_{ars_id}_{route_id}")},
        translation_key="bus_route",
        translation_placeholders={"stop": stop_name, "route": route_no},
        manufacturer="서울시 TOPIS", model="서울 버스 도착정보",
        entry_type=DeviceEntryType.SERVICE,
        via_device_id=via_device_id,
    )


def intercity_bus_route_device(dep_name: str, arr_name: str, grade_key: str,
                               via_device_id: str) -> DeviceInfo:
    """One device per (구간, 등급); both departure sensors live under it.

    Keyed by terminal *names*, not IDs — a route can resolve to more than
    one underlying (system, terminal-id) combination (see
    IntercityBusCoordinator). grade_key is "source:gradeNm" — 고속버스/
    시외버스 stay distinguishable in the device name since they're booked
    on different platforms, even though search doesn't ask the user to
    pick one.
    """
    source, grade = grade_key.split(":", 1)
    express = source == "express"
    label = "고속버스" if express else "시외버스"
    return DeviceInfo(
        identifiers={(DOMAIN, f"intercity_bus_{dep_name}_{arr_name}_{grade_key}")},
        # 고속/시외 is a fixed pair, so it gets its own key rather than a
        # placeholder — a placeholder value would stay Korean.
        translation_key="express_bus_route" if express else "intercity_bus_route",
        translation_placeholders={"departure": dep_name, "arrival": arr_name,
                                  "grade": grade},
        manufacturer="국토교통부(TAGO)", model=f"{label} 배차정보",
        entry_type=DeviceEntryType.SERVICE,
        via_device_id=via_device_id,
    )
