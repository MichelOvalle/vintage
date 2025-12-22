import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os

# 1. Configuración de página
st.set_page_config(page_title="Análisis Vintage Pro", layout="wide")

# Estilos CSS
st.markdown("<style>.main { background-color: #FFFFFF; } [data-testid='stTable'] td { color: black !important; }</style>", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_data():
    file_path = "vintage_acum.parquet"
    if not os.path.exists(file_path):
        st.error(f"Archivo no encontrado: {file_path}")
        return pd.DataFrame()
    try:
        # Cargamos solo lo necesario para ahorrar RAM
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
    # Capital Inicial de la cohorte (Mes 1)
    df_cap = df.groupby('mes_apertura_str')[pref_den + "1"].sum().rename("Capital Inicial")
    
    results = []
    for i in range(1, 25):
        n, d = f"{pref_num}{i}", f"{pref_den}{i}"
        if n in df.columns and d in df.columns:
            # Agregación rápida para no saturar memoria
            agg = df.groupby('mes_apertura_str').agg({n: 'sum', d: 'sum'})
            ratio = (agg[n] / agg[d]).rename(f"Mes {i}")
            results.append(ratio)
    
    if not results: return None, None
    matriz = pd.concat(results, axis=1).sort_index()
    return matriz, df_cap

def renderizar_vintage(matriz, df_cap):
    final = pd.concat([df_cap, matriz], axis=1)
    formatos = {c: "{:.2%}" for c in matriz.columns}
    formatos["Capital Inicial"] = "${:,.0f}"
    
    st.dataframe(
        final.style.format(formatos, na_rep="")
        .background_gradient(cmap='RdYlGn_r', axis=None, subset=matriz.columns)
        .set_properties(**{'color': 'black', 'border': '1px solid #eeeeee'}),
        use_container_width=True
    )

try:
    df_raw = load_data()
    if not df_raw.empty:
        # --- SIDEBAR: LOS 3 FILTROS ---
        st.sidebar.header("Filtros Globales")
        def clean_options(col):
            return sorted([str(x) for x in df_raw[col].unique() if pd.notna(x)])
        
        f_suc = st.sidebar.multiselect("Sucursal", clean_options('nombre_sucursal'))
        f_prod = st.sidebar.multiselect("Producto Agrupado", clean_options('producto_agrupado'))
        f_orig = st.sidebar.multiselect("Origen Limpio", clean_options('PR_Origen_Limpio'))

        # Aplicación de filtros
        df_f = df_raw.copy()
        if f_suc: df_f = df_f[df_f['nombre_sucursal'].isin(f_suc)]
        if f_prod: df_f = df_f[df_f['producto_agrupado'].isin(f_prod)]
        if f_orig: df_f = df_f[df_f['PR_Origen_Limpio'].isin(f_orig)]

        # Filtro de 24 meses (Cosecha reciente)
        f_max = df_raw['mes_apertura'].max()
        f_min = f_max - pd.DateOffset(months=24)
        df_24 = df_f[df_f['mes_apertura'] >= f_min].copy()

        # --- TABS ---
        tab1, tab2, tab3 = st.tabs(["📋 Vintage", "📈 Tendencias", "📍 Detalle Global"])

        with tab1:
            st.title(f"Análisis Vintage (Datos hasta {f_max.strftime('%Y-%m')})")
            # UEN PR
            df_pr = df_24[df_24['uen'] == 'PR']
            m_pr, c_pr = calcular_matriz_datos(df_pr, 'saldo_capital_total_c', 'capital_c')
            if m_pr is not None:
                st.subheader("📊 UEN: PR (30-150)")
                renderizar_vintage(m_pr, c_pr)
            
            st.divider()
            # UEN SOLIDAR
            df_sol = df_24[df_24['uen'] == 'SOLIDAR']
            m_sol, c_sol = calcular_matriz_datos(df_sol, 'saldo_capital_total_890_c', 'capital_c')
            if m_sol is not None:
                st.subheader("📊 UEN: SOLIDAR (8-90)")
                renderizar_vintage(m_sol, c_sol)

        with tab2:
            st.title("Curvas y Top Riesgo")
            col1, col2 = st.columns(2)
            
            with col1:
                if m_pr is not None:
                    fig_lines = go.Figure()
                    for cosecha in m_pr.tail(6).index:
                        fila = m_pr.loc[cosecha].dropna()
                        fig_lines.add_trace(go.Scatter(x=fila.index, y=fila.values, mode='lines+markers', name=cosecha))
                    fig_lines.update_layout(title="Maduración PR (Últ. 6 meses)", yaxis_tickformat='.1%', plot_bgcolor='white')
                    st.plotly_chart(fig_lines, use_container_width=True)
            
            with col2:
                if not df_pr.empty:
                    # Top 5 Riesgo PR (C2)
                    top_pr = df_pr.groupby('producto_agrupado').agg({'saldo_capital_total_c2':'sum','capital_c2':'sum'})
                    top_pr['Ratio'] = top_pr['saldo_capital_total_c2'] / top_pr['capital_c2']
                    res_pr = top_pr.sort_values('Ratio', ascending=False).head(5).reset_index()
                    st.plotly_chart(px.bar(res_pr, x='Ratio', y='producto_agrupado', orientation='h', title="Top 5 Riesgo PR", color='Ratio', color_continuous_scale='Reds').update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat='.1%'))

        with tab3:
            st.title("📍 Análisis Sucursales y Productos (Datos Globales)")
            st.info("💡 Esta sección ignora los filtros laterales para mostrar el desempeño total.")
            # Datos globales de los últimos 24 meses
            df_glob = df_raw[df_raw['mes_apertura'] >= f_min]
            
            c_a, c_b = st.columns(2)
            with c_a:
                st.markdown("### Top 10 Sucursales PR (C2)")
                s_pr = df_glob[df_glob['uen']=='PR'].groupby('nombre_sucursal').apply(lambda x: x['saldo_capital_total_c2'].sum()/x['capital_c2'].sum() if x['capital_c2'].sum()>0 else 0).sort_values(ascending=False).head(10)
                st.table(s_pr.rename("Ratio C2"))
            
            with c_b:
                st.markdown("### Top 10 Sucursales SOLIDAR (C1)")
                s_sol = df_glob[df_glob['uen']=='SOLIDAR'].groupby('nombre_sucursal').apply(lambda x: x['saldo_capital_total_890_c1'].sum()/x['capital_c1'].sum() if x['capital_c1'].sum()>0 else 0).sort_values(ascending=False).head(10)
                st.table(s_sol.rename("Ratio C1"))

    st.caption(f"Usuario: Michel Ovalle | Dashboard de Crédito v5.0")

except Exception as e:
    st.error(f"Error crítico: {e}")