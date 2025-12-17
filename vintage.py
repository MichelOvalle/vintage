import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta

# Configuración de la página
st.set_page_config(page_title="Matriz de Capital Vintage", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_parquet("vintage_acum.parquet")
    if 'mes_apertura' in df.columns:
        df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
    return df

try:
    df_raw = load_data()

    st.title("📊 Matriz de Capital: Vista Rectangular")
    
    # 1. Definir la fecha base (Máximo de mes_apertura)
    fecha_max = df_raw['mes_apertura'].max()
    
    # Filtro de filas: Últimas 24 cosechas (o las que gustes mostrar)
    fecha_inicio_filas = fecha_max - pd.DateOffset(months=24)
    df = df_raw[df_raw['mes_apertura'] >= fecha_inicio_filas].copy()
    df['mes_apertura_str'] = df['mes_apertura'].dt.strftime('%Y-%m')

    # 2. Construcción de la Matriz con Nombres de Columnas Dinámicos
    results = []

    for i in range(25):  # Generamos 25 columnas (0 a 24)
        col_num = f'saldo_capital_total_c{i+1}'
        col_den = f'capital_c{i+1}'
        
        # Calcular nombre de la columna (Fecha de cierre)
        fecha_columna = fecha_max - relativedelta(months=i)
        nombre_col_real = fecha_columna.strftime('%Y-%m')

        if col_num in df.columns and col_den in df.columns:
            # Cálculo del ratio por grupo
            temp = df.groupby('mes_apertura_str').apply(
                lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() != 0 else None
            )
            temp.name = nombre_col_real
            results.append(temp)

    if results:
        # Unimos las series en un DataFrame
        matriz_final = pd.concat(results, axis=1)
        
        # --- APLICANDO EL ORDEN DE TU IMAGEN ---
        
        # Filas: Orden Ascendente (2023-11 arriba, 2025-11 abajo)
        matriz_final = matriz_final.sort_index(ascending=True)
        
        # Columnas: Orden Descendente (2025-11 izquierda, 2023-11 derecha)
        # Como se crearon en orden de i=0 (max) a i=24 (min), ya vienen en ese orden,
        # pero forzamos el ordenamiento de las columnas para asegurar:
        cols_ordenadas = sorted(matriz_final.columns, reverse=True)
        matriz_final = matriz_final.reindex(columns=cols_ordenadas)

        # 3. Mostrar la Matriz en Streamlit
        st.subheader("Ratio de Capital por Mes de Calendario")
        
        # Mostramos la matriz completa (sin máscara triangular)
        st.dataframe(
            matriz_final.style.format("{:.2%}", na_rep=""),
            use_container_width=True
        )

        st.caption(f"Nota: La matriz muestra el ratio calculado para cada intersección de apertura y cierre.")

    else:
        st.error("No se encontraron las columnas 'c1', 'c2', etc. en el archivo.")

except Exception as e:
    st.error(f"Error técnico: {e}")