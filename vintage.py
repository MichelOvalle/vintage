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
    """Función lógica para procesar los datos de las matrices"""
    if df.empty:
        return None, None
    
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

    if not results:
        return None, None

    matriz_ratios = pd.concat(results, axis=1).sort_index(ascending=True)
    cols_ordenadas = sorted(matriz_ratios.columns, reverse=True)
    matriz_ratios = matriz_ratios.reindex(columns=cols_ordenadas)
    
    return matriz_ratios, df_capital_total

def renderizar_estilo(matriz_ratios, df_capital_total):
    """Aplica el estilo visual a la matriz"""
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

    # Procesamiento Base
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
        st.title("Reporte de Ratios por Cosecha")
        
        # Tabla 1: PR
        df_pr = df_base[df_base['uen'] == 'PR']
        m_ratios_pr, m_cap_pr = calcular_matriz_datos(df_pr, fecha_max, 'saldo_capital_total_c', 'capital_c')
        if m_ratios_pr is not None:
            st.subheader("📊 Vintage 30 - 150 (UEN: PR)")
            st.dataframe(renderizar_estilo(m_ratios_pr, m_cap_pr), use_container_width=True)
        
        st.divider()

        # Tabla 2: SOLIDAR
        df_solidar = df_base[df_base['uen'] == 'SOLIDAR']
        m_ratios_sol, m_cap_sol = calcular_matriz_datos(df_solidar, fecha_max, 'saldo_capital_total_890_c', 'capital_c')
        if m_ratios_sol is not None:
            st.subheader("📊 Vintage 8 - 90 (UEN: SOLIDAR)")
            st.dataframe(renderizar_estilo(m_ratios_sol, m_cap_sol), use_container_width=True)

    with tab2:
        st.title("Análisis de Riesgo Temprano")
        st.markdown("Comparativa de la evolución del ratio entre las diferentes cosechas.")

        if m_ratios_pr is not None:
            # Preparar datos para gráfico: Evolución de las últimas 6 cosechas
            df_chart = m_ratios_pr.iloc[-6:].T.reset_index()
            df_chart.columns = ['Meses de Maduración'] + list(df_chart.columns[1:])
            df_chart = df_chart.melt(id_vars='Meses de Maduración', var_name='Cosecha', value_name='Ratio')
            
            fig = px.line(df_chart.dropna(), 
                         x='Meses de Maduración', 
                         y='Ratio', 
                         color='Cosecha',
                         title="Curva de Deterioro: Últimas 6 Cosechas (PR)",
                         markers=True,
                         labels={'Ratio': 'Ratio de Capital (%)'})
            fig.update_layout(yaxis_tickformat='.1%')
            st.plotly_chart(fig, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                # Top Cosechas más riesgosas (mes 1)
                st.subheader("Cosechas con mayor ratio inicial")
                primer_mes = m_ratios_pr.columns[-1] # El mes más reciente de maduración
                top_riesgo = m_ratios_pr[primer_mes].sort_values(ascending=False).head(5)
                st.table(top_riesgo.map(lambda x: f"{x:.2%}"))

            with col2:
                # Volumen de originación
                st.subheader("Volumen de Capital por Cosecha")
                fig_bar = px.bar(m_cap_pr.reset_index(), x='mes_apertura_str', y='Capital Total', 
                                title="Capital Otorgado por Mes", color_discrete_sequence=['#2C3E50'])
                st.plotly_chart(fig_bar, use_container_width=True)

    st.caption(f"Referencia: Fecha de corte máxima {fecha_max.strftime('%Y-%m')}.")

except Exception as e:
    st.error(f"Error técnico: {e}")