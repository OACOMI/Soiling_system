import requests
import pandas as pd

def get_openmeteo_history(lat, lon, start_date, end_date):
    """
    Consulta Open-Meteo para un rango de fechas y devuelve un DataFrame con datos horarios.
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,precipitation,cloudcover",
        "timezone": "auto"
    }
    r = requests.get(url, params=params, timeout=30)
    if r.status_code == 200:
        data = r.json()
        df = pd.DataFrame({
            "time": data["hourly"]["time"],
            "temperature": data["hourly"]["temperature_2m"],
            "precipitation": data["hourly"]["precipitation"],
            "cloudcover": data["hourly"]["cloudcover"]
        })
        df["time"] = pd.to_datetime(df["time"])
        return df
    else:
        print("Error:", r.status_code, r.text)
        return None

def get_openmeteo_events(date_times, lat, lon):
    """
    Cruza los datos horarios de Open-Meteo con las fechas/hora del CSV.
    Devuelve una lista de eventos por cada DateTime.
    """
    start_date = min(date_times).strftime("%Y-%m-%d")
    end_date = max(date_times).strftime("%Y-%m-%d")
    df_clima = get_openmeteo_history(lat, lon, start_date, end_date)
    eventos = []
    if df_clima is not None:
        df_clima["hour"] = df_clima["time"].dt.hour
        df_clima["date"] = df_clima["time"].dt.date
        for dt in date_times:
            fecha = dt.date()
            hora = dt.hour
            clima = df_clima[(df_clima["date"] == fecha) & (df_clima["hour"] == hora)]
            if not clima.empty:
                row = clima.iloc[0]
                if row["precipitation"] > 0:
                    evento = "Lluvia"
                elif row["cloudcover"] > 60:
                    evento = "Nublado"
                else:
                    evento = "Despejado"
                eventos.append(evento)
            else:
                eventos.append("Sin datos")
    else:
        eventos = ["Sin datos"] * len(date_times)
    return eventos
