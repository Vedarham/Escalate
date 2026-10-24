"""Weather data via Open-Meteo (free, no API key) + rule-based construction alerts."""
from __future__ import annotations

import logging

import httpx

from ..schemas import WeatherDay, WeatherSnapshot

log = logging.getLogger("weather")

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Heavy freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Rain showers", 81: "Heavy rain showers", 82: "Violent rain showers",
    85: "Snow showers", 86: "Heavy snow showers", 95: "Thunderstorm", 96: "Thunderstorm with hail",
    99: "Severe thunderstorm with hail",
}


def construction_alerts(days: list[WeatherDay]) -> list[str]:
    alerts: list[str] = []
    if not days:
        return alerts
    today = days[0]
    if (today.precipitation_mm or 0) > 5:
        alerts.append(f"Heavy rain expected today ({today.precipitation_mm} mm): avoid concrete pours and open excavation work.")
    elif (today.precipitation_probability or 0) >= 60:
        alerts.append(f"High chance of rain today ({today.precipitation_probability:.0f}%): keep covers ready for fresh concrete and materials.")
    if (today.wind_max_kmh or 0) > 40:
        alerts.append(f"Strong winds up to {today.wind_max_kmh} km/h: suspend crane lifts and work at height.")
    if (today.temp_max_c or 0) >= 38:
        alerts.append(f"Extreme heat ({today.temp_max_c} C): heat-stress protocol, hot-weather concreting precautions.")
    elif (today.temp_max_c or 0) >= 35:
        alerts.append(f"High temperature ({today.temp_max_c} C): enforce hydration and shaded breaks.")
    if today.temp_min_c is not None and today.temp_min_c <= 5:
        alerts.append(f"Low temperature ({today.temp_min_c} C): cold-weather concreting measures required.")
    if "Thunderstorm" in today.condition:
        alerts.append("Thunderstorm risk: stop crane, scaffold and roof work during lightning; follow 30-30 rule.")
    return alerts


def fetch_weather(location: str, timeout: float = 10.0) -> WeatherSnapshot:
    """Return a forecast snapshot; never raises - returns available=False on any failure."""
    try:
        with httpx.Client(timeout=timeout) as client:
            geo = client.get(GEOCODE_URL, params={"name": location.split(",")[0].strip(), "count": 1})
            geo.raise_for_status()
            results = geo.json().get("results") or []
            if not results:
                return WeatherSnapshot(available=False, location_name=location,
                                       alerts=[f"Location '{location}' not found for weather lookup."])
            place = results[0]
            lat, lon = place["latitude"], place["longitude"]
            name = ", ".join(x for x in [place.get("name"), place.get("admin1"), place.get("country")] if x)
            fc = client.get(FORECAST_URL, params={
                "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 3,
                "current": "temperature_2m,weather_code",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
                         "precipitation_probability_max,wind_gusts_10m_max",
            })
            fc.raise_for_status()
            body = fc.json()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        log.warning("weather lookup failed: %s", exc)
        return WeatherSnapshot(available=False, location_name=location,
                               alerts=["Live weather is unavailable right now; advisory is based on general guidance."])

    daily = body.get("daily", {})
    days: list[WeatherDay] = []
    for i, date in enumerate(daily.get("time", [])):
        def pick(key: str):
            vals = daily.get(key) or []
            return vals[i] if i < len(vals) else None

        days.append(WeatherDay(
            date=date,
            temp_max_c=pick("temperature_2m_max"),
            temp_min_c=pick("temperature_2m_min"),
            precipitation_mm=pick("precipitation_sum"),
            precipitation_probability=pick("precipitation_probability_max"),
            wind_max_kmh=pick("wind_gusts_10m_max"),
            condition=WMO_CODES.get(pick("weather_code"), "Unknown"),
        ))
    current = body.get("current", {})
    return WeatherSnapshot(
        available=True, location_name=name, latitude=lat, longitude=lon,
        current_temp_c=current.get("temperature_2m"),
        current_condition=WMO_CODES.get(current.get("weather_code"), ""),
        days=days, alerts=construction_alerts(days),
    )
