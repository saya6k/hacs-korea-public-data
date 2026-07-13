"""Constants for kr_public_data LLM API tools."""
from __future__ import annotations

from ..const import (
    ENTRY_AIRKOREA,
    ENTRY_ARISU,
    ENTRY_BUS,
    ENTRY_DISASTER,
    ENTRY_EARTHQUAKE,
    ENTRY_FUEL,
    ENTRY_GASAPP,
    ENTRY_KEPCO,
    ENTRY_KMA_WEATHER,
    ENTRY_PHARMACY,
    ENTRY_SAFETY_ALERT,
    ENTRY_SCHOOL,
    ENTRY_TRANSIT,
    ENTRY_WEATHER,
)

SOURCE = "kr_public_data"

API_DESCRIPTIONS: dict[str, str] = {
    ENTRY_KMA_WEATHER: "Korean Meteorological Administration weather forecast.",
    ENTRY_WEATHER: "Korean Meteorological Administration severe weather warnings.",
    ENTRY_AIRKOREA: "Realtime air quality (PM, ozone, UV) for configured stations.",
    ENTRY_TRANSIT: "Realtime Seoul subway arrivals.",
    ENTRY_FUEL: "Korean fuel (gasoline/diesel/LPG) average and lowest prices.",
    ENTRY_SCHOOL: "School lunch menus and class timetables (NEIS).",
    ENTRY_DISASTER: "Korean civil defense disaster messages (재난문자).",
    ENTRY_SAFETY_ALERT: "Active safety/emergency alerts (안전디딤돌) for a region.",
    ENTRY_KEPCO: "KEPCO household electricity usage and bill.",
    ENTRY_GASAPP: "City gas usage and current bill via the gas app.",
    ENTRY_ARISU: "Seoul Arisu water bill and usage.",
    ENTRY_PHARMACY: "Currently open pharmacies (including night/holiday).",
    ENTRY_EARTHQUAKE: "Recently observed earthquakes in/around Korea.",
    ENTRY_BUS: "Realtime city bus arrivals at configured stops (nationwide TAGO + Seoul TOPIS).",
}

API_PROMPTS: dict[str, str] = {
    ENTRY_KMA_WEATHER: (
        "You may use the get_weather_forecast tool to look up the Korean "
        "Meteorological Administration forecast. Pick the appropriate range "
        "('today', 'tomorrow', 'week', or a weekday name). If the user names "
        "a region, pass it through region_name; otherwise omit it to use the "
        "first configured region."
    ),
    ENTRY_WEATHER: (
        "You may use the get_weather_warnings tool to retrieve currently "
        "active KMA severe weather warnings (호우, 폭염, 한파, 강풍, 태풍, "
        "황사, 대설, 건조, 풍랑) for the configured area(s). Summarise active "
        "warnings naturally; if none are active, say so briefly."
    ),
    ENTRY_AIRKOREA: (
        "You may use the get_air_quality tool for realtime PM10/PM2.5/O3 "
        "values, the daily forecast grade, UV index and atmospheric "
        "stagnation. Translate Korean grade words (좋음/보통/나쁨/매우나쁨) "
        "into a natural reply."
    ),
    ENTRY_TRANSIT: (
        "Use get_subway_arrivals for Seoul subway arrivals at configured "
        "stations. The user may say 'when is the next subway/train' — pick "
        "the first configured station if they don't name one."
    ),
    ENTRY_FUEL: (
        "Use get_fuel_prices to retrieve the latest national average and "
        "lowest fuel prices for configured sido/fuel-type combinations. "
        "Prices are in KRW/L."
    ),
    ENTRY_SCHOOL: (
        "Use get_school_meal for the lunch menu (today/tomorrow/a YYYY-MM-DD "
        "date) and get_school_timetable for the class schedule of a "
        "configured grade/class on a given date."
    ),
    ENTRY_DISASTER: (
        "Use get_disaster_messages to retrieve the most recent civil-defense "
        "disaster messages (재난문자). Summarise the latest few; mention "
        "issuing region and time when relevant."
    ),
    ENTRY_SAFETY_ALERT: (
        "Use get_safety_alerts to retrieve currently active safety alerts "
        "for the configured region(s). Summarise; mention when the alerts "
        "were issued."
    ),
    ENTRY_KEPCO: (
        "Use get_electricity_usage to report the household's recent "
        "electricity usage and current bill from KEPCO."
    ),
    ENTRY_GASAPP: (
        "Use get_gas_bill to report the most recent city-gas usage and "
        "billing amount."
    ),
    ENTRY_ARISU: (
        "Use get_water_bill to report the most recent Arisu water usage "
        "and bill amount."
    ),
    ENTRY_PHARMACY: (
        "Use get_open_pharmacies to find pharmacies currently open near the "
        "configured address (q0/q1). Optionally pass a different q1 (읍면동) "
        "to narrow the search."
    ),
    ENTRY_EARTHQUAKE: (
        "Use get_recent_earthquakes to list earthquakes observed recently. "
        "Mention magnitude, depth, location, and time."
    ),
    ENTRY_BUS: (
        "Use get_city_bus_arrivals for city bus arrivals at configured "
        "stops (nationwide TAGO data plus Seoul via TOPIS). Pick the first "
        "configured stop if the user doesn't name one. Convert "
        "arrival_in_seconds to minutes. Use get_intercity_bus_departures "
        "for configured 고속버스/시외버스 routes — today's scheduled "
        "departures, not a live countdown."
    ),
}
