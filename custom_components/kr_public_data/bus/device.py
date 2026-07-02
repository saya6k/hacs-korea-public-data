"""City bus device helpers."""
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from ..const import DOMAIN


def city_bus_route_device(node_id: str, node_name: str, route_id: str, route_no) -> DeviceInfo:
    """One device per (stop, route); both arrival sensors live under it."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"city_bus_{node_id}_{route_id}")},
        name=f"버스 - {node_name} {route_no}번",
        manufacturer="국토교통부(TAGO)", model="시내버스 도착정보",
        entry_type=DeviceEntryType.SERVICE,
    )


def seoul_bus_route_device(ars_id: str, stop_name: str, route_id: str, route_no) -> DeviceInfo:
    """One device per (Seoul stop, route); both arrival sensors live under it."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"seoul_bus_{ars_id}_{route_id}")},
        name=f"버스 - {stop_name} {route_no}번",
        manufacturer="서울시 TOPIS", model="서울 버스 도착정보",
        entry_type=DeviceEntryType.SERVICE,
    )


def intercity_bus_route_device(dep_name: str, arr_name: str, grade_key: str) -> DeviceInfo:
    """One device per (구간, 등급); both departure sensors live under it.

    Keyed by terminal *names*, not IDs — a route can resolve to more than
    one underlying (system, terminal-id) combination (see
    IntercityBusCoordinator). grade_key is "source:gradeNm" — 고속버스/
    시외버스 stay distinguishable in the device name since they're booked
    on different platforms, even though search doesn't ask the user to
    pick one.
    """
    source, grade = grade_key.split(":", 1)
    label = "고속버스" if source == "express" else "시외버스"
    return DeviceInfo(
        identifiers={(DOMAIN, f"intercity_bus_{dep_name}_{arr_name}_{grade_key}")},
        name=f"{label} - {dep_name}→{arr_name} {grade}",
        manufacturer="국토교통부(TAGO)", model=f"{label} 배차정보",
        entry_type=DeviceEntryType.SERVICE,
    )
