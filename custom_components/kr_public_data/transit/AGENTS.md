# `transit` (지하철 실시간 도착정보)

Subway-only: bus arrival tracking and the 환승경로/`bus_api_key` transfer-path actions were removed in 4.6 (see `bus/AGENTS.md` for the current bus service).

- Stations are `subway_station` subentries (`{"station", "lines"}`), one `SubwayCoordinator` per station subentry.
- Entities: one device per (station, line), with 4 sensors under it — 상행/하행 (외선/내선 for 2호선, see `line_directions()`) × next/next-next train.
- The subentry flow discovers a station's lines from live arrivals (`subway_api.discover_lines`), which returns empty after service hours — the line multi-select lets the user override.
- Legacy entries (`subway_items` in entry data) load through a fallback path with the old per-direction devices; legacy bus entities from the pre-4.6 layout are gone, don't try to resurrect them.
