import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta

# 1. Configuración de la página y forzado de tema claro
st.set_page_config(page_title="Matriz Vintage Pro", layout="wide")

# CSS para asegurar fondo blanco y texto negro en la aplicación
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
    # Carga del archivo parquet
    df = pd.read_parquet("vintage_acum.parquet")
    if 'mes_apertura' in df.columns:
        df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
    return df

try:
    df_raw = load_data()

    st.title("📊 Matriz de Capital: Vista con Estadísticas")
    st.markdown("Ratio de Capital (`saldo_capital_total_cX / capital_cX`) con resumen de Promedio, Máximo y Mínimo.")

    # Definir la fecha base
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
        
        # Calcular nombre de la columna (Fecha de cierre)
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
        
        # Orden solicitado: Filas Ascendente (Antiguo -> Nuevo)
        matriz_final = matriz_final.sort_index(ascending=True)
        # Columnas Descendente (Reciente -> Antiguo)
        cols_ordenadas = sorted(matriz_final.columns, reverse=True)
        matriz_final = matriz_final.reindex(columns=cols_ordenadas)

        # --- CÁLCULO DE ESTADÍSTICAS ---
        # Calculamos promedio, máximo y mínimo ignorando los nulos
        stats = pd.DataFrame({
            'Promedio': matriz_final.mean(axis=0),
            'Máximo': matriz_final.max(axis=0),
            'Mínimo': matriz_final.min(axis=0)
        }).T 
        
        # Concatenamos las estadísticas al final de la matriz
        matriz_con_stats = pd.concat([matriz_final, stats])

        # 3. Aplicar Estilo Final
        # Usamos IndexSlice para aplicar estilos a filas específicas sin errores
        idx = pd.IndexSlice
        
        styled_df = (
            matriz_con_stats.style
            .format("{:.2%}", na_rep="") 
            # El heatmap solo se aplica a los datos de las cosechas (excluye filas de estadísticas)
            .background_gradient(cmap='RdYlGn', axis=None, subset=idx[matriz_final.index, :]) 
            .highlight_null(color='white')
            .set_properties(**{
                'color': 'black',
                'border': '1px solid #D3D3D3'
            })
            # Aplicar negrita solo a las filas de resumen
            .set_properties(subset=idx[['Promedio', 'Máximo', 'Mínimo'], :], **{'font-weight': 'bold'})
        )

        st.dataframe(styled_df, use_container_width=True)
        
        st.caption(f"Referencia: Fecha de corte máxima {fecha_max.strftime('%Y-%m')}. Datos de cosechas limitados a los últimos 24 meses.")

    else:
        st.error("No se encontraron las columnas c1, c2, etc. en el archivo.")

except Exception as e:
    st.error(f"Error técnico: {e}")