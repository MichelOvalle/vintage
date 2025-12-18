import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta

# 1. Configuración de la página y forzado de tema claro
st.set_page_config(page_title="Matriz Vintage Pro", layout="wide")

# CSS para asegurar que el fondo de la página sea blanco y el texto general negro
st.markdown("""
    <style>
    .main {
        background-color: #FFFFFF;
    }
    .stDataFrame {
        background-color: #FFFFFF;
    }
    /* Forzar color de texto negro en celdas y cabeceras */
    [data-testid="stTable"] td, [data-testid="stTable"] th {
        color: black !important;
    }
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

    st.title("📊 Matriz de Capital: Heatmap sobre Blanco")
    
    # Parámetros de fechas
    fecha_max = df_raw['mes_apertura'].max()
    fecha_inicio_filas = fecha_max - pd.DateOffset(months=24)
    df = df_raw[df_raw['mes_apertura'] >= fecha_inicio_filas].copy()
    df['mes_apertura_str'] = df['mes_apertura'].dt.strftime('%Y-%m')

    # Construcción de la Matriz
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
        
        # Orden: Filas Ascendente (Viejo->Nuevo), Columnas Descendente (Nuevo->Viejo)
        matriz_final = matriz_final.sort_index(ascending=True)
        cols_ordenadas = sorted(matriz_final.columns, reverse=True)
        matriz_final = matriz_final.reindex(columns=cols_ordenadas)

        # 2. Aplicar Estilo Correcto
        # Aplicamos el heatmap y luego nos aseguramos de que los nulos sean blancos
        styled_df = (
            matriz_final.style
            .format("{:.2%}", na_rep="") 
            .background_gradient(cmap='RdYlGn', axis=None) # Heatmap (ignora nulos por defecto)
            .highlight_null(color='white')                  # Fuerza blanco en los None
            .set_properties(**{
                'color': 'black',                           # Texto siempre negro
                'border': '1px solid #D3D3D3'               # Bordes definidos
            })
        )

        st.dataframe(styled_df, use_container_width=True)

    else:
        st.error("Columnas 'c1', 'c2', etc. no encontradas.")

except Exception as e:
    st.error(f"Error: {e}")