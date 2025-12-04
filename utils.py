import pandas as pd

def get_consecutive_days_below(df, column, threshold):
    """
    Cuenta DÍAS ÚNICOS consecutivos donde el promedio diario está por debajo del umbral
    """
    if df.empty:
        return 0
    
    # Agrupar por DÍA (no por registro) y calcular promedio diario
    df_daily = df.copy()
    df_daily['Date'] = df_daily['DateTime'].dt.date
    daily_avg = df_daily.groupby('Date')[column].mean().reset_index()
    daily_avg = daily_avg.sort_values('Date')
    
    # Encontrar días consecutivos por debajo del umbral
    below_mask = daily_avg[column] < threshold
    
    if not below_mask.any():
        return 0
    
    # Contar la racha consecutiva más larga de DÍAS
    max_consecutive = 0
    current_consecutive = 0
    
    for is_below in below_mask:
        if is_below:
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0
    
    return max_consecutive

def get_days_below_threshold(df, column, threshold):
    """
    Cuenta TOTAL de días únicos donde el promedio diario está por debajo del umbral
    (no necesariamente consecutivos)
    """
    if df.empty:
        return 0
    
    # Agrupar por DÍA y calcular promedio diario
    df_daily = df.copy()
    df_daily['Date'] = df_daily['DateTime'].dt.date
    daily_avg = df_daily.groupby('Date')[column].mean().reset_index()
    
    # Contar cuántos días están por debajo del umbral
    days_below = (daily_avg[column] < threshold).sum()
    
    return days_below

def get_unique_days_count(df):
    """
    Cuenta la cantidad de días únicos en el DataFrame (sin importar cuántos registros por día)
    """
    if df.empty:
        return 0
    return df['DateTime'].dt.date.nunique()

def get_weather_icon(event):
    """
    Retorna el icono correspondiente al evento climático
    """
    icons = {
        "Lluvia": "🌧️",
        "Despejado": "☀️",
        "Nublado": "☁️",
        "Nieve": "❄️",
        "Tormenta": "⛈️",
        "Niebla": "🌫️",
        "Sin datos": "❓",
        "Sin API Key": "❓",
        "Error": "⚠️",
        "Error: Timeout": "⚠️",
        "Error: Conexión": "⚠️"
    }
    return icons.get(event, "⚠️")
