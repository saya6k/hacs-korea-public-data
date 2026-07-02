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
