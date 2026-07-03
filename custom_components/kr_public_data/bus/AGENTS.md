# `bus` (시내/시외/고속버스 도착·배차정보)

Secret field is `api_key` (renamed from `service_key` in 4.8 — dispatch code (`entry.data.get("api_key") or entry.data.get("service_key", "")`) always tries the current name first; don't remove that fallback).

Two subentry types share the one `bus` entry, both dispatched by a `source` field rather than a separate entry type each:
- `city_bus_stop` — one 정류장 per subentry, one coordinator per stop, subscribed to every selected route at that stop. `sub.data["source"]` is `"tago"` or `"seoul"`, set by the config flow based on the chosen city, and picks `CityBusCoordinator` vs `SeoulBusCoordinator` (`ws.bus.go.kr` reuses the same TAGO `api_key` — verified live it authenticates there without a separate 활용신청).
- `intercity_bus_route` — one 구간 (출발-도착 터미널) per subentry, using `IntercityBusCoordinator`. 고속/시외버스 share this one subentry type; `sub.data["source"]` (`"express"` | `"intercity"`) distinguishes them for API purposes only.

`CityBusStopSubentryFlowHandler` and `IntercityBusRouteSubentryFlowHandler` are the two registered subentry flows for `ENTRY_BUS` (see `config_flow.py:async_get_supported_subentry_types`) — this is the one entry type with more than one subentry type, so adding a stop/route genuinely does show a type-selection step first (unlike, say, `transit`, which only has one type and skips straight to the form).
