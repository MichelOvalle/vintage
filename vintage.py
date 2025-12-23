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
    # Aseguramos que solo traiga textos reales y no nulos
    query = f"SELECT DISTINCT {column_name} FROM '{FILE_PATH}' WHERE {column_name} IS NOT NULL ORDER BY {column_name}"
    return [str(row[0]) for row in duckdb.query(query).fetchall()]

def build_in_clause(filter_list):
    """Función auxiliar para construir clausulas IN seguras para SQL"""
    if not filter_list:
        return None
    # Convertimos todo a string y escapamos comillas simples por seguridad
    cleaned_list = [str(item).replace("'", "''") for item in filter_list if item is not None]
    return "('" + "', '".join(cleaned_list) + "')"

def get_vintage_matrix(pref_num, pref_den, uen, filters):
    where = f"WHERE uen = '{uen}' AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
    
    # Aplicación de filtros usando la nueva lógica segura
    for key, col in [('suc', 'nombre_sucursal'), ('prod', 'producto_agrupado'), ('orig', 'PR_Origen_Limpio')]:
        clause = build_in_clause(filters.get(key))
        if clause:
            where += f" AND {col} IN {clause}"

    cols = f"strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum({pref_den}1) as 'Cap_Inicial'"
    for i in range(1, 25):
        cols += f", sum({pref_num}{i}) / NULLIF(sum({pref_den}{i}), 0) as 'Mes {i}'"
    
    query = f"SELECT {cols} FROM '{FILE_PATH}' {where} GROUP BY 1 ORDER BY 1"
    return duckdb.query(query).df().set_index('Cosecha')

# --- LÓGICA PRINCIPAL ---
try:
    if os.path.exists(FILE_PATH):
        # --- SIDEBAR: FILTROS ---
        st.sidebar.header("Filtros Globales")
        f_suc = st.sidebar.multiselect("Sucursal", get_filter_options("nombre_sucursal"))
        f_prod = st.sidebar.multiselect("Producto Agrupado", get_filter_options("producto_agrupado"))
        f_orig = st.sidebar.multiselect("Origen Limpio", get_filter_options("PR_Origen_Limpio"))
        filtros = {'suc': f_suc, 'prod': f_prod, 'orig': f_orig}

        tab1, tab2, tab3 = st.tabs(["📋 Vintage", "📈 Curvas y Tendencias", "📍 Detalle de Desempeño"])

        with tab1:
            st.title("Reporte de Ratios por Cosecha (24 meses)")
            # PR
            m_pr = get_vintage_matrix('saldo_capital_total_c', 'capital_c', 'PR', filtros)
            if not m_pr.empty:
                st.subheader("📊 UEN: PR (30-150)")
                st.dataframe(m_pr.style.format({"Cap_Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in m_pr.columns if 'Mes' in c}, na_rep="").background_gradient(cmap='RdYlGn_r', axis=None, subset=[c for c in m_pr.columns if 'Mes' in c]), use_container_width=True)
            
            st.divider()
            # SOLIDAR
            m_sol = get_vintage_matrix('saldo_capital_total_890_c', 'capital_c', 'SOLIDAR', filtros)
            if not m_sol.empty:
                st.subheader("📊 UEN: SOLIDAR (8-90)")
                st.dataframe(m_sol.style.format({"Cap_Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in m_sol.columns if 'Mes' in c}, na_rep="").background_gradient(cmap='RdYlGn_r', axis=None, subset=[c for c in m_sol.columns if 'Mes' in c]), use_container_width=True)

        with tab2:
            st.title("Análisis de Maduración y Comportamiento")
            if not m_pr.empty:
                fig_curves = go.Figure()
                for cosecha in m_pr.tail(8).index:
                    fila = m_pr.loc[cosecha].drop('Cap_Inicial').dropna()
                    fig_curves.add_trace(go.Scatter(x=fila.index, y=fila.values, mode='lines+markers', name=cosecha))
                fig_curves.update_layout(title="Maduración - PR (Últimas 8 Cosechas)", yaxis_tickformat='.1%', plot_bgcolor='white', xaxis_title="Meses")
                st.plotly_chart(fig_curves, use_container_width=True)

            st.divider()
            st.subheader("Tendencias Globales (Últimos 24 meses)")
            col_g1, col_g2 = st.columns(2)
            
            # Subconsulta común para la ventana de tiempo
            time_filter = f"WHERE {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
            
            with col_g1:
                q_ev_pr = f"SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio FROM '{FILE_PATH}' {time_filter} AND uen='PR' GROUP BY 1 ORDER BY 1"
                df_ev_pr = duckdb.query(q_ev_pr).df()
                st.plotly_chart(px.line(df_ev_pr, x='Cosecha', y='Ratio', title="Ratio C2 Global - PR", markers=True).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'))
                
            with col_g2:
                q_ev_sol = f"SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as Ratio FROM '{FILE_PATH}' {time_filter} AND uen='SOLIDAR' GROUP BY 1 ORDER BY 1"
                df_ev_sol = duckdb.query(q_ev_sol).df()
                st.plotly_chart(px.line(df_ev_sol, x='Cosecha', y='Ratio', title="Ratio C1 Global - SOLIDAR", markers=True, color_discrete_sequence=['red']).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'))

        with tab3:
            st.title("📍 Detalle de Desempeño")
            # Matriz Sucursal vs Producto (C2 - PR)
            st.subheader("🔲 Matriz Sucursal vs Producto (Ratio C2 - PR)")
            q_pivot = f"SELECT nombre_sucursal, producto_agrupado, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1, 2"
            df_pivot = duckdb.query(q_pivot).df().pivot(index='nombre_sucursal', columns='producto_agrupado', values='Ratio')
            st.dataframe(df_pivot.style.format("{:.2%}", na_rep="-").background_gradient(cmap='RdYlGn_r', axis=None), use_container_width=True)

            c_s1, c_s2 = st.columns(2)
            with c_s1:
                st.markdown("#### Top 10 Sucursales Riesgo PR")
                q_s_pr = f"SELECT nombre_sucursal, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as 'Ratio C2' FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
                st.table(duckdb.query(q_s_pr).df().set_index('nombre_sucursal').style.format("{:.2%}"))
            with c_s2:
                st.markdown("#### Top 10 Sucursales Riesgo SOLIDAR")
                q_s_sol = f"SELECT nombre_sucursal, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as 'Ratio C1' FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
                st.table(duckdb.query(q_s_sol).df().set_index('nombre_sucursal').style.format("{:.2%}"))

    else:
        st.error(f"No se encuentra el archivo '{FILE_PATH}'.")

except Exception as e:
    st.error(f"Error técnico detectado: {e}")

st.caption("Dashboard Vintage Pro | Michel Ovalle | Engine: DuckDB")