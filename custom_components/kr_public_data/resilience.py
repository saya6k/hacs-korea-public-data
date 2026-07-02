"""Stale-tolerant coordinator base shared by every service.

Generalizes the pattern proven in disaster/coordinator.py: transient API
blips serve stale data instead of flipping entities unavailable, but
sustained failure is surfaced honestly via UpdateFailed. Subclasses
implement _fetch() and set stale_tolerance to match how fast their data
goes stale (arrival times: low, daily bills: high).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .exceptions import KrAuthError, KrQuotaError
from .utils import TZ_ASIA_SEOUL

_LOGGER = logging.getLogger(__name__)


def _next_midnight_kst() -> datetime:
    now = dt_util.utcnow().astimezone(TZ_ASIA_SEOUL)
    return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


class ResilientCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator with stale-keep, quota pause, and reauth mapping."""

    # Consecutive failures to tolerate (serving stale data) before the
    # coordinator reports UpdateFailed and entities go unavailable.
    stale_tolerance: int = 3

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._consecutive_failures = 0
        self._quota_blocked_until: datetime | None = None
        self._quota_issue_active = False
        self.last_success_time: datetime | None = None

    async def _fetch(self):
        """Fetch fresh data. Subclasses must implement.

        Raise KrAuthError for credential/key problems, KrQuotaError when the
        daily quota is exhausted; any other exception is treated as transient.
        """
        raise NotImplementedError

    async def _async_update_data(self):
        if self._quota_blocked_until:
            if dt_util.utcnow().astimezone(TZ_ASIA_SEOUL) < self._quota_blocked_until:
                return self._stale_or_fail("daily quota exhausted")
            self._quota_blocked_until = None

        try:
            data = await self._fetch()
        except KrAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except KrQuotaError as err:
            self._quota_blocked_until = _next_midnight_kst()
            _LOGGER.warning(
                "%s: daily API quota exceeded, pausing polls until %s: %s",
                self.name, self._quota_blocked_until, err)
            self._set_quota_issue(True)
            return self._stale_or_fail(str(err))
        except Exception as err:
            self._consecutive_failures += 1
            if self.data is not None and self._consecutive_failures <= self.stale_tolerance:
                _LOGGER.warning(
                    "%s: transient API error (%d/%d), serving stale data: %s",
                    self.name, self._consecutive_failures, self.stale_tolerance, err)
                return self.data
            raise UpdateFailed(f"{self.name}: {err}") from err

        self._consecutive_failures = 0
        self.last_success_time = dt_util.utcnow()
        self._set_quota_issue(False)
        return data

    def _set_quota_issue(self, active: bool) -> None:
        if active == self._quota_issue_active:
            return
        self._quota_issue_active = active
        issue_id = f"quota_exceeded_{self.name}"
        if active:
            ir.async_create_issue(
                self.hass, DOMAIN, issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="quota_exceeded",
                translation_placeholders={"name": self.name},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def _stale_or_fail(self, reason: str):
        if self.data is not None:
            return self.data
        raise UpdateFailed(f"{self.name}: {reason}")


async def async_first_refresh_all(coordinators: list[DataUpdateCoordinator],
                                  entry_name: str) -> None:
    """Parallel first refresh for multi-coordinator entries.

    Raises ConfigEntryNotReady only when every coordinator failed, so one
    dead station/region doesn't block the whole entry; stragglers recover
    on their regular schedule.
    """
    if not coordinators:
        return
    await asyncio.gather(*(c.async_refresh() for c in coordinators))
    if not any(c.last_update_success for c in coordinators):
        raise ConfigEntryNotReady(f"{entry_name}: all initial fetches failed")
    for c in coordinators:
        if not c.last_update_success:
            _LOGGER.warning("%s: initial fetch failed; will retry on schedule", c.name)
