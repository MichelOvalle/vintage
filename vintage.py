import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os

# 1. Configuración de página
st.set_page_config(page_title="Análisis Vintage Pro", layout="wide")

# Estilo visual para tablas
st.markdown("<style>.main { background-color: #FFFFFF; } [data-testid='stTable'] td { color: black !important; }</style>", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_data():
    file_path = "vintage_acum.parquet"
    if not os.path.exists(file_path):
        st.error(f"Archivo '{file_path}' no encontrado en el repositorio.")
        return pd.DataFrame()
    try:
        # Carga optimizada
        df = pd.read_parquet(file_path, engine='pyarrow')
        if 'mes_apertura' in df.columns:
            df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
            df['mes_apertura_str'] = df['mes_apertura'].dt.strftime('%Y-%m')
        return df
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame()

def calcular_matriz_datos(df, pref_num, pref_den):
    if df.empty: return None, None
    
    # Capital Inicial: Se calcula sobre la cohorte base (Mes 1)
    df_cap = df.groupby('mes_apertura_str')[pref_den + "1"].sum()
    df_cap.name = "Capital Inicial"

    results = []
    # Ciclo para los 24 meses de maduración
    for i in range(1, 25):
        c_num, c_den = f'{pref_num}{i}', f'{pref_den}{i}'
        if c_num in df.columns and c_den in df.columns:
            # Cálculo vectorizado para ahorrar RAM
            res = df.groupby('mes_apertura_str').agg({c_num: 'sum', c_den: 'sum'})
            temp = res[c_num] / res[c_den]
            temp.name = f"Mes {i}"
            results.append(temp)
    
    if not results: return None, None
    matriz = pd.concat(results, axis=1).sort_index()
    return matriz, df_cap

def renderizar_estilo(matriz, df_cap):
    matriz_final = pd.concat([df_cap, matriz], axis=1)
    formatos = {col: "{:.2%}" for col in matriz.columns}
    formatos["Capital Inicial"] = "${:,.0f}"
    
    return matriz_final.style.format(formatos, na_rep="")\
        .background_gradient(cmap='RdYlGn_r', axis=None, subset=matriz.columns)\
        .set_properties(**{'color': 'black', 'border': '1px solid #eeeeee'})

try:
    df_raw = load_data()
    if not df_raw.empty:
        # --- SIDEBAR: LOS 3 FILTROS SOLICITADOS ---
        st.sidebar.header("Filtros Globales")
        
        def opciones(col):
            return sorted([str(x) for x in df_raw[col].unique() if pd.notna(x)])
        
        f_sucursal = st.sidebar.multiselect("Sucursal", opciones('nombre_sucursal'))
        f_producto = st.sidebar.multiselect("Producto Agrupado", opciones('producto_agrupado'))
        f_origen = st.sidebar.multiselect("Origen Limpio", opciones('PR_Origen_Limpio'))

        # Aplicación de filtros
        df_f = df_raw.copy()
        if f_sucursal: df_f = df_f[df_f['nombre_sucursal'].isin(f_sucursal)]
        if f_producto: df_f = df_f[df_f['producto_agrupado'].isin(f_producto)]
        if f_origen: df_f = df_f[df_f['PR_Origen_Limpio'].isin(f_origen)]

        # Ventana de 24 meses basada en la fecha máxima del archivo
        fecha_max = df_raw['mes_apertura'].max()
        fecha_inicio = fecha_max - pd.DateOffset(months=24)
        df_24 = df_f[df_f['mes_apertura'] >= fecha_inicio].copy()

        # --- TABS: LAS 3 PESTAÑAS SOLICITADAS ---
        tab1, tab2, tab3 = st.tabs(["📋 Vintage", "📈 Tendencias", "📍 Detalle Global"])

        with tab1:
            st.title("Análisis Vintage (24 meses)")
            # Bloque PR
            df_pr = df_24[df_24['uen'] == 'PR']
            m_pr, c_pr = calcular_matriz_datos(df_pr, 'saldo_capital_total_c', 'capital_c')
            if m_pr is not None:
                st.subheader("📊 UEN: PR (Ratio 30-150)")
                st.dataframe(renderizar_estilo(m_pr, c_pr), use_container_width=True)
            
            st.divider()
            # Bloque SOLIDAR
            df_sol = df_24[df_24['uen'] == 'SOLIDAR']
            m_sol, c_sol = calcular_matriz_datos(df_sol, 'saldo_capital_total_890_c', 'capital_c')
            if m_sol is not None:
                st.subheader("📊 UEN: SOLIDAR (Ratio 8-90)")
                st.dataframe(renderizar_estilo(m_sol, c_sol), use_container_width=True)

        with tab2:
            st.title("Top 5 Productos Críticos")
            col_a, col_b = st.columns(2)
            with col_a:
                if not df_pr.empty:
                    # Riesgo PR (C2)
                    r = df_pr.groupby('producto_agrupado').agg({'saldo_capital_total_c2': 'sum', 'capital_c2': 'sum'})
                    r['Ratio'] = r['saldo_capital_total_c2'] / r['capital_c2']
                    res = r.sort_values('Ratio', ascending=False).head(5).reset_index()
                    st.plotly_chart(px.bar(res, x='Ratio', y='producto_agrupado', orientation='h', title="Top 5 PR", 
                                           color='Ratio', color_continuous_scale='Reds').update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat='.1%'))
            with col_b:
                if not df_sol.empty:
                    # Riesgo SOLIDAR (C1)
                    r2 = df_sol.groupby('producto_agrupado').agg({'saldo_capital_total_890_c1': 'sum', 'capital_c1': 'sum'})
                    r2['Ratio'] = r2['saldo_capital_total_890_c1'] / r2['capital_c1']
                    res2 = r2.sort_values('Ratio', ascending=False).head(5).reset_index()
                    st.plotly_chart(px.bar(res2, x='Ratio', y='producto_agrupado', orientation='h', title="Top 5 SOLIDAR", 
                                           color='Ratio', color_continuous_scale='Reds').update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat='.1%'))

        with tab3:
            st.title("📍 Desempeño por Sucursal")
            st.info("Vista global ignorando filtros laterales para comparar sucursales.")
            df_g = df_raw[df_raw['mes_apertura'] >= fecha_inicio]
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Top 10 Sucursales Riesgo PR**")
                s_pr = df_g[df_g['uen']=='PR'].groupby('nombre_sucursal').apply(lambda x: x['saldo_capital_total_c2'].sum()/x['capital_c2'].sum() if x['capital_c2'].sum()>0 else 0).sort_values(ascending=False).head(10)
                st.table(s_pr.rename("Ratio C2"))
            with c2:
                st.write("**Top 10 Sucursales Riesgo SOLIDAR**")
                s_sol = df_g[df_g['uen']=='SOLIDAR'].groupby('nombre_sucursal').apply(lambda x: x['saldo_capital_total_890_c1'].sum()/x['capital_c1'].sum() if x['capital_c1'].sum()>0 else 0).sort_values(ascending=False).head(10)
                st.table(s_sol.rename("Ratio C1"))

    st.caption(f"Desarrollado para Michel Ovalle | Datos hasta: {fecha_max.strftime('%Y-%m')}")

except Exception as e:
    st.error(f"Error crítico: {e}")