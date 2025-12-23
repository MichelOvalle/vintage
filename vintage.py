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
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th { color: black !important; }
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
    """Añade estadísticas al final de forma robusta"""
    if df.empty: return df
    
    mes_cols = [c for c in df.columns if 'Mes ' in c]
    df[mes_cols] = df[mes_cols].apply(pd.to_numeric, errors='coerce')
    
    # Calculamos stats antes de concatenar para evitar errores de tipo
    stats_data = {
        'Mes originacion': ['Promedio', 'Máximo', 'Mínimo'],
        'Capital Inicial': [df['Capital Inicial'].mean(), np.nan, np.nan]
    }
    
    for col in mes_cols:
        stats_data[col] = [df[col].mean(), df[col].max(), df[col].min()]
    
    stats_df = pd.DataFrame(stats_data)
    return pd.concat([df, stats_df], ignore_index=True)

def get_vintage_matrix(pref_num, pref_den, uen, filtros):
    """Consulta y renombra columnas para asegurar que los títulos aparezcan"""
    where = f"WHERE uen = '{uen}' AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
    for key, col in [('suc', 'nombre_sucursal'), ('prod', 'producto_agrupado'), ('orig', 'PR_Origen_Limpio')]:
        clause = build_in_clause(filtros.get(key))
        if clause: where += f" AND {col} IN {clause}"
    
    cols = f"strftime({COL_FECHA}, '%Y-%m') as cosecha_val, sum({pref_den}1) as cap_val"
    for i in range(1, 25):
        cols += f", sum({pref_num}{i}) / NULLIF(sum({pref_den}{i}), 0) as 'Mes {i}'"
    
    df_raw = duckdb.query(f"SELECT {cols} FROM '{FILE_PATH}' {where} GROUP BY 1 ORDER BY 1").df()
    if df_raw.empty: return df_raw
    
    # Renombrado solicitado por Michel
    df_raw = df_raw.rename(columns={'cosecha_val': 'Mes originacion', 'cap_val': 'Capital Inicial'})
    return add_stats_to_df(df_raw)

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
                st.subheader(f"📊 {uen} ({tit})")
                m_v = get_vintage_matrix(p_num, p_den, uen, filtros)
                if not m_v.empty:
                    mes_cols = [c for c in m_v.columns if 'Mes ' in c]
                    # FIX CRÍTICO: Usamos el índice de filas para evitar el error de ambigüedad
                    idx_cosechas = m_v.index[:-3] 
                    
                    st.dataframe(
                        m_v.style.format({"Capital Inicial": "${:,.0f}"} | {c: "{:.2%}" for c in mes_cols}, na_rep="")
                        .background_gradient(cmap='RdYlGn_r', axis=None, subset=pd.IndexSlice[idx_cosechas, mes_cols])
                        .set_properties(**{'color': 'black'}, subset=m_v.columns)
                        .highlight_null(color='white'), 
                        use_container_width=True,
                        hide_index=True
                    )
                st.divider()

        with tab2:
            st.title("Análisis de Maduración y Comportamiento")
            # Maduración (18 meses)
            m_v_mad = get_vintage_matrix('saldo_capital_total_c', 'capital_c', 'PR', filtros)
            if not m_v_mad.empty:
                df_c = m_v_mad.iloc[:-3] 
                fig_m = go.Figure()
                for i, row in df_c.tail(18).iterrows():
                    cos = str(row['Mes originacion'])
                    fila = row.drop(['Mes originacion', 'Capital Inicial']).dropna()
                    fig_m.add_trace(go.Scatter(x=fila.index, y=fila.values, mode='lines+markers', name=cos))
                fig_m.update_layout(title="Maduración - PR (Últimas 18 Cosechas)", yaxis_tickformat='.1%', plot_bgcolor='white', 
                    xaxis_title="Meses de Maduración", yaxis_title="Ratio %",
                    legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5), margin=dict(b=100))
                st.plotly_chart(fig_m, use_container_width=True)
            
            # Evolución Vertical...
            st.divider()
            t_f = f"WHERE {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
            for uen, col_r, col_c, tit_u, line_c in [('PR', 'saldo_capital_total_c2', 'capital_c2', 'PR', 'blue'), 
                                                     ('SOLIDAR', 'saldo_capital_total_890_c1', 'capital_c1', 'SOLIDAR', 'red')]:
                q = f"SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum({col_r})/NULLIF(sum({col_c}),0) as Ratio FROM '{FILE_PATH}' {t_f} AND uen='{uen}' GROUP BY 1 ORDER BY 1"
                df_ev = duckdb.query(q).df()
                st.plotly_chart(px.line(df_ev, x='Cosecha', y='Ratio', title=f"Evolución Global - {tit_u}", markers=True, color_discrete_sequence=[line_c]).update_xaxes(type='category', tickangle=-45).update_layout(yaxis_tickformat='.2%', plot_bgcolor='white', margin=dict(l=60, r=40, b=80, t=60)), use_container_width=True)

        with tab3:
            st.title("📍 Detalle de Desempeño")
            # Matrices de Sucursal (Blindadas con color negro)
            c_mx1, c_mx2 = st.columns(2)
            for uen, col_r, col_c, col_obj in [('PR', 'saldo_capital_total_c2', 'capital_c2', c_mx1), ('SOLIDAR', 'saldo_capital_total_890_c1', 'capital_c1', c_mx2)]:
                with col_obj:
                    st.subheader(f"🔲 Sucursal vs Producto ({uen})")
                    q = f"SELECT COALESCE(nombre_sucursal, 'N/A') as Sucursal, COALESCE(producto_agrupado, 'N/A') as Producto, sum({col_r})/NULLIF(sum({col_c}), 0) as Ratio FROM '{FILE_PATH}' WHERE uen='{uen}' GROUP BY 1, 2"
                    df_m = duckdb.query(q).df()
                    if not df_m.empty:
                        df_p = df_m.pivot(index='Sucursal', columns='Producto', values='Ratio').fillna(0)
                        df_p.index.name, df_p.columns.name = "Sucursal", "Producto"
                        st.dataframe(df_p.style.format("{:.2%}").background_gradient(cmap='RdYlGn_r', axis=None).set_properties(**{'color': 'black'}), use_container_width=True)

except Exception as e:
    st.error(f"Error técnico detectado: {e}")

st.caption("Dashboard Vintage Pro v46.0 | Michel Ovalle | Engine: DuckDB")