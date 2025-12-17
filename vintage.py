import streamlit as st
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Reporte de Saldos de Capital", layout="wide")

@st.cache_data
def load_data():
    # Carga del archivo parquet
    df = pd.read_parquet("vintage_acum.parquet")
    return df

try:
    df = load_data()

    st.title("📋 Resumen de Saldos por Mes de Perturbación")
    
    # 1. Agrupación y Cálculo con el nombre de variable correcto
    # Agrupamos por 'Mes_BperturB' y sumamos 'saldo_capital_total'
    resumen_saldos = df.groupby('Mes_BperturB')['saldo_capital_total'].sum().reset_index()

    # Ordenar por mes (del más reciente al más antiguo)
    resumen_saldos = resumen_saldos.sort_values('Mes_BperturB', ascending=False)

    # 2. Visualización de métricas clave arriba de la tabla
    total_acumulado = resumen_saldos['saldo_capital_total'].sum()
    promedio_mensual = resumen_saldos['saldo_capital_total'].mean()

    col1, col2 = st.columns(2)
    col1.metric("Saldo Capital Total", f"${total_acumulado:,.2f}")
    col2.metric("Promedio por Mes", f"${promedio_mensual:,.2f}")

    # 3. Mostrar la tabla formateada
    st.subheader("Detalle por Mes_BperturB")
    
    # Aplicamos formato de moneda a la columna de saldo
    st.dataframe(
        resumen_saldos.style.format({
            "saldo_capital_total": "${:,.2f}"
        }),
        use_container_width=True,
        hide_index=True
    )

    # 4. Opción para exportar
    csv = resumen_saldos.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Descargar resumen en CSV",
        data=csv,
        file_name='resumen_capital_por_mes.csv',
        mime='text/csv',
    )

except KeyError as e:
    st.error(f"Error: No se encontró la columna {e} en el archivo.")
    st.info("Verifica que las columnas se llamen exactamente 'Mes_BperturB' y 'saldo_capital_total'.")
except Exception as e:
    st.error(f"Ocurrió un error inesperado: {e}")