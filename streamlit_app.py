import streamlit as st
import pandas as pd
import os
from datetime import datetime
from data_manager import load_ubicaciones, save_ubicaciones, add_proyecto, update_proyecto, delete_proyecto
from utils import get_consecutive_days_below, get_weather_icon, get_unique_days_count, get_days_below_threshold
from ui_components import show_kpis, show_chart
from api import get_openmeteo_events
import plotly.graph_objects as go
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
            
    # Agregar selectbox para método de soiling
    metodo_soiling = st.selectbox(
        "Método de cálculo de soiling",
        ["Sin modelo","SOMOSclean", "Kimber"],
        help="Selecciona el método para calcular el soiling ratio"
    )
    
    st.subheader("Carga y filtros de datos")
    uploaded_file = st.file_uploader("Selecciona tu archivo CSV", type=["csv"])
    

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

                # Toggle para mostrar comparación (solo si hay modelo)
            if metodo_soiling != "Sin modelo":
                mostrar_comparacion = st.checkbox(
                    "📊 Comparar con datos originales",
                    value=False,
                    key="comparacion_check",
                    help="Muestra gráfico comparativo entre tus datos medidos y el modelo seleccionado"
                )
            else:
                mostrar_comparacion = False
                
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
""")

st.subheader("Ubicación seleccionada")
st.map(pd.DataFrame({'lat': [lat], 'lon': [lon]}), zoom=8)
st.caption(f"Coordenadas seleccionadas: lat={lat}, lon={lon}")

if 'filtered_df' in locals() and filtered_df is not None and not filtered_df.empty:
    st.subheader("Visualización del Soiling Ratio")
    
    # ========== LÓGICA DE GRAFICACIÓN CON TOGGLE ==========
    if mostrar_comparacion and 'Soiling Ratio Original' in filtered_df.columns:
        # GRÁFICO COMPARATIVO CON ZOOM MEJORADO
        chart_data = filtered_df.groupby('Periodo').agg({
            'Soiling Ratio': 'mean',
            'Soiling Ratio Original': 'mean'
        }).reset_index()
        
        fig = go.Figure()
        
        # Línea de datos originales
        fig.add_trace(go.Scatter(
            x=chart_data['Periodo'], 
            y=chart_data['Soiling Ratio Original'],
            mode='lines+markers',
            name='📊 Datos Medidos',
            line=dict(color='#FF6B6B', width=3),
            marker=dict(size=6, color='#FF6B6B'),
            hovertemplate='<b>%{x}</b><br>Medido: %{y:.4f}<extra></extra>'
        ))
        
        # Línea del modelo
        fig.add_trace(go.Scatter(
            x=chart_data['Periodo'], 
            y=chart_data['Soiling Ratio'],
            mode='lines+markers',
            name=f'🔬 Modelo {metodo_soiling}',
            line=dict(color='#4ECDC4', width=3),
            marker=dict(size=6, color='#4ECDC4'),
            hovertemplate='<b>%{x}</b><br>Modelo: %{y:.4f}<extra></extra>'
        ))
        
        # Ajustar el rango del eje Y dinámicamente
        y_min = min(chart_data['Soiling Ratio'].min(), chart_data['Soiling Ratio Original'].min())
        y_max = max(chart_data['Soiling Ratio'].max(), chart_data['Soiling Ratio Original'].max())
        y_range = y_max - y_min
        
        if y_range < 0.05:
            y_padding = 0.025
        else:
            y_padding = y_range * 0.15
        
        fig.update_layout(
            title=f'Comparación: Datos Medidos vs Modelo {metodo_soiling}',
            xaxis_title='Periodo',
            #yaxis_title='Soiling Ratio',
            yaxis=dict(
                range=[max(0, y_min - y_padding), min(1, y_max + y_padding)],
                tickformat='.3f',
                gridcolor='lightgray',
                showgrid=True
            ),
            xaxis=dict(
                gridcolor='lightgray',
                showgrid=True
            ),
            hovermode='x unified',
            legend=dict(
                yanchor="top", 
                y=0.99, 
                xanchor="left", 
                x=0.01,
                bgcolor="rgba(255,255,255,0.9)",
                bordercolor="lightgray",
                borderwidth=1
            ),
            template="plotly_white",
            height=600
        )
        
        # Selector de rango temporal
        fig.update_xaxes(
            rangeselector=dict(
                buttons=list([
                    dict(count=7, label="7d", step="day", stepmode="backward"),
                    dict(count=14, label="14d", step="day", stepmode="backward"),
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(step="all", label="Todo")
                ]),
                bgcolor="lightgray",
                activecolor="blue",
                x=0.01,
                y=1.12
            )
        )
        
        # Configuración de herramientas
        config = {
            'displayModeBar': True,
            'displaylogo': False,
            'toImageButtonOptions': {
                'format': 'png',
                'filename': f'comparacion_{metodo_soiling}',
                'height': 1080,
                'width': 1920,
                'scale': 2
            }
        }
        
        st.plotly_chart(fig, use_container_width=True, config=config)
    
        fig.update_layout(
            title=f'Comparación: Datos Medidos vs Modelo {metodo_soiling}',
            xaxis_title='Periodo',
            yaxis_title='Soiling Ratio',
            yaxis=dict(
                range=[max(0, y_min - y_padding), min(1, y_max + y_padding)],  # Escala de 0 a 1
                tickformat='.2f',  # Formato decimal, no porcentaje
                tickmode='linear',
                tick0=0,
                dtick=0.05  # Incrementos de 0.05
            ),
            hovermode='x unified',
            legend=dict(
                yanchor="top", 
                y=0.99, 
                xanchor="left", 
                x=0.01,
                bgcolor="rgba(255,255,255,0.9)",
                bordercolor="lightgray",
                borderwidth=1
            ),
            template="plotly_white",
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Métricas de comparación
        st.subheader("📈 Métricas de Comparación")
        error_abs = abs(chart_data['Soiling Ratio'] - chart_data['Soiling Ratio Original']).mean()
        error_pct = (error_abs / chart_data['Soiling Ratio Original'].mean()) * 100
        correlacion = chart_data['Soiling Ratio'].corr(chart_data['Soiling Ratio Original'])
        
        # Calcular RMSE (Root Mean Square Error)
        rmse = ((chart_data['Soiling Ratio'] - chart_data['Soiling Ratio Original']) ** 2).mean() ** 0.5
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Error Absoluto Medio", 
                f"{error_abs:.4f}",
                help="Diferencia promedio entre datos medidos y modelo"
            )
        with col2:
            st.metric(
                "RMSE", 
                f"{rmse:.4f}",
                help="Raíz del error cuadrático medio"
            )
        with col3:
            st.metric(
                "Error Porcentual", 
                f"{error_pct:.2f}%",
                delta=f"{-error_pct:.2f}%" if error_pct < 5 else None,
                delta_color="inverse"
            )
        with col4:
            st.metric(
                "Correlación", 
                f"{correlacion:.3f}",
                help="Correlación entre datos medidos y modelo (1.0 = perfecto)"
            )
        
        # Mostrar estadísticas adicionales
        with st.expander("📊 Ver estadísticas detalladas"):
            st.write("**Datos Medidos:**")
            st.write(f"- Promedio: {chart_data['Soiling Ratio Original'].mean():.4f}")
            st.write(f"- Mínimo: {chart_data['Soiling Ratio Original'].min():.4f}")
            st.write(f"- Máximo: {chart_data['Soiling Ratio Original'].max():.4f}")
            st.write(f"- Desviación estándar: {chart_data['Soiling Ratio Original'].std():.4f}")
            
            st.write(f"\n**Modelo {metodo_soiling}:**")
            st.write(f"- Promedio: {chart_data['Soiling Ratio'].mean():.4f}")
            st.write(f"- Mínimo: {chart_data['Soiling Ratio'].min():.4f}")
            st.write(f"- Máximo: {chart_data['Soiling Ratio'].max():.4f}")
            st.write(f"- Desviación estándar: {chart_data['Soiling Ratio'].std():.4f}")
        
    else:
        # GRÁFICO SIMPLE (sin comparación)
        chart_data = filtered_df.groupby('Periodo')['Soiling Ratio'].mean().reset_index()
        show_chart(chart_data, chart_type)
    # ======================================================

    # KPIs
    sr_avg = filtered_df['Soiling Ratio'].mean()
    sr_loss = (1 - sr_avg) * 100
    days_below = get_days_below_threshold(filtered_df, 'Soiling Ratio', threshold)
    total_days = get_unique_days_count(filtered_df)
    
    if sr_avg >= threshold:
        status = ("🟢 Normal", "green")
    elif sr_avg >= threshold - 0.03:
        status = ("🟡 Advertencia", "orange")
    else:
        status = ("🔴 Limpieza necesaria", "red")
        
    show_kpis(sr_avg, sr_loss, days_below, status, total_days)

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

