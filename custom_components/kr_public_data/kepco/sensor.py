"""KEPCO sensors."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from ..const import DOMAIN
from ..utils import get_value_from_path

def kepco_device(username):
    return DeviceInfo(identifiers={(DOMAIN, f"kepco_{username}")},
                      name=f"한전 ({username})", manufacturer="한국전력공사",
                      model="KEPCO", entry_type=DeviceEntryType.SERVICE)

class KepcoSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator, username, data_key, path, name,
                 device_class=None, state_class=None, unit=None, icon=None):
        super().__init__(coordinator)
        self._data_key = data_key
        self._path = path
        self._attr_unique_id = f"{DOMAIN}_kepco_{username}_{path}"
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon or "mdi:flash"
        self._attr_device_info = kepco_device(username)

    @property
    def native_value(self):
        data = (self.coordinator.data or {}).get(self._data_key, {})
        return get_value_from_path(data, self._path)
