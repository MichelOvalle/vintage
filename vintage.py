import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from statsmodels.tsa.holtwinters import SimpleExpSmoothing

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
    if df.empty: return None, None, None
    df_capital_total = df.groupby('mes_apertura_str')['capital_c1'].sum()
    df_capital_total.name = "Capital Total"

    results_graf, results_tabla = [], []
    for i in range(25):
        col_num, col_den = f'{prefijo_num}{i+1}', f'{prefijo_den}{i+1}'
        nombre_col = f"Mes {i+1}"
        fecha_columna = fecha_max - relativedelta(months=i)
        nombre_col_real = fecha_columna.strftime('%Y-%m')

        if col_num in df.columns and col_den in df.columns:
            temp = df.groupby('mes_apertura_str').apply(
                lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() > 0 else np.nan
            )
            temp_graf = temp.copy(); temp_graf.name = nombre_col; results_graf.append(temp_graf)
            temp_tab = temp.copy(); temp_tab.name = nombre_col_real; results_tabla.append(temp_tab)

    if not results_graf: return None, None, None
    matriz_ratios_grafico = pd.concat(results_graf, axis=1).sort_index(ascending=True)
    matriz_ratios_tabla = pd.concat(results_tabla, axis=1).sort_index(ascending=True)
    matriz_ratios_tabla = matriz_ratios_tabla.reindex(columns=sorted(matriz_ratios_tabla.columns, reverse=True))
    return matriz_ratios_tabla, df_capital_total, matriz_ratios_grafico

def renderizar_estilo(matriz_ratios, df_capital_total):
    matriz_final = pd.concat([df_capital_total, matriz_ratios], axis=1)
    stats = pd.DataFrame({'Promedio': matriz_ratios.mean(axis=0), 'Máximo': matriz_ratios.max(axis=0), 'Mínimo': matriz_ratios.min(axis=0)}).T 
    matriz_con_stats = pd.concat([matriz_final, stats]).replace({np.nan: None})
    idx = pd.IndexSlice
    formatos = {col: "{:.2%}" for col in matriz_ratios.columns}; formatos["Capital Total"] = "${:,.0f}"
    return (matriz_con_stats.style.format(formatos, na_rep="") 
            .background_gradient(cmap='RdYlGn_r', axis=None, subset=idx[matriz_ratios.index, matriz_ratios.columns]) 
            .set_properties(**{'color': 'black', 'border': '1px solid #D3D3D3'}))

def crear_grafico_tendencia_con_pronostico(df, prefijo_num, prefijo_den, cohorte_n, titulo, color_linea):
    if df.empty: return None
    col_num, col_den = f'{prefijo_num}{cohorte_n}', f'{prefijo_den}{cohorte_n}'
    
    if col_num in df.columns and col_den in df.columns:
        df_tend = df.groupby('mes_apertura_str').apply(
            lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() > 0 else np.nan
        ).dropna()
        
        if len(df_tend) < 3: return None
        
        # Pronóstico Simple Exponential Smoothing
        model = SimpleExpSmoothing(df_tend.values, initialization_method="estimated").fit()
        forecast = model.forecast(1)[0]
        
        # Preparar datos para Plotly
        index_actual = list(df_tend.index)
        ultimo_mes = pd.to_datetime(index_actual[-1])
        siguiente_mes = (ultimo_mes + relativedelta(months=1)).strftime('%Y-%m')
        
        fig = go.Figure()
        # Línea Histórica
        fig.add_trace(go.Scatter(x=index_actual, y=df_tend.values, mode='lines+markers', name='Histórico', line=dict(color=color_linea, width=3)))
        # Punto de Pronóstico
        fig.add_trace(go.Scatter(x=[index_actual[-1], siguiente_mes], y=[df_tend.values[-1], forecast], 
                                 mode='lines+markers', name='Pronóstico', line=dict(color='gray', dash='dash')))
        
        fig.update_layout(title=f"{titulo} (Pronóstico: {forecast:.2%})", plot_bgcolor='white', yaxis_tickformat='.1%', xaxis={'type': 'category'})
        fig.update_xaxes(showgrid=True, gridcolor='#f0f0f0', tickangle=-45); fig.update_yaxes(showgrid=True, gridcolor='#f0f0f0')
        return fig
    return None

try:
    df_raw = load_data()
    st.sidebar.header("Filtros Globales")
    f_sucursal = st.sidebar.multiselect("Sucursal", sorted(df_raw['nombre_sucursal'].dropna().unique()))
    f_producto = st.sidebar.multiselect("Producto Agrupado", sorted(df_raw['producto_agrupado'].dropna().unique()))
    f_origen = st.sidebar.multiselect("Origen Limpio", sorted(df_raw['PR_Origen_Limpio'].dropna().unique()))

    df_base = df_raw.copy()
    if f_sucursal: df_base = df_base[df_base['nombre_sucursal'].isin(f_sucursal)]
    if f_producto: df_base = df_base[df_base['producto_agrupado'].isin(f_producto)]
    if f_origen: df_base = df_base[df_base['PR_Origen_Limpio'].isin(f_origen)]

    fecha_max = df_raw['mes_apertura'].max()
    df_24 = df_base[df_base['mes_apertura'] >= (fecha_max - pd.DateOffset(months=24))].copy()
    df_24['mes_apertura_str'] = df_24['mes_apertura'].dt.strftime('%Y-%m')

    tab1, tab2 = st.tabs(["📋 Matrices Vintage", "📈 Análisis Detallado y Pronóstico"])

    df_pr = df_24[df_24['uen'] == 'PR']; df_solidar = df_24[df_24['uen'] == 'SOLIDAR']

    with tab1:
        st.title("Matrices Vintage (24m)")
        m_tabla_pr, m_cap_pr, m_graf_pr = calcular_matriz_datos(df_pr, fecha_max, 'saldo_capital_total_c', 'capital_c')
        if m_tabla_pr is not None:
            st.subheader("📊 Vintage 30 - 150 (PR)"); st.dataframe(renderizar_estilo(m_tabla_pr, m_cap_pr), use_container_width=True)
        m_tabla_sol, m_cap_sol, m_graf_sol = calcular_matriz_datos(df_solidar, fecha_max, 'saldo_capital_total_890_c', 'capital_c')
        if m_tabla_sol is not None:
            st.subheader("📊 Vintage 8 - 90 (SOLIDAR)"); st.dataframe(renderizar_estilo(m_tabla_sol, m_cap_sol), use_container_width=True)

    with tab2:
        st.title("Tendencias Tempranas y Proyecciones")
        col1, col2 = st.columns(2)
        with col1:
            # PR usa C2
            fig_pr = crear_grafico_tendencia_con_pronostico(df_pr, 'saldo_capital_total_c', 'capital_c', 2, "Tendencia C2 - PR", "#1f77b4")
            if fig_pr: st.plotly_chart(fig_pr, use_container_width=True)
        with col2:
            # SOLIDAR usa C1 solicitado
            fig_sol = crear_grafico_tendencia_con_pronostico(df_solidar, 'saldo_capital_total_890_c', 'capital_c', 1, "Tendencia C1 - SOLIDAR", "#d62728")
            if fig_sol: st.plotly_chart(fig_sol, use_container_width=True)

        st.divider()
        st.subheader("Exposición por Origen Limpio (PR)")
        if not df_pr.empty:
            df_stack = df_pr.groupby(['mes_apertura_str', 'PR_Origen_Limpio'])['saldo_capital_total'].sum().reset_index()
            fig_stack = px.bar(df_stack, x='mes_apertura_str', y='saldo_capital_total', color='PR_Origen_Limpio', 
                               color_discrete_map={'Fisico': '#005b7f', 'Digital': '#f37021'}, text_auto='.2s')
            fig_stack.update_layout(barmode='stack', plot_bgcolor='white', xaxis={'type': 'category'})
            st.plotly_chart(fig_stack, use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")