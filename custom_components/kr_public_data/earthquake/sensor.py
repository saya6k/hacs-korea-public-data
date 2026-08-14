"""Earthquake sensors + geolocation + event."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.event import EventEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.kr_public_data.const import DOMAIN

from .api import haversine_km

if TYPE_CHECKING:
    from .coordinator import EarthquakeCoordinator


def eq_device() -> DeviceInfo:
    return DeviceInfo(identifiers={(DOMAIN, "earthquake")},
                      translation_key="earthquake", manufacturer="기상청",
                      model="지진정보", entry_type=DeviceEntryType.SERVICE)

class EarthquakeEvent(CoordinatorEntity, EventEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "earthquake_alert"
    _attr_event_types = ["earthquake_alert"]  # noqa: RUF012  HA entity-attribute convention; the base class owns the name
    _attr_icon = "mdi:earth-arrow-down"
    def __init__(self, coordinator: EarthquakeCoordinator, home_lat: float, home_lon: float,
                 radius_km: float, min_mag: float) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_earthquake_event"
        self._attr_device_info = eq_device()
        self._home_lat = home_lat
        self._home_lon = home_lon
        self._radius = radius_km
        self._min_mag = min_mag
        self._last_dt = None

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data or []
        for eq in data:
            lat = eq.get("latitude")
            lon = eq.get("longitude")
            mag = eq.get("magnitude") or 0
            dt = eq.get("datetime", "")
            if not lat or not lon or not dt:
                continue
            dist = haversine_km(self._home_lat, self._home_lon, lat, lon)
            if dist <= self._radius and mag >= self._min_mag:
                if self._last_dt is not None and dt != self._last_dt:
                    self._trigger_event("earthquake_alert", {
                        "magnitude": mag, "location": eq.get("location",""),
                        "distance_km": round(dist, 1), "datetime": dt,
                        "depth": eq.get("depth",""),
                    })
                self._last_dt = dt
                break
        self.async_write_ha_state()
