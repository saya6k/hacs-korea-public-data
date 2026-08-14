"""GasApp sensors."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.kr_public_data.const import DOMAIN
from custom_components.kr_public_data.utils import get_value_from_path

if TYPE_CHECKING:
    from .coordinator import GasAppCoordinator


def gasapp_device(contract_num: str) -> DeviceInfo:
    return DeviceInfo(identifiers={(DOMAIN, f"gasapp_{contract_num}")},
                      translation_key="gasapp",
                      translation_placeholders={"contract_number": contract_num},
                      manufacturer="한국가스공사",
                      model="가스앱", entry_type=DeviceEntryType.SERVICE)

class GasAppSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator: GasAppCoordinator, contract_num: str, data_key: str,
                 path: str, translation_key: str, unit: str | None = None,
                 icon: str | None = None,
                 state_class: SensorStateClass | None = None) -> None:
        super().__init__(coordinator)
        self._data_key = data_key
        self._path = path
        self._attr_unique_id = f"{DOMAIN}_gasapp_{contract_num}_{path}"
        self._attr_translation_key = translation_key
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon or "mdi:gas-burner"
        self._attr_state_class = state_class
        self._attr_device_info = gasapp_device(contract_num)

    @property
    def native_value(self) -> Any:
        data = (self.coordinator.data or {}).get(self._data_key, {})
        return get_value_from_path(data, self._path)
