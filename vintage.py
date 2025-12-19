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
        col_num, col_den = f'{prefijo_num}{i+1}', f'{prefijo_den}{i+1}'
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

def crear_gauge(valor, titulo, max_val, umbral_amarillo, umbral_rojo):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = valor * 100,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': titulo, 'font': {'size': 18}},
        number = {'suffix': "%", 'font': {'size': 24}, 'valueformat': ".2f"},
        gauge = {
            'axis': {'range': [None, max_val * 100], 'tickwidth': 1},
            'bar': {'color': "black"},
            'steps': [
                {'range': [0, umbral_amarillo * 100], 'color': "#92d050"},
                {'range': [umbral_amarillo * 100, umbral_rojo * 100], 'color': "#ffff00"},
                {'range': [umbral_rojo * 100, max_val * 100], 'color': "#ff0000"}],
        }))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
    return fig

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

    tab1, tab2, tab3, tab4 = st.tabs(["📋 Matrices", "📈 Comportamiento", "📍 Sucursales", "🚀 Resumen Ejecutivo"])

    df_pr = df_24[df_24['uen'] == 'PR']
    df_sol = df_24[df_24['uen'] == 'SOLIDAR']

    with tab1:
        st.title("Matrices Vintage")
        m_tab_pr, m_cap_pr, m_graf_pr = calcular_matriz_datos(df_pr, fecha_max, 'saldo_capital_total_c', 'capital_c')
        if m_tab_pr is not None:
            st.subheader("📊 Vintage PR (C2)"); st.dataframe(renderizar_estilo(m_tab_pr, m_cap_pr), use_container_width=True)
        st.divider()
        m_tab_sol, m_cap_sol, m_graf_sol = calcular_matriz_datos(df_sol, fecha_max, 'saldo_capital_total_890_c', 'capital_c')
        if m_tab_sol is not None:
            st.subheader("📊 Vintage SOLIDAR (C1)"); st.dataframe(renderizar_estilo(m_tab_sol, m_cap_sol), use_container_width=True)

    with tab2:
        st.title("Tendencias")
        if m_graf_pr is not None:
            matriz_12m = m_graf_pr.tail(12)
            fig_lines = go.Figure()
            for cosecha in matriz_12m.index:
                fila = matriz_12m.loc[cosecha].dropna()
                fig_lines.add_trace(go.Scatter(x=fila.index, y=fila.values, mode='lines+markers', name=cosecha))
            fig_lines.update_layout(title="Curvas de Maduración (Últ. 12m) - PR", plot_bgcolor='white', yaxis_tickformat='.1%')
            st.plotly_chart(fig_lines, use_container_width=True)

    with tab3:
        st.title("📍 Detalle Sucursales")
        c_pr, c_sol = st.columns(2)
        with c_pr:
            st.subheader("PR (Ratio C2)")
            if not df_pr.empty:
                df_s_p = df_pr.groupby('nombre_sucursal').apply(lambda x: x['saldo_capital_total_c2'].sum() / x['capital_c2'].sum() if x['capital_c2'].sum() > 0 else 0).reset_index()
                df_s_p.columns = ['Sucursal', 'Ratio C2']; df_s_p = df_s_p.sort_values('Ratio C2', ascending=False)
                st.dataframe(df_s_p.style.format({'Ratio C2': '{:.2%}'}).background_gradient(cmap='RdYlGn_r'), use_container_width=True)
        with c_sol:
            st.subheader("SOLIDAR (Ratio C1)")
            if not df_sol.empty:
                df_s_s = df_sol.groupby('nombre_sucursal').apply(lambda x: x['saldo_capital_total_890_c1'].sum() / x['capital_c1'].sum() if x['capital_c1'].sum() > 0 else 0).reset_index()
                df_s_s.columns = ['Sucursal', 'Ratio C1']; df_s_s = df_s_s.sort_values('Ratio C1', ascending=False)
                st.dataframe(df_s_s.style.format({'Ratio C1': '{:.2%}'}).background_gradient(cmap='RdYlGn_r'), use_container_width=True)

    with tab4:
        st.title("🚀 Resumen Ejecutivo de Riesgos")
        
        def get_kpi(df, num, den):
            m = sorted(df['mes_apertura_str'].unique())
            if len(m) < 2: return 0.0, 0.0
            act = df[df['mes_apertura_str'] == m[-1]]
            r_act = act[num].sum() / act[den].sum() if act[den].sum() > 0 else 0
            ant = df[df['mes_apertura_str'] == m[-2]]
            r_ant = ant[num].sum() / ant[den].sum() if ant[den].sum() > 0 else 0
            return r_act, r_act - r_ant

        r_pr, d_pr = get_kpi(df_pr, 'saldo_capital_total_c2', 'capital_c2')
        r_so, d_so = get_kpi(df_sol, 'saldo_capital_total_890_c1', 'capital_c1')

        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(crear_gauge(r_pr, "Estado Riesgo PR (C2)", 0.10, 0.03, 0.05), use_container_width=True)
            st.metric("Ratio Actual PR", f"{r_pr:.2%}", f"{d_pr:+.2%}", delta_color="inverse")
        with col2:
            st.plotly_chart(crear_gauge(r_so, "Estado Riesgo SOLIDAR (C1)", 0.15, 0.04, 0.07), use_container_width=True)
            st.metric("Ratio Actual SOLIDAR", f"{r_so:.2%}", f"{d_so:+.2%}", delta_color="inverse")
        
        st.divider()
        
        # --- RESUMEN ANALÍTICO DINÁMICO ---
        st.subheader("📑 Análisis de Variables Críticas")
        
        col_txt1, col_txt2 = st.columns(2)
        
        with col_txt1:
            st.markdown("### 🏢 Unidad PR")
            # Cálculo de variables top para el texto
            top_suc_pr = df_pr.groupby('nombre_sucursal').apply(lambda x: x['saldo_capital_total_c2'].sum() / x['capital_c2'].sum() if x['capital_c2'].sum() > 0 else 0).idxmax()
            top_prod_pr = df_pr.groupby('producto_agrupado').apply(lambda x: x['saldo_capital_total_c2'].sum() / x['capital_c2'].sum() if x['capital_c2'].sum() > 0 else 0).idxmax()
            
            st.write(f"""
            * **Comportamiento:** El riesgo se monitorea en el mes 2 (**C2**). Actualmente el indicador se encuentra en **{r_pr:.2%}**.
            * **Sucursales:** La sucursal con mayor presión de riesgo detectada es **{top_suc_pr}**. Se recomienda revisar la calidad de originación en esta plaza.
            * **Productos:** El producto **{top_prod_pr}** presenta la mayor sensibilidad. Un ajuste en los criterios de aceptación para este producto podría estabilizar el ratio general.
            """)

        with col_txt2:
            st.markdown("### 🤝 Unidad SOLIDAR")
            top_suc_so = df_sol.groupby('nombre_sucursal').apply(lambda x: x['saldo_capital_total_890_c1'].sum() / x['capital_c1'].sum() if x['capital_c1'].sum() > 0 else 0).idxmax()
            top_prod_so = df_sol.groupby('producto_agrupado').apply(lambda x: x['saldo_capital_total_890_c1'].sum() / x['capital_c1'].sum() if x['capital_c1'].sum() > 0 else 0).idxmax()
            
            st.write(f"""
            * **Comportamiento:** Análisis preventivo basado en **C1**. El ratio actual de **{r_so:.2%}** indica la salud de la originación inmediata.
            * **Sucursales:** Se observa una desviación prioritaria en la sucursal **{top_suc_so}**. Es necesario reforzar la cobranza preventiva en los primeros 30 días.
            * **Productos:** El producto **{top_prod_so}** lidera el índice de riesgo. Evaluar la mezcla de cartera para favorecer productos con mejor desempeño histórico.
            """)

        st.divider()
        st.subheader("📍 Alertas de Sucursales (Top 3)")
        a, b = st.columns(2)
        with a:
            st.table(df_pr.groupby('nombre_sucursal').apply(lambda x: x['saldo_capital_total_c2'].sum() / x['capital_c2'].sum() if x['capital_c2'].sum() > 0 else 0).nlargest(3).reset_index(name='Ratio').style.format({'Ratio': '{:.2%}'}))
        with b:
            st.table(df_sol.groupby('nombre_sucursal').apply(lambda x: x['saldo_capital_total_890_c1'].sum() / x['capital_c1'].sum() if x['capital_c1'].sum() > 0 else 0).nlargest(3).reset_index(name='Ratio').style.format({'Ratio': '{:.2%}'}))

    st.caption(f"Actualizado: {fecha_max.strftime('%Y-%m')}")

except Exception as e:
    st.error(f"Error: {e}")