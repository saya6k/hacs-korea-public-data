"""GasApp sensors."""
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from ..const import DOMAIN
from ..utils import get_value_from_path

def gasapp_device(contract_num):
    return DeviceInfo(identifiers={(DOMAIN, f"gasapp_{contract_num}")},
                      name=f"가스앱 ({contract_num})", manufacturer="한국가스공사",
                      model="가스앱", entry_type=DeviceEntryType.SERVICE)

class GasAppSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator, contract_num, data_key, path, name,
                 unit=None, icon=None, state_class=None):
        super().__init__(coordinator)
        self._data_key = data_key
        self._path = path
        self._attr_unique_id = f"{DOMAIN}_gasapp_{contract_num}_{path}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon or "mdi:gas-burner"
        self._attr_state_class = state_class
        self._attr_device_info = gasapp_device(contract_num)

    @property
    def native_value(self):
        data = (self.coordinator.data or {}).get(self._data_key, {})
        return get_value_from_path(data, self._path)
