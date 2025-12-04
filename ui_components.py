import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

def show_kpis(sr_avg, sr_loss, days_below, status, total_days=None):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Soiling Ratio Promedio", f"{sr_avg:.2%}")
    with col2:
        st.metric("Pérdida por Ensuciamiento", f"{sr_loss:.2f}%")
    with col3:
        if total_days:
            st.metric("Días con pérdida > umbral", f"{days_below} de {total_days}")
        else:
            st.metric("Días con pérdida", days_below)
    with col4:
        st.markdown(f"<span style='color:{status[1]}'>{status[0]}</span>", unsafe_allow_html=True)

def show_chart(data, chart_type):
    """
    Muestra gráficos con zoom mejorado y mejor visualización de variaciones
    """
    # Calcular rango dinámico del eje Y para mejor visualización
    y_min = data['Soiling Ratio'].min()
    y_max = data['Soiling Ratio'].max()
    y_range = y_max - y_min
    
    # Si el rango es muy pequeño, agregar más padding para ver mejor las variaciones
    if y_range < 0.05:  # Menos del 5% de variación
        y_padding = 0.025  # Padding fijo para ver mejor
    else:
        y_padding = y_range * 0.15  # 15% de padding
    
    y_min_plot = max(0, y_min - y_padding)
    y_max_plot = min(1, y_max + y_padding)
    
    if chart_type == "Línea":
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=data['Periodo'],
            y=data['Soiling Ratio'],
            mode='lines+markers',
            name='Soiling Ratio',
            line=dict(color='#1f77b4', width=3),
            marker=dict(size=6, color='#1f77b4'),
            hovertemplate='<b>%{x}</b><br>SR: %{y:.4f}<extra></extra>'
        ))
        
        fig.update_layout(
            #title='Soiling Ratio por Periodo',
            xaxis_title='Periodo',
            yaxis_title='Soiling Ratio',
            yaxis=dict(
                range=[y_min_plot, y_max_plot],
                tickformat='.3f',
                gridcolor='lightgray',
                showgrid=True
            ),
            xaxis=dict(
                gridcolor='lightgray',
                showgrid=True
            ),
            hovermode='x unified',
            template='plotly_white',
            height=500
        )
        
    elif chart_type == "Barra":
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=data['Periodo'],
            y=data['Soiling Ratio'],
            name='Soiling Ratio',
            marker_color='#1f77b4',
            hovertemplate='<b>%{x}</b><br>SR: %{y:.4f}<extra></extra>'
        ))
        
        fig.update_layout(
            title='Soiling Ratio por Periodo',
            xaxis_title='Periodo',
            yaxis_title='Soiling Ratio',
            yaxis=dict(
                range=[y_min_plot, y_max_plot],
                tickformat='.3f',
                gridcolor='lightgray',
                showgrid=True
            ),
            template='plotly_white',
            height=500
        )
        
    else:  # Área
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=data['Periodo'],
            y=data['Soiling Ratio'],
            mode='lines',
            name='Soiling Ratio',
            fill='tozeroy',
            line=dict(color='#1f77b4', width=2),
            fillcolor='rgba(31, 119, 180, 0.3)',
            hovertemplate='<b>%{x}</b><br>SR: %{y:.4f}<extra></extra>'
        ))
        
        fig.update_layout(
            title='Soiling Ratio por Periodo',
            xaxis_title='Periodo',
            yaxis_title='Soiling Ratio',
            yaxis=dict(
                range=[y_min_plot, y_max_plot],
                tickformat='.3f',
                gridcolor='lightgray',
                showgrid=True
            ),
            xaxis=dict(
                gridcolor='lightgray',
                showgrid=True
            ),
            template='plotly_white',
            height=500
        )
    
    # Configurar herramientas de zoom e interactividad
    fig.update_xaxes(
        rangeslider_visible=False,
        rangeselector=dict(
            buttons=list([
                dict(count=7, label="7d", step="day", stepmode="backward"),
                dict(count=14, label="14d", step="day", stepmode="backward"),
                dict(count=1, label="1m", step="month", stepmode="backward"),
                dict(step="all", label="Todo")
            ]),
            bgcolor="gray",
            activecolor="blue",
            font=dict(
                color="white",              # <-- CAMBIAR AQUÍ: Color del texto
                size=12,                    # Tamaño de la fuente
                family="Arial, sans-serif"  # Familia de fuente
            ),
            x=0.01,
            y=1.15
        )
    )
    
    # Habilitar herramientas de zoom
    config = {
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'eraseshape'],
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
        'toImageButtonOptions': {
            'format': 'png',
            'filename': 'soiling_ratio_chart',
            'height': 1080,
            'width': 1920,
            'scale': 2
        }
    }
    
    st.plotly_chart(fig, use_container_width=True, config=config)
    
    # Instrucciones de uso
    with st.expander("ℹ️ Cómo usar el zoom interactivo"):
        st.markdown("""
        **Herramientas disponibles:**
        - 🔍 **Zoom**: Click y arrastra sobre el área que quieres ampliar
        - 🖱️ **Pan**: Arrastra para mover la vista (después de hacer zoom)
        - 🏠 **Reset**: Doble click para volver a la vista original
        - 📅 **Selectores**: Usa los botones superiores (7d, 14d, 1m, Todo)
        - 💾 **Descargar**: Click en el icono de cámara para guardar la imagen
        
        **Atajos de teclado:**
        - Shift + Click: Zoom en eje X solamente
        - Alt + Click: Zoom en eje Y solamente
        """)
