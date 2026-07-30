from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from custom_components.kr_public_data.const import DOMAIN


def school_device(data: dict) -> DeviceInfo:
    """Device per school. Name = school name."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"school_{data['region_code']}_{data['school_code']}")},
        name=data.get("school_name", "학교"),
        manufacturer="NEIS",
        model="학교정보",
        entry_type=dr.DeviceEntryType.SERVICE,
    )
