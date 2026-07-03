"""Pharmacy sensor - counts open pharmacies."""
from __future__ import annotations
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.location import distance
from ..const import DOMAIN
from .device import pharmacy_region_device


def pharmacies_within_radius(pharmacies, home_lat, home_lon, radius_m):
    """약국 목록 중 (home_lat, home_lon) 기준 radius_m(미터) 이내만 반환."""
    nearby = []
    for p in pharmacies or []:
        try:
            lat, lon = float(p["lat"]), float(p["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        d = distance(home_lat, home_lon, lat, lon)
        if d is not None and d <= radius_m:
            nearby.append(p)
    return nearby


def region_nearby_pharmacies(hass, region: dict, coord):
    """region["location"](지도에서 직접 찍은 위치) 우선, 없으면(레거시 엔트리)
    zone.home(hass.config 좌표) + 예전 flat radius로 폴백해 반경 내 약국 목록을 구한다."""
    loc = region.get("location") or {}
    home_lat = loc.get("latitude", hass.config.latitude)
    home_lon = loc.get("longitude", hass.config.longitude)
    radius = loc.get("radius", region.get("radius", 1000))
    return pharmacies_within_radius(coord.data, home_lat, home_lon, radius)

class PharmacySensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:pharmacy"
    _attr_state_class = SensorStateClass.MEASUREMENT
    def __init__(self, coordinator, q0, q1):
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_pharmacy_{q0}_{q1}"
        self._attr_name = "운영 약국 수"
        self._attr_device_info = pharmacy_region_device(q0, q1)
    @property
    def native_value(self):
        return len(self.coordinator.data or [])


class PharmacyLocationSensor(CoordinatorEntity, SensorEntity):
    """개별 약국 위치 - latitude/longitude 속성으로 지도 카드에 핀 표시.

    약국(hpid)마다 별도 디바이스(pharmacy_device)를 갖는다.
    """
    _attr_has_entity_name = True
    _attr_icon = "mdi:map-marker"

    def __init__(self, coordinator, hpid, name, device_info):
        super().__init__(coordinator)
        self._hpid = hpid
        self._attr_unique_id = f"{DOMAIN}_pharmacy_location_{hpid}"
        self._attr_name = f"{name} 위치"
        self._attr_device_info = device_info

    def _find(self):
        for item in self.coordinator.data or []:
            if item.get("hpid") == self._hpid:
                return item
        return None

    @property
    def native_value(self):
        item = self._find()
        return item.get("address") if item else None

    @property
    def extra_state_attributes(self):
        item = self._find()
        if not item:
            return {}
        attrs = {"phone": item.get("phone", "")}
        try:
            attrs["latitude"] = float(item["lat"])
            attrs["longitude"] = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            pass
        return attrs
