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
