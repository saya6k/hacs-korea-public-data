from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from ..const import DOMAIN

def safety_alert_device(area_code, area_name):
    return DeviceInfo(
        identifiers={(DOMAIN, f"safety_alert_{area_code}")},
        name=f"안전알림 - {area_name}",
        manufacturer="행정안전부", model="안전알림서비스",
        entry_type=DeviceEntryType.SERVICE,
    )
