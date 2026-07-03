# `kma_weather` (기상청 날씨예보)

Shares the same 공공데이터포털 service key as `airkorea` — the config flow lets a user reuse one key across multiple regions/stations.

`kma_weather` is the *forecast* stream (one `weather` entity); `weather_warning` (sub-package `weather/`, see `../weather/AGENTS.md`) is the alert/특보 stream (event entities). They are independent config entries — don't conflate them when debugging.

Regions are subentries, single coordinator per entry (like `disaster`): `region` subentries hold `{"sido", "name", "nx", "ny"}` from the built-in `SIDO_LIST`. `region` is a subentry_type string shared with `disaster`'s region flow (and, historically, `pharmacy`'s before it moved off subentries) — if you touch `config_subentries.region` translations, make sure the change still makes sense for whichever entry types still use it. `__init__.py` rebuilds the coordinator's region list from `entry.subentries` and stores a `region_subs` map; platform shims register each subentry's entities with `config_subentry_id`. Legacy entries (`regions` list in entry data, no subentries) still load through a fallback path — don't remove it.

`KmaRegionSubentryFlowHandler` picks 시도 then a named point from `SIDO_LIST` (which also carries the `nx`/`ny` grid coordinates KMA's grid-forecast API needs).
