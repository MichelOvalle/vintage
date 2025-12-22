import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os

# 1. Configuración de página - DEBE ser la primera instrucción de Streamlit
st.set_page_config(page_title="Análisis Vintage Pro", layout="wide")

# Estilos CSS
st.markdown("<style>.main { background-color: #FFFFFF; } [data-testid='stTable'] td { color: black !important; }</style>", unsafe_allow_html=True)

@st.cache_data(ttl=3600) # Caché por 1 hora para ahorrar memoria
def load_data():
    file_path = "vintage_acum.parquet"
    if not os.path.exists(file_path):
        st.error(f"Archivo no encontrado: {file_path}")
        return pd.DataFrame()
    try:
        # Cargamos solo columnas necesarias si el archivo es muy grande
        df = pd.read_parquet(file_path, engine='pyarrow')
        if 'mes_apertura' in df.columns:
            df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
            # Crear columna de texto una sola vez para ahorrar cómputo
            df['mes_apertura_str'] = df['mes_apertura'].dt.strftime('%Y-%m')
        return df
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame()

def calcular_matriz_optimizada(df, prefijo_num, prefijo_den):
    if df.empty: return None, None
    
    # 1. Agrupación vectorizada (Mucho más rápida que .apply)
    # Sumamos numeradores y denominadores de una vez
    cols_num = [f"{prefijo_num}{i+1}" for i in range(25) if f"{prefijo_num}{i+1}" in df.columns]
    cols_den = [f"{prefijo_den}{i+1}" for i in range(25) if f"{prefijo_den}{i+1}" in df.columns]
    
    # Agrupar por mes
    agrupado = df.groupby('mes_apertura_str').agg({**{c: 'sum' for c in cols_num}, **{c: 'sum' for c in cols_den}})
    
    # 2. Calcular ratios de forma masiva
    matriz_grafico = pd.DataFrame(index=agrupado.index)
    for i in range(len(cols_num)):
        c_num, c_den = cols_num[i], cols_den[i]
        matriz_grafico[f"Mes {i+1}"] = agrupado[c_num] / agrupado[c_den]
    
    # Capital Inicial para la primera columna de la tabla
    cap_inicial = df.groupby('mes_apertura_str')['capital_c1'].sum()
    
    return matriz_grafico.sort_index(), cap_inicial

def renderizar_estilo(matriz, cap_inicial):
    # Unir capital y ratios
    matriz_final = pd.concat([cap_inicial.rename("Capital Inicial"), matriz], axis=1)
    
    # Formatear
    formatos = {col: "{:.2%}" for col in matriz.columns}
    formatos["Capital Inicial"] = "${:,.0f}"
    
    return matriz_final.style.format(formatos, na_rep="")\
        .background_gradient(cmap='RdYlGn_r', axis=None, subset=matriz.columns)\
        .set_properties(**{'color': 'black', 'border': '1px solid #D3D3D3'})

try:
    df_raw = load_data()
    
    if not df_raw.empty:
        # --- SIDEBAR ---
        st.sidebar.header("Filtros")
        # Protegemos contra Nulos y tipos mixtos
        sucursales = sorted([str(x) for x in df_raw['nombre_sucursal'].unique() if pd.notna(x)])
        f_suc = st.sidebar.multiselect("Sucursal", sucursales)
        
        df_filtrado = df_raw.copy()
        if f_suc: df_filtrado = df_filtrado[df_filtrado['nombre_sucursal'].isin(f_suc)]

        # --- TABS ---
        tab1, tab2 = st.tabs(["📋 Vintage", "📈 Tendencias"])

        with tab1:
            st.title("Análisis Vintage")
            # Proceso para UEN PR
            df_pr = df_filtrado[df_filtrado['uen'] == 'PR']
            matriz_pr, cap_pr = calcular_matriz_optimizada(df_pr, 'saldo_capital_total_c', 'capital_c')
            if matriz_pr is not None:
                st.subheader("📊 Vintage (UEN: PR)")
                st.dataframe(renderizar_estilo(matriz_pr, cap_pr), use_container_width=True)

        with tab2:
            st.title("Top 5 Riesgo por Producto")
            # Cálculo de Top 5 más eficiente
            if not df_filtrado.empty:
                # Usamos C2 como referencia de riesgo
                riesgo = df_filtrado.groupby('producto_agrupado').agg({'saldo_capital_total_c2': 'sum', 'capital_c2': 'sum'})
                riesgo['Ratio'] = riesgo['saldo_capital_total_c2'] / riesgo['capital_c2']
                top5 = riesgo.sort_values('Ratio', ascending=False).head(5).reset_index()
                
                fig = px.bar(top5, x='Ratio', y='producto_agrupado', orientation='h', 
                             color='Ratio', color_continuous_scale='Reds')
                fig.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat='.1%')
                st.plotly_chart(fig, use_container_width=True)

    st.caption(f"Usuario: Michel Ovalle | Datos: {len(df_raw)} registros.")

except Exception as e:
    st.error(f"Error crítico en la aplicación: {e}")