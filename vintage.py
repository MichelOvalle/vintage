import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os

# 1. Configuración de página
st.set_page_config(page_title="Análisis Vintage Pro", layout="wide")

# Estilo para asegurar legibilidad
st.markdown("""
    <style>
    .main { background-color: #FFFFFF; }
    [data-testid="stTable"] td { color: black !important; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_data():
    file_path = "vintage_acum.parquet"
    if not os.path.exists(file_path):
        st.error(f"Archivo '{file_path}' no encontrado.")
        return pd.DataFrame()
    try:
        df = pd.read_parquet(file_path, engine='pyarrow')
        if 'mes_apertura' in df.columns:
            df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
            df['mes_apertura_str'] = df['mes_apertura'].dt.strftime('%Y-%m')
        return df
    except Exception as e:
        st.error(f"Error al cargar Parquet: {e}")
        return pd.DataFrame()

def calcular_matriz_datos(df, fecha_max, pref_num, pref_den):
    if df.empty: return None, None, None
    
    # Capital Inicial de la cohorte (usamos el denominador capital_c como base)
    df_cap = df.groupby('mes_apertura_str')[pref_den].sum()
    df_cap.name = "Capital Inicial"

    results = []
    # Generar 24 meses de maduración
    for i in range(1, 25):
        c_num, c_den = f'{pref_num}{i}', f'{pref_den}{i}'
        if c_num in df.columns and c_den in df.columns:
            temp = df.groupby('mes_apertura_str').apply(
                lambda x: x[c_num].sum() / x[c_den].sum() if x[c_den].sum() > 0 else np.nan
            )
            temp.name = f"Mes {i}"
            results.append(temp)
    
    if not results: return None, None, None
    matriz = pd.concat(results, axis=1).sort_index()
    return matriz, df_cap, matriz

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
        # --- SIDEBAR: LOS 3 FILTROS ---
        st.sidebar.header("Filtros Globales")
        def filtrar_lista(col):
            return sorted([str(x) for x in df_raw[col].unique() if pd.notna(x)])
        
        f_sucursal = st.sidebar.multiselect("Sucursal", filtrar_lista('nombre_sucursal'))
        f_producto = st.sidebar.multiselect("Producto Agrupado", filtrar_lista('producto_agrupado'))
        f_origen = st.sidebar.multiselect("Origen Limpio", filtrar_lista('PR_Origen_Limpio'))

        # Aplicar filtros
        df_f = df_raw.copy()
        if f_sucursal: df_f = df_f[df_f['nombre_sucursal'].isin(f_sucursal)]
        if f_producto: df_f = df_f[df_f['producto_agrupado'].isin(f_producto)]
        if f_origen: df_f = df_f[df_f['PR_Origen_Limpio'].isin(f_origen)]

        # Definir ventana de 24 meses
        fecha_max = df_raw['mes_apertura'].max()
        fecha_inicio_24 = fecha_max - pd.DateOffset(months=24)
        
        # DF filtrado por fecha para Tabs 1 y 2
        df_24 = df_f[df_f['mes_apertura'] >= fecha_inicio_24].copy()

        # --- TABS: LAS 3 PESTAÑAS ---
        tab1, tab2, tab3 = st.tabs(["📋 Vintage", "📈 Curvas y Tendencias", "📍 Detalle de Desempeño"])

        with tab1:
            st.title("Análisis Vintage (Últimos 24 meses)")
            # PR
            df_pr = df_24[df_24['uen'] == 'PR']
            m_pr, c_pr, _ = calcular_matriz_datos(df_pr, fecha_max, 'saldo_capital_total_c', 'capital_c')
            if m_pr is not None:
                st.subheader("📊 UEN: PR (Ratio 30-150)")
                st.dataframe(renderizar_estilo(m_pr, c_pr), use_container_width=True)
            
            st.divider()
            # SOLIDAR
            df_sol = df_24[df_24['uen'] == 'SOLIDAR']
            m_sol, c_sol, _ = calcular_matriz_datos(df_sol, fecha_max, 'saldo_capital_total_890_c', 'capital_c')
            if m_sol is not None:
                st.subheader("📊 UEN: SOLIDAR (Ratio 8-90)")
                st.dataframe(renderizar_estilo(m_sol, c_sol), use_container_width=True)

        with tab2:
            st.title("Curvas de Maduración y Comportamiento")
            if m_pr is not None:
                fig_c = go.Figure()
                for cosecha in m_pr.tail(6).index: # Últimas 6 para no saturar
                    fila = m_pr.loc[cosecha].dropna()
                    fig_c.add_trace(go.Scatter(x=fila.index, y=fila.values, mode='lines+markers', name=cosecha))
                fig_c.update_layout(title="Maduración PR (Últimas 6 Cosechas)", yaxis_tickformat='.1%', plot_bgcolor='white')
                st.plotly_chart(fig_c, use_container_width=True)

            st.divider()
            st.subheader("🏆 Top 5 Productos Críticos")
            col_a, col_b = st.columns(2)
            with col_a:
                if not df_pr.empty:
                    top_pr = df_pr.groupby('producto_agrupado').agg({'saldo_capital_total_c2': 'sum', 'capital_c2': 'sum'})
                    top_pr['Ratio'] = top_pr['saldo_capital_total_c2'] / top_pr['capital_c2']
                    res = top_pr.sort_values('Ratio', ascending=False).head(5).reset_index()
                    st.plotly_chart(px.bar(res, x='Ratio', y='producto_agrupado', orientation='h', title="Top 5 PR", color='Ratio', color_continuous_scale='Reds').update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat='.1%'))
            with col_b:
                if not df_sol.empty:
                    top_sol = df_sol.groupby('producto_agrupado').agg({'saldo_capital_total_890_c1': 'sum', 'capital_c1': 'sum'})
                    top_sol['Ratio'] = top_sol['saldo_capital_total_890_c1'] / top_sol['capital_c1']
                    res_s = top_sol.sort_values('Ratio', ascending=False).head(5).reset_index()
                    st.plotly_chart(px.bar(res_s, x='Ratio', y='producto_agrupado', orientation='h', title="Top 5 SOLIDAR", color='Ratio', color_continuous_scale='Reds').update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat='.1%'))

        with tab3:
            st.title("📍 Detalle Global de Desempeño")
            st.info("Esta sección ignora los filtros laterales para mostrar el panorama total de la empresa.")
            # Datos globales últimos 24 meses
            df_g = df_raw[df_raw['mes_apertura'] >= fecha_inicio_24]
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Resumen PR (Global)**")
                res_g_pr = df_g[df_g['uen']=='PR'].groupby('nombre_sucursal').apply(lambda x: x['saldo_capital_total_c2'].sum()/x['capital_c2'].sum() if x['capital_c2'].sum()>0 else 0).sort_values(ascending=False).head(10)
                st.table(res_g_pr.rename("Ratio C2"))
            with col2:
                st.write("**Resumen SOLIDAR (Global)**")
                res_g_sol = df_g[df_g['uen']=='SOLIDAR'].groupby('nombre_sucursal').apply(lambda x: x['saldo_capital_total_890_c1'].sum()/x['capital_c1'].sum() if x['capital_c1'].sum()>0 else 0).sort_values(ascending=False).head(10)
                st.table(res_g_sol.rename("Ratio C1"))

    st.caption(f"Actualizado por Michel Ovalle | Fecha máxima datos: {fecha_max.strftime('%Y-%m')}")

except Exception as e:
    st.error(f"Error detectado: {e}")