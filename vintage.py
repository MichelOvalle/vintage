import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta
import numpy as np

# 1. Configuración de la página
st.set_page_config(page_title="Matriz Vintage Pro", layout="wide")

# CSS para forzar fondo blanco y texto negro
st.markdown("""
    <style>
    .main { background-color: #FFFFFF; }
    .stDataFrame { background-color: #FFFFFF; }
    [data-testid="stTable"] td, [data-testid="stTable"] th { color: black !important; }
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
    st.title("📊 Vintage 30 - 150")

    fecha_max = df_raw['mes_apertura'].max()
    fecha_inicio_filas = fecha_max - pd.DateOffset(months=24)
    df = df_raw[df_raw['mes_apertura'] >= fecha_inicio_filas].copy()
    df['mes_apertura_str'] = df['mes_apertura'].dt.strftime('%Y-%m')

    # Cálculo de Capital Total por Cosecha
    df_capital_total = df.groupby('mes_apertura_str')['capital_c1'].sum()
    df_capital_total.name = "Capital Total"

    # 2. Construcción de la Matriz de Ratios
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
        matriz_ratios = pd.concat(results, axis=1)
        matriz_ratios = matriz_ratios.sort_index(ascending=True)
        cols_ordenadas = sorted(matriz_ratios.columns, reverse=True)
        matriz_ratios = matriz_ratios.reindex(columns=cols_ordenadas)

        # Combinamos Capital Total con ratios
        matriz_final = pd.concat([df_capital_total, matriz_ratios], axis=1)

        # Estadísticas (solo sobre columnas de ratios)
        stats = pd.DataFrame({
            'Promedio': matriz_ratios.mean(axis=0),
            'Máximo': matriz_ratios.max(axis=0),
            'Mínimo': matriz_ratios.min(axis=0)
        }).T 
        
        matriz_con_stats = pd.concat([matriz_final, stats])

        # Limpieza de nulos
        matriz_con_stats = matriz_con_stats.replace({np.nan: None})

        # 3. Aplicar Estilo
        idx = pd.IndexSlice
        
        # Definimos los formatos por columna
        formatos = {col: "{:.2%}" for col in matriz_ratios.columns}
        formatos["Capital Total"] = "${:,.0f}"

        styled_df = (
            matriz_con_stats.style
            .format(formatos, na_rep="") 
            # Heatmap solo en la zona de ratios (excluyendo Capital Total y Stats)
            .background_gradient(cmap='RdYlGn', axis=None, subset=idx[matriz_ratios.index, matriz_ratios.columns]) 
            .highlight_null(color='white')
            .set_properties(**{
                'color': 'black',
                'border': '1px solid #D3D3D3'
            })
            .set_properties(subset=idx[['Promedio', 'Máximo', 'Mínimo'], :], **{'font-weight': 'bold'})
            # Estilo visual para la columna Capital Total
            .set_properties(subset=idx[:, 'Capital Total'], **{'font-weight': 'bold', 'background-color': '#f0f2f6'})
        )

        st.dataframe(styled_df, use_container_width=True)
        st.caption(f"Referencia: Fecha de corte máxima {fecha_max.strftime('%Y-%m')}.")

    else:
        st.error("No se encontraron las columnas necesarias.")

except Exception as e:
    st.error(f"Error técnico: {e}")