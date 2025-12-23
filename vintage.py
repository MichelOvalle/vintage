import streamlit as st
import pandas as pd
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import os

# 1. Configuración de página
st.set_page_config(page_title="Análisis Vintage Pro", layout="wide")

# Estilos CSS para asegurar legibilidad
st.markdown("""
    <style>
    .main { background-color: #FFFFFF; }
    [data-testid="stTable"] td, [data-testid="stTable"] th { color: black !important; }
    [data-testid="stDataFrame"] td { color: black !important; }
    </style>
    """, unsafe_allow_html=True)

FILE_PATH = "vintage_acum.parquet"
# Normalización de fecha para DuckDB
COL_FECHA = "CAST(mes_apertura || '-01' AS DATE)"

@st.cache_data
def get_filter_options(column_name):
    if not os.path.exists(FILE_PATH): return []
    query = f"SELECT DISTINCT {column_name} FROM '{FILE_PATH}' WHERE {column_name} IS NOT NULL ORDER BY {column_name}"
    return [str(row[0]) for row in duckdb.query(query).fetchall()]

def build_in_clause(filter_list):
    if not filter_list: return None
    cleaned = [str(item).replace("'", "''") for item in filter_list if item is not None]
    if not cleaned: return None
    return "('" + "', '".join(cleaned) + "')"

def get_vintage_matrix(pref_num, pref_den, uen, filters):
    where = f"WHERE uen = '{uen}' AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
    for key, col in [('suc', 'nombre_sucursal'), ('prod', 'producto_agrupado'), ('orig', 'PR_Origen_Limpio')]:
        clause = build_in_clause(filters.get(key))
        if clause: where += f" AND {col} IN {clause}"

    cols = f"strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum({pref_den}1) as 'Cap_Inicial'"
    for i in range(1, 25):
        cols += f", sum({pref_num}{i}) / NULLIF(sum({pref_den}{i}), 0) as 'Mes {i}'"
    
    query = f"SELECT {cols} FROM '{FILE_PATH}' {where} GROUP BY 1 ORDER BY 1"
    return duckdb.query(query).df().set_index('Cosecha')

# --- INICIO DASHBOARD ---
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
                st.subheader("📊 UEN: PR (Ratio 30-150)")
                st.dataframe(m_pr.style.format({"Cap_Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in m_pr.columns if 'Mes' in c}, na_rep="").background_gradient(cmap='RdYlGn_r', axis=None, subset=[c for c in m_pr.columns if 'Mes' in c]), use_container_width=True)
            
            st.divider()
            # SOLIDAR
            m_sol = get_vintage_matrix('saldo_capital_total_890_c', 'capital_c', 'SOLIDAR', filtros)
            if not m_sol.empty:
                st.subheader("📊 UEN: SOLIDAR (Ratio 8-90)")
                st.dataframe(m_sol.style.format({"Cap_Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in m_sol.columns if 'Mes' in c}, na_rep="").background_gradient(cmap='RdYlGn_r', axis=None, subset=[c for c in m_sol.columns if 'Mes' in c]), use_container_width=True)

        with tab2:
            st.title("Análisis de Maduración y Comportamiento")
            # 1. Curvas de Maduración
            if not m_pr.empty:
                fig_curves = go.Figure()
                for cosecha in m_pr.tail(8).index:
                    fila = m_pr.loc[cosecha].drop('Cap_Inicial').dropna()
                    fig_curves.add_trace(go.Scatter(x=fila.index, y=fila.values, mode='lines+markers', name=cosecha))
                fig_curves.update_layout(title="Maduración - PR (Últimas 8 Cosechas)", yaxis_tickformat='.1%', plot_bgcolor='white')
                st.plotly_chart(fig_curves, use_container_width=True)

            st.divider()
            # 2. Tendencias Globales 24m
            st.subheader("Tendencia de Comportamiento Global (24 Meses)")
            c_g1, c_g2 = st.columns(2)
            t_filter = f"WHERE {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
            
            with c_g1:
                q_pr = f"SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio FROM '{FILE_PATH}' {t_filter} AND uen='PR' GROUP BY 1 ORDER BY 1"
                st.plotly_chart(px.line(duckdb.query(q_pr).df(), x='Cosecha', y='Ratio', title="Evolución C2 Global - PR", markers=True).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'))
            with c_g2:
                q_sol = f"SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as Ratio FROM '{FILE_PATH}' {t_filter} AND uen='SOLIDAR' GROUP BY 1 ORDER BY 1"
                st.plotly_chart(px.line(duckdb.query(q_sol).df(), x='Cosecha', y='Ratio', title="Evolución C1 Global - SOLIDAR", markers=True, color_discrete_sequence=['red']).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'))

            st.divider()
            # 3. Top 4 Productos Críticos
            st.subheader("⚠️ Evolución de Productos Críticos (Top 4)")
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                q_names_pr = f"SELECT producto_agrupado FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) DESC LIMIT 4"
                list_pr = [str(r[0]) for r in duckdb.query(q_names_pr).fetchall()]
                if list_pr:
                    q_trend_pr = f"SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, producto_agrupado, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio FROM '{FILE_PATH}' WHERE producto_agrupado IN {build_in_clause(list_pr)} AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}') GROUP BY 1, 2 ORDER BY 1"
                    st.plotly_chart(px.line(duckdb.query(q_trend_pr).df(), x='Cosecha', y='Ratio', color='producto_agrupado', title="Top 4 Críticos PR", markers=True).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'))
            with col_t2:
                q_names_sol = f"SELECT producto_agrupado FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1 ORDER BY sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) DESC LIMIT 4"
                list_sol = [str(r[0]) for r in duckdb.query(q_names_sol).fetchall()]
                if list_sol:
                    q_trend_sol = f"SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, producto_agrupado, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as Ratio FROM '{FILE_PATH}' WHERE producto_agrupado IN {build_in_clause(list_sol)} AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}') GROUP BY 1, 2 ORDER BY 1"
                    st.plotly_chart(px.line(duckdb.query(q_trend_sol).df(), x='Cosecha', y='Ratio', color='producto_agrupado', title="Top 4 Críticos SOLIDAR", markers=True).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'))

        with tab3:
            st.title("📍 Detalle de Desempeño")
            
            # --- RESUMEN NARRATIVO ---
            st.subheader("📝 Resumen de Hallazgos")
            
            # Lógica para PR
            q_suc_pr = f"SELECT nombre_sucursal, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY 2 DESC LIMIT 1"
            res_suc_pr = duckdb.query(q_suc_pr).df()
            if not res_suc_pr.empty:
                s_name, s_ratio = res_suc_pr.iloc[0]['nombre_sucursal'], res_suc_pr.iloc[0]['Ratio']
                q_prod_pr = f"SELECT producto_agrupado, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='PR' AND nombre_sucursal = '{s_name}' GROUP BY 1 ORDER BY 2 DESC LIMIT 1"
                p_name, p_ratio = duckdb.query(q_prod_pr).df().iloc[0]['producto_agrupado'], duckdb.query(q_prod_pr).df().iloc[0]['Ratio']
                st.markdown(f"**Para la uen:PR**")
                st.write(f"La sucursal **{s_name}**, tiene el porcentaje más alto con **{s_ratio:.2%}**, siendo el producto_agrupado **{p_name}** el que más participación tiene, con un **{p_ratio:.2%}** para el cohorte C2.")

            st.write("---")

            # Lógica para SOLIDAR
            q_suc_sol = f"SELECT nombre_sucursal, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1 ORDER BY 2 DESC LIMIT 1"
            res_suc_sol = duckdb.query(q_suc_sol).df()
            if not res_suc_sol.empty:
                s_name_s, s_ratio_s = res_suc_sol.iloc[0]['nombre_sucursal'], res_suc_sol.iloc[0]['Ratio']
                q_prod_sol = f"SELECT producto_agrupado, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='SOLIDAR' AND nombre_sucursal = '{s_name_s}' GROUP BY 1 ORDER BY 2 DESC LIMIT 1"
                p_name_s, p_ratio_s = duckdb.query(q_prod_sol).df().iloc[0]['producto_agrupado'], duckdb.query(q_prod_sol).df().iloc[0]['Ratio']
                st.markdown(f"**Para la uen:SOLIDAR**")
                st.write(f"La sucursal **{s_name_s}**, tiene el porcentaje más alto con **{s_ratio_s:.2%}**, siendo el producto_agrupado **{p_name_s}** el que más participación tiene, con un **{p_ratio_s:.2%}** para el cohorte C1.")

            st.divider()
            # 2. MATRIZ SUCURSAL VS PRODUCTO
            st.subheader("🔲 Matriz Sucursal vs Producto (C2 - PR)")
            q_mx = f"SELECT COALESCE(nombre_sucursal, 'N/A') as Sucursal, COALESCE(producto_agrupado, 'N/A') as Producto, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1, 2"
            df_mx = duckdb.query(q_mx).df().pivot(index='Sucursal', columns='Producto', values='Ratio').fillna(0)
            st.dataframe(df_mx.style.format("{:.2%}").background_gradient(cmap='RdYlGn_r', axis=None), use_container_width=True)

            # 3. RANKINGS
            c_s1, c_s2 = st.columns(2)
            with c_s1:
                st.markdown("#### Top 10 Sucursales Riesgo PR")
                q_s_pr = f"SELECT COALESCE(nombre_sucursal, 'N/A') as Sucursal, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as 'Ratio C2' FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
                st.table(duckdb.query(q_s_pr).df().fillna(0).set_index('Sucursal').style.format("{:.2%}"))
            with c_s2:
                st.markdown("#### Top 10 Sucursales Riesgo SOLIDAR")
                q_s_sol = f"SELECT COALESCE(nombre_sucursal, 'N/A') as Sucursal, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as 'Ratio C1' FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
                st.table(duckdb.query(q_s_sol).df().fillna(0).set_index('Sucursal').style.format("{:.2%}"))

except Exception as e:
    st.error(f"Error técnico detectado: {e}")

st.caption("Dashboard Vintage Pro v17.0 | Michel Ovalle | Engine: DuckDB")