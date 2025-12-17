import streamlit as st
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Reporte por Mes de Apertura", layout="wide")

@st.cache_data
def load_data():
    # Carga del archivo parquet
    df = pd.read_parquet("vintage_acum.parquet")
    return df

try:
    df = load_data()

    st.title("📋 Saldo Capital por Mes de Apertura")
    st.markdown("Este reporte suma el saldo capital total basado en la fecha de originación de los créditos.")

    # 1. Agrupación y Cálculo
    # Agrupamos por 'mes_apertura' y sumamos 'saldo_capital_total'
    resumen_apertura = df.groupby('mes_apertura')['saldo_capital_total'].sum().reset_index()

    # Ordenar por mes de apertura (del más reciente al más antiguo)
    resumen_apertura = resumen_apertura.sort_values('mes_apertura', ascending=False)

    # 2. Cálculo de participación porcentual (%)
    total_general = resumen_apertura['saldo_capital_total'].sum()
    resumen_apertura['participacion_pct'] = (resumen_apertura['saldo_capital_total'] / total_general) * 100

    # 3. Métricas destacadas
    col1, col2, col3 = st.columns(3)
    col1.metric("Saldo Total", f"${total_general:,.2f}")
    col2.metric("Total Cosechas", len(resumen_apertura))
    col3.metric("Promedio por Cosecha", f"${resumen_apertura['saldo_capital_total'].mean():,.2f}")

    # 4. Mostrar la tabla formateada
    st.subheader("Desglose por Cosecha (mes_apertura)")
    
    st.dataframe(
        resumen_apertura.style.format({
            "saldo_capital_total": "${:,.2f}",
            "participacion_pct": "{:.2f}%"
        }),
        use_container_width=True,
        hide_index=True
    )

    # 5. Botón de exportación
    csv = resumen_apertura.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Descargar Resumen de Apertura",
        data=csv,
        file_name='resumen_por_mes_apertura.csv',
        mime='text/csv',
    )

except KeyError as e:
    st.error(f"Error: No se encontró la columna {e} en el archivo.")
    st.info("Asegúrate de que las columnas se llamen exactamente 'mes_apertura' y 'saldo_capital_total'.")
except Exception as e:
    st.error(f"Error inesperado: {e}")