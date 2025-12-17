import streamlit as st
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Matriz de Saldos por Maduración", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_parquet("vintage_acum.parquet")
    return df

try:
    df = load_data()

    st.title("📊 Matriz de Saldo Capital Total")
    st.markdown("Desglose por **Mes de Apertura** (filas) y **Meses de Diferencia** (columnas).")

    # 1. Crear la Tabla Pivote (Matriz)
    # Valores: saldo_capital_total
    # Índice (Filas): mes_apertura
    # Columnas (Hacia la derecha): dif_meses
    matriz_saldos = df.pivot_table(
        index='mes_apertura', 
        columns='dif_meses', 
        values='saldo_capital_total', 
        aggfunc='sum'
    )

    # Ordenar los meses de apertura de más reciente a más antiguo
    matriz_saldos = matriz_saldos.sort_index(ascending=False)

    # 2. Mostrar la Matriz en Streamlit
    st.subheader("Distribución de Saldo (Maduración)")
    
    # Aplicamos formato de moneda a toda la tabla
    # Llenamos los valores nulos con 0 para que la tabla sea legible
    st.dataframe(
        matriz_saldos.fillna(0).style.format("${:,.2f}"),
        use_container_width=True
    )

    # 3. Resumen adicional
    with st.expander("Ver total por Mes de Apertura (Suma horizontal)"):
        total_por_mes = matriz_saldos.sum(axis=1).reset_index()
        total_por_mes.columns = ['mes_apertura', 'Saldo Total Acumulado']
        st.dataframe(total_por_mes.style.format({"Saldo Total Acumulado": "${:,.2f}"}))

except KeyError as e:
    st.error(f"Error: Asegúrate de que las columnas 'mes_apertura', 'dif_meses' y 'saldo_capital_total' existan.")
except Exception as e:
    st.error(f"Error inesperado: {e}")