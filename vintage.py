import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta

# Configuración de la página
st.set_page_config(page_title="Matriz Vintage - Texto Blanco", layout="wide")

@st.cache_data
def load_data():
    # Carga del archivo parquet
    df = pd.read_parquet("vintage_acum.parquet")
    if 'mes_apertura' in df.columns:
        df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
    return df

try:
    df_raw = load_data()

    st.title("📊 Matriz de Capital (Texto Blanco)")
    
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
        
        # Orden solicitado: 
        # Filas Ascendente (Antiguo -> Nuevo)
        matriz_final = matriz_final.sort_index(ascending=True)
        # Columnas Descendente (Reciente -> Antiguo)
        cols_ordenadas = sorted(matriz_final.columns, reverse=True)
        matriz_final = matriz_final.reindex(columns=cols_ordenadas)

        # 3. Aplicar Estilo: Heatmap + Texto Blanco
        st.subheader("Ratio de Capital")
        
        # Estilizamos la tabla
        styled_df = (
            matriz_final.style
            .format("{:.2%}", na_rep="") # Formato porcentaje y vacíos para None
            .background_gradient(cmap='RdYlGn', axis=None) # Mapa de calor (rojo-amarillo-verde)
            .set_properties(**{
                'color': 'white', # Cambiamos el color de la fuente a BLANCO
                'font-weight': 'bold' # Opcional: negrita para que resalte más
            })
        )

        st.dataframe(styled_df, use_container_width=True)

        st.caption(f"Filtro aplicado: Cosechas desde {fecha_inicio_filas.strftime('%Y-%m')}")

    else:
        st.error("No se encontraron las columnas c1, c2, etc.")

except Exception as e:
    st.error(f"Error: {e}")