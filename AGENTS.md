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
│   └── <service>/                      ← one sub-package per public-data source,
│       │                                 each with its own AGENTS.md:
│       ├── airkorea/      ├── arisu/        ├── bus/         ├── disaster/
│       ├── earthquake/    ├── fuel/         ├── gasapp/      ├── kepco/
│       ├── kma_weather/   ├── pharmacy/     ├── safety_alert/├── school/
│       ├── transit/       └── weather/
│       (typical: __init__.py, api.py, coordinator.py, sensor.py, services.py, AGENTS.md)
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
7. **LLM tools read from coordinators, not APIs.** Each tool in `llm_api/<service>_tool.py` looks its data up via `self.store["coordinator"].data` (or `subway_coords`/`coordinators`/`school_subs` for multi-instance services). Tools must not call APIs directly — that's the coordinator's job, and it keeps polling under HA's control. When a service can have multiple sub-resources (subentries) with separate coordinators, don't just default to the first one: accept an optional disambiguation parameter and resolve it by name, erroring with the list of configured names when it's ambiguous — see `llm_api/school_tool.py:_resolve_school_coordinator`.
8. **LLM tool result schema follows voice-satellite-card-llm-tools.** Return either `forecast` (weather card UI), `query_type`+financial fields (financial card UI), `results: [{image_url}]` (grid), or `featured_image` (single panel). The voice-satellite card auto-renders these without modification. For tools without a native card UI, generate an SVG via `llm_api/render.py` (`svg_table` or `svg_card`) and put the resulting `data:` URL in `featured_image` or each `results[].image_url`. Always include an `instruction` field telling the LLM the visual is already shown so it keeps the spoken reply brief.

## Service quirks

Each service's specific gotchas (auth quirks, subentry shape, legacy fallbacks) live in its own `custom_components/kr_public_data/<service>/AGENTS.md` — **read the relevant one before touching that service.** Index:

| Service | Doc | One-line hook |
|---|---|---|
| `airkorea` | [`airkorea/AGENTS.md`](custom_components/kr_public_data/airkorea/AGENTS.md) | 대기질, shares service key with `kma_weather`, `station` subentries |
| `arisu` | [`arisu/AGENTS.md`](custom_components/kr_public_data/arisu/AGENTS.md) | 상수도, HTML-scraped (no API key), single coordinator |
| `bus` | [`bus/AGENTS.md`](custom_components/kr_public_data/bus/AGENTS.md) | 버스, the only entry type with 2 subentry types |
| `disaster` | [`disaster/AGENTS.md`](custom_components/kr_public_data/disaster/AGENTS.md) | 긴급재난문자, `region` subentries, single coordinator + filter, `geo_location` platform |
| `earthquake` | [`earthquake/AGENTS.md`](custom_components/kr_public_data/earthquake/AGENTS.md) | 지진정보, simplest service — no regions/subentries at all |
| `fuel` | [`fuel/AGENTS.md`](custom_components/kr_public_data/fuel/AGENTS.md) | 유가정보 (Opinet), `fuel_region` subentries, KATEC→WGS84 coordinate conversion |
| `gasapp` | [`gasapp/AGENTS.md`](custom_components/kr_public_data/gasapp/AGENTS.md) | 가스앱, mobile-app-only OAuth token, no public endpoint |
| `kepco` | [`kepco/AGENTS.md`](custom_components/kr_public_data/kepco/AGENTS.md) | 한전, username/password auth, silent login failure |
| `kma_weather` | [`kma_weather/AGENTS.md`](custom_components/kr_public_data/kma_weather/AGENTS.md) | 날씨예보 (forecast), `region` subentries |
| `pharmacy` | [`pharmacy/AGENTS.md`](custom_components/kr_public_data/pharmacy/AGENTS.md) | 약국정보, flat `regions` list (not subentries), radius-based location sensors |
| `safety_alert` | [`safety_alert/AGENTS.md`](custom_components/kr_public_data/safety_alert/AGENTS.md) | 안전알림, flat `regions` list |
| `school` | [`school/AGENTS.md`](custom_components/kr_public_data/school/AGENTS.md) | NEIS 학교정보, `school` subentries + the reconfigure pattern to copy |
| `transit` | [`transit/AGENTS.md`](custom_components/kr_public_data/transit/AGENTS.md) | 지하철, `subway_station` subentries |
| `weather` | [`weather/AGENTS.md`](custom_components/kr_public_data/weather/AGENTS.md) | 기상특보 (`weather_warning`, alert stream), `area` subentries |

Cross-cutting: **secret field names aren't all `api_key`.** `bus` uses `api_key` (renamed from `service_key` in 4.8), `school` uses `neis_api_key`, `disaster` uses `safety_api_key`, `fuel` uses `opinet_api_key` (renamed from `api_key` in 4.9). Dispatch code and options-flow defaults always try the current name first and fall back to the old one (e.g. `entry.data.get("safety_api_key") or entry.data.get("api_key")`) so pre-rename entries keep working — don't remove those fallbacks. See each service's own doc for its exact field name.

Cross-cutting: **`region` is a subentry_type string shared by several entry types** (`disaster`, `kma_weather`, and — before its 4.9 rewrite — `pharmacy`) whenever their region shape happens to match `{"sido", "sgg"}`. `config_subentries.region` translations in `strings.json`/`ko.json` are shared across all of them — check who's still using it before changing that block. Other subentry_type strings (`fuel_region`, `subway_station`, `station`, `area`, `school`, `city_bus_stop`, `intercity_bus_route`) are each scoped to one entry type.

## Config-flow conventions

`config_flow.py` is a single multi-step `OptionsFlow`/`ConfigFlow` driven by a `user` menu step that branches into per-service step handlers (`async_step_weather_warning`, `async_step_transit`, ...). When adding a new service:

1. Add the service to the `user` step's `menu_options`.
2. Add `async_step_<service>` and any sub-steps it needs.
3. Mirror the step titles & field labels in `strings.json` *and* `translations/ko.json`.
4. Store the resulting entry data with `CONF_ENTRY_TYPE = ENTRY_<X>` so `__init__.py` can route it.
5. Secret fields (API keys, tokens, passwords) use `_password_selector()` (a masked `TextSelector`), never plain `str` — in both the initial `async_step_<service>` schema and the matching branch of `KRPublicDataOptionsFlow._build_schema`.

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

## Release workflow

This repo (and other `ha-*` HACS components, excluding `ha-app*`) ships on a
two-track rolling draft release, maintained by release-drafter since
`15ae319` (#31): a `rc` (prerelease) draft and a `stable` draft, both updated
continuously as PRs merge to `main`.

1. Verify locally with the devcontainer (`scripts/develop`) before merging —
   see Testing above.
2. Once merged and the `rc` draft looks right, publish it as a prerelease
   from the GitHub Releases UI.
3. After the prerelease has been exercised with no issues, promote/publish
   the corresponding `stable` draft.

## When in doubt

- Localization broken? Check rule (2) above before anything else.
- A service won't load? Check the `etype == ENTRY_<X>` branch in `__init__.py` — most failures are config-data shape mismatches against what the coordinator expects.
- API returning 403/SSL errors? The endpoint probably needs `curl_cffi` with a browser impersonation profile, not plain HTTP.
- LLM tool returns blank UI? Confirm the response includes `featured_image` *or* `results[].image_url` — the voice-satellite card matches against those exact keys (plus `forecast` for weather and `query_type` for financial).
- Adding a new service? Update `const.py`, `__init__.py` dispatch, `PLATFORM_MAP`, `config_flow.py`, `strings.json`, every file under `translations/`, `llm_api/const.py` + `llm_api/tools.py` + a `<service>_tool.py`, **and** add a `custom_components/kr_public_data/<service>/AGENTS.md` + an index row above.
