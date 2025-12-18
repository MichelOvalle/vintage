import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from statsmodels.tsa.holtwinters import SimpleExpSmoothing

# 1. Configuración de la página
st.set_page_config(page_title="Reporte Vintage Pro", layout="wide")

# CSS DEFINITIVO Y AGRESIVO
# Inyectamos el estilo directamente en el cuerpo del documento para forzar el renderizado
st.markdown("""
    <style>
    /* 1. Fondo general blanco */
    .main { background-color: #FFFFFF !important; }
    
    /* 2. Forzar texto negro en TODAS las celdas de datos, encabezados y divs internos */
    [data-testid="stDataFrame"] div[role="gridcell"] *, 
    [data-testid="stDataFrame"] div[role="columnheader"] *,
    [data-testid="stDataFrame"] span,
    [data-testid="stDataFrame"] div {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        font-weight: 800 !important;
    }

    /* 3. Asegurar que las celdas vacías sean blancas y no negras */
    [data-testid="stDataFrame"] div[role="gridcell"]:empty,
    [data-testid="stDataFrame"] td:empty {
        background-color: white !important;
    }

    header {visibility: hidden;}
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
        col_num, col_den = f'{prefijo_num}{i+1}' , f'{prefijo_den}{i+1}'
        nombre_col = f"Mes {i+1}"
        fecha_columna = fecha_max - relativedelta(months=i)
        nombre_col_real = fecha_columna.strftime('%Y-%m')

        if col_num in df.columns and col_den in df.columns:
            temp = df.groupby('mes_apertura_str').apply(
                lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() > 0 else np.nan
            )
            t_graf = temp.copy(); t_graf.name = nombre_col; results_graf.append(t_graf)
            t_tab = temp.copy(); t_tab.name = nombre_col_real; results_tabla.append(t_tab)

    if not results_graf: return None, None, None
    m_graf = pd.concat(results_graf, axis=1).sort_index(ascending=True)
    m_tab = pd.concat(results_tabla, axis=1).sort_index(ascending=True)
    m_tab = m_tab.reindex(columns=sorted(m_tab.columns, reverse=True))
    return m_tab, df_capital_total, m_graf

def renderizar_estilo(matriz_ratios, df_capital_total):
    matriz_final = pd.concat([df_capital_total, matriz_ratios], axis=1)
    stats = pd.DataFrame({
        'Promedio': matriz_ratios.mean(axis=0), 
        'Máximo': matriz_ratios.max(axis=0), 
        'Mínimo': matriz_ratios.min(axis=0)
    }).T 
    matriz_con_stats = pd.concat([matriz_final, stats])
    
    idx = pd.IndexSlice
    cols_ratios = matriz_ratios.columns
    
    # Aplicar formato de números ANTES que cualquier estilo visual
    styler = matriz_con_stats.style.format(
        {col: "{:.2%}" for col in cols_ratios}, na_rep=""
    ).format(
        {"Capital Total": "${:,.0f}"}, na_rep=""
    )
    
    # Propiedades base obligatorias
    styler = styler.set_properties(**{
        'color': 'black',
        'font-weight': 'bold',
        'border': '1px solid #D3D3D3'
    })
    
    # Heatmap (Verde para bajo riesgo, Rojo para alto riesgo)
    styler = styler.background_gradient(
        cmap='RdYlGn_r', 
        axis=None, 
        subset=idx[matriz_ratios.index, cols_ratios]
    )
    
    # Limpiar nulos para evitar el fondo negro
    styler = styler.highlight_null(color='white')
    
    return styler

def crear_grafico_tendencia_con_pronostico(df, prefijo_num, prefijo_den, cohorte_n, titulo, color_linea):
    if df.empty: return None
    col_num, col_den = f'{prefijo_num}{cohorte_n}', f'{prefijo_den}{cohorte_n}'
    
    if col_num in df.columns and col_den in df.columns:
        df_tend = df.groupby('mes_apertura_str').apply(
            lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() > 0 else np.nan
        ).dropna()
        
        if len(df_tend) < 3: return None
        
        try:
            model = SimpleExpSmoothing(df_tend.values, initialization_method="estimated").fit()
            forecast = model.forecast(1)[0]
        except:
            forecast = df_tend.tail(3).mean()
        
        idx_act = list(df_tend.index)
        sig_mes = (pd.to_datetime(idx_act[-1]) + relativedelta(months=1)).strftime('%Y-%m')
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=idx_act, y=df_tend.values, mode='lines+markers', name='Real', line=dict(color=color_linea, width=3)))
        fig.add_trace(go.Scatter(x=[idx_act[-1], sig_mes], y=[df_tend.values[-1], forecast], 
                                 mode='lines+markers', name='Pronóstico', line=dict(color='gray', dash='dash')))
        fig.update_layout(title=f"{titulo} (Proyección: {forecast:.2%})", plot_bgcolor='white', yaxis_tickformat='.1%', xaxis={'type': 'category'})
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
    df_base['mes_apertura_str'] = df_base['mes_apertura'].dt.strftime('%Y-%m')
    df_filt = df_base[df_base['mes_apertura'] >= (fecha_max - pd.DateOffset(months=24))].copy()

    tab1, tab2 = st.tabs(["📋 Matrices Vintage", "📈 Análisis de Tendencias"])

    df_pr = df_filt[df_filt['uen'] == 'PR']
    df_sol = df_filt[df_filt['uen'] == 'SOLIDAR']

    with tab1:
        st.title("Matrices Vintage (24 meses)")
        m_t_pr, m_c_pr, m_g_pr = calcular_matriz_datos(df_pr, fecha_max, 'saldo_capital_total_c', 'capital_c')
        if m_t_pr is not None:
            st.subheader("Vintage 30 - 150 (PR)")
            # Mostramos la tabla
            st.dataframe(renderizar_estilo(m_t_pr, m_c_pr), use_container_width=True)
        
        st.divider()
        
        m_t_sol, m_c_sol, m_g_sol = calcular_matriz_datos(df_sol, fecha_max, 'saldo_capital_total_890_c', 'capital_c')
        if m_t_sol is not None:
            st.subheader("Vintage 8 - 90 (SOLIDAR)")
            st.dataframe(renderizar_estilo(m_t_sol, m_c_sol), use_container_width=True)

    with tab2:
        st.title("Análisis Predictivo y Exposición")
        
        if m_g_pr is not None:
            m_12 = m_g_pr.tail(12)
            fig_m = go.Figure()
            for cos in m_12.index:
                f = m_12.loc[cos].dropna()
                fig_m.add_trace(go.Scatter(x=f.index, y=f.values, mode='lines+markers', name=cos))
            fig_m.update_layout(title="Curvas de Maduración (Últ. 12m) - PR", yaxis_tickformat='.1%', plot_bgcolor='white')
            st.plotly_chart(fig_m, use_container_width=True)

        st.divider()

        c1, c2 = st.columns(2)
        with c1:
            f_pr = crear_grafico_tendencia_con_pronostico(df_pr, 'saldo_capital_total_c', 'capital_c', 2, "Tendencia C2 - PR", "#1f77b4")
            if f_pr: st.plotly_chart(f_pr, use_container_width=True)
        with c2:
            f_sol = crear_grafico_tendencia_con_pronostico(df_sol, 'saldo_capital_total_890_c', 'capital_c', 1, "Tendencia C1 - SOLIDAR", "#d62728")
            if f_sol: st.plotly_chart(f_sol, use_container_width=True)

        st.divider()

        if not df_pr.empty:
            df_b = df_pr.groupby(['mes_apertura_str', 'PR_Origen_Limpio'])['saldo_capital_total'].sum().reset_index()
            if not df_b.empty:
                fig_b = px.bar(df_b, x='mes_apertura_str', y='saldo_capital_total', color='PR_Origen_Limpio', 
                               color_discrete_map={'Fisico': '#005b7f', 'Digital': '#f37021'}, text_auto='.2s')
                fig_b.update_layout(title="Saldo Capital Total por Origen (PR)", barmode='stack', plot_bgcolor='white', xaxis={'type': 'category'})
                st.plotly_chart(fig_b, use_container_width=True)

except Exception as e:
    st.error(f"Error en la aplicación: {e}")