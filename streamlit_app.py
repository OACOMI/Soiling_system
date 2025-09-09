import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from pvlib.soiling import kimber

st.set_page_config(
    page_title='Soiling System Dashboard',
    page_icon=':sun_with_face:',
)

# Sidebar: Selección de sistema de soiling y parámetros de ubicación
st.sidebar.header("Configuración del sistema de soiling")
system = st.sidebar.selectbox(
    "Selecciona el sistema de soiling:",
    ["Kimber", "SOLOs System"]
)
st.sidebar.markdown(f"**Sistema seleccionado:** {system}")

st.sidebar.subheader("Ubicación para consulta de lluvia (Kimber)")
lat = st.sidebar.number_input("Latitud", value=19.4326, format="%.4f")
lon = st.sidebar.number_input("Longitud", value=-99.1332, format="%.4f")
api_key = st.sidebar.text_input("API Key de OpenWeather", type="password")

st.title(":sun_with_face: Soiling System Dashboard")
st.markdown("""
Sube un archivo CSV con las columnas **DateTime** y **Soiling Ratio** para visualizar el ensuciamiento de tus paneles solares.
""")

uploaded_file = st.file_uploader("Selecciona tu archivo CSV", type=["csv"])

def get_rain_for_dates(dates, lat, lon, api_key):
    """
    Consulta la API de OpenWeather para obtener lluvia (mm) para cada fecha.
    Usa el endpoint de pronóstico gratuito (solo fechas futuras/cercanas).
    """
    rain_flags = []
    # Obtener pronóstico de lluvia para los próximos 5 días
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={api_key}&units=metric"
    response = requests.get(url)
    if response.status_code != 200:
        st.error("Error al consultar OpenWeather. Revisa tu API Key y ubicación.")
        return [0] * len(dates)
    data = response.json()
    # Crear un dict de lluvia por fecha
    rain_by_date = {}
    for entry in data['list']:
        entry_time = datetime.utcfromtimestamp(entry['dt'])
        rain = entry.get('rain', {}).get('3h', 0)
        date_key = entry_time.date()
        rain_by_date[date_key] = rain_by_date.get(date_key, 0) + rain
    # Asignar bandera de lluvia a cada fecha del DataFrame
    for dt in dates:
        rain = rain_by_date.get(dt.date(), 0)
        rain_flags.append(1 if rain > 0 else 0)
    return rain_flags

def get_consecutive_days_below(df, col, threshold):
    below = df[col] < threshold
    count = 0
    for b in below[::-1]:
        if b:
            count += 1
        else:
            break
    return count

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file, parse_dates=['DateTime'])
        df = df.sort_values('DateTime')
        df['Soiling Ratio'] = pd.to_numeric(df['Soiling Ratio'], errors='coerce')
        df = df.dropna(subset=['Soiling Ratio'])

        if system == "Kimber":
            # Pedir al usuario que consulte la lluvia antes de continuar
            if not api_key:
                st.warning("Ingresa tu API Key de OpenWeather en la barra lateral para usar el modelo Kimber.")
            else:
                if st.button("Consultar lluvia y calcular modelo Kimber"):
                    with st.spinner("Consultando datos de lluvia..."):
                        df['Rain'] = get_rain_for_dates(df['DateTime'], lat, lon, api_key)
                        df['Cleaning'] = 0  # Si no tienes eventos de limpieza
                        # Parámetros de Kimber (puedes hacerlos configurables)
                        rain_accumulation_threshold = 1.0
                        cleaning_threshold = 10.0
                        soiling_interval = 1
                        sr = kimber(
                            df['DateTime'],
                            df['Rain'],
                            cleaning=df['Cleaning'],
                            rain_accumulation_threshold=rain_accumulation_threshold,
                            cleaning_threshold=cleaning_threshold,
                            interval=soiling_interval
                        )
                        df['Soiling Ratio Kimber'] = sr
                    st.success("Modelo Kimber calculado.")
                    # Visualización y KPIs
                    st.line_chart(df.set_index('DateTime')['Soiling Ratio Kimber'], use_container_width=True)
                    st.dataframe(df[['DateTime', 'Soiling Ratio Kimber', 'Rain']])
        else:
            # SOLOs System: solo graficar lo subido
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

            # Visualización
            chart_type = st.selectbox("Tipo de gráfico", ["Línea", "Área", "Barras"])
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

    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")
else:
    st.info("Por favor, sube un archivo CSV para comenzar.")
    
    
