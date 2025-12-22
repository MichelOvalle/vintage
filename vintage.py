import streamlit as st
import pandas as pd
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import os

# 1. Configuración de página
st.set_page_config(page_title="Análisis Vintage Pro (DuckDB)", layout="wide")

# Estilos CSS
st.markdown("<style>.main { background-color: #FFFFFF; } [data-testid='stTable'] td { color: black !important; }</style>", unsafe_allow_html=True)

FILE_PATH = "vintage_acum.parquet"

@st.cache_data
def get_filter_options(column_name):
    if not os.path.exists(FILE_PATH): return []
    # Consultamos solo los valores únicos sin cargar el archivo
    query = f"SELECT DISTINCT {column_name} FROM '{FILE_PATH}' WHERE {column_name} IS NOT NULL ORDER BY {column_name}"
    return [row[0] for row in duckdb.query(query).fetchall()]

def get_vintage_matrix_duckdb(pref_num, pref_den, uen, filters):
    # Construcción dinámica de la consulta SQL para evitar cargar datos innecesarios
    where_clause = f"WHERE uen = '{uen}' AND mes_apertura >= (SELECT max(mes_apertura) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
    
    if filters.get('suc'): where_clause += f" AND nombre_sucursal IN {tuple(filters['suc']) if len(filters['suc']) > 1 else f'(\"{filters['suc'][0]}\")'}"
    if filters.get('prod'): where_clause += f" AND producto_agrupado IN {tuple(filters['prod']) if len(filters['prod']) > 1 else f'(\"{filters['prod'][0]}\")'}"
    if filters.get('orig'): where_clause += f" AND PR_Origen_Limpio IN {tuple(filters['orig']) if len(filters['orig']) > 1 else f'(\"{filters['orig'][0]}\")'}"

    # Seleccionamos capital inicial (Mes 1) y ratios
    cols_sql = f"strftime(mes_apertura, '%Y-%m') as Cosecha, sum({pref_den}1) as 'Capital Inicial'"
    for i in range(1, 25):
        cols_sql += f", sum({pref_num}{i}) / NULLIF(sum({pref_den}{i}), 0) as 'Mes {i}'"
    
    query = f"SELECT {cols_sql} FROM '{FILE_PATH}' {where_clause} GROUP BY 1 ORDER BY 1"
    return duckdb.query(query).df().set_index('Cosecha')

try:
    if os.path.exists(FILE_PATH):
        # --- SIDEBAR: FILTROS DIRECTOS DESDE EL ARCHIVO ---
        st.sidebar.header("Filtros Globales")
        f_suc = st.sidebar.multiselect("Sucursal", get_filter_options("nombre_sucursal"))
        f_prod = st.sidebar.multiselect("Producto Agrupado", get_filter_options("producto_agrupado"))
        f_orig = st.sidebar.multiselect("Origen Limpio", get_filter_options("PR_Origen_Limpio"))
        
        filtros = {'suc': f_suc, 'prod': f_prod, 'orig': f_orig}

        # --- TABS ---
        tab1, tab2, tab3 = st.tabs(["📋 Vintage", "📈 Tendencias", "📍 Detalle Global"])

        with tab1:
            st.title("Análisis Vintage (Carga vía DuckDB)")
            
            # PR
            m_pr = get_vintage_matrix_duckdb('saldo_capital_total_c', 'capital_c', 'PR', filtros)
            if not m_pr.empty:
                st.subheader("📊 UEN: PR")
                st.dataframe(m_pr.style.format({"Capital Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in m_pr.columns if 'Mes' in c}, na_rep="")
                            .background_gradient(cmap='RdYlGn_r', axis=None, subset=[c for c in m_pr.columns if 'Mes' in c]), use_container_width=True)

            st.divider()
            # SOLIDAR
            m_sol = get_vintage_matrix_duckdb('saldo_capital_total_890_c', 'capital_c', 'SOLIDAR', filtros)
            if not m_sol.empty:
                st.subheader("📊 UEN: SOLIDAR")
                st.dataframe(m_sol.style.format({"Capital Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in m_sol.columns if 'Mes' in c}, na_rep="")
                            .background_gradient(cmap='RdYlGn_r', axis=None, subset=[c for c in m_sol.columns if 'Mes' in c]), use_container_width=True)

        with tab2:
            st.title("Top 5 Productos por Riesgo")
            # Consulta SQL para Top 5 PR (C2)
            q_top_pr = f"SELECT producto_agrupado, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY 2 DESC LIMIT 5"
            top_pr = duckdb.query(q_top_pr).df()
            
            # Consulta SQL para Top 5 SOLIDAR (C1)
            q_top_sol = f"SELECT producto_agrupado, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1 ORDER BY 2 DESC LIMIT 5"
            top_sol = duckdb.query(q_top_sol).df()

            col_a, col_b = st.columns(2)
            with col_a:
                st.plotly_chart(px.bar(top_pr, x='Ratio', y='producto_agrupado', orientation='h', title="Top 5 PR", color='Ratio', color_continuous_scale='Reds').update_layout(xaxis_tickformat='.1%', yaxis={'categoryorder':'total ascending'}))
            with col_b:
                st.plotly_chart(px.bar(top_sol, x='Ratio', y='producto_agrupado', orientation='h', title="Top 5 SOLIDAR", color='Ratio', color_continuous_scale='Reds').update_layout(xaxis_tickformat='.1%', yaxis={'categoryorder':'total ascending'}))

        with tab3:
            st.title("📍 Desempeño Sucursales (Global)")
            q_suc_pr = f"SELECT nombre_sucursal, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as 'Ratio C2' FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
            q_suc_sol = f"SELECT nombre_sucursal, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as 'Ratio C1' FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
            
            c_x, c_y = st.columns(2)
            with c_x:
                st.write("**Top 10 Riesgo PR**")
                st.table(duckdb.query(q_suc_pr).df().set_index('nombre_sucursal'))
            with c_y:
                st.write("**Top 10 Riesgo SOLIDAR**")
                st.table(duckdb.query(q_suc_sol).df().set_index('nombre_sucursal'))

    else:
        st.error("Archivo Parquet no encontrado.")

except Exception as e:
    st.error(f"Error técnico detectado: {e}")

st.caption("Procesado con DuckDB Engine | Michel Ovalle")