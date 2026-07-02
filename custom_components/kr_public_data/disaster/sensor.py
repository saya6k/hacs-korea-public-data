"""Disaster sensors + event entity."""
from __future__ import annotations
from typing import Any
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.event import EventEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import callback
from ..const import DOMAIN
from .device import disaster_device, region_label
from .coordinator import DisasterCoordinator, filter_messages


class DisasterRegionEntity(CoordinatorEntity[DisasterCoordinator]):
    """Shared region filtering. region=legacy substring, sido+sgg=subentry."""
    _attr_has_entity_name = True

    def __init__(self, coordinator, region="", sido="", sgg=""):
        super().__init__(coordinator)
        self._region = region
        self._sido = sido
        self._sgg = sgg
        label = region_label(region, sido, sgg)
        self._label = label
        self._suffix = f"_{label}" if label else ""
        self._attr_device_info = disaster_device(label)

    @property
    def _messages(self):
        return filter_messages(self.coordinator.data or [],
                               self._sido, self._sgg, self._region)


class DisasterMessageSensor(DisasterRegionEntity, SensorEntity):
    _attr_icon = "mdi:alert-octagram"
    def __init__(self, coordinator, region="", sido="", sgg=""):
        super().__init__(coordinator, region, sido, sgg)
        self._attr_unique_id = f"{DOMAIN}_disaster_latest{self._suffix}"
        self._attr_name = "최신 재난문자"
    @property
    def native_value(self):
        msgs = self._messages
        if not msgs:
            return "없음"
        return msgs[0].get("message", "")[:255]
    @property
    def extra_state_attributes(self):
        msgs = self._messages
        if not msgs:
            return {}
        d = msgs[0]
        return {k: d.get(k, "") for k in ("level","area","disaster_type") if d.get(k)}

class DisasterCountSensor(DisasterRegionEntity, SensorEntity):
    _attr_icon = "mdi:counter"
    def __init__(self, coordinator, region="", sido="", sgg=""):
        super().__init__(coordinator, region, sido, sgg)
        self._attr_unique_id = f"{DOMAIN}_disaster_count{self._suffix}"
        self._attr_name = "재난문자 수"
    @property
    def native_value(self):
        return len(self._messages)

class DisasterEvent(DisasterRegionEntity, EventEntity):
    _attr_event_types = ["emergency", "urgent", "safety", "disaster_info"]
    _attr_icon = "mdi:alert-circle"
    def __init__(self, coordinator, region="", sido="", sgg=""):
        super().__init__(coordinator, region, sido, sgg)
        self._attr_unique_id = f"{DOMAIN}_disaster_event{self._suffix}"
        self._attr_name = "재난문자 이벤트"
        self._last_id = None

    @callback
    def _handle_coordinator_update(self):
        data = self._messages
        if not data:
            return
        latest = data[0]
        msg_id = latest.get("create_date", "")
        if self._last_id is not None and msg_id and msg_id != self._last_id:
            # 재난문자 등급: 위급재난문자 > 긴급재난문자 > 안전안내문자
            level = (latest.get("level") or "").strip()
            dtype = latest.get("disaster_type") or ""
            if "위급" in level:
                event_type = "emergency"
            elif "긴급" in level:
                event_type = "urgent"
            elif "안전" in level or "안전" in dtype:
                event_type = "safety"
            else:
                event_type = "disaster_info"
            self._trigger_event(event_type, {
                "message": latest.get("message", ""),
                "area": latest.get("area", ""),
                "level": level,
                "disaster_type": dtype,
                "date": str(latest.get("create_date", "")),
            })
        self._last_id = msg_id
        self.async_write_ha_state()
