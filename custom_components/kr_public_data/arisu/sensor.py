"""Arisu sensors."""
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from ..const import DOMAIN

def arisu_device(customer_number):
    return DeviceInfo(identifiers={(DOMAIN, f"arisu_{customer_number}")},
                      name=f"아리수 ({customer_number})", manufacturer="서울시",
                      model="아리수 상수도", entry_type=DeviceEntryType.SERVICE)

class ArisuSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:water"
    def __init__(self, coordinator, customer_number, name, key, unit=None, state_class=None):
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{DOMAIN}_arisu_{customer_number}_{key}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_device_info = arisu_device(customer_number)

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        if self._key == "total_amount":
            return data.get("total_amount", 0)
        elif self._key == "current_usage":
            return data.get("usage_info", {}).get("current_usage")
        elif self._key == "billing_month":
            return data.get("billing_month")
        return None

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        if self._key == "total_amount":
            return {
                "billing_month": data.get("billing_month", ""),
                "customer_info": data.get("customer_info", {}),
                "arrears_info": data.get("arrears_info", {}),
            }
        return {}
