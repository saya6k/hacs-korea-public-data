# `airkorea` (에어코리아 - 대기질)

Shares the same 공공데이터포털 service key as `kma_weather` — the config flow lets a user reuse one key across multiple regions/stations, don't ask for it twice.

Regions are subentries, single coordinator per entry (like `disaster`): `station` subentries hold `{"sido", "stationName"}`, picked from the built-in `STATIONS_BY_SIDO` table. `__init__.py` rebuilds the coordinator's station list from `entry.subentries` and stores a `station_subs` map; `sensor.py`/`binary_sensor.py`/`event.py`/`calendar.py` register each subentry's entities with `config_subentry_id`. Legacy entries (`stations` list in entry data, no subentries) still load through a fallback path — don't remove it.

`StationSubentryFlowHandler` (subentry_type `station`) picks 시도 then station from `STATIONS_BY_SIDO`.
