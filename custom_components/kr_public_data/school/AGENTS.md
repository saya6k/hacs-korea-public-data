# `school` (NEIS - 학교정보)

Secret field is `neis_api_key` (dispatch code and options-flow defaults try `neis_api_key` first, then fall back to `api_key` for pre-4.8 entries — don't remove that fallback).

Supports multiple schools per entry via `school` subentries (since 4.8), structured like `transit`/`bus` — one `SchoolCoordinator` per subentry, not a single shared one. Subentry data holds `{"region_code", "school_code", "school_name", "school_level", "grade_classes", "address", "phone", "period_1".."period_7", "lunch_start", "lunch_end"}`; the entry itself only holds `neis_api_key`.

`SchoolSubentryFlowHandler` ("학교 추가") walks NEIS search → school select → 학년/반 select → 교시 시간 to add another school, and is the only subentry flow so far implementing `async_step_reconfigure` (edits `grade_classes` on an existing school) — copy its `_get_reconfigure_subentry()` / `async_update_and_abort()` pattern if you add editing to another subentry type (as `fuel`'s `FuelRegionSubentryFlowHandler` now does for `fuel_codes`).

Legacy pre-subentry entries (all fields flat in `entry.data`) still load through a fallback path in `__init__.py`/`sensor.py`/`calendar.py` — don't remove it. `llm_api/school_tool.py` picks which school's coordinator to use via an optional `school` tool parameter resolved against `store["school_subs"]` (see root `AGENTS.md` hard rule 7).
