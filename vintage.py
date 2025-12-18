import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta
import numpy as np
import plotly.graph_objects as go
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
    if df.empty: return None, None, None
    
    df_capital_total = df.groupby('mes_apertura_str')['capital_c1'].sum()
    df_capital_total.name = "Capital Total"

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

def crear_grafico_linea_c2(df, prefijo_num, prefijo_den, titulo, color_linea):
    if df.empty: return None
    col_num, col_den = f'{prefijo_num}2', f'{prefijo_den}2'
    if col_num in df.columns and col_den in df.columns:
        df_c2 = df.groupby('mes_apertura_str').apply(
            lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() > 0 else np.nan
        ).reset_index()
        df_c2.columns = ['Cosecha', 'Ratio C2']
        fig = px.line(df_c2, x='Cosecha', y='Ratio C2', title=titulo, markers=True)
        fig.update_traces(line_color=color_linea, line_width=3)
        fig.update_layout(plot_bgcolor='white', yaxis_tickformat='.1%', xaxis={'type': 'category'})
        fig.update_xaxes(showgrid=True, gridcolor='#f0f0f0', tickangle=-45)
        fig.update_yaxes(showgrid=True, gridcolor='#f0f0f0')
        return fig
    return None

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
    tab1, tab2, tab3 = st.tabs(["📋 Matrices Vintage", "📈 Curvas, C2 y Saldo", "📍 Detalle por Sucursal"])

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
        st.title("Análisis de Maduración y Comportamiento")

        if m_graf_pr is not None:
            matriz_12m = m_graf_pr.tail(12)
            fig_lines = go.Figure()
            for cosecha in matriz_12m.index:
                fila = matriz_12m.loc[cosecha].dropna()
                fig_lines.add_trace(go.Scatter(x=fila.index, y=fila.values, mode='lines+markers', name=cosecha))
            fig_lines.update_layout(title="Curvas de Maduración (Últ. 12m) - PR", xaxis_title="Meses de Maduración", yaxis_tickformat='.1%', plot_bgcolor='white', height=400)
            st.plotly_chart(fig_lines, use_container_width=True)

        st.divider()

        st.subheader("Tendencia de Cohorte C2")
        col1, col2 = st.columns(2)
        with col1:
            fig_c2_pr = crear_grafico_linea_c2(df_pr, 'saldo_capital_total_c', 'capital_c', "Ratio C2 - UEN: PR", "#1f77b4")
            if fig_c2_pr: st.plotly_chart(fig_c2_pr, use_container_width=True)
        with col2:
            fig_c2_sol = crear_grafico_linea_c2(df_solidar, 'saldo_capital_total_890_c', 'capital_c', "Ratio C2 - UEN: SOLIDAR", "#d62728")
            if fig_c2_sol: st.plotly_chart(fig_c2_sol, use_container_width=True)

        st.divider()
        
        st.subheader("Evolución del Saldo Capital Total por Origen (PR)")
        if not df_pr.empty:
            df_stack = df_pr.groupby(['mes_apertura_str', 'PR_Origen_Limpio'])['saldo_capital_total'].sum().reset_index()
            df_stack.columns = ['Cosecha', 'Origen', 'Saldo']
            df_stack['Saldo'] = pd.to_numeric(df_stack['Saldo'], errors='coerce').fillna(0)
            fig_stack = px.bar(df_stack, x='Cosecha', y='Saldo', color='Origen', color_discrete_map={'Fisico': '#005b7f', 'Digital': '#f37021'}, text_auto='.2s')
            fig_stack.update_layout(barmode='stack', plot_bgcolor='white', xaxis={'type': 'category'})
            fig_stack.update_yaxes(tickprefix="$", tickformat=",.0f", showgrid=True, gridcolor='#eeeeee')
            st.plotly_chart(fig_stack, use_container_width=True)

    with tab3:
        st.title("📍 Detalle Numérico por Sucursal")
        
        col_pr, col_sol = st.columns(2)
        
        with col_pr:
            st.subheader("UEN: PR (Ratio C2)")
            if not df_pr.empty:
                df_suc_pr = df_pr.groupby('nombre_sucursal').apply(
                    lambda x: x['saldo_capital_total_c2'].sum() / x['capital_c2'].sum() if x['capital_c2'].sum() > 0 else np.nan
                ).reset_index()
                df_suc_pr.columns = ['Sucursal', 'Ratio C2']
                df_suc_pr = df_suc_pr.sort_values(by='Ratio C2', ascending=False).dropna()
                
                st.dataframe(
                    df_suc_pr.style.format({'Ratio C2': '{:.2%}'})
                    .background_gradient(cmap='RdYlGn_r', subset=['Ratio C2']),
                    use_container_width=True
                )
            else:
                st.info("Sin datos para PR")

        with col_sol:
            st.subheader("UEN: SOLIDAR (Ratio C1)")
            if not df_solidar.empty:
                # Nota: Para SOLIDAR usamos C1 y el prefijo de saldo 890
                df_suc_sol = df_solidar.groupby('nombre_sucursal').apply(
                    lambda x: x['saldo_capital_total_890_c1'].sum() / x['capital_c1'].sum() if x['capital_c1'].sum() > 0 else np.nan
                ).reset_index()
                df_suc_sol.columns = ['Sucursal', 'Ratio C1']
                df_suc_sol = df_suc_sol.sort_values(by='Ratio C1', ascending=False).dropna()
                
                st.dataframe(
                    df_suc_sol.style.format({'Ratio C1': '{:.2%}'})
                    .background_gradient(cmap='RdYlGn_r', subset=['Ratio C1']),
                    use_container_width=True
                )
            else:
                st.info("Sin datos para SOLIDAR")

    st.caption(f"Referencia: Datos actualizados hasta {fecha_max.strftime('%Y-%m')}.")

except Exception as e:
    st.error(f"Error técnico: {e}")