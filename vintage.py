import streamlit as st
import pandas as pd
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import os

# 1. Configuración de página
st.set_page_config(page_title="Análisis Vintage Pro", layout="wide")

# Estilos CSS
st.markdown("<style>.main { background-color: #FFFFFF; } [data-testid='stTable'] td { color: black !important; }</style>", unsafe_allow_html=True)

FILE_PATH = "vintage_acum.parquet"
COL_FECHA = "CAST(mes_apertura || '-01' AS DATE)"

@st.cache_data
def get_filter_options(column_name):
    if not os.path.exists(FILE_PATH): return []
    query = f"SELECT DISTINCT {column_name} FROM '{FILE_PATH}' WHERE {column_name} IS NOT NULL ORDER BY {column_name}"
    return [row[0] for row in duckdb.query(query).fetchall()]

def get_vintage_matrix(pref_num, pref_den, uen, filters, months=24):
    where = f"WHERE uen = '{uen}' AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL {months} MONTH FROM '{FILE_PATH}')"
    if filters.get('suc'): where += f" AND nombre_sucursal IN ('{"', '".join(filters['suc'])}')"
    if filters.get('prod'): where += f" AND producto_agrupado IN ('{"', '".join(filters['prod'])}')"
    if filters.get('orig'): where += f" AND PR_Origen_Limpio IN ('{"', '".join(filters['orig'])}')"

    cols = f"strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum({pref_den}1) as 'Cap_Inicial'"
    for i in range(1, 25):
        cols += f", sum({pref_num}{i}) / NULLIF(sum({pref_den}{i}), 0) as 'Mes {i}'"
    
    return duckdb.query(f"SELECT {cols} FROM '{FILE_PATH}' {where} GROUP BY 1 ORDER BY 1").df().set_index('Cosecha')

# --- LÓGICA DE DASHBOARD ---
try:
    if os.path.exists(FILE_PATH):
        # --- SIDEBAR: LOS 3 FILTROS ---
        st.sidebar.header("Filtros Globales")
        f_suc = st.sidebar.multiselect("Sucursal", get_filter_options("nombre_sucursal"))
        f_prod = st.sidebar.multiselect("Producto Agrupado", get_filter_options("producto_agrupado"))
        f_orig = st.sidebar.multiselect("Origen Limpio", get_filter_options("PR_Origen_Limpio"))
        filtros = {'suc': f_suc, 'prod': f_prod, 'orig': f_orig}

        tab1, tab2, tab3 = st.tabs(["📋 Vintage", "📈 Curvas y Tendencias", "📍 Detalle de Desempeño"])

        with tab1:
            st.title("Reporte de Ratios por Cosecha")
            m_pr = get_vintage_matrix('saldo_capital_total_c', 'capital_c', 'PR', filtros)
            if not m_pr.empty:
                st.subheader("📊 UEN: PR (Vintage 30-150)")
                st.dataframe(m_pr.style.format({"Cap_Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in m_pr.columns if 'Mes' in c}, na_rep="").background_gradient(cmap='RdYlGn_r', axis=None, subset=[c for c in m_pr.columns if 'Mes' in c]), use_container_width=True)
            
            st.divider()
            m_sol = get_vintage_matrix('saldo_capital_total_890_c', 'capital_c', 'SOLIDAR', filtros)
            if not m_sol.empty:
                st.subheader("📊 UEN: SOLIDAR (Vintage 8-90)")
                st.dataframe(m_sol.style.format({"Cap_Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in m_sol.columns if 'Mes' in c}, na_rep="").background_gradient(cmap='RdYlGn_r', axis=None, subset=[c for c in m_sol.columns if 'Mes' in c]), use_container_width=True)

        with tab2:
            st.title("Análisis de Maduración y Comportamiento")
            # 1. Curvas de Maduración (Últimas 12 cosechas de PR)
            if not m_pr.empty:
                fig_curves = go.Figure()
                for cosecha in m_pr.tail(12).index:
                    fila = m_pr.loc[cosecha].drop('Cap_Inicial').dropna()
                    fig_curves.add_trace(go.Scatter(x=fila.index, y=fila.values, mode='lines+markers', name=cosecha))
                fig_curves.update_layout(title="Curvas de Maduración - PR (Últ. 12m)", yaxis_tickformat='.1%', plot_bgcolor='white')
                st.plotly_chart(fig_curves, use_container_width=True)

            st.divider()
            # 2. Tendencia C2 Global
            st.subheader("Tendencia de comportamiento (Ratio C2)")
            q_trend = f"SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY 1"
            df_trend = duckdb.query(q_trend).df()
            st.plotly_chart(px.line(df_trend, x='Cosecha', y='Ratio', title="Evolución C2 Global - PR", markers=True).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'))

        with tab3:
            st.title("📍 Análisis Sucursales y productos")
            st.info("💡 Datos Globales: Esta sección ignora los filtros de la barra lateral.")
            
            # 1. Resumen Narrativo (SQL)
            st.subheader("📝 Resumen de Hallazgos")
            q_hallazgos = f"""
                SELECT nombre_sucursal, producto_agrupado, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio 
                FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1, 2 ORDER BY 3 DESC
            """
            df_h = duckdb.query(q_hallazgos).df()
            if not df_h.empty:
                peor = df_h.iloc[0]
                mejor = df_h.iloc[-1]
                st.write(f"La sucursal **{peor['nombre_sucursal']}** presenta el riesgo más alto con el producto **{peor['producto_agrupado']}** ({peor['Ratio']:.2%}).")
                st.write(f"La sucursal **{mejor['nombre_sucursal']}** presenta el mejor desempeño con el producto **{mejor['producto_agrupado']}** ({mejor['Ratio']:.2%}).")

            st.divider()
            # 2. Matriz Cruzada Sucursal vs Producto
            st.subheader("🔲 Matriz Cruzada: Sucursal vs Producto (Ratio C2 - PR)")
            q_matrix = f"""
                SELECT nombre_sucursal, producto_agrupado, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio 
                FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1, 2
            """
            df_pivot = duckdb.query(q_matrix).df().pivot(index='nombre_sucursal', columns='producto_agrupado', values='Ratio')
            st.dataframe(df_pivot.style.format("{:.2%}", na_rep="-").background_gradient(cmap='RdYlGn_r', axis=None), use_container_width=True)

    else:
        st.error("No se encontró el archivo Parquet.")

except Exception as e:
    st.error(f"Error técnico: {e}")

st.caption(f"Referencia: Datos procesados para Michel Ovalle.")