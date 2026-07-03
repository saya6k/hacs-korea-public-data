"""Config flow for 한국 공공데이터."""
from __future__ import annotations
import logging
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector, LocationSelector, LocationSelectorConfig,
    NumberSelector, NumberSelectorConfig, NumberSelectorMode,
    SelectOptionDict, SelectSelector, SelectSelectorConfig, SelectSelectorMode,
    TextSelector, TextSelectorConfig, TextSelectorType,
)
from .const import *
from .utils import sido_short_name

_LOGGER = logging.getLogger(__name__)

# 광역자치단체 → safekorea 법정동 코드 (시군구 목록 조회용)
SIDO_CODES = {
    "서울특별시": "1100000000", "부산광역시": "2600000000",
    "대구광역시": "2700000000", "인천광역시": "2800000000",
    "광주광역시": "2900000000", "대전광역시": "3000000000",
    "울산광역시": "3100000000", "세종특별자치시": "3600000000",
    "경기도": "4100000000", "강원특별자치도": "5100000000",
    "충청북도": "4300000000", "충청남도": "4400000000",
    # 전북은 2026 개편으로 5200000000 (구 4500000000은 빈 목록 반환)
    "전북특별자치도": "5200000000", "전라남도": "4600000000",
    "경상북도": "4700000000", "경상남도": "4800000000",
    "제주특별자치도": "5000000000",
}


async def _async_fetch_sgg_names(sido_name: str) -> list[str]:
    """기초자치단체(시군구) 이름 목록을 safekorea 지역 API에서 조회.

    safekorea가 죽어 있거나 리다이렉트로 튕기면 kma_weather의 내장
    시군구 테이블로 폴백한다 — config flow가 외부 API에 볼모잡히지 않게.
    """
    from .safety_alert.region_api import SafetyAlertRegionApiClient
    code = SIDO_CODES.get(sido_name, "")
    if not code:
        return []
    client = SafetyAlertRegionApiClient()
    names = [s["name"] for s in await client.async_get_sgg_list(code) if s.get("name")]
    if names:
        return names
    from .kma_weather import SIDO_LIST
    return sorted(SIDO_LIST.get(sido_name, {}).keys())


def _sido_selector():
    opts = [SelectOptionDict(value=k, label=k) for k in SIDO_CODES]
    return SelectSelector(SelectSelectorConfig(options=opts,
                                               mode=SelectSelectorMode.DROPDOWN))


def _password_selector():
    return TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _pharmacy_location_fields(hass, region: dict | None = None):
    """지도에서 직접 찍은 위치 기준 반경 내 약국을 개별 위치 센서로 만들지 여부 + 위치/반경.

    zone.home으로 고정하지 않고 LocationSelector로 위치를 직접 지정하게 한다.
    기존 위치가 없으면(신규) hass.config의 홈 좌표를 지도 초기값으로만 사용한다.
    """
    region = region or {}
    loc = region.get("location") or {}
    return {
        vol.Optional("location_sensors", default=region.get("location_sensors", False)): BooleanSelector(),
        vol.Optional("location", default={
            "latitude": loc.get("latitude", hass.config.latitude),
            "longitude": loc.get("longitude", hass.config.longitude),
            "radius": loc.get("radius", region.get("radius", 1000)),
        }): LocationSelector(LocationSelectorConfig(radius=True)),
    }


# ── 버스: TAGO(전국)와 서울(ws.bus.go.kr) 두 소스를 한 검색 흐름으로 통합.
# 두 소스의 응답 필드가 다르므로 여기서 공용 후보/노선 형태로 정규화하고,
# 실제 도착정보 조회·엔티티 생성은 bus/city_coordinator.py 와
# bus/seoul_coordinator.py 가 subentry.data["source"]로 계속 구분한다.

def _bus_city_options(city_codes: dict) -> list[SelectOptionDict]:
    from .bus import SEOUL_CITY_CODE
    opts = [SelectOptionDict(value=SEOUL_CITY_CODE, label="서울특별시")]
    opts += [SelectOptionDict(value=str(k), label=v) for k, v in city_codes.items()]
    return opts


async def _search_bus_stops(session, api_key: str, city_code: str, name: str) -> list[dict]:
    """정류소 검색 → 공용 후보 형태: {id, name, hint}."""
    from .bus import SEOUL_CITY_CODE
    if city_code == SEOUL_CITY_CODE:
        from .bus.seoul_api import search_stops
        candidates = await search_stops(session, api_key, name)
        return [{"id": c["arsId"], "name": c.get("stNm", ""), "hint": c.get("arsId", "")}
                for c in candidates]
    from .bus.api import search_stops
    candidates = await search_stops(session, api_key, int(city_code), name)
    return [{"id": c["nodeid"], "name": c.get("nodenm", ""), "hint": str(c.get("nodeno", ""))}
            for c in candidates]


async def _bus_stop_routes(session, api_key: str, city_code: str, node_id: str) -> list[dict]:
    """경유노선 검색(자동 감지) → 공용 형태: {id, routeNo, label}."""
    from .bus import SEOUL_CITY_CODE
    if city_code == SEOUL_CITY_CODE:
        from .bus.seoul_api import fetch_stop_arrivals
        routes = await fetch_stop_arrivals(session, api_key, node_id)
        return [{"id": r["busRouteId"], "routeNo": r.get("rtNm", ""),
                 "label": f"{r.get('rtNm', '')}번 ({r.get('adirection', '')} 방면)"}
                for r in routes]
    from .bus.api import stop_routes
    routes = await stop_routes(session, api_key, int(city_code), node_id)
    return [{"id": r["routeid"], "routeNo": r.get("routeno", ""),
             "label": f"{r.get('routeno', '')}번 ({r.get('routetp', '')}, "
                      f"{r.get('startnodenm', '')}→{r.get('endnodenm', '')})"}
            for r in routes]


_REGION_GRID = {
"11B10101": (60, 127),  # 서울
"11B20201": (55, 124),  # 인천
"11B20601": (60, 121),  # 수원
"11D10301": (73, 134),  # 춘천
"11D20501": (92, 131),  # 강릉
"11C10301": (69, 106),  # 청주
"11C20401": (67, 100),  # 대전
"11F10201": (58, 74),   # 광주
"11F20501": (63, 89),   # 전주
"11H10701": (89, 90),   # 대구
"11H20201": (98, 76),   # 부산
"11H20301": (102, 84),  # 울산
"11G00201": (52, 38),   # 제주
}

class KRPublicDataConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        return self.async_show_menu(
            step_id="user",
            menu_options=["weather_warning", "transit", "bus", "fuel", "school",
                         "disaster", "safety_alert", "kepco", "gasapp", "arisu",
                         "pharmacy", "airkorea", "kma_weather", "earthquake"],
        )

    # ══════════ 기상특보 ══════════

    async def async_step_weather_warning(self, user_input=None) -> FlowResult:
        from .weather import AREA_CODES
        from .weather.api import validate_kma_api
        errors: dict[str, str] = {}
        area_options = [
            SelectOptionDict(value=code, label=f"{name}")
            for code, name in AREA_CODES.items()
        ]
        if user_input is not None:
            api_key = user_input["api_key"]
            areas = user_input.get("area_codes", [])
            if not isinstance(areas, list):
                areas = [areas]
            if not areas:
                errors["area_codes"] = "no_selection"
            elif await validate_kma_api(api_key, areas[0]):
                return self.async_create_entry(
                    title="기상특보",
                    data={CONF_ENTRY_TYPE: ENTRY_WEATHER, "api_key": api_key},
                    subentries=[
                        {"subentry_type": "area", "title": AREA_CODES.get(c, c),
                         "data": {"area_code": c}, "unique_id": c}
                        for c in areas
                    ])
            else:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="weather_warning",
            data_schema=vol.Schema({
                vol.Required("api_key"): _password_selector(),
                vol.Required("area_codes"): SelectSelector(
                    SelectSelectorConfig(options=area_options, multiple=True,
                                         mode=SelectSelectorMode.DROPDOWN)),
            }),
            errors=errors)

    # ══════════ 지하철 ══════════

    async def async_step_transit(self, user_input=None) -> FlowResult:
        """Step 1: 서울 열린데이터광장 키."""
        from .transit.subway_api import validate_seoul_api
        errors: dict[str, str] = {}
        if user_input is not None:
            seoul_key = user_input["seoul_api_key"]
            if await validate_seoul_api(seoul_key):
                self._data = {
                    CONF_ENTRY_TYPE: ENTRY_TRANSIT,
                    "seoul_api_key": seoul_key,
                }
                return await self.async_step_transit_station()
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="transit",
            data_schema=vol.Schema({
                vol.Required("seoul_api_key"): _password_selector(),
            }),
            errors=errors)

    async def async_step_transit_station(self, user_input=None) -> FlowResult:
        """Step 2: 역 이름 입력 → 운행 노선 자동 감지."""
        from .transit.subway_api import discover_lines
        if user_input is not None:
            self._subway_station = user_input["station"].strip()
            try:
                session = async_get_clientsession(self.hass)
                self._subway_lines_found = await discover_lines(
                    session, self._data["seoul_api_key"], self._subway_station)
            except Exception as e:
                _LOGGER.warning("Subway line discovery failed: %s", e)
                self._subway_lines_found = []
            return await self.async_step_transit_lines()
        return self.async_show_form(
            step_id="transit_station",
            data_schema=vol.Schema({vol.Required("station"): str}))

    async def async_step_transit_lines(self, user_input=None) -> FlowResult:
        """Step 3: 호선 선택 (감지된 노선이 기본값) → 역 subentry."""
        import homeassistant.helpers.config_validation as cv
        from .transit import SUBWAY_LINES
        errors: dict[str, str] = {}
        if user_input is not None:
            lines = user_input.get("lines", [])
            if not lines:
                errors["base"] = "no_selection"
            else:
                station = self._subway_station
                return self.async_create_entry(
                    title="지하철", data=self._data,
                    subentries=[
                        {"subentry_type": "subway_station",
                         "title": f"{station}역",
                         "data": {"station": station, "lines": lines},
                         "unique_id": station}
                    ])
        return self.async_show_form(
            step_id="transit_lines",
            data_schema=vol.Schema({
                vol.Required("lines", default=self._subway_lines_found):
                    cv.multi_select(SUBWAY_LINES),
            }),
            errors=errors)

    # ══════════ 버스 ══════════

    async def async_step_bus(self, user_input=None) -> FlowResult:
        """Step 1: TAGO(국토교통부) 공공데이터포털 서비스키."""
        from .bus.api import validate_bus_api
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input["api_key"]
            session = async_get_clientsession(self.hass)
            if await validate_bus_api(session, api_key):
                self._data = {
                    CONF_ENTRY_TYPE: ENTRY_BUS,
                    "api_key": api_key,
                }
                return await self.async_step_bus_stop_search()
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="bus",
            data_schema=vol.Schema({
                vol.Required("api_key"): _password_selector(),
            }),
            errors=errors)

    async def async_step_bus_stop_search(self, user_input=None) -> FlowResult:
        """Step 2: 도시 선택(서울 포함) + 정류소명 검색."""
        from .bus import CITY_CODES
        errors: dict[str, str] = {}
        if user_input is not None:
            city_code = user_input["city_code"]
            name = user_input["name"].strip()
            session = async_get_clientsession(self.hass)
            try:
                self._bus_candidates = await _search_bus_stops(
                    session, self._data["api_key"], city_code, name)
            except Exception as e:
                _LOGGER.warning("Bus stop search failed: %s", e)
                self._bus_candidates = []
            if not self._bus_candidates:
                errors["base"] = "no_stations_found"
            else:
                self._bus_city_code = city_code
                return await self.async_step_bus_stop_select()
        city_opts = _bus_city_options(CITY_CODES)
        return self.async_show_form(
            step_id="bus_stop_search",
            data_schema=vol.Schema({
                vol.Required("city_code"): SelectSelector(
                    SelectSelectorConfig(options=city_opts, mode=SelectSelectorMode.DROPDOWN)),
                vol.Required("name"): str,
            }),
            errors=errors)

    async def async_step_bus_stop_select(self, user_input=None) -> FlowResult:
        """Step 3: 검색 결과에서 정류소 선택 → 경유노선 자동 감지."""
        if user_input is not None:
            node_id = user_input["node_id"]
            match = next((c for c in self._bus_candidates if c["id"] == node_id), None)
            if match:
                self._bus_node_id = node_id
                self._bus_node_name = match["name"]
                session = async_get_clientsession(self.hass)
                try:
                    self._bus_routes_found = await _bus_stop_routes(
                        session, self._data["api_key"], self._bus_city_code, node_id)
                except Exception as e:
                    _LOGGER.warning("Bus route discovery failed: %s", e)
                    self._bus_routes_found = []
                return await self.async_step_bus_routes()
        stop_opts = [SelectOptionDict(value=c["id"], label=f"{c['name']} ({c['hint']})")
                    for c in self._bus_candidates]
        return self.async_show_form(
            step_id="bus_stop_select",
            data_schema=vol.Schema({
                vol.Required("node_id"): SelectSelector(
                    SelectSelectorConfig(options=stop_opts, mode=SelectSelectorMode.DROPDOWN)),
            }))

    async def async_step_bus_routes(self, user_input=None) -> FlowResult:
        """Step 4: 노선 선택 (감지된 노선이 기본값) → 정류장 subentry."""
        import homeassistant.helpers.config_validation as cv
        from .bus import SEOUL_CITY_CODE
        errors: dict[str, str] = {}
        route_map = {r["id"]: r["label"] for r in self._bus_routes_found}
        if user_input is not None:
            selected = user_input.get("routes", [])
            if not selected:
                errors["base"] = "no_selection"
            else:
                by_id = {r["id"]: r for r in self._bus_routes_found}
                routes = [{"routeId": rid, "routeNo": by_id[rid]["routeNo"]} for rid in selected]
                node_id, node_name = self._bus_node_id, self._bus_node_name
                source = "seoul" if self._bus_city_code == SEOUL_CITY_CODE else "tago"
                return self.async_create_entry(
                    title="버스", data=self._data,
                    subentries=[
                        {"subentry_type": "city_bus_stop",
                         "title": f"{node_name} 정류장",
                         "data": {"source": source, "cityCode": self._bus_city_code,
                                  "nodeId": node_id, "nodeName": node_name, "routes": routes},
                         "unique_id": node_id}
                    ])
        return self.async_show_form(
            step_id="bus_routes",
            data_schema=vol.Schema({
                vol.Required("routes", default=list(route_map)): cv.multi_select(route_map),
            }),
            errors=errors)

    # ══════════ 유가정보 ══════════

    async def async_step_fuel(self, user_input=None) -> FlowResult:
        from .fuel import SIDO_CODES, FUEL_TYPES
        from .fuel.api import validate_opinet
        errors: dict[str, str] = {}

        sido_options = [
            SelectOptionDict(value=k, label=v) for k, v in SIDO_CODES.items()
        ]
        fuel_options = [
            SelectOptionDict(value=k, label=v) for k, v in FUEL_TYPES.items()
        ]

        if user_input is not None:
            api_key = user_input["opinet_api_key"]
            sidos = user_input.get("sido_codes", [])
            fuels = user_input.get("fuel_codes", [])
            if not isinstance(sidos, list):
                sidos = [sidos]
            if not isinstance(fuels, list):
                fuels = [fuels]
            if not sidos or not fuels:
                errors["base"] = "no_selection"
            elif await validate_opinet(api_key):
                # 지역(시도)마다 subentry, 유종은 그 안에서 multi-select로 관리.
                return self.async_create_entry(
                    title="유가정보",
                    data={CONF_ENTRY_TYPE: ENTRY_FUEL, "opinet_api_key": api_key},
                    subentries=[
                        {"subentry_type": "fuel_region", "title": SIDO_CODES.get(s, s),
                         "data": {"sido_code": s, "fuel_codes": fuels}, "unique_id": s}
                        for s in sidos
                    ])
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="fuel",
            data_schema=vol.Schema({
                vol.Required("opinet_api_key"): _password_selector(),
                vol.Required("sido_codes"): SelectSelector(
                    SelectSelectorConfig(options=sido_options, multiple=True,
                                         mode=SelectSelectorMode.DROPDOWN)),
                vol.Required("fuel_codes"): SelectSelector(
                    SelectSelectorConfig(options=fuel_options, multiple=True,
                                         mode=SelectSelectorMode.DROPDOWN)),
            }),
            errors=errors)

    # ══════════ 학교정보 ══════════

    async def async_step_school(self, user_input=None) -> FlowResult:
        from .school import SCHOOL_LEVELS
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input["neis_api_key"]
            self._data = {CONF_ENTRY_TYPE: ENTRY_SCHOOL,
                          "neis_api_key": api_key,
                          "school_level": user_input["school_level"]}
            try:
                session = async_get_clientsession(self.hass)
                from .school.api import NeisApiClient
                c = NeisApiClient(session, api_key)
                await c.search_school("서울")
            except Exception:
                errors["neis_api_key"] = "invalid_api_key"
            if not errors:
                return await self.async_step_school_search()
        return self.async_show_form(
            step_id="school",
            data_schema=vol.Schema({
                vol.Required("neis_api_key"): _password_selector(),
                vol.Required("school_level", default="elementary"): vol.In(SCHOOL_LEVELS),
            }),
            errors=errors)

    async def async_step_school_search(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            from .school.api import NeisApiClient
            from .school.parser import parse_school_info
            c = NeisApiClient(session, self._data["neis_api_key"])
            if "school_search" in user_input:
                schools = await c.search_school(user_input["school_search"])
                if not schools:
                    errors["school_search"] = "no_schools_found"
                else:
                    opts = {
                        f"{s['ATPT_OFCDC_SC_CODE']}_{s['SD_SCHUL_CODE']}":
                        f"{s['SCHUL_NM']} ({s.get('ORG_RDNMA', '')})"
                        for s in schools[:10]}
                    return self.async_show_form(step_id="school_search",
                        data_schema=vol.Schema({vol.Required("selected_school"): vol.In(opts)}))
            elif "selected_school" in user_input:
                rc, sc = user_input["selected_school"].split("_")
                info = await c.get_school_info(rc, sc)
                if info:
                    self._data.update(parse_school_info(info))
                    return await self.async_step_school_class()
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="school_search",
            data_schema=vol.Schema({vol.Required("school_search"): str}),
            errors=errors)

    async def async_step_school_class(self, user_input=None) -> FlowResult:
        import homeassistant.helpers.config_validation as cv
        if user_input is not None:
            # Parse "G-C" format selections into list
            selected = user_input.get("grade_classes", [])
            self._data["grade_classes"] = selected
            # For backward compat, set grade to first selection's grade
            if selected:
                g, cl = selected[0].split("-")
                self._data["grade"] = int(g)
                self._data["classes"] = [s.split("-")[1] for s in selected]
                self._data["class"] = selected[0].split("-")[1]
            return await self.async_step_school_periods()
        max_g = 6 if self._data["school_level"] == "elementary" else 3
        # Build "학년-반" combo options
        combo_opts = {}
        for g in range(1, max_g + 1):
            for cl in range(1, 21):
                key = f"{g}-{cl}"
                combo_opts[key] = f"{g}학년 {cl}반"
        return self.async_show_form(step_id="school_class", data_schema=vol.Schema({
            vol.Required("grade_classes"): cv.multi_select(combo_opts),
        }))

    async def async_step_school_periods(self, user_input=None) -> FlowResult:
        defaults = {1:"09:00-09:50",2:"10:00-10:50",3:"11:00-11:50",
                     4:"12:00-12:50",5:"13:40-14:30",6:"14:40-15:30",7:"15:40-16:30"}
        if user_input is not None:
            self._data.update(user_input)
            school_data = {k: v for k, v in self._data.items()
                           if k not in (CONF_ENTRY_TYPE, "neis_api_key")}
            entry_data = {CONF_ENTRY_TYPE: ENTRY_SCHOOL,
                          "neis_api_key": self._data["neis_api_key"]}
            return self.async_create_entry(
                title="학교정보", data=entry_data,
                subentries=[{
                    "subentry_type": "school",
                    "title": school_data.get("school_name", "학교"),
                    "data": school_data,
                    "unique_id": f"{school_data['region_code']}_{school_data['school_code']}",
                }])
        schema: dict = {vol.Required("period_1", default=defaults[1]): str}
        for i in range(2, 8):
            schema[vol.Optional(f"period_{i}", default=defaults.get(i, ""))] = str
        schema[vol.Optional("lunch_start", default="12:50")] = str
        schema[vol.Optional("lunch_end", default="13:40")] = str
        return self.async_show_form(step_id="school_periods",
                                    data_schema=vol.Schema(schema))

    # ══════════ 재난정보 ══════════

    async def async_step_disaster(self, user_input=None) -> FlowResult:
        """Step 1: API key + 광역자치단체 선택."""
        from .disaster.api import validate_disaster_api
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = user_input["safety_api_key"]
            if not await validate_disaster_api(api_key):
                errors["base"] = "cannot_connect"
            else:
                self._data = {CONF_ENTRY_TYPE: ENTRY_DISASTER, "safety_api_key": api_key}
                self._region_sido = user_input["sido"]
                self._sgg_names = await _async_fetch_sgg_names(self._region_sido)
                if not self._sgg_names:
                    errors["base"] = "cannot_connect"
                else:
                    return await self.async_step_disaster_sgg()
        return self.async_show_form(step_id="disaster",
            data_schema=vol.Schema({
                vol.Required("safety_api_key"): _password_selector(),
                vol.Required("sido", default="서울특별시"): _sido_selector(),
            }),
            errors=errors)

    async def async_step_disaster_sgg(self, user_input=None) -> FlowResult:
        """Step 2: 기초자치단체 체크리스트 → 시군구별 subentry."""
        import homeassistant.helpers.config_validation as cv
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = user_input.get("sgg_list", [])
            if not selected:
                errors["base"] = "no_selection"
            else:
                sido = self._region_sido
                return self.async_create_entry(
                    title="재난정보",
                    data=self._data,
                    subentries=[
                        {"subentry_type": "region",
                         "title": f"{sido} 전체" if sgg == "전체" else f"{sido} {sgg}",
                         "data": {"sido": sido, "sgg": "" if sgg == "전체" else sgg},
                         "unique_id": f"{sido}_전체" if sgg == "전체" else f"{sido}_{sgg}"}
                        for sgg in selected
                    ])
        labels = {"전체": f"{self._region_sido} 전체 (광역자치단체 전체)",
                  **{s: s for s in self._sgg_names}}
        return self.async_show_form(step_id="disaster_sgg",
            data_schema=vol.Schema({
                vol.Required("sgg_list"): cv.multi_select(labels),
            }),
            errors=errors)

    # ══════════ 안전알림 ══════════

    async def async_step_safety_alert(self, user_input=None) -> FlowResult:
        """Select regions for safety alerts (시도 + 시군구)."""
        errors: dict[str, str] = {}
        sido_map = {
            "1100000000": "서울특별시", "2600000000": "부산광역시",
            "2700000000": "대구광역시", "2800000000": "인천광역시",
            "2900000000": "광주광역시", "3000000000": "대전광역시",
            "3100000000": "울산광역시", "3600000000": "세종특별자치시",
            "4100000000": "경기도", "5100000000": "강원특별자치도",
            "4300000000": "충청북도", "4400000000": "충청남도",
            "5200000000": "전북특별자치도", "4600000000": "전라남도",
            "4700000000": "경상북도", "4800000000": "경상남도",
            "5000000000": "제주특별자치도",
        }
        # 서울 자치구
        seoul_gu = {
            "1111000000": "종로구", "1114000000": "중구", "1117000000": "용산구",
            "1120000000": "성동구", "1121500000": "광진구", "1123000000": "동대문구",
            "1126000000": "중랑구", "1129000000": "성북구", "1130500000": "강북구",
            "1132000000": "도봉구", "1135000000": "노원구", "1138000000": "은평구",
            "1141000000": "서대문구", "1144000000": "마포구", "1147000000": "양천구",
            "1150000000": "강서구", "1153000000": "구로구", "1154500000": "금천구",
            "1156000000": "영등포구", "1159000000": "동작구", "1162000000": "관악구",
            "1165000000": "서초구", "1168000000": "강남구", "1171000000": "송파구",
            "1174000000": "강동구",
        }
        all_regions = {**sido_map, **seoul_gu}
        region_opts = [SelectOptionDict(value=k, label=v) for k, v in all_regions.items()]
        if user_input is not None:
            areas = user_input.get("area_codes", [])
            if not isinstance(areas, list):
                areas = [areas]
            if not areas:
                errors["base"] = "no_selection"
            else:
                region_items = [{"code": c, "name": all_regions.get(c, c)} for c in areas]
                return self.async_create_entry(
                    title="안전알림",
                    data={CONF_ENTRY_TYPE: ENTRY_SAFETY_ALERT, "regions": region_items})
        return self.async_show_form(step_id="safety_alert", data_schema=vol.Schema({
            vol.Required("area_codes"): SelectSelector(
                SelectSelectorConfig(options=region_opts, multiple=True,
                                     mode=SelectSelectorMode.DROPDOWN)),
        }), errors=errors)

    # ══════════ 한전 (KEPCO) ══════════

    async def async_step_kepco(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(
                title=f"한전 ({user_input['username']})",
                data={CONF_ENTRY_TYPE: ENTRY_KEPCO,
                      "username": user_input["username"],
                      "password": user_input["password"]})
        return self.async_show_form(step_id="kepco", data_schema=vol.Schema({
            vol.Required("username"): str,
            vol.Required("password"): _password_selector(),
        }), errors=errors)

    # ══════════ 가스앱 ══════════

    async def async_step_gasapp(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(
                title=f"가스앱 ({user_input['contract_num']})",
                data={CONF_ENTRY_TYPE: ENTRY_GASAPP,
                      "token": user_input["token"],
                      "member_id": user_input["member_id"],
                      "contract_num": user_input["contract_num"]})
        return self.async_show_form(step_id="gasapp", data_schema=vol.Schema({
            vol.Required("token"): _password_selector(),
            vol.Required("member_id"): str,
            vol.Required("contract_num"): str,
        }), errors=errors)

    # ══════════ 아리수 (서울 상수도) ══════════

    async def async_step_arisu(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(
                title=f"아리수 ({user_input['customer_number']})",
                data={CONF_ENTRY_TYPE: ENTRY_ARISU,
                      "customer_number": user_input["customer_number"],
                      "customer_name": user_input["customer_name"]})
        return self.async_show_form(step_id="arisu", data_schema=vol.Schema({
            vol.Required("customer_number"): str,
            vol.Required("customer_name"): str,
        }), errors=errors)

    # ══════════ 약국 ══════════

    async def async_step_pharmacy(self, user_input=None) -> FlowResult:
        """Step 1: API key + 광역자치단체 선택."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data = {CONF_ENTRY_TYPE: ENTRY_PHARMACY,
                          "api_key": user_input["api_key"],
                          "q0": user_input["q0"]}
            self._region_sido = user_input["q0"]
            self._sgg_names = await _async_fetch_sgg_names(self._region_sido)
            if not self._sgg_names:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_pharmacy_sgg()
        return self.async_show_form(
            step_id="pharmacy",
            data_schema=vol.Schema({
                vol.Required("api_key"): _password_selector(),
                vol.Required("q0", default="서울특별시"): _sido_selector(),
            }),
            errors=errors,
        )

    async def async_step_pharmacy_sgg(self, user_input=None) -> FlowResult:
        """Step 2: 기초자치단체 체크리스트 → regions 리스트 (subentry 없이 entry.data에 flat 저장)."""
        import homeassistant.helpers.config_validation as cv
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = user_input.get("sgg_list", [])
            if not selected:
                errors["base"] = "no_selection"
            else:
                sido = self._region_sido
                location_sensors = user_input["location_sensors"]
                location = user_input["location"]
                self._data["regions"] = [
                    {"sido": sido, "sgg": sgg,
                     "location_sensors": location_sensors, "location": dict(location)}
                    for sgg in selected
                ]
                return self.async_create_entry(
                    title=f"약국 정보 - {sido}", data=self._data)
        labels = {s: s for s in self._sgg_names}
        return self.async_show_form(step_id="pharmacy_sgg",
            data_schema=vol.Schema({
                vol.Required("sgg_list"): cv.multi_select(labels),
                **_pharmacy_location_fields(self.hass),
            }),
            errors=errors)




# 기상청 예보구역 격자 좌표

    # ══════════ 에어코리아 ══════════
    async def async_step_airkorea(self, user_input=None) -> FlowResult:
        """Step 1: API key + 광역시도 선택."""
        from .airkorea import STATIONS_BY_SIDO
        air_sido = list(STATIONS_BY_SIDO.keys())
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data = {CONF_ENTRY_TYPE: ENTRY_AIRKOREA,
                          "api_key": user_input["api_key"],
                          "living_api_key": user_input.get("living_api_key", "")}
            self._air_sido = user_input["sido"]
            return await self.async_step_airkorea_select()
        sido_opts = [SelectOptionDict(value=k, label=k) for k in air_sido]
        return self.async_show_form(step_id="airkorea", data_schema=vol.Schema({
            vol.Required("api_key"): _password_selector(),
            vol.Optional("living_api_key", default=""): _password_selector(),
            vol.Required("sido", default="서울"): SelectSelector(
                SelectSelectorConfig(options=sido_opts, mode=SelectSelectorMode.DROPDOWN)),
        }), errors=errors)

    async def async_step_airkorea_select(self, user_input=None) -> FlowResult:
        """Step 2: 측정소(시군구) 복수 선택."""
        import homeassistant.helpers.config_validation as cv
        from .airkorea import STATIONS_BY_SIDO
        if user_input is not None:
            selected = user_input.get("stations", [])
            self._data["sido"] = self._air_sido
            return self.async_create_entry(
                title="에어코리아", data=self._data,
                subentries=[
                    {"subentry_type": "station",
                     "title": f"{self._air_sido} {s}",
                     "data": {"sido": self._air_sido, "stationName": s},
                     "unique_id": f"{self._air_sido}_{s}"}
                    for s in selected
                ])
        station_list = STATIONS_BY_SIDO.get(self._air_sido, [])
        labels = {s: s for s in station_list}
        return self.async_show_form(step_id="airkorea_select", data_schema=vol.Schema({
            vol.Required("stations", default=station_list[:3]): cv.multi_select(labels),
        }))

    # ══════════ 기상청 날씨예보 ══════════
    async def async_step_kma_weather(self, user_input=None) -> FlowResult:
        """Step 1: API key + 광역시도 선택."""
        from .kma_weather import SIDO_LIST
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data = {CONF_ENTRY_TYPE: ENTRY_KMA_WEATHER,
                          "api_key": user_input["api_key"]}
            self._kma_sido = user_input["sido"]
            return await self.async_step_kma_weather_sgg()
        sido_opts = [SelectOptionDict(value=k, label=k) for k in SIDO_LIST.keys()]
        return self.async_show_form(step_id="kma_weather", data_schema=vol.Schema({
            vol.Required("api_key"): _password_selector(),
            vol.Required("sido"): SelectSelector(
                SelectSelectorConfig(options=sido_opts,
                                     mode=SelectSelectorMode.DROPDOWN)),
        }), errors=errors)

    async def async_step_kma_weather_sgg(self, user_input=None) -> FlowResult:
        """Step 2: 기초자치단체 + O3/UV 측정소 선택."""
        import homeassistant.helpers.config_validation as cv
        from .kma_weather import SIDO_LIST
        from .airkorea import STATIONS_BY_SIDO, SIDO_AREA_CODE
        sgg_map = SIDO_LIST.get(self._kma_sido, {})
        if user_input is not None:
            selected = user_input.get("regions", [])
            station = user_input.get("air_station") or "none"
            self._data["air_station"] = "" if station == "none" else station
            # 에어코리아 테이블은 축약 시도명("서울")이 키다.
            self._data["area_no"] = SIDO_AREA_CODE.get(
                sido_short_name(self._kma_sido), "")
            self._data["sido"] = self._kma_sido
            return self.async_create_entry(
                title="기상청 날씨예보", data=self._data,
                subentries=[
                    {"subentry_type": "region",
                     "title": f"{self._kma_sido} {r}",
                     "data": {"sido": self._kma_sido, "name": r,
                              "nx": sgg_map[r][0], "ny": sgg_map[r][1]},
                     "unique_id": f"{self._kma_sido}_{r}"}
                    for r in selected if r in sgg_map
                ])
        labels = {k: k for k in sgg_map.keys()}
        air_stations = STATIONS_BY_SIDO.get(sido_short_name(self._kma_sido), [])
        # "" is not usable as a select value in the frontend (it reads as
        # "no selection" and locks the field) — use a "none" sentinel.
        air_opts = [SelectOptionDict(value="none", label="사용 안 함 (날씨만)")]
        air_opts += [SelectOptionDict(value=s, label=f"{s} (O₃/UV 포함)")
                     for s in air_stations[:30]]
        return self.async_show_form(step_id="kma_weather_sgg", data_schema=vol.Schema({
            vol.Required("regions"): cv.multi_select(labels),
            vol.Required("air_station", default="none"): SelectSelector(
                SelectSelectorConfig(options=air_opts,
                                     mode=SelectSelectorMode.DROPDOWN)),
        }))

    # ══════════ 지진 정보 ══════════
    async def async_step_earthquake(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            loc = user_input["location"]
            return self.async_create_entry(title="지진 정보",
                data={CONF_ENTRY_TYPE: ENTRY_EARTHQUAKE,
                      "api_key": user_input["api_key"],
                      "home_latitude": loc["latitude"],
                      "home_longitude": loc["longitude"],
                      "radius_km": loc["radius"] / 1000,
                      "min_magnitude": user_input.get("min_magnitude", 3.0)})
        return self.async_show_form(step_id="earthquake", data_schema=vol.Schema({
            vol.Required("api_key"): _password_selector(),
            vol.Required("location", default={
                "latitude": self.hass.config.latitude,
                "longitude": self.hass.config.longitude,
                "radius": 200000,
            }): LocationSelector(LocationSelectorConfig(radius=True)),
            vol.Optional("min_magnitude", default=3.0): vol.Coerce(float),
        }), errors=errors)

    # ══════════ 재인증 (reauth) ══════════

    async def async_step_reauth(self, entry_data) -> FlowResult:
        etype = entry_data.get(CONF_ENTRY_TYPE)
        if etype == ENTRY_KEPCO:
            return await self.async_step_reauth_kepco()
        if etype == ENTRY_GASAPP:
            return await self.async_step_reauth_gasapp()
        return self.async_abort(reason="reauth_not_supported")

    async def async_step_reauth_kepco(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates={"username": user_input["username"],
                              "password": user_input["password"]})
        return self.async_show_form(step_id="reauth_kepco", data_schema=vol.Schema({
            vol.Required("username"): str,
            vol.Required("password"): _password_selector(),
        }))

    async def async_step_reauth_gasapp(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates={"token": user_input["token"],
                              "member_id": user_input["member_id"],
                              "contract_num": user_input["contract_num"]})
        return self.async_show_form(step_id="reauth_gasapp", data_schema=vol.Schema({
            vol.Required("token"): _password_selector(),
            vol.Required("member_id"): str,
            vol.Required("contract_num"): str,
        }))

        # ══════════ Options Flow =════════

    @staticmethod
    def async_get_options_flow(config_entry):
        return KRPublicDataOptionsFlow(config_entry)

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry):
        etype = config_entry.data.get(CONF_ENTRY_TYPE)
        if etype == ENTRY_FUEL:
            return {"fuel_region": FuelRegionSubentryFlowHandler}
        if etype == ENTRY_DISASTER:
            return {"region": DisasterRegionSubentryFlowHandler}
        if etype == ENTRY_SCHOOL:
            return {"school": SchoolSubentryFlowHandler}
        if etype == ENTRY_KMA_WEATHER:
            return {"region": KmaRegionSubentryFlowHandler}
        if etype == ENTRY_WEATHER:
            return {"area": WarningAreaSubentryFlowHandler}
        if etype == ENTRY_AIRKOREA:
            return {"station": StationSubentryFlowHandler}
        if etype == ENTRY_TRANSIT:
            return {"subway_station": SubwayStationSubentryFlowHandler}
        if etype == ENTRY_BUS:
            return {"city_bus_stop": CityBusStopSubentryFlowHandler,
                    "intercity_bus_route": IntercityBusRouteSubentryFlowHandler}
        return {}


class FuelRegionSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Add one 시도 region (+ 유종 목록) to a fuel entry."""

    async def async_step_user(self, user_input=None):
        from .fuel import SIDO_CODES, FUEL_TYPES
        errors: dict[str, str] = {}
        sido_options = [SelectOptionDict(value=k, label=v) for k, v in SIDO_CODES.items()]
        fuel_options = [SelectOptionDict(value=k, label=v) for k, v in FUEL_TYPES.items()]
        if user_input is not None:
            sido = user_input["sido_code"]
            fuels = user_input.get("fuel_codes", [])
            entry = self._get_entry()
            for sub in entry.subentries.values():
                if sub.data.get("sido_code") == sido:
                    return self.async_abort(reason="already_configured")
            if not fuels:
                errors["base"] = "no_selection"
            else:
                return self.async_create_entry(
                    title=SIDO_CODES.get(sido, sido),
                    data={"sido_code": sido, "fuel_codes": fuels},
                    unique_id=sido)
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("sido_code", default="01"): SelectSelector(
                SelectSelectorConfig(options=sido_options, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required("fuel_codes"): SelectSelector(
                SelectSelectorConfig(options=fuel_options, multiple=True,
                                     mode=SelectSelectorMode.DROPDOWN)),
        }), errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        """이미 등록된 지역의 유종 목록을 수정 (지역을 다시 추가하면 already_configured로 막히므로)."""
        from .fuel import FUEL_TYPES
        subentry = self._get_reconfigure_subentry()
        d = subentry.data
        fuel_options = [SelectOptionDict(value=k, label=v) for k, v in FUEL_TYPES.items()]
        errors: dict[str, str] = {}
        if user_input is not None:
            fuels = user_input.get("fuel_codes", [])
            if not fuels:
                errors["base"] = "no_selection"
            else:
                return self.async_update_and_abort(
                    self._get_entry(), subentry, data_updates={"fuel_codes": fuels})
        return self.async_show_form(step_id="reconfigure", data_schema=vol.Schema({
            vol.Required("fuel_codes", default=d.get("fuel_codes", [])): SelectSelector(
                SelectSelectorConfig(options=fuel_options, multiple=True,
                                     mode=SelectSelectorMode.DROPDOWN)),
        }), errors=errors)


class DisasterRegionSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Add one 기초자치단체 region — or a whole 광역자치단체 — to a disaster entry."""

    def __init__(self):
        self._sido = ""
        self._sgg_names: list[str] = []

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            self._sido = user_input["sido"]
            self._sgg_names = await _async_fetch_sgg_names(self._sido)
            if not self._sgg_names:
                errors["base"] = "cannot_connect"
            else:
                return await self.async_step_sgg()
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("sido", default="서울특별시"): _sido_selector(),
        }), errors=errors)

    async def async_step_sgg(self, user_input=None):
        if user_input is not None:
            sgg = user_input["sgg"]
            whole = sgg == "전체"
            stored_sgg = "" if whole else sgg
            entry = self._get_entry()
            for sub in entry.subentries.values():
                if (sub.data.get("sido") == self._sido
                        and sub.data.get("sgg") == stored_sgg):
                    return self.async_abort(reason="already_configured")
            return self.async_create_entry(
                title=f"{self._sido} 전체" if whole else f"{self._sido} {sgg}",
                data={"sido": self._sido, "sgg": stored_sgg},
                unique_id=f"{self._sido}_전체" if whole else f"{self._sido}_{sgg}")
        sgg_opts = [SelectOptionDict(value="전체",
                                     label=f"{self._sido} 전체 (광역자치단체 전체)")]
        sgg_opts += [SelectOptionDict(value=s, label=s) for s in self._sgg_names]
        return self.async_show_form(step_id="sgg", data_schema=vol.Schema({
            vol.Required("sgg"): SelectSelector(
                SelectSelectorConfig(options=sgg_opts,
                                     mode=SelectSelectorMode.DROPDOWN)),
        }))


class KmaRegionSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Add one 시군구 forecast region to a kma_weather entry."""

    def __init__(self):
        self._sido = ""

    async def async_step_user(self, user_input=None):
        from .kma_weather import SIDO_LIST
        if user_input is not None:
            self._sido = user_input["sido"]
            return await self.async_step_sgg()
        sido_opts = [SelectOptionDict(value=k, label=k) for k in SIDO_LIST]
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("sido", default="서울특별시"): SelectSelector(
                SelectSelectorConfig(options=sido_opts,
                                     mode=SelectSelectorMode.DROPDOWN)),
        }))

    async def async_step_sgg(self, user_input=None):
        from .kma_weather import SIDO_LIST
        sgg_map = SIDO_LIST.get(self._sido, {})
        if user_input is not None:
            name = user_input["sgg"]
            entry = self._get_entry()
            for sub in entry.subentries.values():
                if (sub.data.get("sido") == self._sido
                        and sub.data.get("name") == name):
                    return self.async_abort(reason="already_configured")
            nx, ny = sgg_map[name]
            return self.async_create_entry(
                title=f"{self._sido} {name}",
                data={"sido": self._sido, "name": name, "nx": nx, "ny": ny},
                unique_id=f"{self._sido}_{name}")
        sgg_opts = [SelectOptionDict(value=s, label=s) for s in sgg_map]
        return self.async_show_form(step_id="sgg", data_schema=vol.Schema({
            vol.Required("sgg"): SelectSelector(
                SelectSelectorConfig(options=sgg_opts,
                                     mode=SelectSelectorMode.DROPDOWN)),
        }))


class WarningAreaSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Add one 특보구역 to a weather_warning entry."""

    async def async_step_user(self, user_input=None):
        from .weather import AREA_CODES
        if user_input is not None:
            code = user_input["area_code"]
            entry = self._get_entry()
            for sub in entry.subentries.values():
                if sub.data.get("area_code") == code:
                    return self.async_abort(reason="already_configured")
            return self.async_create_entry(
                title=AREA_CODES.get(code, code),
                data={"area_code": code},
                unique_id=code)
        area_opts = [SelectOptionDict(value=c, label=n)
                     for c, n in AREA_CODES.items()]
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("area_code"): SelectSelector(
                SelectSelectorConfig(options=area_opts,
                                     mode=SelectSelectorMode.DROPDOWN)),
        }))


class StationSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Add one 측정소 to an airkorea entry."""

    def __init__(self):
        self._sido = ""

    async def async_step_user(self, user_input=None):
        from .airkorea import STATIONS_BY_SIDO
        if user_input is not None:
            self._sido = user_input["sido"]
            return await self.async_step_station()
        sido_opts = [SelectOptionDict(value=k, label=k) for k in STATIONS_BY_SIDO]
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("sido", default="서울"): SelectSelector(
                SelectSelectorConfig(options=sido_opts,
                                     mode=SelectSelectorMode.DROPDOWN)),
        }))

    async def async_step_station(self, user_input=None):
        from .airkorea import STATIONS_BY_SIDO
        if user_input is not None:
            station = user_input["station"]
            entry = self._get_entry()
            for sub in entry.subentries.values():
                if sub.data.get("stationName") == station:
                    return self.async_abort(reason="already_configured")
            return self.async_create_entry(
                title=f"{self._sido} {station}",
                data={"sido": self._sido, "stationName": station},
                unique_id=f"{self._sido}_{station}")
        station_opts = [SelectOptionDict(value=s, label=s)
                        for s in STATIONS_BY_SIDO.get(self._sido, [])]
        return self.async_show_form(step_id="station", data_schema=vol.Schema({
            vol.Required("station"): SelectSelector(
                SelectSelectorConfig(options=station_opts,
                                     mode=SelectSelectorMode.DROPDOWN)),
        }))


class SubwayStationSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Add one 역 to a subway entry."""

    def __init__(self):
        self._station = ""
        self._lines_found: list[str] = []

    async def async_step_user(self, user_input=None):
        from .transit.subway_api import discover_lines
        if user_input is not None:
            station = user_input["station"].strip()
            entry = self._get_entry()
            for sub in entry.subentries.values():
                if sub.data.get("station") == station:
                    return self.async_abort(reason="already_configured")
            self._station = station
            try:
                session = async_get_clientsession(self.hass)
                self._lines_found = await discover_lines(
                    session, entry.data["seoul_api_key"], station)
            except Exception as e:
                _LOGGER.warning("Subway line discovery failed: %s", e)
                self._lines_found = []
            return await self.async_step_lines()
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("station"): str,
        }))

    async def async_step_lines(self, user_input=None):
        import homeassistant.helpers.config_validation as cv
        from .transit import SUBWAY_LINES
        errors: dict[str, str] = {}
        if user_input is not None:
            lines = user_input.get("lines", [])
            if not lines:
                errors["base"] = "no_selection"
            else:
                return self.async_create_entry(
                    title=f"{self._station}역",
                    data={"station": self._station, "lines": lines},
                    unique_id=self._station)
        return self.async_show_form(step_id="lines", data_schema=vol.Schema({
            vol.Required("lines", default=self._lines_found):
                cv.multi_select(SUBWAY_LINES),
        }), errors=errors)


class CityBusStopSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Add one 정류장 to a bus entry (TAGO 전국 또는 서울, 한 흐름에서 도시로 구분)."""

    def __init__(self):
        self._city_code: str = ""
        self._candidates: list[dict] = []
        self._node_id = ""
        self._node_name = ""
        self._routes_found: list[dict] = []

    async def async_step_user(self, user_input=None):
        from .bus import CITY_CODES
        errors: dict[str, str] = {}
        if user_input is not None:
            city_code = user_input["city_code"]
            name = user_input["name"].strip()
            entry = self._get_entry()
            session = async_get_clientsession(self.hass)
            try:
                self._candidates = await _search_bus_stops(
                    session, entry.data.get("api_key") or entry.data.get("service_key", ""),
                    city_code, name)
            except Exception as e:
                _LOGGER.warning("Bus stop search failed: %s", e)
                self._candidates = []
            if not self._candidates:
                errors["base"] = "no_stations_found"
            else:
                self._city_code = city_code
                return await self.async_step_select()
        city_opts = _bus_city_options(CITY_CODES)
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("city_code"): SelectSelector(
                SelectSelectorConfig(options=city_opts, mode=SelectSelectorMode.DROPDOWN)),
            vol.Required("name"): str,
        }), errors=errors)

    async def async_step_select(self, user_input=None):
        if user_input is not None:
            node_id = user_input["node_id"]
            match = next((c for c in self._candidates if c["id"] == node_id), None)
            if match:
                entry = self._get_entry()
                for sub in entry.subentries.values():
                    if sub.data.get("nodeId") == node_id:
                        return self.async_abort(reason="already_configured")
                self._node_id = node_id
                self._node_name = match["name"]
                session = async_get_clientsession(self.hass)
                try:
                    self._routes_found = await _bus_stop_routes(
                        session, entry.data.get("api_key") or entry.data.get("service_key", ""),
                        self._city_code, node_id)
                except Exception as e:
                    _LOGGER.warning("Bus route discovery failed: %s", e)
                    self._routes_found = []
                return await self.async_step_routes()
        stop_opts = [SelectOptionDict(value=c["id"], label=f"{c['name']} ({c['hint']})")
                    for c in self._candidates]
        return self.async_show_form(step_id="select", data_schema=vol.Schema({
            vol.Required("node_id"): SelectSelector(
                SelectSelectorConfig(options=stop_opts, mode=SelectSelectorMode.DROPDOWN)),
        }))

    async def async_step_routes(self, user_input=None):
        import homeassistant.helpers.config_validation as cv
        from .bus import SEOUL_CITY_CODE
        errors: dict[str, str] = {}
        route_map = {r["id"]: r["label"] for r in self._routes_found}
        if user_input is not None:
            selected = user_input.get("routes", [])
            if not selected:
                errors["base"] = "no_selection"
            else:
                by_id = {r["id"]: r for r in self._routes_found}
                routes = [{"routeId": rid, "routeNo": by_id[rid]["routeNo"]} for rid in selected]
                source = "seoul" if self._city_code == SEOUL_CITY_CODE else "tago"
                return self.async_create_entry(
                    title=f"{self._node_name} 정류장",
                    data={"source": source, "cityCode": self._city_code,
                          "nodeId": self._node_id, "nodeName": self._node_name,
                          "routes": routes},
                    unique_id=self._node_id)
        return self.async_show_form(step_id="routes", data_schema=vol.Schema({
            vol.Required("routes", default=list(route_map)): cv.multi_select(route_map),
        }), errors=errors)


class IntercityBusRouteSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Add one 시외/고속버스 구간(출발-도착 터미널)을 bus entry에 추가.

    고속버스/시외버스는 별도 선택지로 노출하지 않는다 — 터미널 이름으로
    검색하면 두 시스템을 모두 능동적으로 조회해 실제 배차가 있는 조합만
    사용한다("동서울"이 고속버스 쪽엔 4개, 시외버스 쪽엔 1개 있어도
    사용자는 그 차이를 알 필요가 없다는 피드백 반영).
    """

    def __init__(self):
        self._dep_names: list[str] = []
        self._arr_names: list[str] = []
        self._dep_name = ""
        self._arr_name = ""
        self._queries: list[dict] = []
        self._grades_found: list[str] = []
        self._retry_error: str | None = None

    async def async_step_user(self, user_input=None):
        """출발터미널 검색 (고속/시외 구분 없이 양쪽 다 검색)."""
        from .bus.intercity_api import search_terminals
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input["dep_name"].strip()
            entry = self._get_entry()
            api_key = entry.data.get("api_key") or entry.data.get("service_key", "")
            session = async_get_clientsession(self.hass)
            names: set[str] = set()
            for source in ("express", "intercity"):
                try:
                    candidates = await search_terminals(session, api_key, source, name)
                except Exception as e:
                    _LOGGER.warning("Terminal search failed (%s): %s", source, e)
                    candidates = []
                names.update(c["terminalNm"] for c in candidates)
            self._dep_names = sorted(names)
            if not self._dep_names:
                errors["base"] = "no_stations_found"
            else:
                return await self.async_step_dep_select()
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("dep_name"): str,
        }), errors=errors)

    async def async_step_dep_select(self, user_input=None):
        """출발터미널 선택 → 도착터미널 검색."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._dep_name = user_input["dep_name"]
            return await self.async_step_arr_search()
        if self._retry_error:
            errors["base"] = self._retry_error
            self._retry_error = None
        opts = [SelectOptionDict(value=n, label=n) for n in self._dep_names]
        return self.async_show_form(step_id="dep_select", data_schema=vol.Schema({
            vol.Required("dep_name"): SelectSelector(
                SelectSelectorConfig(options=opts, mode=SelectSelectorMode.DROPDOWN)),
        }), errors=errors)

    async def async_step_arr_search(self, user_input=None):
        """도착터미널 검색 (고속/시외 구분 없이 양쪽 다 검색)."""
        from .bus.intercity_api import search_terminals
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input["arr_name"].strip()
            entry = self._get_entry()
            api_key = entry.data.get("api_key") or entry.data.get("service_key", "")
            session = async_get_clientsession(self.hass)
            names: set[str] = set()
            for source in ("express", "intercity"):
                try:
                    candidates = await search_terminals(session, api_key, source, name)
                except Exception as e:
                    _LOGGER.warning("Terminal search failed (%s): %s", source, e)
                    candidates = []
                names.update(c["terminalNm"] for c in candidates)
            self._arr_names = sorted(names)
            if not self._arr_names:
                errors["base"] = "no_stations_found"
            else:
                return await self.async_step_arr_select()
        if self._retry_error:
            errors["base"] = self._retry_error
            self._retry_error = None
        return self.async_show_form(step_id="arr_search", data_schema=vol.Schema({
            vol.Required("arr_name"): str,
        }), errors=errors)

    async def async_step_arr_select(self, user_input=None):
        """도착터미널 선택 → 고속/시외 양쪽에서 실제 배차·등급 자동 감지."""
        from .bus.intercity_api import discover_queries
        if user_input is not None:
            arr_name = user_input["arr_name"]
            entry = self._get_entry()
            for sub in entry.subentries.values():
                if (sub.data.get("depTerminalName") == self._dep_name
                        and sub.data.get("arrTerminalName") == arr_name):
                    return self.async_abort(reason="already_configured")
            self._arr_name = arr_name
            api_key = entry.data.get("api_key") or entry.data.get("service_key", "")
            session = async_get_clientsession(self.hass)
            try:
                self._queries, dispatches = await discover_queries(
                    session, api_key, self._dep_name, arr_name)
            except Exception as e:
                _LOGGER.warning("Dispatch discovery failed: %s", e)
                self._queries, dispatches = [], []
            # "source:gradeNm" composite — 고속버스/시외버스는 결제 플랫폼이
            # 달라 등급이 같은 이름이어도 합치면 안 된다.
            self._grades_found = sorted({
                f"{d['_source']}:{d['gradeNm']}" for d in dispatches if d.get("gradeNm")
            })
            if not self._grades_found:
                # 두 시스템 다 뒤져도 이 이름 조합엔 배차가 없음 — 도착터미널을
                # 다시 검색해보게 한다(출발은 이미 검증된 이름이라 유지).
                self._retry_error = "no_dispatch_found"
                return await self.async_step_arr_search()
            return await self.async_step_grades()
        opts = [SelectOptionDict(value=n, label=n) for n in self._arr_names]
        return self.async_show_form(step_id="arr_select", data_schema=vol.Schema({
            vol.Required("arr_name"): SelectSelector(
                SelectSelectorConfig(options=opts, mode=SelectSelectorMode.DROPDOWN)),
        }))

    async def async_step_grades(self, user_input=None):
        """등급 선택 (당일 실제 배차에서 감지된 등급이 기본값, 고속/시외 표시) → 구간 subentry."""
        import homeassistant.helpers.config_validation as cv
        errors: dict[str, str] = {}

        def _grade_label(grade_key: str) -> str:
            source, grade = grade_key.split(":", 1)
            return f"{grade} ({'고속버스' if source == 'express' else '시외버스'})"

        grade_map = {g: _grade_label(g) for g in self._grades_found}
        if user_input is not None:
            selected = user_input.get("grades", [])
            if not selected:
                errors["base"] = "no_selection"
            else:
                return self.async_create_entry(
                    title=f"{self._dep_name}→{self._arr_name}",
                    data={"depTerminalName": self._dep_name, "arrTerminalName": self._arr_name,
                          "queries": self._queries, "grades": selected},
                    unique_id=f"{self._dep_name}_{self._arr_name}")
        return self.async_show_form(step_id="grades", data_schema=vol.Schema({
            vol.Required("grades", default=list(grade_map)): cv.multi_select(grade_map),
        }), errors=errors)


class SchoolSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Add another school to a school entry, or edit an existing one's 학년/반."""

    def __init__(self):
        self._data: dict = {}

    async def async_step_user(self, user_input=None):
        from .school import SCHOOL_LEVELS
        if user_input is not None:
            self._data = {"school_level": user_input["school_level"]}
            return await self.async_step_search()
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("school_level", default="elementary"): vol.In(SCHOOL_LEVELS),
        }))

    async def async_step_search(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            entry = self._get_entry()
            api_key = entry.data.get("neis_api_key") or entry.data.get("api_key", "")
            session = async_get_clientsession(self.hass)
            from .school.api import NeisApiClient
            from .school.parser import parse_school_info
            c = NeisApiClient(session, api_key)
            if "school_search" in user_input:
                schools = await c.search_school(user_input["school_search"])
                if not schools:
                    errors["school_search"] = "no_schools_found"
                else:
                    opts = {
                        f"{s['ATPT_OFCDC_SC_CODE']}_{s['SD_SCHUL_CODE']}":
                        f"{s['SCHUL_NM']} ({s.get('ORG_RDNMA', '')})"
                        for s in schools[:10]}
                    return self.async_show_form(step_id="search",
                        data_schema=vol.Schema({vol.Required("selected_school"): vol.In(opts)}))
            elif "selected_school" in user_input:
                rc, sc = user_input["selected_school"].split("_")
                for sub in entry.subentries.values():
                    if sub.data.get("region_code") == rc and sub.data.get("school_code") == sc:
                        return self.async_abort(reason="already_configured")
                info = await c.get_school_info(rc, sc)
                if info:
                    self._data.update(parse_school_info(info))
                    return await self.async_step_class()
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="search",
            data_schema=vol.Schema({vol.Required("school_search"): str}),
            errors=errors)

    async def async_step_class(self, user_input=None):
        import homeassistant.helpers.config_validation as cv
        if user_input is not None:
            selected = user_input.get("grade_classes", [])
            self._data["grade_classes"] = selected
            if selected:
                g, cl = selected[0].split("-")
                self._data["grade"] = int(g)
                self._data["classes"] = [s.split("-")[1] for s in selected]
                self._data["class"] = selected[0].split("-")[1]
            return await self.async_step_periods()
        max_g = 6 if self._data["school_level"] == "elementary" else 3
        combo_opts = {}
        for g in range(1, max_g + 1):
            for cl in range(1, 21):
                combo_opts[f"{g}-{cl}"] = f"{g}학년 {cl}반"
        return self.async_show_form(step_id="class", data_schema=vol.Schema({
            vol.Required("grade_classes"): cv.multi_select(combo_opts),
        }))

    async def async_step_periods(self, user_input=None):
        defaults = {1: "09:00-09:50", 2: "10:00-10:50", 3: "11:00-11:50",
                    4: "12:00-12:50", 5: "13:40-14:30", 6: "14:40-15:30", 7: "15:40-16:30"}
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title=self._data.get("school_name", "학교"),
                data=self._data,
                unique_id=f"{self._data['region_code']}_{self._data['school_code']}")
        schema: dict = {vol.Required("period_1", default=defaults[1]): str}
        for i in range(2, 8):
            schema[vol.Optional(f"period_{i}", default=defaults.get(i, ""))] = str
        schema[vol.Optional("lunch_start", default="12:50")] = str
        schema[vol.Optional("lunch_end", default="13:40")] = str
        return self.async_show_form(step_id="periods", data_schema=vol.Schema(schema))

    async def async_step_reconfigure(self, user_input=None):
        """Edit an existing school's 학년/반 selection."""
        import homeassistant.helpers.config_validation as cv
        subentry = self._get_reconfigure_subentry()
        d = subentry.data
        if user_input is not None:
            selected = user_input.get("grade_classes", [])
            updates = {"grade_classes": selected}
            if selected:
                g, cl = selected[0].split("-")
                updates["grade"] = int(g)
                updates["classes"] = [s.split("-")[1] for s in selected]
                updates["class"] = selected[0].split("-")[1]
            return self.async_update_and_abort(
                self._get_entry(), subentry, data_updates=updates)
        max_g = 6 if d.get("school_level") == "elementary" else 3
        combo_opts = {}
        for g in range(1, max_g + 1):
            for cl in range(1, 21):
                combo_opts[f"{g}-{cl}"] = f"{g}학년 {cl}반"
        return self.async_show_form(step_id="reconfigure", data_schema=vol.Schema({
            vol.Required("grade_classes", default=d.get("grade_classes", [])):
                cv.multi_select(combo_opts),
        }))


class KRPublicDataOptionsFlow(config_entries.OptionsFlow):
    """Handle options for reconfiguration."""

    def __init__(self, config_entry):
        self._entry = config_entry
        self._pharmacy_region_idx: int | None = None

    async def async_step_init(self, user_input=None):
        """Main options step - show editable fields based on entry type."""
        etype = self._entry.data.get(CONF_ENTRY_TYPE)

        if etype == ENTRY_PHARMACY:
            return await self.async_step_pharmacy_options(user_input)

        if user_input is not None:
            if user_input.get("air_station") == "none":
                user_input["air_station"] = ""
            if etype == ENTRY_EARTHQUAKE and "location" in user_input:
                loc = user_input.pop("location")
                user_input["home_latitude"] = loc["latitude"]
                user_input["home_longitude"] = loc["longitude"]
                user_input["radius_km"] = loc["radius"] / 1000
            # Merge new options into data
            new_data = {**self._entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            return self.async_create_entry(title="", data=user_input)

        schema = self._build_schema(etype)
        if schema is None:
            return self.async_abort(reason="no_options")

        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_pharmacy_options(self, user_input=None):
        """약국: API 키 편집. 지역이 하나면 그 지역의 위치 센서 설정도 같은 화면에서 편집."""
        d = self._entry.data
        regions = d.get("regions", [])
        if user_input is not None:
            new_data = {**d, "api_key": user_input["api_key"]}
            if len(regions) == 1:
                new_data["regions"] = [{**regions[0],
                                        "location_sensors": user_input["location_sensors"],
                                        "location": dict(user_input["location"])}]
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            if len(regions) > 1:
                self._pharmacy_region_idx = int(user_input["region"])
                return await self.async_step_pharmacy_region_edit()
            return self.async_create_entry(title="", data={})

        schema = {vol.Required("api_key", default=d.get("api_key", "")): _password_selector()}
        if len(regions) == 1:
            schema.update(_pharmacy_location_fields(self.hass, regions[0]))
        elif len(regions) > 1:
            region_opts = [
                SelectOptionDict(value=str(i), label=f"{r.get('sido', '')} {r.get('sgg', '')}")
                for i, r in enumerate(regions)
            ]
            schema[vol.Required("region", default="0")] = SelectSelector(
                SelectSelectorConfig(options=region_opts, mode=SelectSelectorMode.DROPDOWN))
        return self.async_show_form(step_id="pharmacy_options", data_schema=vol.Schema(schema))

    async def async_step_pharmacy_region_edit(self, user_input=None):
        """다중 지역 엔트리에서, 고른 지역의 위치 센서 설정(location_sensors/radius) 편집."""
        regions = self._entry.data.get("regions", [])
        idx = self._pharmacy_region_idx
        region = regions[idx]
        if user_input is not None:
            new_regions = list(regions)
            new_regions[idx] = {**region,
                                "location_sensors": user_input["location_sensors"],
                                "location": dict(user_input["location"])}
            new_data = {**self._entry.data, "regions": new_regions}
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="pharmacy_region_edit",
            data_schema=vol.Schema(_pharmacy_location_fields(self.hass, region)))

    def _build_schema(self, etype):
        d = self._entry.data

        if etype == ENTRY_WEATHER:
            if self._entry.subentries:
                # 특보구역은 subentry로 관리 — 여기서는 키만 편집.
                return vol.Schema({
                    vol.Required("api_key", default=d.get("api_key", "")): _password_selector(),
                })
            from .weather import AREA_CODES
            area_options = [SelectOptionDict(value=c, label=n) for c, n in AREA_CODES.items()]
            return vol.Schema({
                vol.Required("api_key", default=d.get("api_key", "")): _password_selector(),
                vol.Required("area_codes", default=d.get("area_codes", [])): SelectSelector(
                    SelectSelectorConfig(options=area_options, multiple=True,
                                         mode=SelectSelectorMode.DROPDOWN)),
            })

        elif etype == ENTRY_TRANSIT:
            return vol.Schema({
                vol.Optional("seoul_api_key", default=d.get("seoul_api_key", "")): _password_selector(),
            })

        elif etype == ENTRY_FUEL:
            if self._entry.subentries:
                # 지역/유종은 fuel_region subentry에서 편집 — 여기서는 키만 편집.
                return vol.Schema({
                    vol.Required("opinet_api_key",
                                 default=d.get("opinet_api_key") or d.get("api_key", "")):
                        _password_selector(),
                })
            from .fuel import SIDO_CODES, FUEL_TYPES
            sido_opts = [SelectOptionDict(value=k, label=v) for k, v in SIDO_CODES.items()]
            fuel_opts = [SelectOptionDict(value=k, label=v) for k, v in FUEL_TYPES.items()]
            cur_sidos = list(set(c["sido_code"] for c in d.get("configs", [])))
            cur_fuels = list(set(c["fuel_code"] for c in d.get("configs", [])))
            return vol.Schema({
                vol.Required("opinet_api_key",
                             default=d.get("opinet_api_key") or d.get("api_key", "")):
                    _password_selector(),
                vol.Required("sido_codes", default=cur_sidos): SelectSelector(
                    SelectSelectorConfig(options=sido_opts, multiple=True,
                                         mode=SelectSelectorMode.DROPDOWN)),
                vol.Required("fuel_codes", default=cur_fuels): SelectSelector(
                    SelectSelectorConfig(options=fuel_opts, multiple=True,
                                         mode=SelectSelectorMode.DROPDOWN)),
            })

        elif etype == ENTRY_SCHOOL:
            if self._entry.subentries:
                # 학교별 학년/반은 school subentry에서 편집 — 여기서는 키만 편집.
                return vol.Schema({
                    vol.Required("neis_api_key",
                                 default=d.get("neis_api_key") or d.get("api_key", "")):
                        _password_selector(),
                })
            import homeassistant.helpers.config_validation as cv
            max_g = 6 if d.get("school_level") == "elementary" else 3
            combo_opts = {}
            for g in range(1, max_g + 1):
                for cl in range(1, 21):
                    combo_opts[f"{g}-{cl}"] = f"{g}학년 {cl}반"
            cur = d.get("grade_classes", [])
            return vol.Schema({
                vol.Required("neis_api_key",
                             default=d.get("neis_api_key") or d.get("api_key", "")):
                    _password_selector(),
                vol.Required("grade_classes", default=cur): cv.multi_select(combo_opts),
            })

        elif etype == ENTRY_DISASTER:
            return vol.Schema({
                vol.Required("safety_api_key",
                             default=d.get("safety_api_key") or d.get("api_key", "")):
                    _password_selector(),
            })

        elif etype == ENTRY_EARTHQUAKE:
            return vol.Schema({
                vol.Required("api_key", default=d.get("api_key", "")): _password_selector(),
                vol.Required("location", default={
                    "latitude": d.get("home_latitude", self.hass.config.latitude),
                    "longitude": d.get("home_longitude", self.hass.config.longitude),
                    "radius": d.get("radius_km", 200) * 1000,
                }): LocationSelector(LocationSelectorConfig(radius=True)),
                vol.Optional("min_magnitude", default=d.get("min_magnitude", 3.0)): vol.Coerce(float),
            })

        elif etype == ENTRY_SAFETY_ALERT:
            sido_map = {
                "1100000000": "서울특별시", "2600000000": "부산광역시",
                "2700000000": "대구광역시", "2800000000": "인천광역시",
                "2900000000": "광주광역시", "3000000000": "대전광역시",
                "3100000000": "울산광역시", "3600000000": "세종특별자치시",
                "4100000000": "경기도", "5100000000": "강원특별자치도",
                "4300000000": "충청북도", "4400000000": "충청남도",
                "5200000000": "전북특별자치도", "4600000000": "전라남도",
                "4700000000": "경상북도", "4800000000": "경상남도",
                "5000000000": "제주특별자치도",
            }
            cur_codes = [r["code"] for r in d.get("regions", [])]
            opts = [SelectOptionDict(value=k, label=v) for k, v in sido_map.items()]
            return vol.Schema({
                vol.Required("area_codes", default=cur_codes): SelectSelector(
                    SelectSelectorConfig(options=opts, multiple=True,
                                         mode=SelectSelectorMode.DROPDOWN)),
            })

        elif etype == ENTRY_KEPCO:
            return vol.Schema({
                vol.Required("username", default=d.get("username", "")): str,
                vol.Required("password", default=d.get("password", "")): _password_selector(),
            })

        elif etype == ENTRY_GASAPP:
            return vol.Schema({
                vol.Required("token", default=d.get("token", "")): _password_selector(),
                vol.Required("member_id", default=d.get("member_id", "")): str,
                vol.Required("contract_num", default=d.get("contract_num", "")): str,
            })

        elif etype == ENTRY_ARISU:
            return vol.Schema({
                vol.Required("customer_number", default=d.get("customer_number", "")): str,
                vol.Required("customer_name", default=d.get("customer_name", "")): str,
            })

        elif etype == ENTRY_AIRKOREA:
            return vol.Schema({
                vol.Required("api_key", default=d.get("api_key", "")): _password_selector(),
                vol.Optional("living_api_key", default=d.get("living_api_key", "")): _password_selector(),
            })

        elif etype == ENTRY_KMA_WEATHER:
            from .airkorea import STATIONS_BY_SIDO
            stations = STATIONS_BY_SIDO.get(sido_short_name(d.get("sido", "")), [])
            air_opts = [SelectOptionDict(value="none", label="사용 안 함 (날씨만)")]
            air_opts += [SelectOptionDict(value=s, label=f"{s} (O₃/UV 포함)")
                         for s in stations[:30]]
            return vol.Schema({
                vol.Required("api_key", default=d.get("api_key", "")): _password_selector(),
                vol.Required("air_station",
                             default=d.get("air_station") or "none"): SelectSelector(
                    SelectSelectorConfig(options=air_opts,
                                         mode=SelectSelectorMode.DROPDOWN)),
            })

        elif etype == ENTRY_EARTHQUAKE:
            return vol.Schema({
                vol.Required("api_key", default=d.get("api_key", "")): _password_selector(),
                vol.Optional("radius_km", default=d.get("radius_km", 200)): vol.Coerce(int),
                vol.Optional("min_magnitude", default=d.get("min_magnitude", 3.0)): vol.Coerce(float),
            })

        elif etype == ENTRY_BUS:
            return vol.Schema({
                vol.Optional("api_key",
                             default=d.get("api_key") or d.get("service_key", "")):
                    _password_selector(),
            })

        return None
