import streamlit as st
import pandas as pd
from pandas.tseries.offsets import MonthEnd

# Configuración de la página
st.set_page_config(page_title="Matriz Vintage - Últimos 24 Meses", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_parquet("vintage_acum.parquet")
    # Aseguramos que mes_apertura sea tipo datetime para poder filtrar por tiempo
    df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
    return df

try:
    df = load_data()

    st.title("📊 Matriz de Saldos (Últimos 24 Meses)")
    
    # 1. Determinar el rango de fechas
    fecha_max = df['mes_apertura'].max()
    # Calculamos 24 meses hacia atrás desde la fecha máxima
    fecha_inicio = fecha_max - pd.DateOffset(months=24)

    # 2. Filtrar el DataFrame
    df_filtrado = df[df['mes_apertura'] >= fecha_inicio].copy()

    # Formateamos la fecha para que se vea bien en la tabla (YYYY-MM)
    df_filtrado['mes_apertura_str'] = df_filtrado['mes_apertura'].dt.strftime('%Y-%m')

    st.info(f"Mostrando cosechas desde **{fecha_inicio.strftime('%B %Y')}** hasta **{fecha_max.strftime('%B %Y')}**.")

    # 3. Crear la Tabla Pivote
    # Usamos 'mes_apertura_str' para las filas y 'dif_meses' para las columnas
    matriz_saldos = df_filtrado.pivot_table(
        index='mes_apertura_str', 
        columns='dif_meses', 
        values='saldo_capital_total', 
        aggfunc='sum'
    )

    # Ordenar las filas de la más reciente a la más antigua
    matriz_saldos = matriz_saldos.sort_index(ascending=False)

    # 4. Mostrar la Matriz
    # Llenamos con 0 y aplicamos formato de moneda
    st.dataframe(
        matriz_saldos.fillna(0).style.format("${:,.2f}"),
        use_container_width=True
    )

    # 5. Métricas de Control
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Fecha Máxima en Datos", fecha_max.strftime('%Y-%m'))
    with col2:
        total_ventana = df_filtrado['saldo_capital_total'].sum()
        st.metric("Saldo Total (Ventana 24m)", f"${total_ventana:,.2f}")

except Exception as e:
    st.error(f"Error al procesar los datos: {e}")
    st.info("Verifica que las columnas 'mes_apertura', 'dif_meses' y 'saldo_capital_total' existan.")