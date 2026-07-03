# `weather` (기상특보 - ENTRY_WEATHER / `weather_warning`)

This sub-package implements the `weather_warning` entry type (const `ENTRY_WEATHER`) — the alert/특보 stream (event entities). It is *not* the forecast; that's `kma_weather` (see `../kma_weather/AGENTS.md`), an independent config entry.

Regions are subentries, single coordinator per entry (like `disaster`): `area` subentries hold `{"area_code"}` from `weather/AREA_CODES`. `__init__.py` rebuilds the coordinator's area-code list from `entry.subentries` and stores an `areas` map; platform shims register each subentry's entities with `config_subentry_id`. Legacy entries (`area_codes` list in entry data, no subentries) still load through a fallback path — don't remove it.

`WarningAreaSubentryFlowHandler` (subentry_type `area`) picks one area from `AREA_CODES`.

Legacy (pre-subentry) entries expose their flat `area_codes` list for editing on the plain options-flow screen (unlike `area` subentries, which have no reconfigure step and can only be removed/re-added). Shrinking that list isn't a subentry deletion, so it isn't covered by Home Assistant's native per-subentry cleanup. `weather/cleanup.py:async_cleanup_stale_weather_entities()` runs at the end of every `ENTRY_WEATHER` setup (called from `__init__.py`, after `area_codes` is resolved) and removes any entity/device for an area code no longer in that list. It diffs the *entire* entry's registered entities against the forward-built expected id set rather than pattern-matching unique_ids — safe here (unlike `pharmacy`/`fuel`) because every entity under a `weather_warning` entry belongs to some area code; there's no other entity kind mixed in that a naive full-entry diff would wrongly catch.
