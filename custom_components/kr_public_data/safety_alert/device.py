from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from custom_components.kr_public_data.const import DOMAIN


def safety_alert_device(area_code: str, area_name: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"safety_alert_{area_code}")},
        translation_key="safety_alert",
        translation_placeholders={"area": area_name},
        manufacturer="행정안전부", model="안전알림서비스",
        entry_type=DeviceEntryType.SERVICE,
    )
