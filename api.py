import requests
import pandas as pd
from io import StringIO
import openmeteo_requests
import requests_cache
from retry_requests import retry

def get_nrel_solar_data(lat, lon, api_key, year="2020"):
    url = "https://developer.nrel.gov/api/solar/nsrdb_psm3_download.csv"
    params = {
        "api_key": api_key,
        "wkt": f"POINT({lon} {lat})",
        "names": year,
        "leap_day": "false",
        "interval": "60",
        "utc": "false",
        "full_name": "Omar Altamirano",
        "email": "oaltamirano.trainee@beetmann.com",
        "affiliation": "Beetmann",
        "mailing_list": "false",
        "attributes": "ghi,dhi,dni,wind_speed,air_temperature,cloud_type"
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        lines = response.text.splitlines()
        skip = 0
        for i, line in enumerate(lines):
            if line.startswith("Year"):
                skip = i
                break
        df = pd.read_csv(StringIO('\n'.join(lines[skip:])))
        return df
    else:
        print("Error:", response.status_code, response.text)
        return None

def get_weather_events_openmeteo(dates, lat, lon):
    """
    Consulta Open-Meteo y devuelve una lista de eventos climáticos ("Lluvia" o "Normal") para cada fecha.
    """
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation",
        "start_date": min(dates).strftime("%Y-%m-%d"),
        "end_date": max(dates).strftime("%Y-%m-%d"),
        "timezone": "auto"
    }
    try:
        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]
        hourly = response.Hourly()
        precip = hourly.Variables(0).ValuesAsNumpy()
        times = pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left"
        )
        precip_df = pd.DataFrame({"DateTime": times, "precipitation": precip})
        precip_df["date"] = precip_df["DateTime"].dt.date
        rain_by_date = precip_df.groupby("date")["precipitation"].sum().to_dict()
        events = []
        for dt in dates:
            rain = rain_by_date.get(dt.date(), 0)
            if rain > 0:
                events.append("Lluvia")
            else:
                events.append("Normal")
        return events
    except Exception as e:
        return ["Error API"] * len(dates)
# Uso:
api_key = "K8Sa04srQoqiB1ildfRq5MiZL6O2tFm89qpPsb4G"
lat, lon = 19.43, -99.13  # Ejemplo: CDMX
df = get_nrel_solar_data(lat, lon, api_key)
if df is not None:
    print(df.head())
