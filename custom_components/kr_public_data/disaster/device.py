from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from custom_components.kr_public_data.const import DOMAIN


def disaster_device(region: str = "") -> DeviceInfo:
    label = f"재난문자 - {region}" if region else "재난문자"
    did = f"disaster_{region}" if region else "disaster"
    return DeviceInfo(identifiers={(DOMAIN, did)}, name=label,
                      manufacturer="행정안전부", model="재난안전데이터",
                      entry_type=DeviceEntryType.SERVICE)

def region_label(region: str = "", sido: str = "", sgg: str = "") -> str:
    """sido+sgg: subentry region label ('시도 시군구' or '시도 전체'). Else legacy region."""
    if sido:
        return f"{sido} {sgg}" if sgg else f"{sido} 전체"
    return region
