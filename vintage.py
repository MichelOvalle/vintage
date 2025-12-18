import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta
import numpy as np
import plotly.express as px

# 1. Configuración de la página
st.set_page_config(page_title="Reporte Vintage Pro", layout="wide")

# CSS para forzar fondo blanco y texto negro
st.markdown("""
    <style>
    .main { background-color: #FFFFFF; }
    .stDataFrame { background-color: #FFFFFF; }
    [data-testid="stTable"] td, [data-testid="stTable"] th { color: black !important; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data
def load_data():
    df = pd.read_parquet("vintage_acum.parquet")
    if 'mes_apertura' in df.columns:
        df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
    return df

def calcular_matriz_datos(df, fecha_max, prefijo_num, prefijo_den):
    if df.empty: return None, None
    
    df_capital_total = df.groupby('mes_apertura_str')['capital_c1'].sum()
    df_capital_total.name = "Capital Total"

    results = []
    for i in range(25):
        col_num = f'{prefijo_num}{i+1}'
        col_den = f'{prefijo_den}{i+1}'
        fecha_columna = fecha_max - relativedelta(months=i)
        nombre_col_real = fecha_columna.strftime('%Y-%m')
        if col_num in df.columns and col_den in df.columns:
            temp = df.groupby('mes_apertura_str').apply(
                lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() > 0 else np.nan
            )
            temp.name = nombre_col_real
            results.append(temp)

    if not results: return None, None
    matriz_ratios = pd.concat(results, axis=1).sort_index(ascending=True)
    cols_ordenadas = sorted(matriz_ratios.columns, reverse=True)
    matriz_ratios = matriz_ratios.reindex(columns=cols_ordenadas)
    return matriz_ratios, df_capital_total

def renderizar_estilo(matriz_ratios, df_capital_total):
    matriz_final = pd.concat([df_capital_total, matriz_ratios], axis=1)
    stats = pd.DataFrame({
        'Promedio': matriz_ratios.mean(axis=0),
        'Máximo': matriz_ratios.max(axis=0),
        'Mínimo': matriz_ratios.min(axis=0)
    }).T 
    matriz_con_stats = pd.concat([matriz_con_stats := matriz_final, stats]).replace({np.nan: None})
    idx = pd.IndexSlice
    formatos = {col: "{:.2%}" for col in matriz_ratios.columns}
    formatos["Capital Total"] = "${:,.0f}"
    return (
        matriz_con_stats.style
        .format(formatos, na_rep="") 
        .background_gradient(cmap='RdYlGn_r', axis=None, subset=idx[matriz_ratios.index, matriz_ratios.columns]) 
        .highlight_null(color='white')
        .set_properties(**{'color': 'black', 'border': '1px solid #D3D3D3'})
        .set_properties(subset=idx[['Promedio', 'Máximo', 'Mínimo'], :], **{'font-weight': 'bold'})
        .set_properties(subset=idx[:, 'Capital Total'], **{'font-weight': 'bold', 'background-color': '#f0f2f6'})
    )

try:
    df_raw = load_data()
    
    # --- SIDEBAR ---
    st.sidebar.header("Filtros Globales")
    def crear_filtro(label, col_name):
        options = sorted(df_raw[col_name].dropna().unique())
        return st.sidebar.multiselect(label, options)

    f_sucursal = crear_filtro("Sucursal", "nombre_sucursal")
    f_producto = crear_filtro("Producto Agrupado", "producto_agrupado")
    f_origen = crear_filtro("Origen Limpio", "PR_Origen_Limpio")

    df_base = df_raw.copy()
    if f_sucursal: df_base = df_base[df_base['nombre_sucursal'].isin(f_sucursal)]
    if f_producto: df_base = df_base[df_base['producto_agrupado'].isin(f_producto)]
    if f_origen: df_base = df_base[df_base['PR_Origen_Limpio'].isin(f_origen)]

    fecha_max = df_raw['mes_apertura'].max()
    fecha_inicio_filas = fecha_max - pd.DateOffset(months=24)
    df_base = df_base[df_base['mes_apertura'] >= fecha_inicio_filas].copy()
    df_base['mes_apertura_str'] = df_base['mes_apertura'].dt.strftime('%Y-%m')

    # --- TABS ---
    tab1, tab2 = st.tabs(["📋 Matrices Vintage", "📈 Análisis de Tendencias"])

    with tab1:
        # Lógica de matrices (PR y SOLIDAR)
        df_pr = df_base[df_base['uen'] == 'PR']
        m_ratios_pr, m_cap_pr = calcular_matriz_datos(df_pr, fecha_max, 'saldo_capital_total_c', 'capital_c')
        if m_ratios_pr is not None:
            st.subheader("📊 Vintage 30 - 150 (UEN: PR)")
            st.dataframe(renderizar_estilo(m_ratios_pr, m_cap_pr), use_container_width=True)
        
        st.divider()

        df_solidar = df_base[df_base['uen'] == 'SOLIDAR']
        m_ratios_sol, m_cap_sol = calcular_matriz_datos(df_solidar, fecha_max, 'saldo_capital_total_890_c', 'capital_c')
        if m_ratios_sol is not None:
            st.subheader("📊 Vintage 8 - 90 (UEN: SOLIDAR)")
            st.dataframe(renderizar_estilo(m_ratios_sol, m_cap_sol), use_container_width=True)

    with tab2:
        st.title("Estado Actual de la Cartera")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            if m_ratios_pr is not None:
                # Tomamos la columna más reciente (el dato de hoy) para cada cosecha
                ultima_col = m_ratios_pr.columns[0] 
                df_hoy_pr = m_ratios_pr[ultima_col].reset_index()
                df_hoy_pr.columns = ['Cosecha', 'Ratio']
                
                fig_pr = px.line(df_hoy_pr, x='Cosecha', y='Ratio', 
                                title=f"Ratio Actual por Cosecha (PR) - Corte {ultima_col}",
                                markers=True, color_discrete_sequence=['red'])
                fig_pr.update_layout(yaxis_tickformat='.1%')
                st.plotly_chart(fig_pr, use_container_width=True)

        with col_b:
            if m_ratios_sol is not None:
                ultima_col_sol = m_ratios_sol.columns[0]
                df_hoy_sol = m_ratios_sol[ultima_col_sol].reset_index()
                df_hoy_sol.columns = ['Cosecha', 'Ratio']
                
                fig_sol = px.line(df_hoy_sol, x='Cosecha', y='Ratio', 
                                 title=f"Ratio Actual por Cosecha (SOLIDAR) - Corte {ultima_col_sol}",
                                 markers=True, color_discrete_sequence=['blue'])
                fig_sol.update_layout(yaxis_tickformat='.1%')
                st.plotly_chart(fig_sol, use_container_width=True)

        # Gráfico de barras de Capital Total combinado
        st.subheader("Originación de Capital por UEN")
        df_vol = pd.DataFrame({
            'PR': m_cap_pr if m_cap_pr is not None else 0,
            'SOLIDAR': m_cap_sol if m_cap_sol is not None else 0
        }).fillna(0).reset_index()
        
        fig_vol = px.bar(df_vol, x='mes_apertura_str', y=['PR', 'SOLIDAR'], 
                        title="Comparativo de Capital Otorgado", barmode='group')
        st.plotly_chart(fig_vol, use_container_width=True)

    st.caption(f"Referencia: Fecha de corte máxima {fecha_max.strftime('%Y-%m')}.")

except Exception as e:
    st.error(f"Error técnico: {e}")