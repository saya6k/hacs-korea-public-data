"""Safety alert: binary_sensor + event + text sensor."""
from __future__ import annotations
from typing import Any
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.components.event import EventEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import callback
from ..const import DOMAIN
from .coordinator import SafetyAlertCoordinator
from .device import safety_alert_device


class SafetyAlertBinarySensor(CoordinatorEntity[SafetyAlertCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_icon = "mdi:alert"

    def __init__(self, coordinator, area_code, area_name):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_safety_{area_code}"
        self._attr_name = "알림 상태"
        self._attr_device_info = safety_alert_device(area_code, area_name)

    @property
    def is_on(self):
        return (self.coordinator.data or {}).get("has_data", False)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        return {"count": data.get("count", 0)}


class SafetyAlertTextSensor(CoordinatorEntity[SafetyAlertCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:message-alert"

    def __init__(self, coordinator, area_code, area_name):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_safety_text_{area_code}"
        self._attr_name = "최신 알림"
        self._attr_device_info = safety_alert_device(area_code, area_name)

    @property
    def native_value(self):
        alerts = (self.coordinator.data or {}).get("alerts", [])
        if not alerts:
            return "알림 없음"
        return alerts[0].get("MSG_CN", "")[:255]

    @property
    def extra_state_attributes(self):
        alerts = (self.coordinator.data or {}).get("alerts", [])
        if not alerts:
            return {}
        a = alerts[0]
        attrs: dict[str, Any] = {
            "area": a.get("RCV_AREA_NM", ""),
            "date": a.get("CRT_DT", ""),
            "type": a.get("DST_SE_NM", ""),
            "level": a.get("EMRG_STEP_NM", "") or a.get("MSG_SE_NM", ""),
        }
        if len(alerts) > 1:
            attrs["recent"] = [
                {"message": al.get("MSG_CN", "")[:100],
                 "area": al.get("RCV_AREA_NM", ""),
                 "date": al.get("CRT_DT", ""),
                 "type": al.get("DST_SE_NM", ""),
                 "level": al.get("EMRG_STEP_NM", "") or al.get("MSG_SE_NM", "")}
                for al in alerts[:10]
            ]
        return attrs


class SafetyAlertEvent(CoordinatorEntity[SafetyAlertCoordinator], EventEntity):
    _attr_has_entity_name = True
    _attr_event_types = ["safety_alert"]
    _attr_icon = "mdi:alert-circle"

    def __init__(self, coordinator, area_code, area_name):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_safety_event_{area_code}"
        self._attr_name = "알림 이벤트"
        self._attr_device_info = safety_alert_device(area_code, area_name)
        self._last_id = None

    @callback
    def _handle_coordinator_update(self):
        alerts = (self.coordinator.data or {}).get("alerts", [])
        if not alerts:
            return
        latest = alerts[0]
        msg_id = latest.get("MD101_SN", "") or latest.get("CRT_DT", "")
        if self._last_id is not None and msg_id != self._last_id:
            self._trigger_event("safety_alert", {
                "message": latest.get("MSG_CN", ""),
                "area": latest.get("RCV_AREA_NM", ""),
                "date": latest.get("CRT_DT", ""),
                "type": latest.get("DST_SE_NM", ""),
                "level": latest.get("EMRG_STEP_NM", "") or latest.get("MSG_SE_NM", ""),
            })
        self._last_id = msg_id
        self.async_write_ha_state()


class SafetyAlertCountSensor(CoordinatorEntity[SafetyAlertCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator, area_code, area_name):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_safety_count_{area_code}"
        self._attr_name = "활성 알림 수"
        self._attr_device_info = safety_alert_device(area_code, area_name)

    @property
    def native_value(self):
        return (self.coordinator.data or {}).get("count", 0)
