import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta
import numpy as np
import plotly.graph_objects as go

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
    
    # Capital inicial otorgado
    df_capital_total = df.groupby('mes_apertura_str')['capital_c1'].sum()
    df_capital_total.name = "Capital Total"

    # Datos para gráfico (Mes 1, Mes 2...)
    results_graf = []
    for i in range(25):
        col_num = f'{prefijo_num}{i+1}'
        col_den = f'{prefijo_den}{i+1}'
        nombre_col = f"Mes {i+1}"
        if col_num in df.columns and col_den in df.columns:
            temp = df.groupby('mes_apertura_str').apply(
                lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() > 0 else np.nan
            )
            temp.name = nombre_col
            results_graf.append(temp)

    # Datos para tabla (Fechas reales)
    results_tabla = []
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
            results_tabla.append(temp)

    if not results_graf: return None, None, None
    matriz_ratios_grafico = pd.concat(results_graf, axis=1).sort_index(ascending=True)
    matriz_ratios_tabla = pd.concat(results_tabla, axis=1).sort_index(ascending=True)
    cols_ordenadas = sorted(matriz_ratios_tabla.columns, reverse=True)
    matriz_ratios_tabla = matriz_ratios_tabla.reindex(columns=cols_ordenadas)
    return matriz_ratios_tabla, df_capital_total, matriz_ratios_grafico

def renderizar_estilo(matriz_ratios, df_capital_total):
    matriz_final = pd.concat([df_capital_total, matriz_ratios], axis=1)
    stats = pd.DataFrame({
        'Promedio': matriz_ratios.mean(axis=0),
        'Máximo': matriz_ratios.max(axis=0),
        'Mínimo': matriz_ratios.min(axis=0)
    }).T 
    matriz_con_stats = pd.concat([matriz_final, stats]).replace({np.nan: None})
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
    fecha_inicio_24 = fecha_max - pd.DateOffset(months=24)
    df_24 = df_base[df_base['mes_apertura'] >= fecha_inicio_24].copy()
    df_24['mes_apertura_str'] = df_24['mes_apertura'].dt.strftime('%Y-%m')

    # --- TABS ---
    tab1, tab2 = st.tabs(["📋 Matrices Vintage", "📈 Curvas de Maduración (Últ. 12m)"])

    # DataFrames específicos por UEN
    df_pr = df_24[df_24['uen'] == 'PR']
    df_solidar = df_24[df_24['uen'] == 'SOLIDAR']

    with tab1:
        st.title("Reporte de Ratios por Cosecha (Histórico 24m)")
        
        m_tabla_pr, m_cap_pr, m_graf_pr = calcular_matriz_datos(df_pr, fecha_max, 'saldo_capital_total_c', 'capital_c')
        if m_tabla_pr is not None:
            st.subheader("📊 Vintage 30 - 150 (UEN: PR)")
            st.dataframe(renderizar_estilo(m_tabla_pr, m_cap_pr), use_container_width=True)
        
        st.divider()

        m_tabla_sol, m_cap_sol, m_graf_sol = calcular_matriz_datos(df_solidar, fecha_max, 'saldo_capital_total_890_c', 'capital_c')
        if m_tabla_sol is not None:
            st.subheader("📊 Vintage 8 - 90 (UEN: SOLIDAR)")
            st.dataframe(renderizar_estilo(m_tabla_sol, m_cap_sol), use_container_width=True)

    with tab2:
        st.title("Comportamiento Reciente por Maduración")
        st.markdown("Visualización de las curvas de las **últimas 12 cosechas**.")

        def crear_grafico_vintage_12m(matriz_graf, titulo):
            if matriz_graf is None: return None
            matriz_12m = matriz_graf.tail(12)
            fig = go.Figure()
            for cosecha in matriz_12m.index:
                fila = matriz_12m.loc[cosecha].dropna()
                fig.add_trace(go.Scatter(
                    x=fila.index, 
                    y=fila.values, 
                    mode='lines+markers', 
                    name=cosecha, 
                    line=dict(width=2.5)
                ))
            fig.update_layout(
                title=titulo, 
                xaxis_title="Meses de Maduración", 
                yaxis_title="Ratio de Capital", 
                yaxis_tickformat='.1%', 
                hovermode="x unified", 
                plot_bgcolor='white', 
                height=500
            )
            fig.update_xaxes(showgrid=True, gridcolor='#f0f0f0')
            fig.update_yaxes(showgrid=True, gridcolor='#f0f0f0')
            return fig

        if m_graf_pr is not None:
            st.plotly_chart(crear_grafico_vintage_12m(m_graf_pr, "Curvas de Maduración (Últ. 12 Cosechas) - PR"), use_container_width=True)

        st.divider()

        if m_graf_sol is not None:
            st.plotly_chart(crear_grafico_vintage_12m(m_graf_sol, "Curvas de Maduración (Últ. 12 Cosechas) - SOLIDAR"), use_container_width=True)

    st.caption(f"Referencia: Datos filtrados hasta {fecha_max.strftime('%Y-%m')}.")

except Exception as e:
    st.error(f"Error técnico: {e}")