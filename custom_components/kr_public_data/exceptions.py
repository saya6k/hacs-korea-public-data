"""Shared exception hierarchy for API error classification.

Coordinators (see resilience.py) map these onto HA behavior:
KrAuthError → reauth flow, KrQuotaError → poll pause until midnight KST,
KrTransientError / anything else → stale-keep with tolerance.
"""
from __future__ import annotations


class KrApiError(Exception):
    """Base error for all kr_public_data API failures."""


class KrAuthError(KrApiError):
    """Credentials or service key rejected — needs user action."""


class KrQuotaError(KrApiError):
    """Daily request quota exceeded — resets at midnight KST."""


class KrTransientError(KrApiError):
    """Intermittent failure (TLS reset, timeout, 5xx, bad payload)."""


def raise_for_result_code(code: str | None, msg: str = "") -> None:
    """Map 공공데이터포털 standard result codes to typed errors.

    22 = LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS (daily quota),
    30/31/32 = service key unregistered / expired / wrong domain.
    Anything else (including 00/03) is left to the caller.
    """
    if code == "22":
        raise KrQuotaError(f"daily quota exceeded: {msg}")
    if code in ("30", "31", "32"):
        raise KrAuthError(f"service key rejected (code {code}): {msg}")
