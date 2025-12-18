import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta
import numpy as np

# 1. Configuración de la página
st.set_page_config(page_title="Matriz Vintage Pro", layout="wide")

# CSS para forzar fondo blanco y texto negro en el contenedor de Streamlit
st.markdown("""
    <style>
    .main { background-color: #FFFFFF; }
    [data-testid="stDataFrame"] { background-color: #FFFFFF !important; }
    /* Forzar que el texto sea negro incluso en modo oscuro del sistema */
    div[data-testid="stTable"] td, div[data-testid="stTable"] th { color: black !important; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def load_data():
    df = pd.read_parquet("vintage_acum.parquet")
    if 'mes_apertura' in df.columns:
        df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
    return df

try:
    df_raw = load_data()
    st.title("📊 Matriz de Capital: Vista Final Limpia")

    fecha_max = df_raw['mes_apertura'].max()
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
                lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() != 0 else np.nan
            )
            temp.name = nombre_col_real
            results.append(temp)

    if results:
        matriz_final = pd.concat(results, axis=1)
        matriz_final = matriz_final.sort_index(ascending=True)
        cols_ordenadas = sorted(matriz_final.columns, reverse=True)
        matriz_final = matriz_final.reindex(columns=cols_ordenadas)

        # --- ESTADÍSTICAS ---
        stats = pd.DataFrame({
            'Promedio': matriz_final.mean(axis=0),
            'Máximo': matriz_final.max(axis=0),
            'Mínimo': matriz_final.min(axis=0)
        }).T 
        
        # Unimos todo
        matriz_con_stats = pd.concat([matriz_final, stats])

        # --- LIMPIEZA CONTRA EL "NONE" ---
        # Aseguramos que todo lo vacío sea NaN de numpy para que .format(na_rep="") lo reconozca
        matriz_con_stats = matriz_con_stats.fillna(np.nan)

        # 3. Aplicar Estilo
        idx = pd.IndexSlice
        styled_df = (
            matriz_con_stats.style
            # na_rep="" hace que la celda se vea vacía (sin "None")
            .format("{:.2%}", na_rep="") 
            # Forzamos fondo blanco base ANTES del gradiente
            .set_properties(**{
                'color': 'black',
                'background-color': 'white',
                'border': '1px solid #D3D3D3'
            })
            # El heatmap se aplica encima del blanco solo en las celdas con datos
            .background_gradient(cmap='RdYlGn', axis=None, subset=idx[matriz_final.index, :]) 
            # Reforzamos el blanco para los nulos (por si el gradiente intenta pintarlos)
            .highlight_null(color='white')
            # Negritas en estadísticas
            .set_properties(subset=idx[['Promedio', 'Máximo', 'Mínimo'], :], **{'font-weight': 'bold'})
        )

        st.dataframe(styled_df, use_container_width=True)
        st.caption(f"Referencia: Fecha de corte máxima {fecha_max.strftime('%Y-%m')}.")

    else:
        st.error("No se encontraron las columnas necesarias.")

except Exception as e:
    st.error(f"Error técnico: {e}")