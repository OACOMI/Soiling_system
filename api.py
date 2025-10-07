import requests
import pandas as pd

def get_weatherapi_history(lat, lon, date, api_key):
    """
    Consulta WeatherAPI para datos históricos de clima en una fecha y ubicación específica.
    Devuelve un diccionario con temperatura, precipitación, nubosidad, etc.
    """
    url = "https://api.weatherapi.com/v1/history.json"
    params = {
        "key": api_key,
        "q": f"{lat},{lon}",
        "dt": date  # formato 'YYYY-MM-DD'
    }
    r = requests.get(url, params=params, timeout=30)
    if r.status_code == 200:
        data = r.json()
        # Ejemplo: obtener datos horarios
        hours = data["forecast"]["forecastday"][0]["hour"]
        df = pd.DataFrame(hours)
        df["time"] = pd.to_datetime(df["time"])
        return df
    else:
        print("Error:", r.status_code, r.text)
        return None

def get_weatherapi_events(date_times, lat, lon, api_key):
    """
    Consulta WeatherAPI solo una vez por día y cruza los datos horarios con tu DataFrame.
    Devuelve una lista de eventos (ejemplo: 'Lluvia', 'Despejado', etc.) por cada DateTime.
    """
    eventos = []
    fechas = sorted(set(dt.strftime("%Y-%m-%d") for dt in date_times))
    clima_por_fecha = {}
    for fecha in fechas:
        df_clima = get_weatherapi_history(lat, lon, fecha, api_key)
        clima_por_fecha[fecha] = df_clima

    for dt in date_times:
        fecha = dt.strftime("%Y-%m-%d")
        hora = dt.hour
        df_clima = clima_por_fecha.get(fecha)
        if df_clima is not None:
            clima = df_clima[df_clima["time"].dt.hour == hora]
            if not clima.empty:
                row = clima.iloc[0]
                if row["precip_mm"] > 0:
                    evento = "Lluvia"
                elif row["cloud"] > 60:
                    evento = "Nublado"
                else:
                    evento = "Despejado"
                eventos.append(evento)
            else:
                eventos.append("Sin datos")
        else:
            eventos.append("Sin datos")
    return eventos
