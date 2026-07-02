# 한국 공공데이터 — Home Assistant Integration

한국 공공데이터 서비스를 하나의 Home Assistant 통합으로 묶었습니다. 기상특보, 대중교통 도착, 유가, 학교 급식, 재난문자, KEPCO 전기요금, 도시가스 사용량, 수도요금, 대기질, 지진 이벤트 등 한국 정부·공공기관 API에서 가져옵니다.

동일 통합 내에서 각 서비스를 독립적으로 설정 — 모든 서비스가 하나의 도메인 아래 별도 config entry로 등록됩니다.

## 지원 서비스

| 서비스 | 출처 | 플랫폼 |
| --- | --- | --- |
| `weather_warning` | 기상청 특보 | event, calendar, binary_sensor |
| `transit` | 서울시 교통 / KakaoMap 정류장 | sensor |
| `fuel` | 오피넷 유가정보 | sensor |
| `school` | NEIS 학교 급식·시간표 | sensor, calendar |
| `disaster` | 행안부 재난문자 | sensor, event |
| `safety_alert` | 안전디딤돌 안전안내문자 | binary_sensor, sensor, event |
| `kepco` | 한전 사이버지점 (전기요금) | sensor |
| `gasapp` | 가스앱 (도시가스 사용량) | sensor |
| `arisu` | 서울시 아리수 (수도요금) | sensor |
| `pharmacy` | 응급의료포털 약국 | sensor |
| `airkorea` | 에어코리아 대기질 + 생활기상지수 | sensor, binary_sensor, event, calendar |
| `kma_weather` | 기상청 동네예보 | weather |
| `earthquake` | 기상청 지진 | event |

## 설치 (HACS)

1. HACS → Integrations → ⋮ → **Custom repositories** — 이 repo URL을 카테고리 **Integration**으로 추가
2. **한국 공공데이터** 설치
3. Home Assistant 재시작
4. 설정 → 기기 및 서비스 → **통합 추가** → "한국 공공데이터" (또는 "Korean Public Data") 검색
5. 메뉴에서 서비스를 선택하고 API 키 / 지역 입력

각 서비스는 별도로 추가합니다. **통합 추가**를 반복해 더 추가하세요.

## 수동 설치

`custom_components/kr_public_data/`를 HA config의 `custom_components/`에 복사 후 재시작.

## API 키

대부분의 서비스는 한국 공공데이터 포털의 무료 API 키가 필요합니다:

- 공공데이터포털 — <https://www.data.go.kr/> (weather_warning, fuel, pharmacy, airkorea, kma_weather, earthquake, disaster)
- 서울 열린데이터 광장 — <https://data.seoul.go.kr/> (transit subway)
- NEIS 교육정보 개방 포털 — <https://open.neis.go.kr/> (school)
- KEPCO 사이버지점 — <https://cyber.kepco.co.kr/> (API 키가 아닌 로그인 자격증명)
- 가스앱 — 모바일 앱 토큰 (gasapp)
- 서울시 아리수 — 고객번호 + 성명 (arisu)

config flow가 각 서비스에 필요한 키를 안내합니다.

## Home Assistant에 노출되는 서비스

구성된 서비스는 HA 액션을 등록합니다. 추가한 entry에 따라 사용 가능한 액션이 달라집니다:

- `kr_public_data.search_pharmacy` — 지역 영업 약국 조회 (pharmacy)
- `kr_public_data.get_living_index_forecast` — 자외선 / 대기정체 예보 (airkorea)

파라미터는 `custom_components/kr_public_data/services.yaml` 참조.

## LLM 도구 (음성 비서 intent)

각 추가된 서비스는 자체 **LLM API**를 등록하여, Home Assistant 대화 에이전트(및 연결된 음성 비서 — Assist, OpenAI, Anthropic, Google, Ollama)가 도구로 호출할 수 있게 합니다. 실제로 구성된 서비스만 intent로 활성화됩니다.

**설정 → 음성 비서 → [에이전트] → LLM API**에서 API 선택(추가된 서비스마다 하나) 후, "지하철 언제 와?", "오늘 학교 급식 뭐야?", "지금 약국 열린 데 있어?" 같은 질문 가능.

| 서비스 | 도구 | UI 표시 |
| --- | --- | --- |
| `kma_weather` | `get_weather_forecast` | 네이티브 날씨 카드 (예보 행) |
| `weather_warning` | `get_weather_warnings` | 활성 특보 테이블 / "안전" 카드 |
| `airkorea` | `get_air_quality` | 측정소 + 자외선 / 정체 테이블 |
| `transit` | `get_subway_arrivals`, `get_bus_arrivals` | 역/정류장별 도착 테이블 |
| `fuel` | `get_fuel_prices` | 가격표 (평균 + 최저가 주유소) |
| `school` | `get_school_meal`, `get_school_timetable` | 메뉴 카드 / 시간표 |
| `disaster` | `get_disaster_messages` | 메시지 카드 그리드 |
| `safety_alert` | `get_safety_alerts` | 알림 카드 그리드 |
| `kepco` | `get_electricity_usage` | kWh + 요금 사용량 카드 |
| `gasapp` | `get_gas_bill` | 청구서 카드 |
| `arisu` | `get_water_bill` | 사용량 포함 청구서 카드 |
| `pharmacy` | `get_open_pharmacies` | 약국 카드 그리드 (영업/마감) |
| `earthquake` | `get_recent_earthquakes` | 최근 이벤트 테이블 |

결과 스키마는 [voice-satellite-card-llm-tools](https://github.com/jxlarrea/voice-satellite-card-llm-tools)를 따르므로, [voice-satellite card](https://github.com/jxlarrea/voice-satellite-card-integration)가 시각 패널을 자동 렌더링합니다 (`kma_weather`는 날씨 카드; 나머지는 `featured_image`와 `results[]`를 통한 SVG 테이블 / 카드). 일반 대화 에이전트도 구조화된 JSON을 받아 설명에 사용합니다.

## 개발

아키텍처와 컨벤션은 `AGENTS.md` 참조.

실제 Home Assistant 설치에 대해 테스트하기 위한 devcontainer가 제공됩니다. VS Code에서 Dev Containers 확장으로 폴더를 열고 실행:

```bash
scripts/develop
```

컨테이너 내부에서 HA가 표준 포트 8123을 바인딩합니다. 호스트 네트워크에서 실행 중인 프로덕션 HA 인스턴스와 구분되도록 컨테이너 호스트명은 `kr-public-data-dev`로 설정됩니다. VS Code는 8123을 호스트로 포워딩합니다 (호스트에 이미 8123이 사용 중이면 다른 포트가 자동 선택됨).

## 라이선스

[MIT](LICENSE)
