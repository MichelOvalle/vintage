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
    return [str(row[0]) for row in duckdb.query(query).fetchall()]

def build_in_clause(filter_list):
    if not filter_list: return None
    cleaned_list = [str(item).replace("'", "''") for item in filter_list if item is not None]
    return "('" + "', '".join(cleaned_list) + "')"

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

# --- LÓGICA DE DASHBOARD ---
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
            st.title("Reporte de Ratios por Cosecha (Últ. 24 meses)")
            m_pr = get_vintage_matrix('saldo_capital_total_c', 'capital_c', 'PR', filtros)
            if not m_pr.empty:
                st.subheader("📊 UEN: PR (Ratio 30-150)")
                st.dataframe(m_pr.style.format({"Cap_Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in m_pr.columns if 'Mes' in c}, na_rep="").background_gradient(cmap='RdYlGn_r', axis=None, subset=[c for c in m_pr.columns if 'Mes' in c]), use_container_width=True)
            
            st.divider()
            m_sol = get_vintage_matrix('saldo_capital_total_890_c', 'capital_c', 'SOLIDAR', filtros)
            if not m_sol.empty:
                st.subheader("📊 UEN: SOLIDAR (Ratio 8-90)")
                st.dataframe(m_sol.style.format({"Cap_Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in m_sol.columns if 'Mes' in c}, na_rep="").background_gradient(cmap='RdYlGn_r', axis=None, subset=[c for c in m_sol.columns if 'Mes' in c]), use_container_width=True)

        with tab2:
            st.title("Análisis de Maduración y Comportamiento")
            
            # 1. Curvas de Maduración (Gráfica definida)
            if not m_pr.empty:
                fig_curves = go.Figure()
                for cosecha in m_pr.tail(8).index:
                    fila = m_pr.loc[cosecha].drop('Cap_Inicial').dropna()
                    fig_curves.add_trace(go.Scatter(x=fila.index, y=fila.values, mode='lines+markers', name=cosecha))
                fig_curves.update_layout(title="Curvas de Maduración - PR (Últimas 8 Cosechas)", yaxis_tickformat='.1%', plot_bgcolor='white', xaxis_title="Meses")
                st.plotly_chart(fig_curves, use_container_width=True)

            st.divider()
            # 2. Tendencias Globales (X: 24 meses) - GRÁFICAS RESTAURADAS
            st.subheader("Tendencia de Comportamiento Global (Ventana 24 meses)")
            col_g1, col_g2 = st.columns(2)
            time_filter = f"WHERE {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
            
            with col_g1:
                q_ev_pr = f"SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio FROM '{FILE_PATH}' {time_filter} AND uen='PR' GROUP BY 1 ORDER BY 1"
                st.plotly_chart(px.line(duckdb.query(q_ev_pr).df(), x='Cosecha', y='Ratio', title="Ratio C2 Global - PR", markers=True, color_discrete_sequence=['#1f77b4']).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'), use_container_width=True)
                
            with col_g2:
                q_ev_sol = f"SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as Ratio FROM '{FILE_PATH}' {time_filter} AND uen='SOLIDAR' GROUP BY 1 ORDER BY 1"
                st.plotly_chart(px.line(duckdb.query(q_ev_sol).df(), x='Cosecha', y='Ratio', title="Ratio C1 Global - SOLIDAR", markers=True, color_discrete_sequence=['#d62728']).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'), use_container_width=True)

            st.divider()
            # 3. Top 4 Productos Críticos (Evolución Temporal) - GRÁFICAS RESTAURADAS
            st.subheader("⚠️ Top 4 Productos Críticos (Evolución Temporal)")
            col_t1, col_t2 = st.columns(2)
            
            with col_t1:
                # Top 4 PR
                q_top4_names_pr = f"SELECT producto_agrupado FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) DESC LIMIT 4"
                list_pr = [r[0] for r in duckdb.query(q_top4_names_pr).fetchall()]
                if list_pr:
                    q_pr_trend = f"SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, producto_agrupado, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio FROM '{FILE_PATH}' WHERE producto_agrupado IN ('{"', '".join(list_pr)}') AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}') GROUP BY 1, 2 ORDER BY 1"
                    st.plotly_chart(px.line(duckdb.query(q_pr_trend).df(), x='Cosecha', y='Ratio', color='producto_agrupado', title="Productos Críticos C2 - PR", markers=True).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'), use_container_width=True)

            with col_t2:
                # Top 4 SOLIDAR
                q_top4_names_sol = f"SELECT producto_agrupado FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1 ORDER BY sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) DESC LIMIT 4"
                list_sol = [r[0] for r in duckdb.query(q_top4_names_sol).fetchall()]
                if list_sol:
                    q_sol_trend = f"SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, producto_agrupado, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as Ratio FROM '{FILE_PATH}' WHERE producto_agrupado IN ('{"', '".join(list_sol)}') AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}') GROUP BY 1, 2 ORDER BY 1"
                    st.plotly_chart(px.line(duckdb.query(q_sol_trend).df(), x='Cosecha', y='Ratio', color='producto_agrupado', title="Productos Críticos C1 - SOLIDAR", markers=True).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'), use_container_width=True)

        with tab3:
            st.title("📍 Detalle de Desempeño")
            
            # 1. RESUMEN NARRATIVO (PR Y SOLIDAR COMPLETOS)
            st.subheader("📝 Resumen de Hallazgos")
            c_res1, c_res2 = st.columns(2)
            
            with c_res1:
                st.markdown("#### UEN: PR")
                q_pr_res = f"SELECT nombre_sucursal, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY 2 DESC"
                df_pr_res = duckdb.query(q_pr_res).df().dropna()
                if not df_pr_res.empty:
                    st.write(f"🚩 **Punto Crítico:** Sucursal **{df_pr_res.iloc[0]['nombre_sucursal']}** ({df_pr_res.iloc[0]['Ratio']:.2%})")
                    st.write(f"✅ **Mejor Desempeño:** Sucursal **{df_pr_res.iloc[-1]['nombre_sucursal']}** ({df_pr_res.iloc[-1]['Ratio']:.2%})")

            with c_res2:
                st.markdown("#### UEN: SOLIDAR")
                q_sol_res = f"SELECT nombre_sucursal, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1 ORDER BY 2 DESC"
                df_sol_res = duckdb.query(q_sol_res).df().dropna()
                if not df_sol_res.empty:
                    st.write(f"🚩 **Punto Crítico:** Sucursal **{df_sol_res.iloc[0]['nombre_sucursal']}** ({df_sol_res.iloc[0]['Ratio']:.2%})")
                    st.write(f"✅ **Mejor Desempeño:** Sucursal **{df_sol_res.iloc[-1]['nombre_sucursal']}** ({df_sol_res.iloc[-1]['Ratio']:.2%})")

            st.divider()
            # 2. MATRIZ SUCURSAL VS PRODUCTO
            st.subheader("🔲 Matriz Sucursal vs Producto (Ratio C2 - PR)")
            q_pivot = f"SELECT COALESCE(nombre_sucursal, 'N/A') as Sucursal, COALESCE(producto_agrupado, 'N/A') as Producto, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1, 2"
            df_p = duckdb.query(q_pivot).df().pivot(index='Sucursal', columns='Producto', values='Ratio').fillna(0)
            st.dataframe(df_p.style.format("{:.2%}").background_gradient(cmap='RdYlGn_r', axis=None), use_container_width=True)

            # 3. RANKINGS
            st.divider()
            c_s1, c_s2 = st.columns(2)
            with c_s1:
                st.markdown("#### Top 10 Sucursales Riesgo PR")
                q_s_pr = f"SELECT COALESCE(nombre_sucursal, 'N/A') as Sucursal, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as 'Ratio C2' FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
                st.table(duckdb.query(q_s_pr).df().fillna(0).set_index('Sucursal').style.format("{:.2%}"))
            with c_s2:
                st.markdown("#### Top 10 Sucursales Riesgo SOLIDAR")
                q_s_sol = f"SELECT COALESCE(nombre_sucursal, 'N/A') as Sucursal, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as 'Ratio C1' FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
                st.table(duckdb.query(q_s_sol).df().fillna(0).set_index('Sucursal').style.format("{:.2%}"))

    else:
        st.error(f"Error: Archivo '{FILE_PATH}' no encontrado.")

except Exception as e:
    st.error(f"Error técnico detectado: {e}")

st.caption("Dashboard Vintage Pro | Michel Ovalle | Engine: DuckDB | Ventana: 24 meses")