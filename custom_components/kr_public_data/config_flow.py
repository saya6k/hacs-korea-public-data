"""Config flow for 한국 공공데이터."""
from __future__ import annotations
import logging
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict, SelectSelector, SelectSelectorConfig, SelectSelectorMode,
)
from .const import *

_LOGGER = logging.getLogger(__name__)


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
        self._bus_stops: list[dict] = []
        self._bus_routes: list[dict] = []
        self._selected_stop: dict = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        return self.async_show_menu(
            step_id="user",
            menu_options=["weather_warning", "transit", "fuel", "school",
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
                    data={CONF_ENTRY_TYPE: ENTRY_WEATHER,
                          "api_key": api_key, "area_codes": areas})
            else:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="weather_warning",
            data_schema=vol.Schema({
                vol.Required("api_key"): str,
                vol.Required("area_codes"): SelectSelector(
                    SelectSelectorConfig(options=area_options, multiple=True,
                                         mode=SelectSelectorMode.DROPDOWN)),
            }),
            errors=errors)

    # ══════════ 대중교통 ══════════

    async def async_step_transit(self, user_input=None) -> FlowResult:
        if user_input is not None:
            self._data = {
                CONF_ENTRY_TYPE: ENTRY_TRANSIT,
                "seoul_api_key": user_input.get("seoul_api_key", ""),
                "bus_api_key": user_input.get("bus_api_key", ""),
                "subway_items": [], "bus_stops": [],
            }
            return await self.async_step_transit_add()
        return self.async_show_form(
            step_id="transit",
            data_schema=vol.Schema({
                vol.Optional("seoul_api_key"): str,
                vol.Optional("bus_api_key", description={"suggested_value": "환승경로 조회용 (선택)"}): str,
            }))

    async def async_step_transit_add(self, user_input=None) -> FlowResult:
        return self.async_show_menu(
            step_id="transit_add",
            menu_options=["transit_subway", "transit_bus_search", "transit_done"])

    # ── 지하철 ──
    async def async_step_transit_subway(self, user_input=None) -> FlowResult:
        from .transit import DIRECTIONS, SUBWAY_LINES
        if user_input is not None:
            self._data["subway_items"].append({
                "station": user_input["station"].strip(),
                "direction": user_input["direction"],
                "line_id": user_input.get("line_id", ""),
            })
            return await self.async_step_transit_add()
        dir_opts = {d: d for d in DIRECTIONS}
        line_opts = {"": "전체 (필터 없음)"}
        line_opts.update(SUBWAY_LINES)
        return self.async_show_form(
            step_id="transit_subway",
            data_schema=vol.Schema({
                vol.Required("station"): str,
                vol.Required("direction", default="상행"): vol.In(dir_opts),
                vol.Optional("line_id", default=""): vol.In(line_opts),
            }))

    # ── 버스: 정류장 ID 입력 (KakaoMap) ──
    async def async_step_transit_bus_search(self, user_input=None) -> FlowResult:
        import homeassistant.helpers.config_validation as cv
        errors: dict[str, str] = {}
        if user_input is not None:
            stop_id = user_input["kakao_stop_id"].strip()
            from .transit.bus_api import fetch_stop_data, build_bus_labels
            try:
                session = async_get_clientsession(self.hass)
                data = await fetch_stop_data(session, stop_id)
                stop_name = data.get("name", stop_id)
                bus_labels = build_bus_labels(data)
                if not bus_labels:
                    errors["kakao_stop_id"] = "no_stops_found"
                else:
                    self._bus_stop_id = stop_id
                    self._bus_stop_name = stop_name
                    self._bus_labels = bus_labels
                    return await self.async_step_transit_bus_select()
            except Exception as e:
                _LOGGER.error("KakaoMap bus stop error: %s", e)
                errors["kakao_stop_id"] = "cannot_connect"
        return self.async_show_form(
            step_id="transit_bus_search",
            data_schema=vol.Schema({
                vol.Required("kakao_stop_id"): str,
            }),
            errors=errors,
            description_placeholders={
                "tip": "카카오맵에서 정류장 검색 후 URL의 busstopid 값을 입력하세요"
            })

    # ── 버스: 노선 복수 선택 ──
    async def async_step_transit_bus_select(self, user_input=None) -> FlowResult:
        import homeassistant.helpers.config_validation as cv
        if user_input is not None:
            selected = user_input.get("buses", [])
            self._data.setdefault("bus_stops", []).append({
                "stop_id": self._bus_stop_id,
                "stop_name": self._bus_stop_name,
                "buses": selected,
            })
            return await self.async_step_transit_add()
        return self.async_show_form(
            step_id="transit_bus_select",
            data_schema=vol.Schema({
                vol.Required("buses", default=list(self._bus_labels.keys())):
                    cv.multi_select(self._bus_labels),
            }))

    # ── 대중교통 완료 ──
    async def async_step_transit_done(self, user_input=None) -> FlowResult:
        return self.async_create_entry(title="대중교통", data=self._data)

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
            api_key = user_input["api_key"]
            sidos = user_input.get("sido_codes", [])
            fuels = user_input.get("fuel_codes", [])
            if not isinstance(sidos, list):
                sidos = [sidos]
            if not isinstance(fuels, list):
                fuels = [fuels]
            if not sidos or not fuels:
                errors["base"] = "no_selection"
            elif await validate_opinet(api_key):
                # Build all combinations
                configs = []
                for s in sidos:
                    for f in fuels:
                        configs.append({"sido_code": s, "fuel_code": f})
                return self.async_create_entry(
                    title="유가정보",
                    data={CONF_ENTRY_TYPE: ENTRY_FUEL,
                          "api_key": api_key, "configs": configs})
            else:
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="fuel",
            data_schema=vol.Schema({
                vol.Required("api_key"): str,
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
            api_key = user_input["api_key"]
            self._data = {CONF_ENTRY_TYPE: ENTRY_SCHOOL,
                          "api_key": api_key,
                          "school_level": user_input["school_level"]}
            try:
                session = async_get_clientsession(self.hass)
                from .school.api import NeisApiClient
                c = NeisApiClient(session, api_key)
                await c.search_school("서울")
            except Exception:
                errors["api_key"] = "invalid_api_key"
            if not errors:
                return await self.async_step_school_search()
        return self.async_show_form(
            step_id="school",
            data_schema=vol.Schema({
                vol.Required("api_key"): str,
                vol.Required("school_level", default="elementary"): vol.In(SCHOOL_LEVELS),
            }),
            errors=errors)

    async def async_step_school_search(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            from .school.api import NeisApiClient
            from .school.parser import parse_school_info
            c = NeisApiClient(session, self._data["api_key"])
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
            title = "학교정보"
            return self.async_create_entry(title=title, data=self._data)
        schema: dict = {vol.Required("period_1", default=defaults[1]): str}
        for i in range(2, 8):
            schema[vol.Optional(f"period_{i}", default=defaults.get(i, ""))] = str
        schema[vol.Optional("lunch_start", default="12:50")] = str
        schema[vol.Optional("lunch_end", default="13:40")] = str
        return self.async_show_form(step_id="school_periods",
                                    data_schema=vol.Schema(schema))

    # ══════════ 재난정보 ══════════

    async def async_step_disaster(self, user_input=None) -> FlowResult:
        from .disaster.api import validate_disaster_api
        errors: dict[str, str] = {}
        region_opts = [SelectOptionDict(value="", label="전체 (필터 없음)")]
        for name in ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
                      "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]:
            region_opts.append(SelectOptionDict(value=name, label=name))
        if user_input is not None:
            api_key = user_input["api_key"]
            if await validate_disaster_api(api_key):
                region = user_input.get("region_filter", "")
                sub = user_input.get("sub_region", "").strip()
                if sub:
                    region = sub  # 세부 지역이 있으면 그것을 사용
                title = f"재난정보 - {region}" if region else "재난정보"
                return self.async_create_entry(title=title,
                    data={CONF_ENTRY_TYPE: ENTRY_DISASTER,
                          "api_key": api_key,
                          "region_filter": region})
            else:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="disaster",
            data_schema=vol.Schema({
                vol.Required("api_key"): str,
                vol.Optional("region_filter", default=""): SelectSelector(
                    SelectSelectorConfig(options=region_opts,
                                         mode=SelectSelectorMode.DROPDOWN)),
                vol.Optional("sub_region", default=""): str,
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
            "4500000000": "전북특별자치도", "4600000000": "전라남도",
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
            vol.Required("password"): str,
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
            vol.Required("token"): str,
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
        errors: dict[str, str] = {}
        sido_opts = {
            "서울특별시": "서울특별시", "부산광역시": "부산광역시",
            "대구광역시": "대구광역시", "인천광역시": "인천광역시",
            "광주광역시": "광주광역시", "대전광역시": "대전광역시",
            "울산광역시": "울산광역시", "세종특별자치시": "세종특별자치시",
            "경기도": "경기도", "강원특별자치도": "강원특별자치도",
            "충청북도": "충청북도", "충청남도": "충청남도",
            "전북특별자치도": "전북특별자치도", "전라남도": "전라남도",
            "경상북도": "경상북도", "경상남도": "경상남도",
            "제주특별자치도": "제주특별자치도",
        }
        if user_input is not None:
            return self.async_create_entry(
                title="약국 정보",
                data={CONF_ENTRY_TYPE: ENTRY_PHARMACY,
                      "api_key": user_input["api_key"],
                      "q0": user_input["q0"],
                      "q1": user_input.get("q1", "")})
        return self.async_show_form(
            step_id="pharmacy",
            data_schema=vol.Schema({
                vol.Required("api_key"): str,
                vol.Required("q0", default="서울특별시"): vol.In(sido_opts),
                vol.Optional("q1", default="",
                             description={"suggested_value": "시군구 (예: 강남구)"}): str,
            }),
            errors=errors,
            description_placeholders={
                "api_key_desc": "공공데이터포털(data.go.kr)에서 발급받은 서비스 키",
                "q0_desc": "시도를 선택하세요",
                "q1_desc": "시군구를 입력하세요 (선택, 예: 강남구)",
            },
        )




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
            vol.Required("api_key"): str,
            vol.Optional("living_api_key", default=""): str,
            vol.Required("sido", default="서울"): SelectSelector(
                SelectSelectorConfig(options=sido_opts, mode=SelectSelectorMode.DROPDOWN)),
        }), errors=errors)

    async def async_step_airkorea_select(self, user_input=None) -> FlowResult:
        """Step 2: 측정소(시군구) 복수 선택."""
        import homeassistant.helpers.config_validation as cv
        from .airkorea import STATIONS_BY_SIDO
        if user_input is not None:
            selected = user_input.get("stations", [])
            self._data["stations"] = [{"stationName": s} for s in selected]
            self._data["sido"] = self._air_sido
            return self.async_create_entry(title="에어코리아", data=self._data)
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
            vol.Required("api_key"): str,
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
            regions = [{"name": r,
                        "nx": sgg_map[r][0], "ny": sgg_map[r][1]}
                       for r in selected if r in sgg_map]
            self._data["regions"] = regions
            self._data["air_station"] = user_input.get("air_station", "")
            self._data["area_no"] = SIDO_AREA_CODE.get(self._kma_sido, "")
            self._data["sido"] = self._kma_sido
            return self.async_create_entry(title="기상청 날씨예보", data=self._data)
        labels = {k: k for k in sgg_map.keys()}
        air_stations = STATIONS_BY_SIDO.get(self._kma_sido, [])
        air_opts = {"": "사용 안 함 (날씨만)"}
        air_opts.update({s: f"{s} (O₃/UV 포함)" for s in air_stations[:30]})
        return self.async_show_form(step_id="kma_weather_sgg", data_schema=vol.Schema({
            vol.Required("regions"): cv.multi_select(labels),
            vol.Optional("air_station", default=""): vol.In(air_opts),
        }))

    # ══════════ 지진 정보 ══════════
    async def async_step_earthquake(self, user_input=None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(title="지진 정보",
                data={CONF_ENTRY_TYPE: ENTRY_EARTHQUAKE,
                      "api_key": user_input["api_key"],
                      "home_latitude": user_input.get("latitude", 37.5665),
                      "home_longitude": user_input.get("longitude", 126.978),
                      "radius_km": user_input.get("radius_km", 200),
                      "min_magnitude": user_input.get("min_magnitude", 3.0)})
        return self.async_show_form(step_id="earthquake", data_schema=vol.Schema({
            vol.Required("api_key"): str,
            vol.Optional("latitude", default=37.5665): vol.Coerce(float),
            vol.Optional("longitude", default=126.978): vol.Coerce(float),
            vol.Optional("radius_km", default=200): vol.Coerce(int),
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
            vol.Required("password"): str,
        }))

    async def async_step_reauth_gasapp(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                data_updates={"token": user_input["token"],
                              "member_id": user_input["member_id"],
                              "contract_num": user_input["contract_num"]})
        return self.async_show_form(step_id="reauth_gasapp", data_schema=vol.Schema({
            vol.Required("token"): str,
            vol.Required("member_id"): str,
            vol.Required("contract_num"): str,
        }))

        # ══════════ Options Flow =════════

    @staticmethod
    def async_get_options_flow(config_entry):
        return KRPublicDataOptionsFlow(config_entry)


class KRPublicDataOptionsFlow(config_entries.OptionsFlow):
    """Handle options for reconfiguration."""

    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        """Main options step - show editable fields based on entry type."""
        etype = self._entry.data.get(CONF_ENTRY_TYPE)

        if user_input is not None:
            # Merge new options into data
            new_data = {**self._entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            return self.async_create_entry(title="", data=user_input)

        schema = self._build_schema(etype)
        if schema is None:
            return self.async_abort(reason="no_options")

        return self.async_show_form(step_id="init", data_schema=schema)

    def _build_schema(self, etype):
        d = self._entry.data

        if etype == ENTRY_WEATHER:
            from .weather import AREA_CODES
            area_options = [SelectOptionDict(value=c, label=n) for c, n in AREA_CODES.items()]
            return vol.Schema({
                vol.Required("api_key", default=d.get("api_key", "")): str,
                vol.Required("area_codes", default=d.get("area_codes", [])): SelectSelector(
                    SelectSelectorConfig(options=area_options, multiple=True,
                                         mode=SelectSelectorMode.DROPDOWN)),
            })

        elif etype == ENTRY_TRANSIT:
            return vol.Schema({
                vol.Optional("seoul_api_key", default=d.get("seoul_api_key", "")): str,
                vol.Optional("bus_api_key", default=d.get("bus_api_key", "")): str,
            })

        elif etype == ENTRY_FUEL:
            from .fuel import SIDO_CODES, FUEL_TYPES
            sido_opts = [SelectOptionDict(value=k, label=v) for k, v in SIDO_CODES.items()]
            fuel_opts = [SelectOptionDict(value=k, label=v) for k, v in FUEL_TYPES.items()]
            cur_sidos = list(set(c["sido_code"] for c in d.get("configs", [])))
            cur_fuels = list(set(c["fuel_code"] for c in d.get("configs", [])))
            return vol.Schema({
                vol.Required("api_key", default=d.get("api_key", "")): str,
                vol.Required("sido_codes", default=cur_sidos): SelectSelector(
                    SelectSelectorConfig(options=sido_opts, multiple=True,
                                         mode=SelectSelectorMode.DROPDOWN)),
                vol.Required("fuel_codes", default=cur_fuels): SelectSelector(
                    SelectSelectorConfig(options=fuel_opts, multiple=True,
                                         mode=SelectSelectorMode.DROPDOWN)),
            })

        elif etype == ENTRY_SCHOOL:
            import homeassistant.helpers.config_validation as cv
            max_g = 6 if d.get("school_level") == "elementary" else 3
            combo_opts = {}
            for g in range(1, max_g + 1):
                for cl in range(1, 21):
                    combo_opts[f"{g}-{cl}"] = f"{g}학년 {cl}반"
            cur = d.get("grade_classes", [])
            return vol.Schema({
                vol.Required("grade_classes", default=cur): cv.multi_select(combo_opts),
            })

        elif etype == ENTRY_DISASTER:
            return vol.Schema({
                vol.Required("api_key", default=d.get("api_key", "")): str,
            })

        elif etype == ENTRY_SAFETY_ALERT:
            sido_map = {
                "1100000000": "서울특별시", "2600000000": "부산광역시",
                "2700000000": "대구광역시", "2800000000": "인천광역시",
                "2900000000": "광주광역시", "3000000000": "대전광역시",
                "3100000000": "울산광역시", "3600000000": "세종특별자치시",
                "4100000000": "경기도", "5100000000": "강원특별자치도",
                "4300000000": "충청북도", "4400000000": "충청남도",
                "4500000000": "전북특별자치도", "4600000000": "전라남도",
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
                vol.Required("password", default=d.get("password", "")): str,
            })

        elif etype == ENTRY_GASAPP:
            return vol.Schema({
                vol.Required("token", default=d.get("token", "")): str,
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
                vol.Required("api_key", default=d.get("api_key", "")): str,
                vol.Optional("living_api_key", default=d.get("living_api_key", "")): str,
            })

        elif etype == ENTRY_KMA_WEATHER:
            return vol.Schema({
                vol.Required("api_key", default=d.get("api_key", "")): str,
            })

        elif etype == ENTRY_EARTHQUAKE:
            return vol.Schema({
                vol.Required("api_key", default=d.get("api_key", "")): str,
                vol.Optional("radius_km", default=d.get("radius_km", 200)): vol.Coerce(int),
                vol.Optional("min_magnitude", default=d.get("min_magnitude", 3.0)): vol.Coerce(float),
            })

        return None
