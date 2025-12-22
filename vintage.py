import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import os

# 1. Configuración de página
st.set_page_config(page_title="Análisis Vintage Pro", layout="wide")

@st.cache_data(ttl=3600)
def load_data():
    file_path = "vintage_acum.parquet"
    if not os.path.exists(file_path):
        st.error(f"Archivo no encontrado: {file_path}")
        return pd.DataFrame()
    try:
        df = pd.read_parquet(file_path, engine='pyarrow')
        if 'mes_apertura' in df.columns:
            df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
            df['mes_apertura_str'] = df['mes_apertura'].dt.strftime('%Y-%m')
        return df
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame()

def calcular_matriz_optimizada(df, pref_num, pref_den):
    if df.empty: return None, None
    cols_num = [f"{pref_num}{i+1}" for i in range(25) if f"{pref_num}{i+1}" in df.columns]
    cols_den = [f"{pref_den}{i+1}" for i in range(25) if f"{pref_den}{i+1}" in df.columns]
    
    agrupado = df.groupby('mes_apertura_str').agg({**{c: 'sum' for c in cols_num}, **{c: 'sum' for c in cols_den}})
    matriz = pd.DataFrame(index=agrupado.index)
    for i in range(len(cols_num)):
        matriz[f"Mes {i+1}"] = agrupado[cols_num[i]] / agrupado[cols_den[i]]
    
    cap_inicial = df.groupby('mes_apertura_str')['capital_c1'].sum()
    return matriz.sort_index(), cap_inicial

def renderizar_estilo(matriz, cap_inicial):
    matriz_final = pd.concat([cap_inicial.rename("Capital Inicial"), matriz], axis=1)
    formatos = {col: "{:.2%}" for col in matriz.columns}
    formatos["Capital Inicial"] = "${:,.0f}"
    
    return matriz_final.style.format(formatos, na_rep="")\
        .background_gradient(cmap='RdYlGn_r', axis=None, subset=matriz.columns)\
        .set_properties(**{'color': 'black', 'border': '1px solid #D3D3D3'})

try:
    df_raw = load_data()
    if not df_raw.empty:
        # --- SIDEBAR ---
        st.sidebar.header("Filtros Globales")
        sucursales = sorted([str(x) for x in df_raw['nombre_sucursal'].unique() if pd.notna(x)])
        f_suc = st.sidebar.multiselect("Seleccionar Sucursal", sucursales)
        
        df_f = df_raw.copy()
        if f_suc: df_f = df_f[df_f['nombre_sucursal'].isin(f_suc)]

        # --- TABS ---
        t1, t2 = st.tabs(["📋 Vintage", "📈 Top 5 Riesgo"])

        with t1:
            st.title("Análisis Vintage (24 meses)")
            # PR
            df_pr = df_f[df_f['uen'] == 'PR']
            m_pr, c_pr = calcular_matriz_optimizada(df_pr, 'saldo_capital_total_c', 'capital_c')
            if m_pr is not None:
                st.subheader("📊 UEN: PR (Ratio 30-150)")
                st.dataframe(renderizar_estilo(m_pr, c_pr), use_container_width=True)
            
            st.divider()
            # SOLIDAR
            df_sol = df_f[df_f['uen'] == 'SOLIDAR']
            m_sol, c_sol = calcular_matriz_optimizada(df_sol, 'saldo_capital_total_890_c', 'capital_c')
            if m_sol is not None:
                st.subheader("📊 UEN: SOLIDAR (Ratio 8-90)")
                st.dataframe(renderizar_estilo(m_sol, c_sol), use_container_width=True)

        with t2:
            st.title("🏆 Top 5 Productos por Riesgo")
            col_a, col_b = st.columns(2)
            with col_a:
                if not df_pr.empty:
                    r = df_pr.groupby('producto_agrupado').agg({'saldo_capital_total_c2': 'sum', 'capital_c2': 'sum'})
                    r['Ratio'] = r['saldo_capital_total_c2'] / r['capital_c2']
                    top = r.sort_values('Ratio', ascending=False).head(5).reset_index()
                    st.plotly_chart(px.bar(top, x='Ratio', y='producto_agrupado', orientation='h', title="Top 5 PR (C2)", color='Ratio', color_continuous_scale='Reds').update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat='.1%'), use_container_width=True)
            with col_b:
                if not df_sol.empty:
                    r2 = df_sol.groupby('producto_agrupado').agg({'saldo_capital_total_890_c1': 'sum', 'capital_c1': 'sum'})
                    r2['Ratio'] = r2['saldo_capital_total_890_c1'] / r2['capital_c1']
                    top2 = r2.sort_values('Ratio', ascending=False).head(5).reset_index()
                    st.plotly_chart(px.bar(top2, x='Ratio', y='producto_agrupado', orientation='h', title="Top 5 SOLIDAR (C1)", color='Ratio', color_continuous_scale='Reds').update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat='.1%'), use_container_width=True)

    st.caption(f"Referencia: Datos procesados para Michel Ovalle.")

except Exception as e:
    st.error(f"Error detectado: {e}")