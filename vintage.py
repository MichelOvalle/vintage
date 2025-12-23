import streamlit as st
import pandas as pd
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import os

# 1. Configuración de página
st.set_page_config(page_title="Análisis Vintage Pro", layout="wide")

# Estilos CSS para legibilidad y prevención de errores visuales
st.markdown("""
    <style>
    .main { background-color: #FFFFFF; }
    [data-testid="stTable"] td, [data-testid="stTable"] th { color: black !important; }
    [data-testid="stDataFrame"] td { color: black !important; }
    </style>
    """, unsafe_allow_html=True)

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

def add_stats_rows(df):
    """Añade filas de Promedio, Máximo y Mínimo al final del DataFrame"""
    if df.empty: return df
    
    # Calculamos stats solo para las columnas de 'Mes X'
    mes_cols = [c for c in df.columns if 'Mes' in c]
    
    stats_df = pd.DataFrame(index=['Promedio', 'Máximo', 'Mínimo'], columns=df.columns)
    
    for col in mes_cols:
        stats_df.at['Promedio', col] = df[col].mean()
        stats_df.at['Máximo', col] = df[col].max()
        stats_df.at['Mínimo', col] = df[col].min()
    
    # Para Capital Inicial en las filas de stats dejamos vacío o total
    stats_df.at['Promedio', 'Cap_Inicial'] = df['Cap_Inicial'].mean()
    
    return pd.concat([df, stats_df])

def get_vintage_matrix(pref_num, pref_den, uen, filtros):
    where = f"WHERE uen = '{uen}' AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
    for key, col in [('suc', 'nombre_sucursal'), ('prod', 'producto_agrupado'), ('orig', 'PR_Origen_Limpio')]:
        clause = build_in_clause(filtros.get(key))
        if clause: where += f" AND {col} IN {clause}"

    cols = f"strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum({pref_den}1) as 'Cap_Inicial'"
    for i in range(1, 25):
        cols += f", sum({pref_num}{i}) / NULLIF(sum({pref_den}{i}), 0) as 'Mes {i}'"
    
    df = duckdb.query(f"SELECT {cols} FROM '{FILE_PATH}' {where} GROUP BY 1 ORDER BY 1").df().set_index('Cosecha')
    return add_stats_rows(df)

# --- LÓGICA DASHBOARD ---
try:
    if os.path.exists(FILE_PATH):
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
                mes_cols = [c for c in m_pr.columns if 'Mes' in c]
                st.dataframe(m_pr.style.format({"Cap_Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in mes_cols}, na_rep="")
                            .background_gradient(cmap='RdYlGn_r', axis=None, subset=(m_pr.index[:-3], mes_cols)), use_container_width=True)
            
            st.divider()
            # SOLIDAR
            m_sol = get_vintage_matrix('saldo_capital_total_890_c', 'capital_c', 'SOLIDAR', filtros)
            if not m_sol.empty:
                st.subheader("📊 UEN: SOLIDAR (Ratio 8-90)")
                mes_cols_s = [c for c in m_sol.columns if 'Mes' in c]
                st.dataframe(m_sol.style.format({"Cap_Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in mes_cols_s}, na_rep="")
                            .background_gradient(cmap='RdYlGn_r', axis=None, subset=(m_sol.index[:-3], mes_cols_s)), use_container_width=True)

        with tab2:
            st.title("Análisis de Maduración y Comportamiento")
            # Curvas PR (Sin las filas de stats)
            if not m_pr.empty:
                df_curves = m_pr.iloc[:-3]
                fig = go.Figure()
                for cosecha in df_curves.tail(8).index:
                    fila = df_curves.loc[cosecha].drop('Cap_Inicial').dropna()
                    fig.add_trace(go.Scatter(x=fila.index, y=fila.values, mode='lines+markers', name=cosecha))
                fig.update_layout(title="Maduración - PR (Últimas 8 Cosechas)", yaxis_tickformat='.1%', plot_bgcolor='white')
                st.plotly_chart(fig, use_container_width=True)

            # Tendencias Globales
            st.divider()
            c1, c2 = st.columns(2)
            t_f = f"WHERE {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
            with c1:
                q = f"SELECT strftime({COL_FECHA}, '%Y-%m') as C, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2),0) as R FROM '{FILE_PATH}' {t_f} AND uen='PR' GROUP BY 1 ORDER BY 1"
                st.plotly_chart(px.line(duckdb.query(q).df(), x='C', y='R', title="Evolución C2 Global - PR", markers=True).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'))
            with c2:
                q = f"SELECT strftime({COL_FECHA}, '%Y-%m') as C, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1),0) as R FROM '{FILE_PATH}' {t_f} AND uen='SOLIDAR' GROUP BY 1 ORDER BY 1"
                st.plotly_chart(px.line(duckdb.query(q).df(), x='C', y='R', title="Evolución C1 Global - SOLIDAR", markers=True, color_discrete_sequence=['red']).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'))

            # Top 4 Productos
            st.divider()
            c3, c4 = st.columns(2)
            with c3:
                q_n = f"SELECT producto_agrupado FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2),0) DESC LIMIT 4"
                l = [str(r[0]) for r in duckdb.query(q_n).fetchall()]
                if l:
                    q_t = f"SELECT strftime({COL_FECHA}, '%Y-%m') as C, producto_agrupado as P, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2),0) as R FROM '{FILE_PATH}' WHERE P IN {build_in_clause(l)} AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}') GROUP BY 1, 2 ORDER BY 1"
                    st.plotly_chart(px.line(duckdb.query(q_t).df(), x='C', y='R', color='P', title="Top 4 Críticos PR", markers=True).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'))
            with c4:
                q_n = f"SELECT producto_agrupado FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1 ORDER BY sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1),0) DESC LIMIT 4"
                l = [str(r[0]) for r in duckdb.query(q_n).fetchall()]
                if l:
                    q_t = f"SELECT strftime({COL_FECHA}, '%Y-%m') as C, producto_agrupado as P, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1),0) as R FROM '{FILE_PATH}' WHERE P IN {build_in_clause(l)} AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}') GROUP BY 1, 2 ORDER BY 1"
                    st.plotly_chart(px.line(duckdb.query(q_t).df(), x='C', y='R', color='P', title="Top 4 Críticos SOLIDAR", markers=True).update_layout(yaxis_tickformat='.1%', plot_bgcolor='white'))

        with tab3:
            st.title("📍 Detalle de Desempeño")
            # Resumen Narrativo
            st.subheader("📝 Resumen de Hallazgos")
            for uen, col_r, cohorte in [('PR', 'saldo_capital_total_c2', 'C2'), ('SOLIDAR', 'saldo_capital_total_890_c1', 'C1')]:
                q_s = f"SELECT nombre_sucursal, sum({col_r})/NULLIF(sum(capital_c2 if '{uen}'='PR' else capital_c1), 0) as R FROM '{FILE_PATH}' WHERE uen='{uen}' GROUP BY 1 ORDER BY 2 DESC LIMIT 1"
                res_s = duckdb.query(q_s).df()
                if not res_s.empty:
                    s_n, s_r = res_s.iloc[0]['nombre_sucursal'], res_s.iloc[0]['R']
                    q_p = f"SELECT producto_agrupado, sum({col_r})/NULLIF(sum(capital_c2 if '{uen}'='PR' else capital_c1), 0) as R FROM '{FILE_PATH}' WHERE uen='{uen}' AND nombre_sucursal = '{s_n}' GROUP BY 1 ORDER BY 2 DESC LIMIT 1"
                    res_p = duckdb.query(q_p).df()
                    p_n, p_r = res_p.iloc[0]['producto_agrupado'], res_p.iloc[0]['R']
                    st.write(f"**Para la uen:{uen}**")
                    st.write(f"La sucursal **{s_n}**, tiene el porcentaje más alto con **{s_r:.2%}**, siendo el producto_agrupado **{p_n}** el que más participación tiene, con un **{p_r:.2%}** para el cohorte {cohorte}.")

            # Matrices y Rankings (Simplificados para RAM)
            st.divider()
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.subheader("🔲 Sucursal vs Producto (C2 - PR)")
                q = f"SELECT nombre_sucursal as S, producto_agrupado as P, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as R FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1, 2"
                df_m = duckdb.query(q).df().pivot(index='S', columns='P', values='R').fillna(0)
                st.dataframe(df_m.style.format("{:.2%}").background_gradient(cmap='RdYlGn_r', axis=None), use_container_width=True)
            with col_m2:
                st.subheader("🔲 Sucursal vs Producto (C1 - SOLIDAR)")
                q = f"SELECT nombre_sucursal as S, producto_agrupado as P, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as R FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1, 2"
                df_m = duckdb.query(q).df().pivot(index='S', columns='P', values='R').fillna(0)
                st.dataframe(df_m.style.format("{:.2%}").background_gradient(cmap='RdYlGn_r', axis=None), use_container_width=True)

    else:
        st.error(f"Archivo '{FILE_PATH}' no encontrado.")
except Exception as e:
    st.error(f"Error técnico detectado: {e}")