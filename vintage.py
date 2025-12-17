import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta

# Configuración de la página
st.set_page_config(page_title="Matriz de Capital - Orden Específico", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_parquet("vintage_acum.parquet")
    if 'mes_apertura' in df.columns:
        df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
    return df

try:
    df_raw = load_data()

    st.title("📊 Matriz de Capital: Orden Personalizado")
    
    # 1. Definir la fecha base
    fecha_max = df_raw['mes_apertura'].max()
    
    # Filtro de filas: Últimas 24 cosechas
    fecha_inicio_filas = fecha_max - pd.DateOffset(months=24)
    df = df_raw[df_raw['mes_apertura'] >= fecha_inicio_filas].copy()
    df['mes_apertura_str'] = df['mes_apertura'].dt.strftime('%Y-%m')

    # 2. Construcción de la Matriz
    results = []

    for i in range(25):
        col_num = f'saldo_capital_total_c{i+1}'
        col_den = f'capital_c{i+1}'
        
        fecha_columna = fecha_max - relativedelta(months=i)
        nombre_col_real = fecha_columna.strftime('%Y-%m')

        if col_num in df.columns and col_den in df.columns:
            temp = df.groupby('mes_apertura_str').apply(
                lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() != 0 else None
            )
            temp.name = nombre_col_real
            results.append(temp)

    if results:
        matriz_final = pd.concat(results, axis=1)
        
        # --- AJUSTE DE ÓRDENES SOLICITADOS ---
        
        # 1. Filas en orden ASCENDENTE (de la fecha más vieja a la más nueva)
        matriz_final = matriz_final.sort_index(ascending=True)
        
        # 2. Columnas en orden DESCENDENTE (de la más reciente a la más antigua)
        # Como las columnas se generaron de 0 a 24 (Reciente -> Antigua), 
        # simplemente nos aseguramos de mantener ese orden original de la lista 'results'
        columnas_ordenadas = sorted(matriz_final.columns, reverse=True)
        matriz_final = matriz_final.reindex(columns=columnas_ordenadas)

        # 3. Mostrar la Matriz en Streamlit
        st.subheader("Desglose de Capital")
        st.write("Filas: Antiguo → Reciente | Columnas: Reciente → Antiguo")
        
        st.dataframe(
            matriz_final.style.format("{:.2%}", na_rep="-"),
            use_container_width=True
        )

        st.caption(f"Referencia: Fecha más reciente en datos es {fecha_max.strftime('%Y-%m')}")

    else:
        st.error("No se encontraron las columnas 'c1', 'c2', etc.")

except Exception as e:
    st.error(f"Error técnico: {e}")