"""School sensors (lunch + info)."""
from datetime import date
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from ..const import DOMAIN
from .device import school_device

class SchoolLunchSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:food"
    _attr_has_entity_name = True
    _attr_translation_key = "school_lunch"
    def __init__(self, coordinator, data):
        super().__init__(coordinator)
        self.data_source = data
        rc = data["region_code"]
        sc = data["school_code"]
        self._attr_unique_id = f"{DOMAIN}_lunch_{rc}_{sc}"
        self._attr_device_info = school_device(data)
    @property
    def native_value(self):
        lunch = (self.coordinator.data or {}).get("lunch", {}).get(date.today().isoformat())
        return ", ".join(lunch["menu"]) if lunch else "급식 없음"
    @property
    def extra_state_attributes(self):
        lunch = (self.coordinator.data or {}).get("lunch", {}).get(date.today().isoformat(), {})
        return {k: lunch.get(k) for k in ("menu", "calorie", "allergy_codes") if lunch.get(k)}

class SchoolInfoSensor(CoordinatorEntity, SensorEntity):
    _attr_icon = "mdi:school"
    _attr_has_entity_name = True
    _attr_translation_key = "school_info"
    def __init__(self, coordinator, data):
        super().__init__(coordinator)
        self.data_source = data
        rc = data["region_code"]
        sc = data["school_code"]
        self._attr_unique_id = f"{DOMAIN}_info_{rc}_{sc}"
        self._attr_device_info = school_device(data)
    @property
    def native_value(self):
        return self.data_source.get("school_name", "")
    @property
    def extra_state_attributes(self):
        d = self.data_source
        return {
            "school_name": d.get("school_name", ""),
            "grade_classes": d.get("grade_classes", []),
            "address": d.get("address", ""),
            "phone": d.get("phone", ""),
        }
