"""Sensor platform dispatcher."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ENTRY_TYPE,
    DOMAIN,
    ENTRY_AIRKOREA,
    ENTRY_ARISU,
    ENTRY_BUS,
    ENTRY_DISASTER,
    ENTRY_FUEL,
    ENTRY_GASAPP,
    ENTRY_KEPCO,
    ENTRY_PHARMACY,
    ENTRY_SAFETY_ALERT,
    ENTRY_SCHOOL,
    ENTRY_TRANSIT,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            async_add_entities: AddEntitiesCallback) -> None:
    etype = entry.data.get(CONF_ENTRY_TYPE)
    store = hass.data[DOMAIN][entry.entry_id]
    entities = []

    if etype == ENTRY_TRANSIT:
        from .transit import line_directions
        from .transit.device import (
            subway_device,
            subway_line_device,
            subway_station_device,
            subway_station_device_id,
            subway_station_key,
        )
        from .transit.sensor import SubwayArrivalSensor, SubwayStationLineSensor
        station_subs = store.get("station_subs") or {}
        for sub_id, info in station_subs.items():
            coord = info["coordinator"]
            station = info["station"]
            ents = []
            # One 역 hub device, one child device per line under it; 4 sensors
            # under each line (2 directions × next/next-next).
            hub_id = subway_station_device_id(hass, entry, sub_id, station)
            ents.append(SubwayStationLineSensor(
                coord, subway_station_key(station), info["lines"],
                subway_station_device(station)))
            for lid in info["lines"]:
                di = subway_line_device(station, lid, hub_id)
                for direction in line_directions(lid):
                    for idx in range(2):
                        ents.append(SubwayArrivalSensor(
                            coord, station, direction, lid, idx, di,
                            name_prefix=direction))
            async_add_entities(ents, config_subentry_id=sub_id)
        if not station_subs:
            # legacy entry: per-(station, direction, line) devices
            for station, coord in store.get("subway_coords", {}).items():
                for item in store.get("subway_items", []):
                    if item["station"] != station:
                        continue
                    di = subway_device(item["station"], item["direction"], item.get("line_id",""))
                    for idx in range(2):
                        entities.append(SubwayArrivalSensor(
                            coord, item["station"], item["direction"],
                            item.get("line_id",""), idx, di))

    elif etype == ENTRY_FUEL:
        from .fuel.sensor import FuelAvgSensor, FuelLowLocationSensor, FuelLowSensor
        c = store["coordinator"]
        if entry.subentries:
            for sub_id, sub in entry.subentries.items():
                sido = sub.data["sido_code"]
                ents = []
                for fuel in sub.data.get("fuel_codes", []):
                    ents += [FuelAvgSensor(c, sido, fuel), FuelLowSensor(c, sido, fuel),
                             FuelLowLocationSensor(c, sido, fuel)]
                async_add_entities(ents, config_subentry_id=sub_id)
        else:
            for cfg in store.get("configs", []):
                entities += [FuelAvgSensor(c, cfg["sido_code"], cfg["fuel_code"]),
                             FuelLowSensor(c, cfg["sido_code"], cfg["fuel_code"]),
                             FuelLowLocationSensor(c, cfg["sido_code"], cfg["fuel_code"])]

    elif etype == ENTRY_SCHOOL:
        from .school.sensor import SchoolInfoSensor, SchoolLunchSensor
        school_subs = store.get("school_subs") or {}
        for sub_id, info in school_subs.items():
            coord = info["coordinator"]
            data = info["data"]
            async_add_entities(
                [SchoolLunchSensor(coord, data), SchoolInfoSensor(coord, data)],
                config_subentry_id=sub_id)
        if not school_subs:
            entities = [SchoolLunchSensor(store["coordinator"], entry.data),
                        SchoolInfoSensor(store["coordinator"], entry.data)]

    elif etype == ENTRY_DISASTER:
        from .disaster.sensor import DisasterCountSensor, DisasterMessageSensor
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
        from .safety_alert.sensor import SafetyAlertCountSensor, SafetyAlertTextSensor
        for region in store.get("regions", []):
            coord = store["coordinators"].get(region["code"])
            if coord:
                entities.append(SafetyAlertTextSensor(coord, region["code"], region["name"]))
                entities.append(SafetyAlertCountSensor(coord, region["code"], region["name"]))

    elif etype == ENTRY_KEPCO:
        from homeassistant.components.sensor import SensorStateClass

        from .kepco.sensor import KepcoSensor
        c = store["coordinator"]
        u = entry.data["username"]
        entities = [
            KepcoSensor(c, u, "usage_info", "result.SESS_CUSTNO", "kepco_customer_number"),
            KepcoSensor(c, u, "usage_info", "result.SESS_CNTR_KND_NM", "kepco_contract_type"),
            KepcoSensor(c, u, "usage_info", "result.BILL_LAST_MONTH", "kepco_bill_last_month",
                        unit="원", state_class=SensorStateClass.TOTAL),
            KepcoSensor(c, u, "usage_info", "result.PREDICT_TOTAL_CHARGE_REV",
                        "kepco_bill_predicted",
                        unit="원", state_class=SensorStateClass.TOTAL),
            KepcoSensor(c, u, "recent_usage", "result.F_AP_QT", "kepco_usage_current",
                        unit="kWh", state_class=SensorStateClass.TOTAL_INCREASING),
        ]

    elif etype == ENTRY_GASAPP:
        from .gasapp.sensor import GasAppSensor
        c = store["coordinator"]
        cn = entry.data["contract_num"]
        entities = [GasAppSensor(c, cn, "current_bill", "title1", "gas_bill_title"),
                    GasAppSensor(c, cn, "current_bill", "title2", "gas_bill_total",
                                 unit="원")]

    elif etype == ENTRY_ARISU:
        from .arisu.sensor import ArisuSensor
        c = store["coordinator"]
        cn = entry.data["customer_number"]
        entities = [ArisuSensor(c, cn, "arisu_bill", "total_amount", unit="원"),
                    ArisuSensor(c, cn, "arisu_usage", "current_usage", unit="㎥"),
                    ArisuSensor(c, cn, "arisu_billing_month", "billing_month")]

    elif etype == ENTRY_PHARMACY:
        from .pharmacy.device import pharmacy_device, pharmacy_region_device_id
        from .pharmacy.sensor import (
            PharmacyLocationSensor,
            PharmacySensor,
            region_nearby_pharmacies,
        )
        for i, region in enumerate(store.get("regions", [])):
            coord = store["coordinators"].get(i)
            if not coord:
                continue
            sido, sgg = region.get("sido", ""), region.get("sgg", "")
            ents = [PharmacySensor(coord, sido, sgg)]
            sub_id = region.get("subentry_id")
            if region.get("location_sensors"):
                # Each nearby pharmacy keeps its own device, as a child of the region's.
                hub_id = pharmacy_region_device_id(hass, entry, sub_id, sido, sgg)
                nearby = region_nearby_pharmacies(hass, region, coord)
                ents += [PharmacyLocationSensor(
                            coord, p["hpid"],
                            pharmacy_device(p["hpid"], p["name"], hub_id))
                         for p in nearby if p.get("hpid")]
            if sub_id:
                async_add_entities(ents, config_subentry_id=sub_id)
            else:
                entities += ents

    elif etype == ENTRY_AIRKOREA:
        from .airkorea.sensor import (
            POLLUTANTS,
            AirQualitySensor,
            AirStagnationSensor,
            UVIndexSensor,
        )
        c = store["coordinator"]

        def _station_sensors(name: str) -> list[Entity]:
            sensors: list[Entity] = [AirQualitySensor(c, name, field, tkey, unit)
                                     for field, tkey, unit in POLLUTANTS]
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

    elif etype == ENTRY_BUS:
        from .bus.device import (
            bus_stop_device,
            bus_stop_device_id,
            bus_stop_key,
            city_bus_route_device,
            intercity_bus_route_device,
            intercity_bus_section_device,
            intercity_bus_section_device_id,
            intercity_bus_section_key,
            seoul_bus_route_device,
        )
        from .bus.intercity_sensor import (
            IntercityBusDepartureSensor,
            IntercityBusFareSensor,
            IntercityBusSectionSensor,
        )
        from .bus.sensor import CityBusArrivalSensor
        from .bus.seoul_sensor import SeoulBusArrivalSensor
        from .bus.stop_sensor import BusStopRouteSensor
        stop_subs = store.get("stop_subs") or {}
        for sub_id, info in stop_subs.items():
            coord = info["coordinator"]
            node_id = info["nodeId"]
            node_name = info["nodeName"]
            seoul = info["kind"] == "seoul"
            ents = []
            # One 정류장 hub device, one child device per route under it; 2 sensors
            # under each route (next/next-next).
            hub_id = bus_stop_device_id(hass, entry, sub_id, info)
            ents.append(BusStopRouteSensor(
                coord, bus_stop_key(info), info["routes"], bus_stop_device(info),
                seoul=seoul))
            for route in info["routes"]:
                if seoul:
                    di = seoul_bus_route_device(node_id, node_name, route["routeId"],
                                                route["routeNo"], hub_id)
                    sensor_cls = SeoulBusArrivalSensor
                else:
                    di = city_bus_route_device(node_id, node_name, route["routeId"],
                                               route["routeNo"], hub_id)
                    sensor_cls = CityBusArrivalSensor
                for idx in range(2):
                    ents.append(sensor_cls(coord, node_id, route["routeId"], idx, di))
            async_add_entities(ents, config_subentry_id=sub_id)

        route_subs = store.get("route_subs") or {}
        for sub_id, info in route_subs.items():
            coord = info["coordinator"]
            dep_name = info["depTerminalName"]
            arr_name = info["arrTerminalName"]
            ents = []
            # One 구간 hub device, one child device per grade under it; 2 departure
            # sensors + 2 fare sensors under each grade.
            hub_id = intercity_bus_section_device_id(hass, entry, sub_id,
                                                     dep_name, arr_name)
            ents.append(IntercityBusSectionSensor(
                coord, intercity_bus_section_key(dep_name, arr_name), info["grades"],
                intercity_bus_section_device(dep_name, arr_name)))
            for grade in info["grades"]:
                di = intercity_bus_route_device(dep_name, arr_name, grade, hub_id)
                for idx in range(2):
                    ents.append(IntercityBusDepartureSensor(
                        coord, dep_name, arr_name, grade, idx, di))
                    ents.append(IntercityBusFareSensor(coord, dep_name, arr_name, grade, idx, di))
            async_add_entities(ents, config_subentry_id=sub_id)

    if entities:
        async_add_entities(entities)
