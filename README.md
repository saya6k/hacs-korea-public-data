# 한국 공공데이터 — Home Assistant Integration

[![Built with Claude Code](https://img.shields.io/badge/Built%20with%20Claude%20Code-D97757?style=for-the-badge&logo=claude&logoColor=white)](https://claude.ai/code)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-41BDF5?style=for-the-badge&logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=white)](https://hacs.xyz/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Shell](https://img.shields.io/badge/Shell-4EAA25?style=for-the-badge&logo=gnubash&logoColor=white)](https://www.gnu.org/software/bash/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/saya6k)

Korean public data services unified into a single Home Assistant integration. Pulls weather warnings, transit arrivals, fuel prices, school meals, disaster alerts, KEPCO bills, gas usage, water bills, air quality, earthquake events, and more from Korean government / utility APIs.

Configure each service independently from the same integration — every service is a separate config entry under one domain.

## Supported services

| Service          | Source (Korean)                                      | Platforms                                  |
| ---------------- | ---------------------------------------------------- | ------------------------------------------ |
| `weather_warning`| 기상청 특보                                          | event, calendar, binary_sensor             |
| `transit`        | 서울시 교통 / KakaoMap 정류장                        | sensor                                     |
| `fuel`           | 오피넷 유가정보                                      | sensor                                     |
| `school`         | NEIS 학교 급식·시간표                                | sensor, calendar                           |
| `disaster`       | 행안부 재난문자                                      | sensor, event                              |
| `safety_alert`   | 안전디딤돌 안전안내문자                              | binary_sensor, sensor, event               |
| `kepco`          | 한전 사이버지점 (전기요금)                           | sensor                                     |
| `gasapp`         | 가스앱 (도시가스 사용량)                             | sensor                                     |
| `arisu`          | 서울시 아리수 (수도요금)                             | sensor                                     |
| `pharmacy`       | 응급의료포털 약국                                    | sensor                                     |
| `airkorea`       | 에어코리아 대기질 + 생활기상지수                     | sensor, binary_sensor, event, calendar     |
| `kma_weather`    | 기상청 동네예보                                      | weather                                    |
| `earthquake`     | 기상청 지진                                          | event                                      |

## Installation (HACS)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=saya6k&repository=ha-korea-public-data&category=integration)

1. HACS → Integrations → ⋮ → **Custom repositories** — add this repo URL with category **Integration**.
2. Install **한국 공공데이터**.
3. Restart Home Assistant.
4. Settings → Devices & Services → **Add integration** → search "한국 공공데이터" (or "Korean Public Data").
5. Pick a service from the menu and provide its API key / region.

Each service is added separately. Repeat **Add integration** to add more.

## Manual installation

Copy `custom_components/kr_public_data/` into your HA config's `custom_components/` folder and restart.

## API keys

Most services require a free API key from a Korean public data portal. See:

- 공공데이터포털 — <https://www.data.go.kr/> (weather_warning, fuel, pharmacy, airkorea, kma_weather, earthquake, disaster)
- 서울 열린데이터 광장 — <https://data.seoul.go.kr/> (transit subway)
- NEIS 교육정보 개방 포털 — <https://open.neis.go.kr/> (school)
- KEPCO 사이버지점 — <https://cyber.kepco.co.kr/> (login credentials, not an API key)
- 가스앱 — mobile-app token (gasapp)
- 서울시 아리수 — 고객번호 + 성명 (arisu)

The config flow tells you which key each service expects.

## Services exposed to Home Assistant

Configured services register HA actions. Available actions depend on which entries you've added:

- `kr_public_data.search_pharmacy` — list operating pharmacies in a region (pharmacy)
- `kr_public_data.get_living_index_forecast` — UV / air-stagnation forecast (airkorea)

See `custom_components/kr_public_data/services.yaml` for parameters.

## LLM tools (voice assistant intents)

Each added service registers its own **LLM API** that Home Assistant's conversation agent (and any voice assistant connected to it — Assist, OpenAI, Anthropic, Google, Ollama) can call as a tool. Only services you've actually configured become available as intents.

Pick the API in **Settings → Voice assistants → [your agent] → LLM API** (one per added service), then ask the assistant questions like "지하철 언제 와?", "오늘 학교 급식 뭐야?", "지금 약국 열린 데 있어?".

| Service | Tools | UI shown |
| --- | --- | --- |
| `kma_weather` | `get_weather_forecast` | Native weather card (forecast rows) |
| `weather_warning` | `get_weather_warnings` | Table of active 특보 / "안전" card |
| `airkorea` | `get_air_quality` | Table of stations + UV / 정체 |
| `transit` | `get_subway_arrivals`, `get_bus_arrivals` | Arrival table per station / stop |
| `fuel` | `get_fuel_prices` | Price table (avg + cheapest stations) |
| `school` | `get_school_meal`, `get_school_timetable` | Menu card / timetable |
| `disaster` | `get_disaster_messages` | Grid of message cards |
| `safety_alert` | `get_safety_alerts` | Grid of alert cards |
| `kepco` | `get_electricity_usage` | Usage card with kWh + bill |
| `gasapp` | `get_gas_bill` | Bill card |
| `arisu` | `get_water_bill` | Bill card with usage |
| `pharmacy` | `get_open_pharmacies` | Grid of pharmacy cards (open/closed) |
| `earthquake` | `get_recent_earthquakes` | Recent events table |

The result schema follows [voice-satellite-card-llm-tools](https://github.com/jxlarrea/voice-satellite-card-llm-tools), so the [voice-satellite card](https://github.com/jxlarrea/voice-satellite-card-integration) automatically renders the visual panels (weather card for `kma_weather`; SVG tables / cards for everything else via `featured_image` and `results[]`). Plain conversation agents still get the structured JSON for narration.

## Development

See `AGENTS.md` for architecture and conventions.

A devcontainer is provided for testing against a real Home Assistant install. Open the folder in VS Code with the Dev Containers extension and run:

```bash
scripts/develop
```

HA binds the standard port 8123 inside the container. The container's hostname is set to `kr-public-data-dev` so it's distinguishable from any production HA instance you run on the host network. VS Code forwards 8123 to the host (and auto-picks a different host port if 8123 is already taken there).

## License

[MIT](LICENSE)
