import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta

# Configuración de la página
st.set_page_config(page_title="Matriz de Capital por Fecha de Cierre", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_parquet("vintage_acum.parquet")
    if 'mes_apertura' in df.columns:
        df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
    return df

try:
    df_raw = load_data()

    st.title("📊 Matriz de Capital: Fechas de Cierre Reales")
    st.markdown("Columnas dinámicas calculadas desde la fecha máxima hacia atrás.")

    # 1. Definir la fecha base (Máximo de mes_apertura)
    fecha_max = df_raw['mes_apertura'].max()
    
    # Filtro de filas: Últimas 24 cosechas
    fecha_inicio_filas = fecha_max - pd.DateOffset(months=24)
    df = df_raw[df_raw['mes_apertura'] >= fecha_inicio_filas].copy()
    df['mes_apertura_str'] = df['mes_apertura'].dt.strftime('%Y-%m')

    # 2. Construcción de la Matriz con Nombres de Columnas Dinámicos
    results = []
    nombres_columnas = {}

    for i in range(25):  # De 0 a 24 meses
        # Nombre de las columnas de origen en el parquet
        col_num = f'saldo_capital_total_c{i+1}'
        col_den = f'capital_c{i+1}'
        
        # Calcular la fecha de cierre para esta columna (dif_meses = i)
        # Fecha máxima menos i meses
        fecha_columna = fecha_max - relativedelta(months=i)
        nombre_col_real = fecha_columna.strftime('%Y-%m')

        if col_num in df.columns and col_den in df.columns:
            # Cálculo del ratio
            temp = df.groupby('mes_apertura_str').apply(
                lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() != 0 else None
            )
            temp.name = nombre_col_real
            results.append(temp)

    if results:
        # Unimos las series en un DataFrame
        matriz_final = pd.concat(results, axis=1)
        
        # Ordenamos las filas (cosechas) de la más reciente a la más antigua
        matriz_final = matriz_final.sort_index(ascending=False)

        # 3. Mostrar la Matriz en Streamlit
        st.subheader("Ratio de Capital por Mes de Calendario")
        
        # Estilo de la tabla
        st.dataframe(
            matriz_final.style.format("{:.2%}", na_rep="-")
            .background_gradient(cmap='RdYlGn', axis=None),
            use_container_width=True
        )

        st.caption(f"Nota: Las columnas representan el cierre de mes calculado desde el máximo ({fecha_max.strftime('%Y-%m')}).")

    else:
        st.error("No se encontraron las columnas 'c1', 'c2', etc. en el archivo.")

except Exception as e:
    st.error(f"Error técnico: {e}")