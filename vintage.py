import streamlit as st
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Reporte de Saldos", layout="wide")

@st.cache_data
def load_data():
    # Carga del archivo parquet
    df = pd.read_parquet("vintage_acum.parquet")
    return df

try:
    df = load_data()

    st.title("📋 Resumen de Saldos por Mes")
    st.markdown("Cálculo de la suma de saldo capital total agrupado por periodo.")

    # 1. Agrupación y Cálculo
    # Agrupamos por 'mes_bperturb' y sumamos 'saldo_capital_total'
    resumen_saldos = df.groupby('mes_bperturb')['saldo_capital_total'].sum().reset_index()

    # Ordenar por mes para que la tabla sea lógica
    resumen_saldos = resumen_saldos.sort_values('mes_bperturb', ascending=False)

    # 2. Formato de la tabla
    # Renombramos columnas para que se vean mejor en la vista
    resumen_saldos.columns = ['Mes (bperturb)', 'Suma Saldo Capital Total']

    # 3. Mostrar métricas destacadas (opcional)
    total_general = resumen_saldos['Suma Saldo Capital Total'].sum()
    st.metric("Saldo Total General", f"${total_general:,.2f}")

    # 4. Mostrar la tabla en Streamlit
    st.subheader("Tabla de Datos Agrupados")
    st.dataframe(
        resumen_saldos.style.format({"Suma Saldo Capital Total": "${:,.2f}"}),
        use_container_width=True,
        hide_index=True
    )

    # 5. Botón para descargar este resumen
    csv = resumen_saldos.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Descargar este resumen como CSV",
        data=csv,
        file_name='resumen_saldos_vintage.csv',
        mime='text/csv',
    )

except Exception as e:
    st.error(f"Error al procesar los datos: {e}")
    st.info("Asegúrate de que las columnas 'mes_bperturb' y 'saldo_capital_total' existan en tu archivo.")