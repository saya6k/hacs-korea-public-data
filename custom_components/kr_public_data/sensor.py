"""Sensor platform dispatcher."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import *

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    etype = entry.data.get(CONF_ENTRY_TYPE)
    store = hass.data[DOMAIN][entry.entry_id]
    entities = []

    if etype == ENTRY_TRANSIT:
        from .transit.sensor import SubwayArrivalSensor, BusArrivalSensor
        from .transit.device import subway_device, bus_stop_device
        for station, coord in store.get("subway_coords", {}).items():
            for item in store.get("subway_items", []):
                if item["station"] != station: continue
                di = subway_device(item["station"], item["direction"], item.get("line_id",""))
                for idx in range(2):
                    entities.append(SubwayArrivalSensor(
                        coord, item["station"], item["direction"], item.get("line_id",""), idx, di))
        for stop in store.get("bus_stops", []):
            coord = store.get("bus_coords", {}).get(stop["stop_id"])
            if not coord: continue
            di = bus_stop_device(stop["stop_id"], stop["stop_name"])
            for bus_name in stop.get("buses", []):
                for idx in range(2):
                    entities.append(BusArrivalSensor(coord, bus_name, idx, di))

    elif etype == ENTRY_FUEL:
        from .fuel.sensor import FuelAvgSensor, FuelLowSensor
        c = store["coordinator"]
        for cfg in store.get("configs", []):
            entities += [FuelAvgSensor(c, cfg["sido_code"], cfg["fuel_code"]),
                         FuelLowSensor(c, cfg["sido_code"], cfg["fuel_code"])]

    elif etype == ENTRY_SCHOOL:
        from .school.sensor import SchoolLunchSensor, SchoolInfoSensor
        entities = [SchoolLunchSensor(store["coordinator"], entry),
                    SchoolInfoSensor(store["coordinator"], entry)]

    elif etype == ENTRY_DISASTER:
        from .disaster.sensor import DisasterMessageSensor, DisasterCountSensor
        c = store["coordinator"]
        regions = store.get("regions") or {}
        for sub_id, r in regions.items():
            async_add_entities(
                [DisasterMessageSensor(c, sido=r.get("sido", ""), sgg=r.get("sgg", "")),
                 DisasterCountSensor(c, sido=r.get("sido", ""), sgg=r.get("sgg", ""))],
                config_subentry_id=sub_id)
        if not regions:
            region = store.get("region", "")
            entities = [DisasterMessageSensor(c, region), DisasterCountSensor(c, region)]

    elif etype == ENTRY_SAFETY_ALERT:
        from .safety_alert.sensor import SafetyAlertTextSensor, SafetyAlertCountSensor
        for region in store.get("regions", []):
            coord = store["coordinators"].get(region["code"])
            if coord:
                entities.append(SafetyAlertTextSensor(coord, region["code"], region["name"]))
                entities.append(SafetyAlertCountSensor(coord, region["code"], region["name"]))

    elif etype == ENTRY_KEPCO:
        from .kepco.sensor import KepcoSensor
        from homeassistant.components.sensor import SensorStateClass
        c = store["coordinator"]; u = entry.data["username"]
        entities = [
            KepcoSensor(c, u, "usage_info", "result.SESS_CUSTNO", "고객번호"),
            KepcoSensor(c, u, "usage_info", "result.SESS_CNTR_KND_NM", "전력구분"),
            KepcoSensor(c, u, "usage_info", "result.BILL_LAST_MONTH", "지난달 요금",
                        unit="원", state_class=SensorStateClass.TOTAL),
            KepcoSensor(c, u, "usage_info", "result.PREDICT_TOTAL_CHARGE_REV", "예상 요금",
                        unit="원", state_class=SensorStateClass.TOTAL),
            KepcoSensor(c, u, "recent_usage", "result.F_AP_QT", "현재 사용량",
                        unit="kWh", state_class=SensorStateClass.TOTAL_INCREASING),
        ]

    elif etype == ENTRY_GASAPP:
        from .gasapp.sensor import GasAppSensor
        c = store["coordinator"]; cn = entry.data["contract_num"]
        entities = [GasAppSensor(c, cn, "current_bill", "title1", "청구 제목"),
                    GasAppSensor(c, cn, "current_bill", "title2", "총 요금", unit="원")]

    elif etype == ENTRY_ARISU:
        from .arisu.sensor import ArisuSensor
        c = store["coordinator"]; cn = entry.data["customer_number"]
        entities = [ArisuSensor(c, cn, "수도 요금", "total_amount", unit="원"),
                    ArisuSensor(c, cn, "사용량", "current_usage", unit="㎥"),
                    ArisuSensor(c, cn, "청구월", "billing_month")]

    elif etype == ENTRY_PHARMACY:
        from .pharmacy.sensor import PharmacySensor
        for sub_id, sub in entry.subentries.items():
            coord = store["coordinators"].get(sub_id)
            if coord:
                async_add_entities(
                    [PharmacySensor(coord, sub.data.get("sido", ""), sub.data.get("sgg", ""))],
                    config_subentry_id=sub_id)
        if not entry.subentries:
            entities = [PharmacySensor(store["coordinator"], entry.data["q0"], entry.data.get("q1",""))]

    elif etype == ENTRY_AIRKOREA:
        from .airkorea.sensor import AirQualitySensor, POLLUTANTS, UVIndexSensor, AirStagnationSensor
        c = store["coordinator"]

        def _station_sensors(name):
            sensors = [AirQualitySensor(c, name, field, label, unit)
                       for field, label, unit in POLLUTANTS]
            # Living index sensors per station (same data, different device)
            sensors += [UVIndexSensor(c, name), AirStagnationSensor(c, name)]
            return sensors

        station_subs = store.get("station_subs") or {}
        for sub_id, st in station_subs.items():
            async_add_entities(_station_sensors(st["stationName"]),
                               config_subentry_id=sub_id)
        if not station_subs:
            for st in store.get("stations", []):
                entities += _station_sensors(st["stationName"])

    if entities:
        async_add_entities(entities)
