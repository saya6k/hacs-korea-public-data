"""Pharmacy open-now binary sensor."""
from __future__ import annotations
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from ..const import DOMAIN

_DAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]  # datetime.weekday() 순서


def _parse_hhmm(s: str) -> int | None:
    """'0900' -> 540(분). 형식이 아니면 None."""
    if not s or len(s) != 4 or not s.isdigit():
        return None
    return int(s[:2]) * 60 + int(s[2:])


def is_pharmacy_open(duty_time: dict, now) -> bool:
    """오늘 요일의 dutyTime 범위("HHMM~HHMM")에 현재 시각이 들어가는지."""
    hours = duty_time.get(_DAY_NAMES[now.weekday()], "")
    if "~" not in hours:
        return False
    start_s, end_s = hours.split("~", 1)
    start, end = _parse_hhmm(start_s), _parse_hhmm(end_s)
    if start is None or end is None:
        return False
    minutes_now = now.hour * 60 + now.minute
    if end <= start:
        # 자정을 넘기는 영업시간 (예: 22:00~06:00, 또는 24시간이면 0000~2400이라 여기 안 걸림)
        return minutes_now >= start or minutes_now < end
    return start <= minutes_now < end


class PharmacyOpenBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """개별 약국의 현재 운영 여부. PharmacyLocationSensor와 같은 지역 디바이스에 묶인다."""
    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:pharmacy"

    def __init__(self, coordinator, hpid, name, device_info):
        super().__init__(coordinator)
        self._hpid = hpid
        self._attr_unique_id = f"{DOMAIN}_pharmacy_open_{hpid}"
        self._attr_name = f"{name} 운영 중"
        self._attr_device_info = device_info

    def _find(self):
        for item in self.coordinator.data or []:
            if item.get("hpid") == self._hpid:
                return item
        return None

    @property
    def is_on(self):
        item = self._find()
        if not item:
            return None
        return is_pharmacy_open(item.get("duty_time", {}), dt_util.now())
