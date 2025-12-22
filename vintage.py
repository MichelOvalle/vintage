import streamlit as st
import pandas as pd
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import os

# 1. Configuración de página
st.set_page_config(page_title="Análisis Vintage Pro (DuckDB)", layout="wide")

# Estilos CSS para limpieza visual
st.markdown("""
    <style>
    .main { background-color: #FFFFFF; }
    [data-testid="stTable"] td, [data-testid="stTable"] th { color: black !important; }
    [data-testid="stDataFrame"] td { color: black !important; }
    </style>
    """, unsafe_allow_html=True)

FILE_PATH = "vintage_acum.parquet"

@st.cache_data
def get_filter_options(column_name):
    if not os.path.exists(FILE_PATH): return []
    query = f"SELECT DISTINCT {column_name} FROM '{FILE_PATH}' WHERE {column_name} IS NOT NULL ORDER BY {column_name}"
    return [row[0] for row in duckdb.query(query).fetchall()]

def get_vintage_matrix_duckdb(pref_num, pref_den, uen, filters):
    # SOLUCIÓN AL ERROR DE FORMATO:
    # Concatenamos '||-01' al campo mes_apertura para que DuckDB lo reconozca como DATE
    
    col_fecha = f"CAST(mes_apertura || '-01' AS DATE)"
    
    where_clause = f"""
        WHERE uen = '{uen}' 
        AND {col_fecha} >= (SELECT max({col_fecha}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')
    """
    
    # Manejo de filtros dinámicos
    if filters.get('suc'):
        vals = "', '".join(filters['suc'])
        where_clause += f" AND nombre_sucursal IN ('{vals}')"
    if filters.get('prod'):
        vals = "', '".join(filters['prod'])
        where_clause += f" AND producto_agrupado IN ('{vals}')"
    if filters.get('orig'):
        vals = "', '".join(filters['orig'])
        where_clause += f" AND PR_Origen_Limpio IN ('{vals}')"

    # Construcción de la consulta SQL
    cols_sql = f"strftime({col_fecha}, '%Y-%m') as Cosecha, sum({pref_den}1) as 'Capital Inicial'"
    for i in range(1, 25):
        cols_sql += f", sum({pref_num}{i}) / NULLIF(sum({pref_den}{i}), 0) as 'Mes {i}'"
    
    query = f"SELECT {cols_sql} FROM '{FILE_PATH}' {where_clause} GROUP BY 1 ORDER BY 1"
    return duckdb.query(query).df().set_index('Cosecha')

# --- LÓGICA PRINCIPAL ---
try:
    if os.path.exists(FILE_PATH):
        # --- SIDEBAR: LOS 3 FILTROS ---
        st.sidebar.header("Filtros Globales")
        f_suc = st.sidebar.multiselect("Sucursal", get_filter_options("nombre_sucursal"))
        f_prod = st.sidebar.multiselect("Producto Agrupado", get_filter_options("producto_agrupado"))
        f_orig = st.sidebar.multiselect("Origen Limpio", get_filter_options("PR_Origen_Limpio"))
        
        filtros = {'suc': f_suc, 'prod': f_prod, 'orig': f_orig}

        # --- TABS: LAS 3 PESTAÑAS ---
        tab1, tab2, tab3 = st.tabs(["📋 Vintage", "📈 Tendencias", "📍 Detalle Global"])

        with tab1:
            st.title("Análisis Vintage (Carga Optimizada DuckDB)")
            
            # Bloque UEN: PR
            m_pr = get_vintage_matrix_duckdb('saldo_capital_total_c', 'capital_c', 'PR', filtros)
            if not m_pr.empty:
                st.subheader("📊 UEN: PR (Vintage 30-150)")
                st.dataframe(
                    m_pr.style.format({"Capital Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in m_pr.columns if 'Mes' in c}, na_rep="")
                    .background_gradient(cmap='RdYlGn_r', axis=None, subset=[c for c in m_pr.columns if 'Mes' in c]),
                    use_container_width=True
                )

            st.divider()
            # Bloque UEN: SOLIDAR
            m_sol = get_vintage_matrix_duckdb('saldo_capital_total_890_c', 'capital_c', 'SOLIDAR', filtros)
            if not m_sol.empty:
                st.subheader("📊 UEN: SOLIDAR (Vintage 8-90)")
                st.dataframe(
                    m_sol.style.format({"Capital Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in m_sol.columns if 'Mes' in c}, na_rep="")
                    .background_gradient(cmap='RdYlGn_r', axis=None, subset=[c for c in m_sol.columns if 'Mes' in c]),
                    use_container_width=True
                )

        with tab2:
            st.title("Top 5 Productos Críticos")
            # Consultas SQL para los gráficos con corrección de tipos
            q_pr = f"SELECT producto_agrupado, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY 2 DESC LIMIT 5"
            q_sol = f"SELECT producto_agrupado, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1 ORDER BY 2 DESC LIMIT 5"
            
            c1, c2 = st.columns(2)
            with c1:
                df_top_pr = duckdb.query(q_pr).df()
                st.plotly_chart(px.bar(df_top_pr, x='Ratio', y='producto_agrupado', orientation='h', title="Top 5 Riesgo PR", color='Ratio', color_continuous_scale='Reds').update_layout(xaxis_tickformat='.1%', yaxis={'categoryorder':'total ascending'}))
            with c2:
                df_top_sol = duckdb.query(q_sol).df()
                st.plotly_chart(px.bar(df_top_sol, x='Ratio', y='producto_agrupado', orientation='h', title="Top 5 Riesgo SOLIDAR", color='Ratio', color_continuous_scale='Reds').update_layout(xaxis_tickformat='.1%', yaxis={'categoryorder':'total ascending'}))

        with tab3:
            st.title("📍 Desempeño Sucursales")
            st.info("💡 Top 10 sucursales con mayor ratio de riesgo acumulado.")
            q_suc_pr = f"SELECT nombre_sucursal, sum(saldo_capital_total_c2)/NULLIF(sum(capital_c2), 0) as 'Ratio C2' FROM '{FILE_PATH}' WHERE uen='PR' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
            q_suc_sol = f"SELECT nombre_sucursal, sum(saldo_capital_total_890_c1)/NULLIF(sum(capital_c1), 0) as 'Ratio C1' FROM '{FILE_PATH}' WHERE uen='SOLIDAR' GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
            
            cx, cy = st.columns(2)
            with cx:
                st.write("**Top 10 Sucursales PR**")
                st.table(duckdb.query(q_suc_pr).df().set_index('nombre_sucursal').style.format("{:.2%}"))
            with cy:
                st.write("**Top 10 Sucursales SOLIDAR**")
                st.table(duckdb.query(q_suc_sol).df().set_index('nombre_sucursal').style.format("{:.2%}"))

    else:
        st.error(f"No se encuentra el archivo '{FILE_PATH}' en el repositorio.")

except Exception as e:
    st.error(f"Error técnico detectado: {e}")

st.caption("Procesamiento Analítico vía DuckDB Engine | Usuario: Michel Ovalle")