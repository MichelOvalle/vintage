import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os

# 1. Configuración de página
st.set_page_config(page_title="Análisis Vintage Pro", layout="wide")

# Estilo para celdas negras y fondo blanco
st.markdown("<style>.main { background-color: #FFFFFF; } [data-testid='stTable'] td { color: black !important; }</style>", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def get_processed_data():
    file_path = "vintage_acum.parquet"
    if not os.path.exists(file_path):
        return None, None, None
    
    try:
        # Cargamos el archivo una sola vez
        df = pd.read_parquet(file_path, engine='pyarrow')
        
        # Limpieza y optimización inmediata
        if 'mes_apertura' in df.columns:
            df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
            
            # FILTRO CRÍTICO: Solo 24 meses para no saturar la RAM
            f_max = df['mes_apertura'].max()
            f_min = f_max - pd.DateOffset(months=24)
            df = df[df['mes_apertura'] >= f_min].copy()
            df['mes_apertura_str'] = df['mes_apertura'].dt.strftime('%Y-%m')
        
        # Reducimos peso de columnas de texto
        for col in ['uen', 'nombre_sucursal', 'producto_agrupado', 'PR_Origen_Limpio']:
            if col in df.columns:
                df[col] = df[col].astype('category')
                
        return df, f_max, f_min
    except Exception as e:
        st.error(f"Error al cargar: {e}")
        return None, None, None

def calcular_matriz_segura(df, pref_num, pref_den):
    if df.empty: return None, None
    
    # Capital Inicial: Suma de la columna del mes 1
    col_cap = f"{pref_den}1"
    cap_inicial = df.groupby('mes_apertura_str')[col_cap].sum().rename("Capital Inicial")
    
    # Ratios (Mes 1 al 24)
    results = []
    for i in range(1, 25):
        n, d = f"{pref_num}{i}", f"{pref_den}{i}"
        if n in df.columns and d in df.columns:
            # Operación vectorizada (consume menos RAM que .apply)
            agg = df.groupby('mes_apertura_str')[[n, d]].sum()
            results.append((agg[n] / agg[d]).rename(f"Mes {i}"))
    
    if not results: return None, None
    matriz = pd.concat(results, axis=1).sort_index()
    return matriz, cap_inicial

# --- CARGA DE DATOS ---
df_raw, f_max, f_min = get_processed_data()

if df_raw is not None:
    # --- SIDEBAR: LOS 3 FILTROS ---
    st.sidebar.header("Filtros Globales")
    
    sucursales = sorted(df_raw['nombre_sucursal'].cat.categories.tolist())
    f_suc = st.sidebar.multiselect("Sucursal", sucursales)
    
    productos = sorted(df_raw['producto_agrupado'].cat.categories.tolist())
    f_prod = st.sidebar.multiselect("Producto", productos)
    
    origenes = sorted(df_raw['PR_Origen_Limpio'].cat.categories.tolist())
    f_orig = st.sidebar.multiselect("Origen", origenes)

    # Aplicar filtros
    df_f = df_raw.copy()
    if f_suc: df_f = df_f[df_f['nombre_sucursal'].isin(f_suc)]
    if f_prod: df_f = df_f[df_f['producto_agrupado'].isin(f_prod)]
    if f_orig: df_f = df_f[df_f['PR_Origen_Limpio'].isin(f_orig)]

    # --- TABS ---
    tab1, tab2, tab3 = st.tabs(["📋 Vintage", "📈 Tendencias", "📍 Detalle Global"])

    with tab1:
        st.title(f"Vintage (Cosechas {f_min.strftime('%Y-%m')} a {f_max.strftime('%Y-%m')})")
        
        # PR
        m_pr, c_pr = calcular_matriz_segura(df_f[df_f['uen']=='PR'], 'saldo_capital_total_c', 'capital_c')
        if m_pr is not None:
            st.subheader("📊 UEN: PR")
            st.dataframe(pd.concat([c_pr, m_pr], axis=1).style.format({"Capital Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in m_pr.columns}, na_rep="")
                        .background_gradient(cmap='RdYlGn_r', axis=None, subset=m_pr.columns), use_container_width=True)
        
        st.divider()
        # SOLIDAR
        m_sol, c_sol = calcular_matriz_segura(df_f[df_f['uen']=='SOLIDAR'], 'saldo_capital_total_890_c', 'capital_c')
        if m_sol is not None:
            st.subheader("📊 UEN: SOLIDAR")
            st.dataframe(pd.concat([c_sol, m_sol], axis=1).style.format({"Capital Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in m_sol.columns}, na_rep="")
                        .background_gradient(cmap='RdYlGn_r', axis=None, subset=m_sol.columns), use_container_width=True)

    with tab2:
        st.title("Top 5 Productos Críticos")
        c1, c2 = st.columns(2)
        with c1:
            if not df_f[df_f['uen']=='PR'].empty:
                # Riesgo PR (C2)
                res = df_f[df_f['uen']=='PR'].groupby('producto_agrupado').agg({'saldo_capital_total_c2':'sum','capital_c2':'sum'})
                top = (res['saldo_capital_total_c2']/res['capital_c2']).sort_values(ascending=False).head(5).reset_index()
                top.columns = ['Producto', 'Ratio']
                st.plotly_chart(px.bar(top, x='Ratio', y='Producto', orientation='h', title="Top 5 Riesgo PR", color='Ratio', color_continuous_scale='Reds').update_layout(xaxis_tickformat='.1%', yaxis={'categoryorder':'total ascending'}))

        with c2:
            if not df_f[df_f['uen']=='SOLIDAR'].empty:
                # Riesgo SOLIDAR (C1)
                res2 = df_f[df_f['uen']=='SOLIDAR'].groupby('producto_agrupado').agg({'saldo_capital_total_890_c1':'sum','capital_c1':'sum'})
                top2 = (res2['saldo_capital_total_890_c1']/res2['capital_c1']).sort_values(ascending=False).head(5).reset_index()
                top2.columns = ['Producto', 'Ratio']
                st.plotly_chart(px.bar(top2, x='Ratio', y='Producto', orientation='h', title="Top 5 Riesgo SOLIDAR", color='Ratio', color_continuous_scale='Reds').update_layout(xaxis_tickformat='.1%', yaxis={'categoryorder':'total ascending'}))

    with tab3:
        st.title("📍 Desempeño por Sucursal")
        st.info("Vista comparativa de sucursales (Datos Globales últimos 24 meses)")
        ca, cb = st.columns(2)
        # Usamos df_raw para ignorar filtros laterales en esta pestaña
        with ca:
            st.write("**Top 10 Riesgo PR**")
            s_pr = df_raw[df_raw['uen']=='PR'].groupby('nombre_sucursal').apply(lambda x: x['saldo_capital_total_c2'].sum()/x['capital_c2'].sum() if x['capital_c2'].sum()>0 else 0).sort_values(ascending=False).head(10)
            st.table(s_pr.rename("Ratio C2"))
        with cb:
            st.write("**Top 10 Riesgo SOLIDAR**")
            s_sol = df_raw[df_raw['uen']=='SOLIDAR'].groupby('nombre_sucursal').apply(lambda x: x['saldo_capital_total_890_c1'].sum()/x['capital_c1'].sum() if x['capital_c1'].sum()>0 else 0).sort_values(ascending=False).head(10)
            st.table(s_sol.rename("Ratio C1"))

st.caption(f"Usuario: Michel Ovalle | Carga optimizada v6.0")