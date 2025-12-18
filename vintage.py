import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta
import numpy as np

# 1. Configuración de la página
st.set_page_config(page_title="Matriz Vintage Pro", layout="wide")

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
        
        matriz_con_stats = pd.concat([matriz_final, stats])

        # --- ESTILO HTML RADICAL ---
        # Definimos el estilo de la tabla con CSS incrustado
        table_style = [
            {'selector': '', 'props': [('background-color', 'white'), ('color', 'black'), ('border-collapse', 'collapse'), ('width', '100%')]},
            {'selector': 'td, th', 'props': [('border', '1px solid #e0e0e0'), ('padding', '8px'), ('text-align', 'center'), ('font-family', 'sans-serif')]},
            {'selector': 'th', 'props': [('background-color', '#f8f9fa'), ('font-weight', 'bold')]}
        ]

        idx = pd.IndexSlice
        styled_html = (
            matriz_con_stats.style
            .format("{:.2%}", na_rep="") # Elimina el texto "None"
            .set_table_styles(table_style)
            .set_properties(**{'background-color': 'white', 'color': 'black'}) # Fuerza fondo blanco
            # Heatmap solo en datos
            .background_gradient(cmap='RdYlGn', axis=None, subset=idx[matriz_final.index, :])
            # Negritas en estadísticas
            .set_properties(subset=idx[['Promedio', 'Máximo', 'Mínimo'], :], **{'font-weight': 'bold'})
            .to_html()
        )

        # Inyectamos el HTML directamente
        st.write(styled_html, unsafe_allow_html=True)
        
        st.caption(f"<br>Referencia: Fecha de corte máxima {fecha_max.strftime('%Y-%m')}.", unsafe_allow_html=True)

    else:
        st.error("No se encontraron las columnas necesarias.")

except Exception as e:
    st.error(f"Error técnico: {e}")