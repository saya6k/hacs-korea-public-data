# Repository agent instructions

> `CLAUDE.md` and `GEMINI.md` are local symlinks to this file (gitignored) — edit `AGENTS.md`.

Agent assets live under `.agents/` (the source of truth): `skills/`, `workflows/` (commands), `agents/`, and `memory/` (Claude's per-project memory). `.claude/` is a real directory: its `settings.json` is Claude-specific and tracked; its per-item symlinks into `.agents/` (`skills`, `commands` → `workflows`, `agents`) and `settings.local.json` are local-only, as are the `CLAUDE.md`/`GEMINI.md` → `AGENTS.md` symlinks and `.gemini` → `.agents`.

This file briefs Claude / GPT / other coding agents on the conventions and load-bearing facts of `ha_korean_public_data`. Read this before making changes.

## Repository layout

```
ha_korean_public_data/
├── custom_components/kr_public_data/   ← the HA integration (edit this)
│   ├── __init__.py                     ← per-service async_setup_entry dispatch
│   ├── const.py                        ← DOMAIN + ENTRY_* service identifiers
│   ├── config_flow.py                  ← multi-service menu config flow
│   ├── manifest.json
│   ├── services.yaml                   ← HA actions exposed to users
│   ├── strings.json                    ← English source-of-truth for translations
│   ├── translations/                   ← per-locale UI strings (ko.json)
│   ├── sensor.py / binary_sensor.py / calendar.py / event.py
│   │                                   ← shared platform shims; per-service entity
│   │                                     classes live in the sub-package
│   ├── utils.py
│   ├── llm_api/                        ← per-entry LLM API + tools (intents)
│   │   ├── __init__.py                 ← async_setup_llm_api / cleanup
│   │   ├── base_tool.py                ← BaseKRTool reads coordinator data
│   │   ├── const.py                    ← API names + per-service api_prompt
│   │   ├── render.py                   ← SVG table/card → data: URL helpers
│   │   ├── tools.py                    ← TOOLS_BY_ETYPE registry
│   │   └── <service>_tool.py           ← one llm.Tool subclass per service
│   └── <service>/                      ← one sub-package per public-data source:
│       ├── airkorea/      ├── arisu/        ├── disaster/    ├── earthquake/
│       ├── fuel/          ├── gasapp/       ├── kepco/       ├── kma_weather/
│       ├── pharmacy/      ├── safety_alert/ ├── school/      ├── transit/
│       └── weather/
│       (typical: __init__.py, api.py, coordinator.py, sensor.py, services.py)
├── .devcontainer/
├── scripts/
│   ├── setup                           ← installs HA + dev deps in the container
│   └── develop                         ← runs HA from this checkout for live testing
├── hacs.json
└── README.md
```

## Hard rules

1. **One domain, many services.** Everything ships under `domain: kr_public_data`. Each public-data source is a *config entry type*, dispatched by `entry.data[CONF_ENTRY_TYPE]` in `__init__.py:async_setup_entry`. Adding a new source means: adding an `ENTRY_<X>` constant in `const.py`, a sub-package, a branch in `async_setup_entry`, an entry in `PLATFORM_MAP`, and a config-flow step.
2. **Never set `_attr_name` on an entity that has `_attr_translation_key`.** HA's `Entity._name_internal` returns `_attr_name` first and never consults the translation map afterwards — this silently breaks every non-English UI. Pick one or the other.
3. **Translations live in two places.** `strings.json` is the English source of truth; `translations/<lang>.json` files are the localized copies. They must share the same key tree. Add a Korean entry to `translations/ko.json` whenever you add an English entry to `strings.json`.
4. **Coordinators per service.** Each sub-package owns its own `DataUpdateCoordinator` subclass in `<service>/coordinator.py`. Entities read `self.coordinator.data[...]`; they do not call APIs directly. Multi-region services keep a dict of coordinators keyed by region/station/stop and store it in `hass.data[DOMAIN][entry.entry_id]`.
5. **Cloud polling, not push.** `manifest.json` declares `iot_class: cloud_polling`. Don't introduce websockets / MQTT without coordinating with the user — most Korean public APIs only support polling, and rate limits are tight.
6. **HTTP client: `curl_cffi`.** Several Korean government APIs reject default Python TLS fingerprints. Use `curl_cffi` (already in `requirements`) for the API calls that need browser-like TLS, not `aiohttp`/`requests`. Stick with whichever the existing `<service>/api.py` already uses.
7. **LLM tools read from coordinators, not APIs.** Each tool in `llm_api/<service>_tool.py` looks its data up via `self.store["coordinator"].data` (or `subway_coords`/`bus_coords`/`coordinators` for multi-region services). Tools must not call APIs directly — that's the coordinator's job, and it keeps polling under HA's control.
8. **LLM tool result schema follows voice-satellite-card-llm-tools.** Return either `forecast` (weather card UI), `query_type`+financial fields (financial card UI), `results: [{image_url}]` (grid), or `featured_image` (single panel). The voice-satellite card auto-renders these without modification. For tools without a native card UI, generate an SVG via `llm_api/render.py` (`svg_table` or `svg_card`) and put the resulting `data:` URL in `featured_image` or each `results[].image_url`. Always include an `instruction` field telling the LLM the visual is already shown so it keeps the spoken reply brief.

## Service quirks

- **`transit`**: bus stops are identified by KakaoMap stop IDs (not the public bus-stop ID). The config flow's bus search step expects the user to copy the ID from a KakaoMap URL.
- **`kepco`**: authenticates with username/password against 사이버지점 (no API key). Login can fail silently — `__init__.py` swallows the exception so the entry still loads with stale data.
- **`gasapp`**: requires an OAuth-style token + member-id + contract number captured from the mobile app. There is no public OAuth endpoint.
- **`airkorea` / `kma_weather`**: share the same 공공데이터포털 service key. The config flow lets you reuse one key across multiple regions/stations.
- **`weather_warning` vs `kma_weather`**: `weather_warning` is the alert/특보 stream (event entities); `kma_weather` is the forecast (weather entity). They are independent entries.
- **`pharmacy`**: the `search_pharmacy` action is registered globally on entry setup; only one pharmacy entry should exist per HA instance.
- **`pharmacy` / `disaster` regions are config subentries.** The main entry holds the API key; each 기초자치단체 (시군구) is a `region` subentry (`{"sido", "sgg"}`), added via the checklist in the config flow or the "지역 추가" subentry flow (`RegionSubentryFlowHandler`). Entities are registered with `config_subentry_id` so removing a subentry cleans up its device. The 시군구 list is fetched live from the safekorea region API (`safety_alert/region_api.py`). Legacy entries (pre-subentry `q0`/`q1` or `region_filter` in entry data) still load through fallback paths in `__init__.py`/`sensor.py`/`event.py` — don't remove them.
- **`disaster`** polls once per entry: a single coordinator fetches all messages and each subentry's entities filter with `disaster/coordinator.py:filter_messages` (시군구, 시도 전체, 전국 match). `pharmacy` is the opposite — the API queries per region, so it's one coordinator per subentry.
- **`kma_weather` / `weather_warning` / `airkorea` regions are also subentries**, but with a single coordinator per entry (like `disaster`): `kma_weather` uses `region` subentries (`{"sido", "name", "nx", "ny"}` from the built-in `SIDO_LIST`), `weather_warning` uses `area` subentries (`{"area_code"}` from `weather/AREA_CODES`), `airkorea` uses `station` subentries (`{"sido", "stationName"}` from `STATIONS_BY_SIDO`). `__init__.py` rebuilds the coordinator's region/station list from `entry.subentries` and stores a `region_subs`/`areas`/`station_subs` map; platform shims register each subentry's entities with `config_subentry_id`. Legacy entries (`regions`/`area_codes`/`stations` lists in entry data, no subentries) still load through fallback paths — don't remove them.

## Config-flow conventions

`config_flow.py` is a single multi-step `OptionsFlow`/`ConfigFlow` driven by a `user` menu step that branches into per-service step handlers (`async_step_weather_warning`, `async_step_transit`, ...). When adding a new service:

1. Add the service to the `user` step's `menu_options`.
2. Add `async_step_<service>` and any sub-steps it needs.
3. Mirror the step titles & field labels in `strings.json` *and* `translations/ko.json`.
4. Store the resulting entry data with `CONF_ENTRY_TYPE = ENTRY_<X>` so `__init__.py` can route it.

## Entity translation flow

`_attr_has_entity_name = True` + `_attr_translation_key = "<key>"` →
HA looks up `entity.<platform>.<key>.name` from `translations/<ha_ui_lang>.json` (falls back to `strings.json`).

For state-enum sensors, also populate `entity.<platform>.<key>.state.<value>`.
For event entities with attribute enums, populate `entity.<platform>.<key>.state_attributes.event_type.state.<value>`.

## Testing

Use the devcontainer:

```bash
scripts/develop          # boots HA on :8123 with this integration mounted
```

There is no automated test suite. The integration is validated by:

1. Starting the devcontainer.
2. Adding each service via Settings → Devices & Services with real API keys.
3. Watching `home-assistant.log` for coordinator update failures and HTTP errors.

## LLM API registration

`llm_api/__init__.py` registers one `llm.API` per *added* config entry. The API id is `kr_public_data__<etype>__<entry_id>`, so every entry gets a unique surface and unloading one entry doesn't disturb others. `__init__.py:async_setup_entry` calls `async_setup_llm_api(...)` after coordinator first refresh and stores the unregister callback in `store["unregister_llm"]`; `async_unload_entry` invokes it before unloading platforms. The `conversation` HA component is declared as a manifest dependency so `homeassistant.helpers.llm` is guaranteed to be importable.

When adding a new service: also append the etype to `llm_api/const.py` (API name + `api_prompt`), add a `<service>_tool.py` with one or more `BaseKRTool` subclasses, and register them in `llm_api/tools.py:TOOLS_BY_ETYPE`. The tool's `name` and `parameters` (`vol.Schema`) are exposed verbatim to the conversation agent.

## When in doubt

- Localization broken? Check rule (2) above before anything else.
- A service won't load? Check the `etype == ENTRY_<X>` branch in `__init__.py` — most failures are config-data shape mismatches against what the coordinator expects.
- API returning 403/SSL errors? The endpoint probably needs `curl_cffi` with a browser impersonation profile, not plain HTTP.
- LLM tool returns blank UI? Confirm the response includes `featured_image` *or* `results[].image_url` — the voice-satellite card matches against those exact keys (plus `forecast` for weather and `query_type` for financial).
- Adding a new service? Update `const.py`, `__init__.py` dispatch, `PLATFORM_MAP`, `config_flow.py`, `strings.json`, every file under `translations/`, **and** `llm_api/const.py` + `llm_api/tools.py` + a `<service>_tool.py`.
