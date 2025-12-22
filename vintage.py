import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os

# 1. Configuración de página (Debe ser la primera instrucción)
st.set_page_config(page_title="Análisis Vintage Pro", layout="wide")

# Estilo para celdas y limpieza visual
st.markdown("<style>.main { background-color: #FFFFFF; } [data-testid='stTable'] td { color: black !important; }</style>", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_data_optimized():
    file_path = "vintage_acum.parquet"
    if not os.path.exists(file_path):
        st.error("Archivo Parquet no encontrado.")
        return pd.DataFrame()
    
    try:
        # Cargamos solo los metadatos para identificar columnas de capital y saldo
        meta = pd.read_parquet(file_path, engine='pyarrow')
        cols_base = ['mes_apertura', 'uen', 'nombre_sucursal', 'producto_agrupado', 'PR_Origen_Limpio']
        # Identificamos columnas de meses (1 al 24)
        cols_calc = [c for c in meta.columns if ('capital' in c.lower() or 'saldo' in c.lower())]
        cols_final = list(set(cols_base + cols_calc))
        
        # Carga real solo con las columnas necesarias para ahorrar RAM
        df = pd.read_parquet(file_path, columns=cols_final, engine='pyarrow')
        
        if 'mes_apertura' in df.columns:
            df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
            df['mes_apertura_str'] = df['mes_apertura'].dt.strftime('%Y-%m')
        return df
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame()

def calcular_matriz_vintage(df, pref_num, pref_den):
    if df.empty: return None, None
    
    # Capital Inicial: Suma del capital en el mes 1 de la cosecha
    col_cap_ini = f"{pref_den}1"
    if col_cap_ini not in df.columns: col_cap_ini = pref_den # Fallback
    
    cap_inicial = df.groupby('mes_apertura_str')[col_cap_ini].sum()
    
    results = []
    for i in range(1, 25):
        n, d = f"{pref_num}{i}", f"{pref_den}{i}"
        if n in df.columns and d in df.columns:
            # Agregación vectorizada
            agg = df.groupby('mes_apertura_str')[[n, d]].sum()
            ratio = (agg[n] / agg[d]).rename(f"Mes {i}")
            results.append(ratio)
    
    if not results: return None, None
    matriz = pd.concat(results, axis=1).sort_index()
    return matriz, cap_inicial

def renderizar_estilo(matriz, cap_inicial):
    final = pd.concat([cap_inicial.rename("Capital Inicial"), matriz], axis=1)
    formatos = {col: "{:.2%}" for col in matriz.columns}
    formatos["Capital Inicial"] = "${:,.0f}"
    
    return final.style.format(formatos, na_rep="")\
        .background_gradient(cmap='RdYlGn_r', axis=None, subset=matriz.columns)\
        .set_properties(**{'color': 'black', 'border': '1px solid #eeeeee'})

try:
    df_raw = load_data_optimized()
    
    if not df_raw.empty:
        # --- FILTRO 24 MESES ---
        fecha_max = df_raw['mes_apertura'].max()
        fecha_inicio = fecha_max - pd.DateOffset(months=24)
        df_base = df_raw[df_raw['mes_apertura'] >= fecha_inicio].copy()

        # --- SIDEBAR: LOS 3 FILTROS ---
        st.sidebar.header("Filtros de Análisis")
        def get_opts(col):
            return sorted([str(x) for x in df_base[col].unique() if pd.notna(x)])

        f_suc = st.sidebar.multiselect("Sucursal", get_opts('nombre_sucursal'))
        f_prod = st.sidebar.multiselect("Producto Agrupado", get_opts('producto_agrupado'))
        f_orig = st.sidebar.multiselect("Origen Limpio", get_opts('PR_Origen_Limpio'))

        df_f = df_base.copy()
        if f_suc: df_f = df_f[df_f['nombre_sucursal'].isin(f_suc)]
        if f_prod: df_f = df_f[df_f['producto_agrupado'].isin(f_prod)]
        if f_orig: df_f = df_f[df_f['PR_Origen_Limpio'].isin(f_orig)]

        # --- TABS ---
        tab1, tab2, tab3 = st.tabs(["📋 Vintage", "📈 Tendencias", "📍 Detalle Sucursales"])

        with tab1:
            st.title(f"Análisis Vintage (Desde {fecha_inicio.strftime('%b %Y')})")
            # Bloque PR
            st.subheader("📊 UEN: PR (Ratio 30-150)")
            df_pr = df_f[df_f['uen'] == 'PR']
            m_pr, c_pr = calcular_matriz_vintage(df_pr, 'saldo_capital_total_c', 'capital_c')
            if m_pr is not None:
                st.dataframe(renderizar_estilo(m_pr, c_pr), use_container_width=True)
            
            st.divider()
            # Bloque SOLIDAR
            st.subheader("📊 UEN: SOLIDAR (Ratio 8-90)")
            df_sol = df_f[df_f['uen'] == 'SOLIDAR']
            m_sol, c_sol = calcular_matriz_vintage(df_sol, 'saldo_capital_total_890_c', 'capital_c')
            if m_sol is not None:
                st.dataframe(renderizar_estilo(m_sol, c_sol), use_container_width=True)

        with tab2:
            st.title("🏆 Top 5 Productos por Riesgo")
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("### Top 5 PR (C2)")
                if not df_pr.empty:
                    # Calculamos ratio acumulado para el top
                    r_pr = df_pr.groupby('producto_agrupado').agg({'saldo_capital_total_c2':'sum','capital_c2':'sum'})
                    r_pr['Ratio'] = r_pr['saldo_capital_total_c2'] / r_pr['capital_c2']
                    res_pr = r_pr.sort_values('Ratio', ascending=False).head(5).reset_index()
                    st.plotly_chart(px.bar(res_pr, x='Ratio', y='producto_agrupado', orientation='h', color='Ratio', color_continuous_scale='Reds').update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat='.1%'), use_container_width=True)

            with col_b:
                st.markdown("### Top 5 SOLIDAR (C1)")
                if not df_sol.empty:
                    r_sol = df_sol.groupby('producto_agrupado').agg({'saldo_capital_total_890_c1':'sum','capital_c1':'sum'})
                    r_sol['Ratio'] = r_sol['saldo_capital_total_890_c1'] / r_sol['capital_c1']
                    res_sol = r_sol.sort_values('Ratio', ascending=False).head(5).reset_index()
                    st.plotly_chart(px.bar(res_sol, x='Ratio', y='producto_agrupado', orientation='h', color='Ratio', color_continuous_scale='Reds').update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat='.1%'), use_container_width=True)

        with tab3:
            st.title("📍 Análisis Sucursales y Productos")
            st.info("💡 Este detalle muestra el riesgo por sucursal considerando los filtros seleccionados.")
            if not df_f.empty:
                # Matriz Sucursal vs Producto para PR
                st.subheader("Matriz Sucursal PR (Ratio C2)")
                df_tab3_pr = df_f[df_f['uen']=='PR']
                if not df_tab3_pr.empty:
                    pivot_pr = df_tab3_pr.pivot_table(index='nombre_sucursal', columns='producto_agrupado', 
                                                      values=['saldo_capital_total_c2', 'capital_c2'], aggfunc='sum')
                    matriz_suc_pr = pivot_pr['saldo_capital_total_c2'] / pivot_pr['capital_c2']
                    st.dataframe(matriz_suc_pr.style.format("{:.2%}", na_rep="-").background_gradient(cmap='RdYlGn_r', axis=None), use_container_width=True)

    st.caption(f"Referencia: Datos procesados hasta {fecha_max.strftime('%Y-%m')}. Usuario: Michel Ovalle.")

except Exception as e:
    st.error(f"Error técnico detectado: {e}")