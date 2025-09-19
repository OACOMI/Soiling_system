import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime
import os
import base64
from api import get_weather_events_openmeteo

st.set_page_config(
    page_title='Soiling System Dashboard',
    page_icon=':🌍:',
)
with open('style.css')as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html = True)

NREL_API_KEY = "K8Sa04srQoqiB1ildfRq5MiZL6O2tFm89qpPsb4G"  

# --- SIDEBAR ---
with st.sidebar:
    # Logo
    img_path = os.path.join(os.path.dirname(__file__), "data", "logo_beetmann.png")
    with open(img_path, "rb") as img_file:
        img_base64 = base64.b64encode(img_file.read()).decode()
    st.markdown(
        f"""
        <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 1rem;">
            <img src="data:image/png;base64,{img_base64}" alt="Logo" style="max-width: 80%; height: auto;">
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.header("Configuración del sistema de soiling")
    system = st.selectbox(
        "Selecciona el sistema de soiling:",
        ["Kimber","SOLOs System"],
        key="soiling_system_select"
    )
    st.markdown(f"**Sistema seleccionado:** {system}")

    # --- UBICACIONES DESDE EXCEL ---
    ubicaciones_path = os.path.join(os.path.dirname(__file__), "ubi", "ubicaciones.xlsx")
    
    if os.path.exists(ubicaciones_path):
        ubicaciones_df = pd.read_excel(ubicaciones_path)
        # Limpia los nombres de columnas de espacios y caracteres invisibles
        ubicaciones_df.columns = [col.strip() for col in ubicaciones_df.columns]
        # Quita duplicados por proyecto
        ubicaciones_df = ubicaciones_df.drop_duplicates(subset="Proyecto", keep="first")
    else:
        ubicaciones_df = pd.DataFrame(columns=["Proyecto", "Latitud", "Longitud"])

    proyectos = ubicaciones_df["Proyecto"].tolist()
    selected_proyecto = st.selectbox("Selecciona un proyecto", proyectos + ["Agregar nuevo"], key="proyecto_select")
    
    if selected_proyecto == "Agregar nuevo":
        nuevo_nombre = st.text_input("Nombre del nuevo proyecto")
        nueva_lat = st.number_input("Latitud", format="%.6f", key="nueva_lat")
        nueva_lon = st.number_input("Longitud", format="%.6f", key="nueva_lon")
        if st.button("Guardar nuevo proyecto"):
            if nuevo_nombre and not ubicaciones_df["Proyecto"].eq(nuevo_nombre).any():
                new_row = pd.DataFrame([{"Proyecto": nuevo_nombre, "Latitud": nueva_lat, "Longitud": nueva_lon}])
                ubicaciones_df = pd.concat([ubicaciones_df, new_row], ignore_index=True)
                ubicaciones_df.to_excel(ubicaciones_path, index=False)
                st.success("Proyecto agregado. Recarga la página para verlo en la lista.")
            else:
                st.warning("El nombre del proyecto ya existe o está vacío.")
        lat = nueva_lat
        lon = nueva_lon
    else:
        # Mostrar y permitir editar la ubicación seleccionada
        row = ubicaciones_df[ubicaciones_df["Proyecto"] == selected_proyecto].iloc[0]
        lat = st.number_input("Latitud", value=float(row["Latitud"]), format="%.6f", key="edit_lat")
        lon = st.number_input("Longitud", value=float(row["Longitud"]), format="%.6f", key="edit_lon")
        if st.button("Actualizar ubicación"):
            ubicaciones_df.loc[ubicaciones_df["Proyecto"] == selected_proyecto, ["Latitud", "Longitud"]] = [lat, lon]
            ubicaciones_df.to_excel(ubicaciones_path, index=False)
            st.success("Ubicación actualizada.")


    st.subheader("Carga y filtros de datos")
    uploaded_file = st.file_uploader("Selecciona tu archivo CSV", type=["csv"])

    # ...resto del código sidebar y main page...

    # Variables para usar después
    df = None
    filtered_df = None
    min_date = None
    max_date = None
    date_range = None
    period = None
    threshold = None
    chart_type = None

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file, parse_dates=['DateTime'])
            df = df.sort_values('DateTime')
            df['Soiling Ratio'] = pd.to_numeric(df['Soiling Ratio'], errors='coerce')
            df = df.dropna(subset=['Soiling Ratio'])

            # Consulta clima si hay API Key
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

            with st.spinner("Consultando clima..."):
                df['Clima'] = get_weather_events_openmeteo(df['DateTime'], lat, lon)

            # Selección de rango de fechas
            min_date = df['DateTime'].min().date()
            max_date = df['DateTime'].max().date()
            date_range = st.slider(
                "Selecciona el rango de fechas",
                min_value=min_date,
                max_value=max_date,
                value=(min_date, max_date)
            )
            mask = (df['DateTime'].dt.date >= date_range[0]) & (df['DateTime'].dt.date <= date_range[1])
            filtered_df = df.loc[mask].copy()

            # Agrupación por periodo
            period = st.selectbox("Agrupar por:", ["Día", "Semana", "Mes", "Todo el histórico"])
            if period == "Semana":
                filtered_df['Periodo'] = filtered_df['DateTime'].dt.to_period('W').apply(lambda r: r.start_time)
            elif period == "Mes":
                filtered_df['Periodo'] = filtered_df['DateTime'].dt.to_period('M').apply(lambda r: r.start_time)
            elif period == "Día":
                filtered_df['Periodo'] = filtered_df['DateTime'].dt.date
            else:
                filtered_df['Periodo'] = 'Histórico'

            # Umbral de alerta
            threshold = st.slider("Umbral de alerta para limpieza (%)", min_value=70, max_value=100, value=90)
            threshold = threshold / 100.0

            # Tipo de gráfico
            chart_type = st.selectbox("Tipo de gráfico", ["Línea", "Área", "Barras"])

        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")

# --- MAIN PAGE ---
st.title(":🌍: Soiling System Dashboard")
st.markdown("""
Sube un archivo CSV con las columnas **DateTime** y **Soiling Ratio** para visualizar el ensuciamiento de tus paneles solares.
""")

# Mostrar mapa con la ubicación seleccionada
st.subheader("Ubicación seleccionada")
st.map(pd.DataFrame({'lat': [lat], 'lon': [lon]}), zoom=8)
st.caption(f"Coordenadas seleccionadas: lat={lat}, lon={lon}")

# ...después de mostrar el mapa y las coordenadas seleccionadas...

# Obtén el año de tus datos (puedes tomar el año de la primera fecha)
if uploaded_file is not None and df is not None and not df.empty:
    year = df['DateTime'].dt.year.min()
    nrel_df = get_nrel_weather_events(lat, lon, NREL_API_KEY, year=str(year))

    if nrel_df is not None:
        # Convierte las columnas de fecha y hora en NREL a un datetime para cruzar
        nrel_df['DateTime'] = pd.to_datetime(
            nrel_df['Year'].astype(str) + '-' +
            nrel_df['Month'].astype(str).str.zfill(2) + '-' +
            nrel_df['Day'].astype(str).str.zfill(2) + 'T' +
            nrel_df['Hour'].astype(str).str.zfill(2) + ':00:00'
        )

        # Redondea tus fechas al inicio de la hora para hacer el merge
        df['DateTime_hour'] = df['DateTime'].dt.floor('H')
        nrel_df['DateTime_hour'] = nrel_df['DateTime']

        # Une los eventos de NREL a tu DataFrame principal
        df = pd.merge(df, nrel_df[['DateTime_hour', 'Evento']], on='DateTime_hour', how='left')
        df = df.rename(columns={'Evento': 'Evento NREL'})

        # Ahora puedes mostrar el evento NREL junto con tus datos
        st.subheader("Datos con evento climático NREL")
        st.dataframe(df[['DateTime', 'Soiling Ratio', 'Clima', 'Evento NREL']])
    else:
        st.warning("No se pudo obtener información de NREL para esta ubicación.")
        
# Mostrar ilustración meteorológica
def get_weather_icon(event):
    if event == "Lluvia":
        return "🌧️"
    elif event == "Normal":
        return "☀️"
    elif event == "Sin API Key":
        return "❓"
    else:
        return "⚠️"

def get_consecutive_days_below(df, col, threshold):
    below = df[col] < threshold
    count = 0
    for b in below[::-1]:
        if b:
            count += 1
        else:
            break
    return count

if 'filtered_df' in locals() and filtered_df is not None and not filtered_df.empty:
    # Visualización
    chart_data = filtered_df.groupby('Periodo')['Soiling Ratio'].mean().reset_index()

    st.subheader("Visualización del Soiling Ratio")
    if chart_type == "Línea":
        st.line_chart(chart_data.set_index('Periodo')['Soiling Ratio'], use_container_width=True)
    elif chart_type == "Área":
        st.area_chart(chart_data.set_index('Periodo')['Soiling Ratio'], use_container_width=True)
    else:
        st.bar_chart(chart_data.set_index('Periodo')['Soiling Ratio'], use_container_width=True)

    # KPIs rápidos
    sr_avg = filtered_df['Soiling Ratio'].mean()
    sr_loss = (1 - sr_avg) * 100
    days_below = get_consecutive_days_below(filtered_df, 'Soiling Ratio', threshold)
    if sr_avg >= threshold:
        status = ("🟢 Normal", "green")
    elif sr_avg >= threshold - 0.05:
        status = ("🟡 Advertencia", "orange")
    else:
        status = ("🔴 Limpieza necesaria", "red")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("SR Promedio", f"{sr_avg*100:.2f}%")
    col2.metric("Pérdida de rendimiento", f"{sr_loss:.2f}%")
    col3.metric("Días bajo umbral", days_below)
    col4.markdown(f"<h3 style='color:{status[1]}'>{status[0]}</h3>", unsafe_allow_html=True)

    # Comparar periodos
    st.subheader("Comparar periodos")
    compare = st.checkbox("Comparar con periodo anterior")
    if compare and period != "Todo el histórico":
        periods = chart_data['Periodo'].unique()
        if len(periods) > 1:
            current = chart_data.iloc[-1]['Soiling Ratio']
            previous = chart_data.iloc[-2]['Soiling Ratio']
            diff = current - previous
            st.write(f"SR actual: {current*100:.2f}%, periodo anterior: {previous*100:.2f}%, diferencia: {diff*100:.2f}%")
        else:
            st.info("No hay suficiente información para comparar periodos.")

    # Recomendaciones de limpieza
    st.subheader("Fechas recomendadas para limpieza")
    clean_recommend = filtered_df[filtered_df['Soiling Ratio'] < threshold]
    st.dataframe(clean_recommend[['DateTime', 'Soiling Ratio']])

    # SR promedio por semana o mes
    st.subheader("SR promedio por semana o mes")
    if period in ["Semana", "Mes"]:
        st.dataframe(chart_data)

    # Días de pérdida acumulada
    st.subheader("Días de pérdida acumulada")
    loss_days = filtered_df[filtered_df['Soiling Ratio'] < threshold]['DateTime'].dt.date.nunique()
    st.write(f"Días de pérdida acumulada: {loss_days}")

    # Mostrar clima en la tabla con iconos
    st.subheader("Clima por fecha")
    filtered_df['Clima Icono'] = filtered_df['Clima'].apply(get_weather_icon)
    st.dataframe(filtered_df[['DateTime', 'Soiling Ratio', 'Clima', 'Clima Icono']])

    # Exportar reportes
    st.subheader("Exportar reportes")
    export_type = st.selectbox("Formato de exportación", ["CSV", "Excel"])
    if st.button("Exportar recomendaciones de limpieza"):
        export_df = clean_recommend[['DateTime', 'Soiling Ratio']]
        if export_type == "CSV":
            st.download_button("Descargar CSV", export_df.to_csv(index=False), file_name="recomendaciones_limpieza.csv")
        else:
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                export_df.to_excel(writer, index=False)
            st.download_button("Descargar Excel", buffer.getvalue(), file_name="recomendaciones_limpieza.xlsx")

    if st.button("Exportar SR promedio por periodo"):
        if export_type == "CSV":
            st.download_button("Descargar CSV", chart_data.to_csv(index=False), file_name="sr_promedio_periodo.csv")
        else:
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                chart_data.to_excel(writer, index=False)
            st.download_button("Descargar Excel", buffer.getvalue(), file_name="sr_promedio_periodo.xlsx")
else:
    st.info("Por favor, sube un archivo CSV y selecciona los filtros en la barra lateral.") 
    
