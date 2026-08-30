"""정류장 단위 센서 - 허브 디바이스에 붙는 유일한 엔티티.

노선별 도착 센서는 자식 디바이스에 있고, 이건 정류장 전체를 한 눈에
보는 용도다. TAGO(`city_coordinator`)와 서울(`seoul_coordinator`)은
coordinator.data 모양이 달라서 `seoul` 플래그로 갈라 읽는다.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.kr_public_data.const import DOMAIN

if TYPE_CHECKING:
    from .city_coordinator import CityBusCoordinator
    from .seoul_coordinator import SeoulBusCoordinator


class BusStopRouteSensor(CoordinatorEntity, SensorEntity):
    """지금 도착정보가 잡히는 노선 수 + 그 노선 번호들."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:bus-multiple"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "bus_stop_routes"

    def __init__(self, coordinator: CityBusCoordinator | SeoulBusCoordinator,
                 stop_key: str, routes: list[dict],
                 device_info: DeviceInfo, *, seoul: bool) -> None:
        super().__init__(coordinator)
        self._routes = routes
        self._seoul = seoul
        self._attr_unique_id = f"{DOMAIN}_{stop_key}_routes"
        self._attr_device_info = device_info

    def _running(self) -> list[str]:
        """도착 데이터가 실제로 있는 노선의 번호. 막차 이후에는 빈 리스트다."""
        data = self.coordinator.data or {}
        out = []
        for route in self._routes:
            item = data.get(route["routeId"])
            # TAGO는 노선당 도착 리스트, 서울은 단일 dict(vehId1이 있어야 유효).
            running = bool(item and item.get("vehId1")) if self._seoul else bool(item)
            if running:
                out.append(route["routeNo"])
        return sorted(out)

    @property
    def native_value(self) -> int:
        return len(self._running())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "routes": self._running(),
            "all_routes": sorted(r["routeNo"] for r in self._routes),
        }
