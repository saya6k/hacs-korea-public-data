"""노선 운행 여부 - 각 노선/등급 자식 디바이스에 붙는다.

도착·배차 센서는 "다음 차가 언제"를 보여주지만 막차가 끊기면 그냥 None이
되어, 자동화에서 "차가 아직 다니는가"를 묻기 어렵다. 이 binary_sensor가
그 질문에 답한다: 코디네이터가 이번 갱신에서 받아온 데이터에 차량이 있으면
on, 없으면(= 막차 종료) off. API 자체가 실패하면 CoordinatorEntity가
unavailable로 만들어 주므로, off는 "받아왔는데 차가 없다"만을 뜻한다.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.device_registry import ChildDeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.kr_public_data.const import DOMAIN

if TYPE_CHECKING:
    from .city_coordinator import CityBusCoordinator
    from .intercity_coordinator import IntercityBusCoordinator
    from .seoul_coordinator import SeoulBusCoordinator


class BusRouteRunningBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """이 정류장에서 해당 노선이 지금 운행 중인가."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "bus_route_running"

    def __init__(self, coordinator: CityBusCoordinator | SeoulBusCoordinator,
                 stop_key: str, route_id: str, device_info: ChildDeviceInfo, *,
                 seoul: bool) -> None:
        super().__init__(coordinator)
        self._route_id = route_id
        self._seoul = seoul
        self._attr_unique_id = f"{DOMAIN}_{stop_key}_{route_id}_running"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool:
        item = (self.coordinator.data or {}).get(self._route_id)
        # TAGO는 노선당 도착 리스트, 서울은 단일 dict(vehId1이 있어야 유효).
        if self._seoul:
            return bool(item and item.get("vehId1"))
        return bool(item)


class IntercityBusGradeRunningBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """이 구간의 해당 등급에 남은 배차가 있는가."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "intercity_bus_grade_running"

    def __init__(self, coordinator: IntercityBusCoordinator, section_key: str,
                 grade_key: str, device_info: ChildDeviceInfo) -> None:
        super().__init__(coordinator)
        self._grade_key = grade_key
        self._attr_unique_id = f"{DOMAIN}_{section_key}_{grade_key}_running"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data or {}).get(self._grade_key))
