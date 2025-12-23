import streamlit as st
import pandas as pd
import numpy as np
import duckdb
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta

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

def add_stats_to_df(df, columns):
    if df.empty: return df
    df[columns] = df[columns].apply(pd.to_numeric, errors='coerce')
    stats = pd.DataFrame(index=['Promedio', 'Máximo', 'Mínimo'], columns=df.columns)
    for col in columns:
        stats.at['Promedio', col] = df[col].mean()
        stats.at['Máximo', col] = df[col].max()
        stats.at['Mínimo', col] = df[col].min()
    stats.at['Promedio', 'Capital inicial'] = df['Capital inicial'].mean()
    return pd.concat([df, stats])

def get_calendar_vintage(pref_num, pref_den, uen, filtros):
    # 1. Obtener la fecha máxima para los encabezados
    max_date_str = duckdb.query(f"SELECT max({COL_FECHA}) FROM '{FILE_PATH}'").fetchall()[0][0]
    max_date = pd.to_datetime(max_date_str)
    
    # Generar nombres de columnas (dic-25, nov-25...)
    headers = []
    for i in range(24):
        d = max_date - relativedelta(months=i)
        headers.append(d.strftime('%b-%y').lower())

    # 2. Consulta base (Vintage tradicional)
    where = f"WHERE uen = '{uen}' AND {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
    for key, col in [('suc', 'nombre_sucursal'), ('prod', 'producto_agrupado'), ('orig', 'PR_Origen_Limpio')]:
        clause = build_in_clause(filtros.get(key))
        if clause: where += f" AND {col} IN {clause}"
    
    cols_query = f"strftime({COL_FECHA}, '%Y-%m') as 'Mes Originacion', sum({pref_den}1) as 'Capital inicial'"
    for i in range(1, 26): # Pedimos un poco más por si acaso
        cols_query += f", sum({pref_num}{i}) / NULLIF(sum({pref_den}{i}), 0) as 'm{i}'"
    
    df_raw = duckdb.query(f"SELECT {cols_query} FROM '{FILE_PATH}' {where} GROUP BY 1 ORDER BY 1").df()
    
    if df_raw.empty: return pd.DataFrame()

    # 3. Transformación a "Mes Cierre Calendario"
    # Michel: Aquí alineamos el Mes 1, 2, 3 al encabezado dic-25, nov-25...
    rows = []
    for _, row in df_raw.iterrows():
        orig_date = pd.to_datetime(row['Mes Originacion'] + "-01")
        new_row = {'Mes Originacion': row['Mes Originacion'], 'Capital inicial': row['Capital inicial']}
        
        for i, h_text in enumerate(headers):
            # Calculamos cuántos meses han pasado desde la originación hasta ese encabezado
            target_date = max_date - relativedelta(months=i)
            diff_months = (target_date.year - orig_date.year) * 12 + (target_date.month - orig_date.month) + 1
            
            if 1 <= diff_months <= 24:
                new_row[h_text] = row[f'm{diff_months}']
            else:
                new_row[h_text] = np.nan
        rows.append(new_row)

    df_final = pd.DataFrame(rows).set_index('Mes Originacion')
    return add_stats_to_df(df_final, headers), headers

# --- DASHBOARD ---
try:
    if os.path.exists(FILE_PATH):
        st.sidebar.header("Filtros Globales")
        filtros = {'suc': st.sidebar.multiselect("Sucursal", get_filter_options("nombre_sucursal")),
                   'prod': st.sidebar.multiselect("Producto Agrupado", get_filter_options("producto_agrupado")),
                   'orig': st.sidebar.multiselect("Origen Limpio", get_filter_options("PR_Origen_Limpio"))}

        tab1, tab2, tab3 = st.tabs(["📋 Vintage", "📈 Curvas y Tendencias", "📍 Detalle de Desempeño"])

        with tab1:
            st.title("Reporte de Ratios por Mes de Cierre (Calendario)")
            for uen, p_num, p_den, tit in [('PR', 'saldo_capital_total_c', 'capital_c', 'Ratio 30-150'), 
                                           ('SOLIDAR', 'saldo_capital_total_890_c', 'capital_c', 'Ratio 8-90')]:
                st.subheader(f"📊 {uen} ({tit})")
                m_v, headers = get_calendar_vintage(p_num, p_den, uen, filtros)
                if not m_v.empty:
                    st.dataframe(
                        m_v.style.format({"Capital inicial": "${:,.0f}"} | {c: "{:.2%}" for c in headers}, na_rep="")
                        .background_gradient(cmap='RdYlGn_r', axis=None, subset=(m_v.index[:-3], headers))
                        .set_properties(**{'color': 'black'}, subset=headers)
                        .highlight_null(color='white'), use_container_width=True
                    )
                st.divider()

        with tab2:
            st.title("Análisis de Maduración y Comportamiento")
            # Michel: Las gráficas de tendencia siguen usando la lógica de 24 meses verticales
            t_f = f"WHERE {COL_FECHA} >= (SELECT max({COL_FECHA}) - INTERVAL 24 MONTH FROM '{FILE_PATH}')"
            
            # 1. Curvas de Maduración PR (18 meses)
            # Reutilizamos la consulta base para la maduración
            m_v_raw = get_vintage_matrix('saldo_capital_total_c', 'capital_c', 'PR', filtros)
            if not m_v_raw.empty:
                df_c = m_v_raw.iloc[:-3]
                fig_m = go.Figure()
                for cos in df_c.tail(18).index:
                    fila = df_c.loc[cos].drop('Cap_Inicial').dropna()
                    fig_m.add_trace(go.Scatter(x=fila.index, y=fila.values, mode='lines+markers', name=cos))
                fig_m.update_layout(title="Maduración - PR (Últimas 18 Cosechas)", yaxis_tickformat='.1%', plot_bgcolor='white', 
                                    xaxis_title="Meses de Maduración", yaxis_title="Ratio %",
                                    legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5), margin=dict(b=100))
                st.plotly_chart(fig_m, use_container_width=True)

            # Resto de gráficas de evolución vertical...
            for uen, col_r, col_c, tit_u, line_c in [('PR', 'saldo_capital_total_c2', 'capital_c2', 'PR', 'blue'), ('SOLIDAR', 'saldo_capital_total_890_c1', 'capital_c1', 'SOLIDAR', 'red')]:
                q = f"SELECT strftime({COL_FECHA}, '%Y-%m') as Cosecha, sum({col_r})/NULLIF(sum({col_c}),0) as Ratio FROM '{FILE_PATH}' {t_f} AND uen='{uen}' GROUP BY 1 ORDER BY 1"
                df_e = duckdb.query(q).df()
                fig_e = px.line(df_e, x='Cosecha', y='Ratio', title=f"Evolución Global - {tit_u}", markers=True, color_discrete_sequence=[line_c])
                fig_e.update_xaxes(type='category', tickangle=-45)
                fig_e.update_layout(yaxis_tickformat='.2%', plot_bgcolor='white', margin=dict(l=60, r=40, b=80, t=60))
                st.plotly_chart(fig_e, use_container_width=True)

        with tab3:
            st.title("📍 Detalle de Desempeño")
            # Narrativas y Matrices de Sucursal (Sin cambios de lógica, solo visuales)
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

st.caption("Dashboard Vintage Pro v42.0 | Michel Ovalle | Engine: DuckDB")