import streamlit as st
import pandas as pd
import os
from datetime import datetime
from data_manager import load_ubicaciones, save_ubicaciones, add_proyecto, update_proyecto, delete_proyecto
from utils import get_consecutive_days_below, get_weather_icon
from ui_components import show_kpis, show_chart
from api import get_openmeteo_events
import base64
import os
from api import get_openmeteo_events
from soiling_methods import apply_soiling_method, generar_recomendaciones

st.set_page_config(
    page_title='Soiling System Dashboard',
    page_icon=':🌍:',
)
with open('style.css') as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

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
    ubicaciones_path = os.path.join(os.path.dirname(__file__), "ubi", "ubicaciones.xlsx")
    ubicaciones_df = load_ubicaciones(ubicaciones_path)
    proyectos = ubicaciones_df["Proyecto"].tolist()
    selected_proyecto = st.selectbox("Selecciona un proyecto", proyectos + ["Agregar nuevo"], key="proyecto_select")

    if selected_proyecto == "Agregar nuevo":
        nuevo_nombre = st.text_input("Nombre del nuevo proyecto")
        nueva_lat = st.number_input("Latitud", format="%.6f", key="nueva_lat")
        nueva_lon = st.number_input("Longitud", format="%.6f", key="nueva_lon")
        if st.button("Guardar nuevo proyecto"):
            ubicaciones_df = add_proyecto(ubicaciones_df, nuevo_nombre, nueva_lat, nueva_lon)
            save_ubicaciones(ubicaciones_df, ubicaciones_path)
            st.success("Proyecto agregado. Recarga la página para verlo en la lista.")
        lat = nueva_lat
        lon = nueva_lon
    else:
        row = ubicaciones_df[ubicaciones_df["Proyecto"] == selected_proyecto].iloc[0]
        lat = st.number_input("Latitud", value=float(row["Latitud"]), format="%.6f", key="edit_lat")
        lon = st.number_input("Longitud", value=float(row["Longitud"]), format="%.6f", key="edit_lon")
        if st.button("Actualizar ubicación"):
            ubicaciones_df = update_proyecto(ubicaciones_df, selected_proyecto, lat, lon)
            save_ubicaciones(ubicaciones_df, ubicaciones_path)
            st.success("Ubicación actualizada.")
        if st.button("Eliminar proyecto"):
            ubicaciones_df = delete_proyecto(ubicaciones_df, selected_proyecto)
            save_ubicaciones(ubicaciones_df, ubicaciones_path)
            st.success("Proyecto eliminado. Recarga la página para actualizar la lista.")

    st.subheader("Carga y filtros de datos")
    uploaded_file = st.file_uploader("Selecciona tu archivo CSV", type=["csv"])
    
    # Agregar selectbox para método de soiling
    metodo_soiling = st.selectbox(
        "Método de cálculo de soiling",
        ["Sin modelo","SOMOSclean", "Kimber"],
        help="Selecciona el método para calcular el soiling ratio"
    )
    
    df = None
    filtered_df = None
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
            
            #df = apply_soiling_method(df, metodo_soiling)
            
            # Filtrar solo horas entre 6:00 y 20:00 (8 pm)
            df['hour'] = df['DateTime'].dt.hour
            df = df[(df['hour'] >= 6) & (df['hour'] <= 20)]
            df = df.drop(columns=['hour'])  # Opcional, para limpiar la columna extra

            df['DateTime_hour'] = df['DateTime'].dt.floor('H')

             
            with st.spinner("Consultando clima..."):
                df['Clima'] = get_openmeteo_events(df['DateTime'], lat, lon)
                
            # Aplicar método de soiling DESPUÉS de obtener clima
            df = apply_soiling_method(df, metodo_soiling)
            st.info(f"✓ Método {metodo_soiling} aplicado correctamente")

            min_date = df['DateTime'].min().date()
            max_date = df['DateTime'].max().date()

            if min_date < max_date:
                date_range = st.slider(
                    "Selecciona el rango de fechas",
                    min_value=min_date,
                    max_value=max_date,
                    value=(min_date, max_date)
                )
                mask = (df['DateTime'].dt.date >= date_range[0]) & (df['DateTime'].dt.date <= date_range[1])
                filtered_df = df.loc[mask].copy()
            else:
                filtered_df = df.copy()

            period = st.selectbox("Agrupar por:", ["Día", "Semana", "Mes", "Todo el histórico"])
            if period == "Semana":
                filtered_df['Periodo'] = filtered_df['DateTime'].dt.to_period('W').apply(lambda r: r.start_time)
            elif period == "Mes":
                filtered_df['Periodo'] = filtered_df['DateTime'].dt.to_period('M').apply(lambda r: r.start_time)
            elif period == "Día":
                filtered_df['Periodo'] = filtered_df['DateTime'].dt.date
            else:
                filtered_df['Periodo'] = 'Histórico'

            threshold = st.slider("Umbral de alerta para limpieza (%)", min_value=70, max_value=100, value=90)
            threshold = threshold / 100.0

            chart_type = st.selectbox("Tipo de gráfico", ["Línea", "Área", "Barras"])

        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")

# --- MAIN PAGE ---
st.title("🌍: Soiling System Dashboard")
st.markdown("""
Sube un archivo CSV con las columnas **DateTime** y **Soiling Ratio** para visualizar el ensuciamiento de tus paneles solares.  
*
""")

st.subheader("Ubicación seleccionada")
st.map(pd.DataFrame({'lat': [lat], 'lon': [lon]}), zoom=8)
st.caption(f"Coordenadas seleccionadas: lat={lat}, lon={lon}")

if 'filtered_df' in locals() and filtered_df is not None and not filtered_df.empty:
    chart_data = filtered_df.groupby('Periodo')['Soiling Ratio'].mean().reset_index()
    st.subheader("Visualización del Soiling Ratio")
    show_chart(chart_data, chart_type)

    sr_avg = filtered_df['Soiling Ratio'].mean()
    sr_loss = (1 - sr_avg) * 100
    days_below = get_consecutive_days_below(filtered_df, 'Soiling Ratio', threshold)
    if sr_avg >= threshold:
        status = ("🟢 Normal", "green")
    elif sr_avg >= threshold - 0.03:
        status = ("🟡 Advertencia", "orange")
    else:
        status = ("🔴 Limpieza necesaria", "red")
        
    show_kpis(sr_avg, sr_loss, days_below, status)
    
    # Agregar sección de recomendaciones
    st.subheader(f"📋 Recomendaciones basadas en {metodo_soiling}")
    recomendaciones = generar_recomendaciones(filtered_df, metodo_soiling, threshold)
    st.markdown(recomendaciones)
    
    st.subheader("Clima por fecha")
    filtered_df['Clima Icono'] = filtered_df['Clima'].apply(get_weather_icon)
    st.dataframe(filtered_df[['DateTime', 'Soiling Ratio', 'Clima', 'Clima Icono']])
    
    # Recomendaciones de limpieza
    st.subheader("Fechas recomendadas para limpieza")
    clean_recommend = filtered_df[filtered_df['Soiling Ratio'] < threshold]
    st.dataframe(clean_recommend[['DateTime', 'Soiling Ratio']])

else:
    st.info("Por favor, sube un archivo CSV y selecciona los filtros en la barra lateral.")
