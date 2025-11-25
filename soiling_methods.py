import pandas as pd
import numpy as np

def calculate_kimber_ratio(df, cleaning_threshold=25.0, soiling_rate=0.0015, 
                          grace_period_days=15, max_soiling=0.30):
    """
    Método Kimber (basado en pvlib)
    El ensuciamiento se acumula a tasa constante hasta ser limpiado manual o naturalmente.
    
    Parámetros:
    - cleaning_threshold: Umbral de lluvia (mm) para limpieza total
    - soiling_rate: Tasa de acumulación diaria (default 0.15%)
    - grace_period_days: Días sin ensuciamiento después de lluvia fuerte
    - max_soiling: Máximo nivel de ensuciamiento (default 30%)
    """
    df = df.copy()
    df = df.sort_values('DateTime')
    
    soiling_loss = []
    cumulative_loss = 0.0
    grace_counter = 0  # Contador de días de gracia después de lluvia
    
    # Agrupar por día para sumar precipitación diaria
    df['date'] = df['DateTime'].dt.date
    daily_precip = df.groupby('date')['precipitation'].sum().to_dict()
    
    for idx, row in df.iterrows():
        fecha = row['date']
        precip_daily = daily_precip.get(fecha, 0)
        
        # Si hay lluvia que supera el umbral, limpieza total
        if precip_daily >= cleaning_threshold:
            cumulative_loss = 0.0
            grace_counter = grace_period_days  # Activar período de gracia
        # Período de gracia: tierra húmeda, sin ensuciamiento
        elif grace_counter > 0:
            grace_counter -= 1/24  # Decrementar por hora
            # No acumular ensuciamiento durante el período de gracia
        else:
            # Acumulación normal a tasa constante
            cumulative_loss += soiling_rate / 24  # Por hora
            
            # Limitar al máximo de ensuciamiento
            cumulative_loss = min(cumulative_loss, max_soiling)
        
        # Soiling Ratio = 1 - pérdida acumulada
        soiling_loss.append(1 - cumulative_loss)
    
    df['Soiling Ratio Kimber'] = soiling_loss
    df = df.drop(columns=['date'])
    return df

def calculate_somosclean_ratio(df, delta_SL_sat=0.25, k=15.0, heavy_rain_threshold=5.0):
    """
    Método SOMOSclean (ENEL)
    Modelo empírico basado en crecimiento exponencial complementario.
    
    Fórmula: SL = ΔSLsat * (1 - e^(-eqD/k))
    
    Parámetros:
    - delta_SL_sat: Nivel de saturación máximo (20-30%, default 25%)
    - k: Constante de tiempo que representa la tasa de ensuciamiento (días)
    - heavy_rain_threshold: Umbral de precipitación para limpieza total (mm)
    """
    df = df.copy()
    df = df.sort_values('DateTime')
    
    soiling_loss = []
    eqD = 0.0  # Días equivalentes desde última limpieza
    
    for idx, row in df.iterrows():
        clima = row.get('Clima', 'Sin datos')
        precip = row.get('precipitation', 0)  # precipitación en mm
        
        # Calcular factor f según eventos
        if clima == 'Lluvia':
            if precip >= heavy_rain_threshold:
                # Limpieza total (lluvia intensa)
                f = 0.0
            elif precip >= 1.0:
                # Limpieza parcial proporcional a la lluvia
                # f decrece linealmente de 1 a 0 entre 1mm y heavy_rain_threshold
                f = 1 - (precip / heavy_rain_threshold)
                f = max(0, min(1, f))
            else:
                # Lluvia ligera, sin limpieza significativa
                f = 0.95
        elif clima == 'Despejado':
            # Días despejados pueden aumentar ensuciamiento (eventos de polvo)
            # Se asume f ligeramente > 1 para simular acumulación acelerada
            f = 1.1
        else:
            # Día normal sin eventos especiales
            f = 1.0
        
        # Actualizar eqD según la fórmula: eqD(d) = f * (eqD(d-1) + 1)
        eqD = f * (eqD + 1)
        
        # Calcular pérdida por ensuciamiento según modelo exponencial
        SL = delta_SL_sat * (1 - np.exp(-eqD / k))
        
        # Soiling Ratio = 1 - SL
        soiling_loss.append(1 - SL)
    
    df['Soiling Ratio SOMOSclean'] = soiling_loss
    return df

def apply_soiling_method(df, metodo):
    """
    Aplica el método de soiling seleccionado y actualiza la columna 'Soiling Ratio'.
    Si es "Sin modelo", normaliza los datos originales para mejor visualización.
    """
    if metodo == "SOMOSclean":
        df = calculate_somosclean_ratio(df)
        df['Soiling Ratio'] = df['Soiling Ratio SOMOSclean']
        df.drop(columns=['Soiling Ratio SOMOSclean'], inplace=True)
    elif metodo == "Kimber":
        df = calculate_kimber_ratio(df)
        df['Soiling Ratio'] = df['Soiling Ratio Kimber']
        df.drop(columns=['Soiling Ratio Kimber'], inplace=True)
    elif metodo == "Sin modelo":
        # Normalizar datos si están en rango 0-100 en lugar de 0-1
        max_val = df['Soiling Ratio'].max()
        if max_val > 10:  # Si los valores son > 10, probablemente están en escala 0-100
            df['Soiling Ratio'] = df['Soiling Ratio'] / 100.0
            import streamlit as st
            st.info("✓ Datos normalizados a escala 0-1 para mejor visualización")
    
    return df

def generar_recomendaciones(df, metodo, threshold):
    """
    Genera recomendaciones de limpieza basadas en el método y los datos.
    Umbral crítico: SR < 0.96 (pérdida > 4%)
    """
    recomendaciones = []
    
    # Calcular métricas
    sr_avg = df['Soiling Ratio'].mean()
    sr_min = df['Soiling Ratio'].min()
    perdida_avg = (1 - sr_avg) * 100  # Pérdida promedio en %
    perdida_max = (1 - sr_min) * 100  # Pérdida máxima en %
    
    # Umbral crítico: 4% de pérdida = SR < 0.96
    umbral_critico = 0.96
    dias_bajo_umbral = len(df[df['Soiling Ratio'] < umbral_critico])
    total_dias = len(df['DateTime'].dt.date.unique())
    
    # Recomendación por método
    if metodo == "SOMOSclean":
        if sr_avg < 0.96:  # Pérdida > 4%
            recomendaciones.append(f"🔴 **Limpieza urgente recomendada** - Pérdida promedio de {perdida_avg:.2f}% según SOMOSclean")
            recomendaciones.append(f"   Pérdida máxima alcanzada: {perdida_max:.2f}%")
            recomendaciones.append(f"   Modelo validado con error promedio de 0.71% (ENEL)")
        elif sr_avg < 0.98:  # Pérdida entre 2-4%
            recomendaciones.append(f"🟡 **Programar limpieza preventiva** - Pérdida de {perdida_avg:.2f}% según SOMOSclean")
            recomendaciones.append(f"   Nivel de saturación aproximándose")
        else:
            recomendaciones.append(f"✅ **Sistema operando óptimamente** - Pérdida controlada ({perdida_avg:.2f}%) según SOMOSclean")
        
        # Análisis específico de eventos de limpieza
        dias_lluvia_intensa = len(df[(df['Clima'] == 'Lluvia') & (df.get('precipitation', 0) >= 5)])
        dias_lluvia_parcial = len(df[(df['Clima'] == 'Lluvia') & (df.get('precipitation', 0) < 5) & (df.get('precipitation', 0) >= 1)])
        
        if dias_lluvia_intensa > 0:
            recomendaciones.append(f"🌧️ {dias_lluvia_intensa} eventos de limpieza total por lluvia intensa")
        if dias_lluvia_parcial > 0:
            recomendaciones.append(f"💧 {dias_lluvia_parcial} eventos de limpieza parcial")
        if dias_lluvia_intensa == 0 and dias_lluvia_parcial == 0:
            recomendaciones.append(f"☀️ Sin eventos de limpieza natural - Limpieza manual urgente")
        
        # Frecuencia basada en constante de tiempo k (15 días típico)
        if dias_bajo_umbral > total_dias * 0.3:
            recomendaciones.append(f"📅 Frecuencia óptima: Limpieza cada 10-12 días")
        else:
            recomendaciones.append(f"📅 Frecuencia óptima: Limpieza cada 18-22 días")
            
    elif metodo == "Kimber":
        if sr_avg < 0.96:  # Pérdida > 4%
            recomendaciones.append(f"🔴 **Limpieza inmediata necesaria** - Pérdida de {perdida_avg:.2f}% según Kimber")
            recomendaciones.append(f"   Pérdida máxima alcanzada: {perdida_max:.2f}%")
            recomendaciones.append(f"   Modelo: acumulación constante hasta limpieza natural o manual")
        elif sr_avg < 0.98:  # Pérdida entre 2-4%
            recomendaciones.append(f"🟡 **Limpieza preventiva recomendada** - Pérdida de {perdida_avg:.2f}% según Kimber")
        else:
            recomendaciones.append(f"✅ **Desempeño óptimo** - Pérdida controlada ({perdida_avg:.2f}%) según Kimber")
        
        # Análisis de eventos de limpieza (threshold 25mm)
        df['date_temp'] = df['DateTime'].dt.date
        daily_precip = df.groupby('date_temp')['precipitation'].sum()
        dias_limpieza_total = len(daily_precip[daily_precip >= 25.0])
        
        if dias_limpieza_total > 0:
            recomendaciones.append(f"🌧️ {dias_limpieza_total} eventos de limpieza por lluvia (≥25mm)")
            recomendaciones.append(f"   Período de gracia de 7 días aplicado después de cada evento")
        else:
            recomendaciones.append(f"☀️ Sin lluvias suficientes para limpieza natural (requiere ≥25mm)")
        
        # Frecuencia recomendada
        if dias_bajo_umbral > total_dias * 0.3:
            recomendaciones.append(f"📅 Frecuencia recomendada: Limpieza cada 7-10 días (alta acumulación)")
        elif dias_bajo_umbral > 0:
            recomendaciones.append(f"📅 Frecuencia recomendada: Limpieza cada 15-20 días")
        else:
            recomendaciones.append(f"📅 Frecuencia recomendada: Limpieza cada 25-30 días")
    
    elif metodo == "Sin modelo":
        if sr_avg < 0.96:  # Pérdida > 4%
            recomendaciones.append(f"🔴 **Limpieza urgente recomendada** - Pérdida promedio de {perdida_avg:.2f}%")
            recomendaciones.append(f"   Pérdida máxima detectada: {perdida_max:.2f}%")
        elif sr_avg < 0.98:  # Pérdida entre 2-4%
            recomendaciones.append(f"🟡 **Considerar limpieza preventiva** - Pérdida de {perdida_avg:.2f}%")
        else:
            recomendaciones.append(f"✅ **Sistema en rangos aceptables** - Pérdida mínima ({perdida_avg:.2f}%)")
        
        # Análisis de clima
        dias_lluvia = len(df[df['Clima'] == 'Lluvia'])
        dias_despejado = len(df[df['Clima'] == 'Despejado'])
        
        if dias_lluvia > 0:
            recomendaciones.append(f"🌧️ {dias_lluvia} días con lluvia detectados")
        if dias_despejado > total_dias * 0.7:
            recomendaciones.append(f"☀️ Período mayormente seco ({dias_despejado} días) - Mayor acumulación esperada")
        
        # Frecuencia básica
        if dias_bajo_umbral > total_dias * 0.3:
            recomendaciones.append(f"📅 Frecuencia sugerida: Limpieza cada 10-15 días")
        elif dias_bajo_umbral > 0:
            recomendaciones.append(f"📅 Frecuencia sugerida: Limpieza cada 20-25 días")
        else:
            recomendaciones.append(f"📅 Frecuencia sugerida: Limpieza cada 30 días")
    
    # Estadísticas adicionales
    recomendaciones.append(f"\n**📊 Estadísticas del período:**")
    recomendaciones.append(f"  - Días con pérdida > 4%: {dias_bajo_umbral} de {total_dias}")
    recomendaciones.append(f"  - Soiling Ratio promedio: {sr_avg*100:.2f}%")
    recomendaciones.append(f"  - Soiling Ratio mínimo: {sr_min*100:.2f}%")
    
    # Mejores fechas para limpieza (días con mayor pérdida)
    df_sorted = df.sort_values('Soiling Ratio')
    peores_dias = df_sorted.head(min(5, len(df)))
    
    recomendaciones.append("\n**📍 Fechas prioritarias para limpieza:**")
    for idx, row in peores_dias.iterrows():
        fecha = row['DateTime'].strftime('%Y-%m-%d')
        ratio = row['Soiling Ratio'] * 100
        perdida = (1 - row['Soiling Ratio']) * 100
        clima = row.get('Clima', 'Sin datos')
        recomendaciones.append(f"  - {fecha}: SR = {ratio:.1f}% (Pérdida: {perdida:.1f}%, Clima: {clima})")
    
    return "\n".join(recomendaciones)
