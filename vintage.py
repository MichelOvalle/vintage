import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configuración inicial
st.set_page_config(page_title="Vintage Credit Analysis", layout="wide")

@st.cache_data
def load_data():
    # Cargamos el parquet que subiste a GitHub con LFS
    df = pd.read_parquet("vintage_acum.parquet")
    # Aseguramos que las columnas de fecha o periodos sean strings o fechas para el orden
    return df

try:
    df = load_data()
    
    st.title("📊 Monitor de Cosechas (Vintage Analysis)")
    st.sidebar.header("Configuración de la Vista")

    # Identificación automática de columnas (puedes ajustar los nombres)
    cols = df.columns.tolist()
    
    with st.sidebar:
        st.subheader("Variables")
        cohor_col = st.selectbox("Columna de Cosecha (Cohorte):", cols, index=0)
        madur_col = st.selectbox("Meses de Maduración:", cols, index=1)
        value_col = st.selectbox("Métrica (Mora/Monto):", cols, index=2)
        
        st.divider()
        st.info("Este dashboard lee directamente el archivo procesado en Parquet.")

    # --- FILA 1: Gráfico de Líneas Interactivo ---
    st.subheader("📈 Curvas de Maduración Acumulada")
    fig_line = px.line(
        df, 
        x=madur_col, 
        y=value_col, 
        color=cohor_col,
        markers=True,
        template="plotly_white",
        labels={madur_col: "Meses tras Apertura", value_col: "Tasa Acumulada (%)"}
    )
    st.plotly_chart(fig_line, use_container_width=True)

    # --- FILA 2: Matriz de Calor (Heatmap) ---
    st.subheader("🌡️ Matriz de Comportamiento")
    
    # Pivotamos los datos para crear la matriz
    pivot_df = df.pivot(index=cohor_col, columns=madur_col, values=value_col)
    
    fig_heat = px.imshow(
        pivot_df,
        labels=dict(x="Meses de Maduración", y="Cosecha", color="Valor"),
        x=pivot_df.columns,
        y=pivot_df.index,
        color_continuous_scale='YlOrRd' # De amarillo a rojo (típico de riesgo)
    )
    st.plotly_chart(fig_heat, use_container_width=True)

    # --- FILA 3: Tabla de Datos ---
    if st.checkbox("Ver Tabla de Datos Completa"):
        st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"Error al cargar el archivo: {e}")
    st.warning("Asegúrate de que 'vintage_acum.parquet' esté en la carpeta 'Vintage'.")