"""호선 운행 여부 - 각 (역, 호선) 자식 디바이스에 붙는다.

도착 센서는 열차가 끊기면 None이 되어 "아직 다니는가"를 묻기 어렵다.
한 호선은 방향별 키(`{direction}_{line_id}`)로 나뉘어 들어오므로, 어느
방향이든 도착 데이터가 있으면 운행 중으로 본다. API 실패는 CoordinatorEntity가
unavailable로 처리하므로 off는 "받아왔는데 열차가 없다"만을 뜻한다.
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

from . import line_directions

if TYPE_CHECKING:
    from .subway_coordinator import SubwayCoordinator


class SubwayLineRunningBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """이 역에서 해당 호선이 지금 운행 중인가."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "subway_line_running"

    def __init__(self, coordinator: SubwayCoordinator, station: str, line_id: str,
                 device_info: ChildDeviceInfo) -> None:
        super().__init__(coordinator)
        self._line_id = line_id
        self._attr_unique_id = f"{DOMAIN}_subway_{station}_{line_id}_running"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data or {}
        return any(data.get(f"{d}_{self._line_id}") for d in line_directions(self._line_id))
