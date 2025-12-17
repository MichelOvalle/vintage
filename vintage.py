import streamlit as st
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Matriz de Ratio de Capital", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_parquet("vintage_acum.parquet")
    # Convertir a datetime para filtrar
    if 'mes_apertura' in df.columns:
        df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
    return df

try:
    df_raw = load_data()

    st.title("📊 Matriz de Ratio: Saldo Capital / Capital Inicial")
    st.markdown("Cálculo dinámico: `saldo_capital_total_cX / capital_cX` por cada mes de maduración.")

    # 1. Filtro de los últimos 24 meses
    fecha_max = df_raw['mes_apertura'].max()
    fecha_inicio = fecha_max - pd.DateOffset(months=24)
    df = df_raw[df_raw['mes_apertura'] >= fecha_inicio].copy()

    # 2. Creación de la Matriz de Ratios
    # Vamos a crear un nuevo DataFrame donde el índice sea el mes de apertura
    df['mes_apertura_str'] = df['mes_apertura'].dt.strftime('%Y-%m')
    
    # Preparamos una lista para almacenar los resultados por cada dif_meses
    results = []

    # Iteramos para crear las columnas de dif_meses 0 a 24 (según el patrón c1 a c25)
    # Nota: Siguiendo tu patrón dif_meses=0 -> c1, dif_meses=1 -> c2...
    for i in range(25):  # Esto generará desde dif_meses 0 hasta 24
        col_num = f'saldo_capital_total_c{i+1}'
        col_den = f'capital_c{i+1}'
        
        if col_num in df.columns and col_den in df.columns:
            # Calculamos el ratio para esta maduración específica
            # Usamos sum() por si hay múltiples registros para el mismo mes_apertura
            temp = df.groupby('mes_apertura_str').apply(
                lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() != 0 else 0
            )
            temp.name = i # El nombre de la serie será el dif_meses (0, 1, 2...)
            results.append(temp)

    if results:
        # Unimos todos los meses en una sola matriz
        matriz_ratios = pd.concat(results, axis=1)
        matriz_ratios = matriz_ratios.sort_index(ascending=False)

        # 3. Mostrar la Matriz
        st.subheader("Visualización de Ratios (Porcentaje)")
        
        # Aplicamos un gradiente de color para identificar caídas de saldo fácilmente
        st.dataframe(
            matriz_ratios.style.format("{:.2%}")
            .background_gradient(cmap='RdYlGn', axis=None), # Verde es más capital, rojo es menos
            use_container_width=True
        )

        # 4. Notas técnicas
        st.caption(f"Datos filtrados desde {fecha_inicio.strftime('%Y-%m')} hasta {fecha_max.strftime('%Y-%m')}.")
        st.info("La fórmula aplicada es: (Suma de saldo_capital_total_cX) / (Suma de capital_cX) para cada celda.")

    else:
        st.error("No se encontraron columnas con el formato 'saldo_capital_total_cX' o 'capital_cX'.")

except Exception as e:
    st.error(f"Error en el procesamiento: {e}")