"""Shared pharmacy region device info."""
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from ..const import DOMAIN


def pharmacy_region_device(q0: str, q1: str) -> DeviceInfo:
    label = q1 if q1 else q0
    return DeviceInfo(identifiers={(DOMAIN, f"pharmacy_{q0}_{q1}")},
                      name=f"약국 - {label}", manufacturer="건강보험심사평가원",
                      model="약국 운영정보", entry_type=DeviceEntryType.SERVICE)
