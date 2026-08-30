"""City bus device helpers."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import (
    ChildDeviceInfo,
    DeviceEntryType,
    DeviceInfo,
)

from custom_components.kr_public_data.const import DOMAIN


def bus_stop_key(info: dict) -> str:
    """Identifier of the 정류장 hub device, also the prefix of its entity's unique_id.

    Seoul and TAGO stops are numbered independently, so the source has to be part
    of the key — an arsId and a nodeId can collide.
    """
    prefix = "seoul_bus_stop" if info["kind"] == "seoul" else "city_bus_stop"
    return f"{prefix}_{info['nodeId']}"


def bus_stop_device(info: dict) -> DeviceInfo:
    """The 정류장 hub: main device carrying the stop's route child devices.

    `info` is the stop's entry in store["stop_subs"] (nodeId / nodeName / kind).
    """
    seoul = info["kind"] == "seoul"
    return DeviceInfo(
        identifiers={(DOMAIN, bus_stop_key(info))},
        translation_key="bus_stop",
        translation_placeholders={"stop": info["nodeName"]},
        manufacturer="서울시 TOPIS" if seoul else "국토교통부(TAGO)",
        model="버스 정류장",
        entry_type=DeviceEntryType.SERVICE,
    )


@callback
def bus_stop_device_id(hass: HomeAssistant, entry: ConfigEntry, sub_id: str | None,
                       info: dict) -> str:
    """Register the 정류장 hub device and return its id, for use as parent_device_id.

    Registered here rather than left to the entity platform because the id must
    be known *before* the route child devices that reference it are built.
    """
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=sub_id,
        **bus_stop_device(info),
    ).id


def intercity_bus_section_key(dep_name: str, arr_name: str) -> str:
    """Identifier of the 구간 hub device, also the prefix of its entity's unique_id."""
    return f"intercity_bus_section_{dep_name}_{arr_name}"


def intercity_bus_section_device(dep_name: str, arr_name: str) -> DeviceInfo:
    """The 구간 hub: main device carrying the section's 등급 child devices.

    고속버스 and 시외버스 are booked on different platforms and stay separate
    devices (see intercity_bus_route_device), but they are the same 구간 to the
    user — this hub is what puts them side by side.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, intercity_bus_section_key(dep_name, arr_name))},
        translation_key="intercity_bus_section",
        translation_placeholders={"departure": dep_name, "arrival": arr_name},
        manufacturer="국토교통부(TAGO)", model="버스 구간",
        entry_type=DeviceEntryType.SERVICE,
    )


@callback
def intercity_bus_section_device_id(hass: HomeAssistant, entry: ConfigEntry,
                                    sub_id: str | None, dep_name: str,
                                    arr_name: str) -> str:
    """Register the 구간 hub device and return its id, for use as parent_device_id.

    Registered here rather than left to the entity platform because the id must
    be known *before* the 등급 child devices that reference it are built.
    """
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=sub_id,
        **intercity_bus_section_device(dep_name, arr_name),
    ).id


def city_bus_route_device(node_id: str, node_name: str, route_id: str, route_no: str,
                          parent_device_id: str) -> ChildDeviceInfo:
    """One child device per (stop, route); both arrival sensors live under it.

    Identifiers are unchanged from when this was a main device, so HA converts
    existing entries in place and device ids survive. Child devices carry no
    manufacturer/model/entry_type — those live on the 정류장 hub.
    """
    return ChildDeviceInfo(
        identifiers={(DOMAIN, f"city_bus_{node_id}_{route_id}")},
        translation_key="bus_route",
        translation_placeholders={"stop": node_name, "route": route_no},
        parent_device_id=parent_device_id,
    )


def seoul_bus_route_device(ars_id: str, stop_name: str, route_id: str, route_no: str,
                           parent_device_id: str) -> ChildDeviceInfo:
    """One child device per (Seoul stop, route); both arrival sensors live under it."""
    return ChildDeviceInfo(
        identifiers={(DOMAIN, f"seoul_bus_{ars_id}_{route_id}")},
        translation_key="bus_route",
        translation_placeholders={"stop": stop_name, "route": route_no},
        parent_device_id=parent_device_id,
    )


def intercity_bus_route_device(dep_name: str, arr_name: str, grade_key: str,
                               parent_device_id: str) -> ChildDeviceInfo:
    """One child device per (구간, 등급); both departure sensors live under it.

    Keyed by terminal *names*, not IDs — a route can resolve to more than
    one underlying (system, terminal-id) combination (see
    IntercityBusCoordinator). grade_key is "source:gradeNm" — 고속버스/
    시외버스 stay distinguishable in the device name since they're booked
    on different platforms, even though search doesn't ask the user to
    pick one.
    """
    source, grade = grade_key.split(":", 1)
    express = source == "express"
    return ChildDeviceInfo(
        identifiers={(DOMAIN, f"intercity_bus_{dep_name}_{arr_name}_{grade_key}")},
        # 고속/시외 is a fixed pair, so it gets its own key rather than a
        # placeholder — a placeholder value would stay Korean.
        translation_key="express_bus_route" if express else "intercity_bus_route",
        translation_placeholders={"departure": dep_name, "arrival": arr_name,
                                  "grade": grade},
        parent_device_id=parent_device_id,
    )
