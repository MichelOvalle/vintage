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
    cleaned = [str(item).replace("'", "''") for item in filter_list if item is not None]
    return "('" + "', '".join(cleaned) + "')"

def get_vintage_data(pref_num, pref_den, uen, filtros):
    """Obtiene los datos puros sin procesar stats en el mismo DF para ahorrar RAM"""
    where = f"WHERE uen = '{uen}' AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
    for key, col in [('suc', 'nombre_sucursal'), ('prod', 'producto_agrupado'), ('orig', 'PR_Origen_Limpio')]:
        clause = build_in_clause(filtros.get(key))
        if clause: where += f" AND {col} IN {clause}"

    cols = f"strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum({pref_den}1) as 'Cap_Inicial'"
    for i in range(1, 25):
        cols += f", sum({pref_num}{i}) / NULLIF(sum({pref_den}{i}), 0) as 'Mes {i}'"
    
    return duckdb.query(f"SELECT {cols} FROM '{FILE_PATH}' {where} GROUP BY 1 ORDER BY 1").df().set_index('Cosecha')

# --- INICIO DASHBOARD ---
try:
    if os.path.exists(FILE_PATH):
        st.sidebar.header("Filtros Globales")
        filtros = {
            'suc': st.sidebar.multiselect("Sucursal", get_filter_options("nombre_sucursal")),
            'prod': st.sidebar.multiselect("Producto Agrupado", get_filter_options("producto_agrupado")),
            'orig': st.sidebar.multiselect("Origen Limpio", get_filter_options("PR_Origen_Limpio"))
        }

        tab1, tab2, tab3 = st.tabs(["📋 Vintage", "📈 Curvas y Tendencias", "📍 Detalle de Desempeño"])

        with tab1:
            st.title("Reporte de Ratios por Cosecha (24 meses)")
            
            for uen, p_num, p_den, tit in [('PR', 'saldo_capital_total_c', 'capital_c', 'Ratio 30-150'), 
                                           ('SOLIDAR', 'saldo_capital_total_890_c', 'capital_c', 'Ratio 8-90')]:
                st.subheader(f"📊 UEN: {uen} ({tit})")
                df_v = get_vintage_data(p_num, p_den, uen, filtros)
                if not df_v.empty:
                    # TABLA SIN GRADIENTE PARA EVITAR FONDO NEGRO
                    mes_cols = [c for c in df_v.columns if 'Mes' in c]
                    st.dataframe(df_v.style.format({"Cap_Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in mes_cols}, na_rep="-"), use_container_width=True)
                    
                    # MÉTRICAS DE RESUMEN (ESTADÍSTICAS) EN COLUMNAS
                    c1, c2, c3 = st.columns(3)
                    c1.metric(f"Promedio {uen}", f"{df_v[mes_cols].mean().mean():.2%}")
                    c2.metric(f"Máximo {uen}", f"{df_v[mes_cols].max().max():.2%}")
                    c3.metric(f"Mínimo {uen}", f"{df_v[mes_cols].min().min():.2%}")
                st.divider()

        with tab2:
            st.title("Análisis de Maduración y Comportamiento")
            # 5 GRÁFICAS REQUERIDAS
            t_f = f"WHERE {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
            
            # Gráfica 1: Curvas de Maduración PR
            q_c = f"SELECT strftime({COL_FECHA}, '%Y-%m') as C, producto_agrupado, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2),0) as R FROM '{FILE_PATH}' {t_f} AND uen='PR' GROUP BY 1, 2"
            df_c = duckdb.query(q_c).df()
            
            col_a, col_b = st.columns(2)
            with col_a:
                # Gráfica 2: Tendencia Global PR
                q_p = f"SELECT strftime({COL_FECHA}, '%Y-%m') as C, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2),0) as R FROM '{FILE_PATH}' {t_f} AND uen='PR' GROUP BY 1 ORDER BY 1"
                st.plotly_chart(px.line(duckdb.query(q_p).df(), x='C', y='R', title="Evolución C2 Global - PR", markers=True).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'), use_container_width=True)
                
                # Gráfica 4: Top 4 PR
                qn = f"SELECT producto_agrupado FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2),0) DESC LIMIT 4"
                list_n = [str(r[0]) for r in duckdb.query(qn).fetchall()]
                if list_n:
                    qt = f"SELECT strftime({COL_FECHA}, '%Y-%m') as C, producto_agrupado as P, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2),0) as R FROM '{FILE_PATH}' WHERE P IN {build_in_clause(list_n)} AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}') GROUP BY 1, 2 ORDER BY 1"
                    st.plotly_chart(px.line(duckdb.query(qt).df(), x='C', y='R', color='P', title="Top 4 Críticos PR", markers=True).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'), use_container_width=True)

            with col_b:
                # Gráfica 3: Tendencia Global SOLIDAR
                q_s = f"SELECT strftime({COL_FECHA}, '%Y-%m') as C, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1),0) as R FROM '{FILE_PATH}' {t_f} AND uen='SOLIDAR' GROUP BY 1 ORDER BY 1"
                st.plotly_chart(px.line(duckdb.query(q_s).df(), x='C', y='R', title="Evolución C1 Global - SOLIDAR", markers=True, color_discrete_sequence=['red']).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'), use_container_width=True)
                
                # Gráfica 5: Top 4 SOLIDAR
                qn_s = f"SELECT producto_agrupado FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1 ORDER BY sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1),0) DESC LIMIT 4"
                list_s = [str(r[0]) for r in duckdb.query(qn_s).fetchall()]
                if list_s:
                    qt_s = f"SELECT strftime({COL_FECHA}, '%Y-%m') as C, producto_agrupado as P, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1),0) as R FROM '{FILE_PATH}' WHERE P IN {build_in_clause(list_s)} AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}') GROUP BY 1, 2 ORDER BY 1"
                    st.plotly_chart(px.line(duckdb.query(qt_s).df(), x='C', y='R', color='P', title="Top 4 Críticos SOLIDAR", markers=True).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'), use_container_width=True)

        with tab3:
            st.title("📍 Detalle de Desempeño")
            st.subheader("📝 Resumen de Hallazgos")
            
            # NARRATIVA PR Y SOLIDAR
            for uen, col_r, col_c, coh in [('PR', 'saldo_capital_total_c2', 'capital_c2', 'C2'), ('SOLIDAR', 'saldo_capital_total_890_c1', 'capital_c1', 'C1')]:
                q_sn = f"SELECT nombre_sucursal as n, sum({col_r})/NULLIF(sum({col_c}), 0) as r FROM '{FILE_PATH}' WHERE uen='{uen}' GROUP BY 1 ORDER BY 2 DESC LIMIT 1"
                res_s = duckdb.query(q_sn).df()
                if not res_s.empty:
                    sn, sr = res_s.iloc[0]['n'], res_s.iloc[0]['r']
                    q_pn = f"SELECT producto_agrupado as n, sum({col_r})/NULLIF(sum({col_c}), 0) as r FROM '{FILE_PATH}' WHERE uen='{uen}' AND nombre_sucursal = '{sn}' GROUP BY 1 ORDER BY 2 DESC LIMIT 1"
                    pn, pr = duckdb.query(q_pn).df().iloc[0]['n'], duckdb.query(q_pn).df().iloc[0]['r']
                    st.write(f"**Para la uen:{uen}**")
                    st.write(f"La sucursal **{sn}**, tiene el porcentaje más alto con **{sr:.2%}**, siendo el producto_agrupado **{pn}** el que más participación tiene, con un **{pr:.2%}** para el cohorte {coh}.")

            st.divider()
            # MATRICES CON COLOR (Aquí sí se permiten porque son pequeñas)
            c_mx1, c_mx2 = st.columns(2)
            with c_mx1:
                st.subheader("🔲 Sucursal vs Producto (C2 - PR)")
                q_mx = f"SELECT nombre_sucursal as S, producto_agrupado as P, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as R FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1, 2"
                df_mx = duckdb.query(q_mx).df().pivot(index='S', columns='P', values='R').fillna(0)
                st.dataframe(df_mx.style.format("{:.2%}").background_gradient(cmap='RdYlGn_r', axis=None), use_container_width=True)
            with c_mx2:
                st.subheader("🔲 Sucursal vs Producto (C1 - SOLIDAR)")
                q_mx_s = f"SELECT nombre_sucursal as S, producto_agrupado as P, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as R FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1, 2"
                df_mx_s = duckdb.query(q_mx_s).df().pivot(index='S', columns='P', values='R').fillna(0)
                st.dataframe(df_mx_s.style.format("{:.2%}").background_gradient(cmap='RdYlGn_r', axis=None), use_container_width=True)

    else:
        st.error(f"Archivo '{FILE_PATH}' no encontrado.")

except Exception as e:
    st.error(f"Error técnico detectado: {e}")