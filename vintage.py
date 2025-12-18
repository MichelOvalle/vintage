import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta
import numpy as np

# 1. Configuración de la página
st.set_page_config(page_title="Reporte Vintage Pro", layout="wide")

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

def generar_matriz_vintage(df, fecha_max, prefijo_num, prefijo_den, titulo):
    """Función auxiliar para generar y estilar las matrices vintage"""
    st.subheader(f"📊 {titulo}")
    
    if df.empty:
        st.warning(f"No hay datos disponibles para los filtros seleccionados en {titulo}.")
        return

    df_capital_total = df.groupby('mes_apertura_str')['capital_c1'].sum()
    df_capital_total.name = "Capital Total"

    results = []
    for i in range(25):
        col_num = f'{prefijo_num}{i+1}'
        col_den = f'{prefijo_den}{i+1}'
        
        fecha_columna = fecha_max - relativedelta(months=i)
        nombre_col_real = fecha_columna.strftime('%Y-%m')

        if col_num in df.columns and col_den in df.columns:
            temp = df.groupby('mes_apertura_str').apply(
                lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() > 0 else np.nan
            )
            temp.name = nombre_col_real
            results.append(temp)

    if results:
        matriz_ratios = pd.concat(results, axis=1)
        matriz_ratios = matriz_ratios.sort_index(ascending=True)
        cols_ordenadas = sorted(matriz_ratios.columns, reverse=True)
        matriz_ratios = matriz_ratios.reindex(columns=cols_ordenadas)

        matriz_final = pd.concat([df_capital_total, matriz_ratios], axis=1)

        # Estadísticas
        stats = pd.DataFrame({
            'Promedio': matriz_ratios.mean(axis=0),
            'Máximo': matriz_ratios.max(axis=0),
            'Mínimo': matriz_ratios.min(axis=0)
        }).T 
        
        matriz_con_stats = pd.concat([matriz_final, stats])
        matriz_con_stats = matriz_con_stats.replace({np.nan: None})

        # Aplicar Estilo
        idx = pd.IndexSlice
        formatos = {col: "{:.2%}" for col in matriz_ratios.columns}
        formatos["Capital Total"] = "${:,.0f}"

        styled_df = (
            matriz_con_stats.style
            .format(formatos, na_rep="") 
            .background_gradient(cmap='RdYlGn_r', axis=None, subset=idx[matriz_ratios.index, matriz_ratios.columns]) 
            .highlight_null(color='white')
            .set_properties(**{'color': 'black', 'border': '1px solid #D3D3D3'})
            .set_properties(subset=idx[['Promedio', 'Máximo', 'Mínimo'], :], **{'font-weight': 'bold'})
            .set_properties(subset=idx[:, 'Capital Total'], **{'font-weight': 'bold', 'background-color': '#f0f2f6'})
        )
        st.dataframe(styled_df, use_container_width=True)
    else:
        st.error(f"No se encontraron columnas con el prefijo {prefijo_num}")

try:
    df_raw = load_data()
    
    st.sidebar.header("Filtros de Segmentación")
    st.sidebar.info("Nota: Las tablas tienen una UEN fija asignada.")

    def crear_filtro(label, col_name):
        options = sorted(df_raw[col_name].dropna().unique())
        return st.sidebar.multiselect(label, options)

    # Quitamos UEN de los filtros laterales porque ahora es fija por tabla
    f_sucursal = crear_filtro("Sucursal", "nombre_sucursal")
    f_producto = crear_filtro("Producto Agrupado", "producto_agrupado")
    f_origen = crear_filtro("Origen Limpio", "PR_Origen_Limpio")

    # Filtro base (común para ambas tablas)
    df_base = df_raw.copy()
    if f_sucursal: df_base = df_base[df_base['nombre_sucursal'].isin(f_sucursal)]
    if f_producto: df_base = df_base[df_base['producto_agrupado'].isin(f_producto)]
    if f_origen: df_base = df_base[df_base['PR_Origen_Limpio'].isin(f_origen)]

    fecha_max = df_raw['mes_apertura'].max()
    fecha_inicio_filas = fecha_max - pd.DateOffset(months=24)
    df_base = df_base[df_base['mes_apertura'] >= fecha_inicio_filas].copy()
    df_base['mes_apertura_str'] = df_base['mes_apertura'].dt.strftime('%Y-%m')

    st.title("📊 Reporte de Ratios Vintage")

    # --- TABLA 1: Vintage 30 - 150 (Filtro UEN = PR) ---
    df_pr = df_base[df_base['uen'] == 'PR']
    generar_matriz_vintage(df_pr, fecha_max, 'saldo_capital_total_c', 'capital_c', "Vintage 30 - 150 (UEN: PR)")
    
    st.write("---") 
    
    # --- TABLA 2: Vintage 8 - 90 (Filtro UEN = SOLIDAR) ---
    df_solidar = df_base[df_base['uen'] == 'SOLIDAR']
    generar_matriz_vintage(df_solidar, fecha_max, 'saldo_capital_total_890_c', 'capital_c', "Vintage 8 - 90 (UEN: SOLIDAR)")

    st.caption(f"Referencia: Fecha de corte máxima {fecha_max.strftime('%Y-%m')}.")

except Exception as e:
    st.error(f"Error técnico: {e}")