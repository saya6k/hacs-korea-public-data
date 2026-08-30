"""Shared pharmacy region device info."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from custom_components.kr_public_data.const import DOMAIN


def pharmacy_region_device(q0: str, q1: str) -> DeviceInfo:
    label = q1 if q1 else q0
    return DeviceInfo(identifiers={(DOMAIN, f"pharmacy_{q0}_{q1}")},
                      translation_key="pharmacy",
                      translation_placeholders={"name": label},
                      manufacturer="건강보험심사평가원",
                      model="약국 운영정보", entry_type=DeviceEntryType.SERVICE)


@callback
def pharmacy_region_device_id(hass: HomeAssistant, entry: ConfigEntry,
                              sub_id: str | None, q0: str, q1: str) -> str:
    """Register the region device up front and return its id, for use as via_device_id.

    The region device is the one PharmacySensor lives on, so the entity platform
    would create it anyway — but its id has to be known *before* the per-pharmacy
    devices that reference it are built, hence the explicit registration.
    """
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id=sub_id,
        **pharmacy_region_device(q0, q1),
    ).id


def pharmacy_device(hpid: str, name: str, via_device_id: str) -> DeviceInfo:
    """One device per individual nearby pharmacy (location + open-now 센서 묶음)."""
    return DeviceInfo(identifiers={(DOMAIN, f"pharmacy_hpid_{hpid}")},
                      translation_key="pharmacy",
                      translation_placeholders={"name": name},
                      manufacturer="건강보험심사평가원",
                      model="약국 운영정보", entry_type=DeviceEntryType.SERVICE,
                      via_device_id=via_device_id)
