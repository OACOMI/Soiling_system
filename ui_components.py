# ui_components.py
import streamlit as st

def show_kpis(sr_avg, sr_loss, days_below, status):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("SR Promedio", f"{sr_avg*100:.2f}%")
    col2.metric("Pérdida de rendimiento", f"{sr_loss:.2f}%")
    col3.metric("Días bajo umbral", days_below)
    col4.markdown(f"<h3 style='color:{status[1]}'>{status[0]}</h3>", unsafe_allow_html=True)

def show_chart(chart_data, chart_type):
    if chart_type == "Línea":
        st.line_chart(chart_data.set_index('Periodo')['Soiling Ratio'], use_container_width=True)
    elif chart_type == "Área":
        st.area_chart(chart_data.set_index('Periodo')['Soiling Ratio'], use_container_width=True)
    else:
        st.bar_chart(chart_data.set_index('Periodo')['Soiling Ratio'], use_container_width=True)
        
        
