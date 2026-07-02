"""Disaster geolocation entities - one per active message in a region.

Disaster messages (재난문자) only carry a text area name, no coordinates, so
each entity is placed at its 시도's approximate centroid rather than the
precise incident location. An entity exists for as long as its message
stays inside the coordinator's rolling fetch window; once the message ages
out, the entity is removed.
"""
from __future__ import annotations
import logging

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.core import callback

from ..const import DOMAIN
from .coordinator import DisasterCoordinator, filter_messages
from .device import disaster_device

_LOGGER = logging.getLogger(__name__)

# Approximate 시도 office coordinates - one marker per 광역자치단체.
SIDO_CENTROIDS = {
    "서울특별시": (37.5665, 126.9780),
    "부산광역시": (35.1796, 129.0756),
    "대구광역시": (35.8714, 128.6014),
    "인천광역시": (37.4563, 126.7052),
    "광주광역시": (35.1595, 126.8526),
    "대전광역시": (36.3504, 127.3845),
    "울산광역시": (35.5384, 129.3114),
    "세종특별자치시": (36.4801, 127.2890),
    "경기도": (37.4138, 127.5183),
    "강원특별자치도": (37.8228, 128.1555),
    "충청북도": (36.6357, 127.4917),
    "충청남도": (36.5184, 126.8000),
    "전북특별자치도": (35.7175, 127.1530),
    "전라남도": (34.8161, 126.4630),
    "경상북도": (36.4919, 128.8889),
    "경상남도": (35.4606, 128.2132),
    "제주특별자치도": (33.4996, 126.5312),
}


def _msg_key(label: str, message: dict) -> str:
    return f"{label}_{message.get('create_date', '')}_{(message.get('area') or '')[:30]}"


class DisasterGeoLocationManager:
    """Adds/removes one geolocation entity per active message in a region."""

    def __init__(self, coordinator: DisasterCoordinator, sido: str, sgg: str,
                 label: str, async_add_entities) -> None:
        self._coordinator = coordinator
        self._sido = sido
        self._sgg = sgg
        self._label = label
        self._add_entities = async_add_entities
        self._active: dict[str, DisasterGeoLocationEntity] = {}
        self._remove_listener = coordinator.async_add_listener(self._sync)
        self._sync()

    @callback
    def _sync(self) -> None:
        msgs = filter_messages(self._coordinator.data or [], self._sido, self._sgg)
        current_keys = {_msg_key(self._label, m) for m in msgs}
        for key in list(self._active):
            if key not in current_keys:
                stale = self._active.pop(key)
                self._coordinator.hass.async_create_task(stale.async_remove())
        new_entities = []
        for m in msgs:
            key = _msg_key(self._label, m)
            if key not in self._active:
                ent = DisasterGeoLocationEntity(m, self._sido, self._label, key)
                self._active[key] = ent
                new_entities.append(ent)
        if new_entities:
            self._add_entities(new_entities)

    def unload(self) -> None:
        self._remove_listener()


class DisasterGeoLocationEntity(GeolocationEvent):
    _attr_has_entity_name = True
    _attr_icon = "mdi:alert-octagram"
    _attr_unit_of_measurement = "km"
    _attr_source = "kr_public_data_disaster"
    _attr_should_poll = False

    def __init__(self, message: dict, sido: str, label: str, key: str) -> None:
        self._message = message
        self._attr_unique_id = f"{DOMAIN}_disaster_geo_{key}"
        self._attr_name = message.get("disaster_type") or "재난문자"
        self._attr_device_info = disaster_device(label)
        self._attr_latitude, self._attr_longitude = SIDO_CENTROIDS.get(sido, (None, None))

    @property
    def extra_state_attributes(self):
        return {
            "message": self._message.get("message", ""),
            "area": self._message.get("area", ""),
            "level": self._message.get("level", ""),
            "created_at": self._message.get("create_date", ""),
        }
