"""KEPCO sensors."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.kr_public_data.const import DOMAIN
from custom_components.kr_public_data.utils import get_value_from_path

if TYPE_CHECKING:
    from .coordinator import KepcoCoordinator


def kepco_device(username: str) -> DeviceInfo:
    return DeviceInfo(identifiers={(DOMAIN, f"kepco_{username}")},
                      translation_key="kepco",
                      translation_placeholders={"username": username},
                      manufacturer="한국전력공사",
                      model="KEPCO", entry_type=DeviceEntryType.SERVICE)

class KepcoSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator: KepcoCoordinator, username: str, data_key: str, path: str,
                 translation_key: str, device_class: SensorDeviceClass | None = None,
                 state_class: SensorStateClass | None = None, unit: str | None = None,
                 icon: str | None = None) -> None:
        super().__init__(coordinator)
        self._data_key = data_key
        self._path = path
        self._attr_unique_id = f"{DOMAIN}_kepco_{username}_{path}"
        self._attr_translation_key = translation_key
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon or "mdi:flash"
        self._attr_device_info = kepco_device(username)

    @property
    def native_value(self) -> Any:
        data = (self.coordinator.data or {}).get(self._data_key, {})
        return get_value_from_path(data, self._path)
