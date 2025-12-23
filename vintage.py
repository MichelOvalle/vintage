import streamlit as st
import pandas as pd
import numpy as np
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import os

# 1. Configuración de página
st.set_page_config(page_title="Análisis Vintage Pro", layout="wide")

# Estilos CSS
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

def add_stats_to_df(df):
    if df.empty: return df
    mes_cols = [c for c in df.columns if 'Mes' in c]
    df[mes_cols] = df[mes_cols].apply(pd.to_numeric, errors='coerce')
    stats = pd.DataFrame(index=['Promedio', 'Máximo', 'Mínimo'], columns=df.columns)
    for col in mes_cols:
        stats.at['Promedio', col] = df[col].mean()
        stats.at['Máximo', col] = df[col].max()
        stats.at['Mínimo', col] = df[col].min()
    stats.at['Promedio', 'Cap_Inicial'] = df['Cap_Inicial'].mean()
    return pd.concat([df, stats])

def get_vintage_matrix(pref_num, pref_den, uen, filtros):
    where = f"WHERE uen = '{uen}' AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
    for key, col in [('suc', 'nombre_sucursal'), ('prod', 'producto_agrupado'), ('orig', 'PR_Origen_Limpio')]:
        clause = build_in_clause(filtros.get(key))
        if clause: where += f" AND {col} IN {clause}"
    cols = f"strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum({pref_den}1) as 'Cap_Inicial'"
    for i in range(1, 25):
        cols += f", sum({pref_num}{i}) / NULLIF(sum({pref_den}{i}), 0) as 'Mes {i}'"
    df = duckdb.query(f"SELECT {cols} FROM '{FILE_PATH}' {where} GROUP BY 1 ORDER BY 1").df().set_index('Cosecha')
    return add_stats_to_df(df)

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
            for uen, p_num, p_den, tit in [('PR', 'saldo_capital_total_c', 'capital_c', 'Ratio 30-150'), ('SOLIDAR', 'saldo_capital_total_890_c', 'capital_c', 'Ratio 8-90')]:
                st.subheader(f"📊 {uen} ({tit})")
                m_v = get_vintage_matrix(p_num, p_den, uen, filtros)
                if not m_v.empty:
                    mes_cols = [c for c in m_v.columns if 'Mes' in c]
                    st.dataframe(m_v.style.format({"Cap_Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in mes_cols}, na_rep="")
                                .background_gradient(cmap='RdYlGn_r', axis=None, subset=(m_v.index[:-3], mes_cols))
                                .highlight_null(color='white'), use_container_width=True)

        with tab2:
            st.title("Análisis de Maduración y Comportamiento")
            t_f = f"WHERE {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
            
            # 1. Curvas de Maduración (18 meses)
            m_v_pr = get_vintage_matrix('saldo_capital_total_c', 'capital_c', 'PR', filtros)
            if not m_v_pr.empty:
                df_c = m_v_pr.iloc[:-3] 
                fig_m = go.Figure()
                for cos in df_c.tail(18).index:
                    fila = df_c.loc[cos].drop('Cap_Inicial').dropna()
                    fig_m.add_trace(go.Scatter(x=fila.index, y=fila.values, mode='lines+markers', name=cos))
                fig_m.update_layout(title="Maduración - PR (Últimas 18 Cosechas)", yaxis_tickformat='.1%', plot_bgcolor='white', xaxis_title="Meses de Maduración", yaxis_title="Ratio %",
                    legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5), margin=dict(b=100))
                st.plotly_chart(fig_m, use_container_width=True)
            
            st.divider()
            st.subheader("Tendencias de Comportamiento Global (24 Meses)")
            
            # Evolución Global
            for uen, col_r, col_c, tit, col_line in [('PR', 'saldo_capital_total_c2', 'capital_c2', 'PR', 'blue'), ('SOLIDAR', 'saldo_capital_total_890_c1', 'capital_c1', 'SOLIDAR', 'red')]:
                q = f"SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum({col_r})/NULLIF(sum({col_c}),0) as Ratio FROM '{FILE_PATH}' {t_f} AND uen='{uen}' GROUP BY 1 ORDER BY 1"
                df_ev = duckdb.query(q).df()
                fig_ev = px.line(df_ev, x='Cosecha', y='Ratio', title=f"Evolución Global - {tit}", markers=True, color_discrete_sequence=[col_line], labels={'Cosecha': 'Cosecha', 'Ratio': 'Ratio %'})
                fig_ev.update_xaxes(type='category', tickangle=-45)
                fig_ev.update_layout(yaxis_tickformat='.2%', plot_bgcolor='white', margin=dict(l=60, r=40, b=80, t=60))
                st.plotly_chart(fig_ev, use_container_width=True)

            st.divider()
            st.subheader("⚠️ Evolución de Productos Críticos")
            
            for uen, col_r, col_c, tit in [('PR', 'saldo_capital_total_c2', 'capital_c2', 'PR'), ('SOLIDAR', 'saldo_capital_total_890_c1', 'capital_c1', 'SOLIDAR')]:
                # RANKING: Detectamos los 4 nombres únicos
                qn = f"SELECT COALESCE(producto_agrupado, 'SIN NOMBRE') as P FROM '{FILE_PATH}' {t_f} AND uen='{uen}' GROUP BY 1 ORDER BY sum({col_r})/NULLIF(sum({col_c}), 0) DESC LIMIT 4"
                list_p = [str(r[0]) for r in duckdb.query(qn).fetchall()]
                
                # DIAGNÓSTICO (Expandible para no estorbar)
                with st.expander(f"Depuración: Productos detectados en {tit}"):
                    st.write(f"Buscando histórico para: {list_p}")

                if list_p:
                    p_clause = build_in_clause(list_p)
                    # CONSULTA DE TENDENCIA: Corregida para no perder datos por alias
                    qt = f"""
                        SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, 
                               COALESCE(producto_agrupado, 'SIN NOMBRE') as Producto, 
                               sum({col_r})/NULLIF(sum({col_c}),0) as Ratio 
                        FROM '{FILE_PATH}' 
                        WHERE uen='{uen}' AND COALESCE(producto_agrupado, 'SIN NOMBRE') IN {p_clause} 
                              AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}') 
                        GROUP BY 1, 2 ORDER BY 1
                    """
                    df_t = duckdb.query(qt).df()
                    fig_t = px.line(df_t, x='Cosecha', y='Ratio', color='Producto', title=f"Top {len(list_p)} Críticos {tit}", markers=True, labels={'Cosecha': 'Cosecha', 'Ratio': 'Ratio %'})
                    fig_t.update_xaxes(type='category', tickangle=-45)
                    fig_t.update_layout(yaxis_tickformat='.2%', plot_bgcolor='white', margin=dict(b=80))
                    st.plotly_chart(fig_t, use_container_width=True)

        with tab3:
            st.title("📍 Detalle de Desempeño")
            # Resúmenes Narrativos
            for uen, col_r, col_c, coh in [('PR', 'saldo_capital_total_c2', 'capital_c2', 'C2'), ('SOLIDAR', 'saldo_capital_total_890_c1', 'capital_c1', 'C1')]:
                q_sn = f"SELECT nombre_sucursal as n, sum({col_r})/NULLIF(sum({col_c}), 0) as r FROM '{FILE_PATH}' WHERE uen='{uen}' GROUP BY 1 ORDER BY 2 DESC LIMIT 1"
                res_s = duckdb.query(q_sn).df()
                if not res_s.empty:
                    sn, sr = res_s.iloc[0]['n'], res_s.iloc[0]['r']
                    q_pn = f"SELECT producto_agrupado as n, sum({col_r})/NULLIF(sum({col_c}), 0) as r FROM '{FILE_PATH}' WHERE uen='{uen}' AND nombre_sucursal = '{sn}' GROUP BY 1 ORDER BY 2 DESC LIMIT 1"
                    res_p = duckdb.query(q_pn).df()
                    pn, pr = res_p.iloc[0]['n'], res_p.iloc[0]['r']
                    st.write(f"**Para la uen:{uen}**")
                    st.write(f"La sucursal **{sn}**, tiene el porcentaje más alto con **{sr:.2%}**, siendo el producto_agrupado **{pn}** el que más participación tiene, con un **{pr:.2%}** para el cohorte {coh}.")
            
            st.divider()
            c_mx1, c_mx2 = st.columns(2)
            for uen, col_r, col_c, col_obj in [('PR', 'saldo_capital_total_c2', 'capital_c2', c_mx1), ('SOLIDAR', 'saldo_capital_total_890_c1', 'capital_c1', c_mx2)]:
                with col_obj:
                    st.subheader(f"🔲 Sucursal vs Producto ({uen})")
                    q = f"SELECT COALESCE(nombre_sucursal, 'N/A') as Sucursal, COALESCE(producto_agrupado, 'N/A') as Producto, sum({col_r})/NULLIF(sum({col_c}), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='{uen}' GROUP BY 1, 2"
                    df_m = duckdb.query(q).df()
                    if not df_m.empty:
                        df_p = df_m.pivot(index='Sucursal', columns='Producto', values='Ratio').fillna(0)
                        df_p.index.name, df_p.columns.name = "Sucursal", "Producto"
                        st.dataframe(df_p.style.format("{:.2%}").background_gradient(cmap='RdYlGn_r', axis=None), use_container_width=True)

            st.divider()
            c_rk1, c_rk2 = st.columns(2)
            with c_rk1:
                st.markdown("#### Top 10 Sucursales Riesgo PR")
                q_rk_pr = f"SELECT COALESCE(nombre_sucursal, 'N/A') as Sucursal, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as 'Ratio C2' FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
                df_rk_pr = duckdb.query(q_rk_pr).df().fillna(0)
                if not df_rk_pr.empty:
                    st.table(df_rk_pr.set_index('Sucursal').style.format("{:.2%}"))

            with c_rk2:
                st.markdown("#### Top 10 Sucursales Riesgo SOLIDAR")
                q_rk_sol = f"SELECT COALESCE(nombre_sucursal, 'N/A') as Sucursal, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as 'Ratio C1' FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
                df_rk_sol = duckdb.query(q_rk_sol).df().fillna(0)
                if not df_rk_sol.empty:
                    st.table(df_rk_sol.set_index('Sucursal').style.format("{:.2%}"))

except Exception as e:
    st.error(f"Error técnico detectado: {e}")

st.caption("Dashboard Vintage Pro v39.0 | Michel Ovalle | Engine: DuckDB")