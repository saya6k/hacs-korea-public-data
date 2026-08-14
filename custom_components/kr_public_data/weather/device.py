"""Weather device helpers."""
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from custom_components.kr_public_data.const import DOMAIN

from . import AREA_CODES


def weather_device(area_code: str) -> DeviceInfo:
    name = AREA_CODES.get(area_code, area_code)
    return DeviceInfo(
        identifiers={(DOMAIN, f"weather_{area_code}")},
        translation_key="weather_warning",
        translation_placeholders={"area": name},
        manufacturer="기상청", model="기상특보 서비스",
        entry_type=DeviceEntryType.SERVICE,
    )
