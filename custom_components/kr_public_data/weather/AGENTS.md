# `weather` (기상특보 - ENTRY_WEATHER / `weather_warning`)

This sub-package implements the `weather_warning` entry type (const `ENTRY_WEATHER`) — the alert/특보 stream (event entities). It is *not* the forecast; that's `kma_weather` (see `../kma_weather/AGENTS.md`), an independent config entry.

Regions are subentries, single coordinator per entry (like `disaster`): `area` subentries hold `{"area_code"}` from `weather/AREA_CODES`. `__init__.py` rebuilds the coordinator's area-code list from `entry.subentries` and stores an `areas` map; platform shims register each subentry's entities with `config_subentry_id`. Legacy entries (`area_codes` list in entry data, no subentries) still load through a fallback path — don't remove it.

`WarningAreaSubentryFlowHandler` (subentry_type `area`) picks one area from `AREA_CODES`.
