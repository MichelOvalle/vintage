import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta

# Configuración de la página
st.set_page_config(page_title="Matriz de Capital - Vista Limpia", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_parquet("vintage_acum.parquet")
    if 'mes_apertura' in df.columns:
        df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
    return df

try:
    df_raw = load_data()

    st.title("📊 Matriz de Capital (Vista de Tabla)")
    st.markdown("Filtro aplicado: **Mes de Apertura ≤ Mes de Cierre** (sin mapa de calor).")

    # 1. Definir la fecha base
    fecha_max = df_raw['mes_apertura'].max()
    
    # Filtro de filas: Últimas 24 cosechas
    fecha_inicio_filas = fecha_max - pd.DateOffset(months=24)
    df = df_raw[df_raw['mes_apertura'] >= fecha_inicio_filas].copy()
    
    # Normalizar fecha de apertura para comparación
    df['mes_apertura_dt'] = df['mes_apertura'].dt.to_period('M').dt.to_timestamp()

    # 2. Construcción de la Matriz
    results = []
    
    for i in range(25):  # De 0 a 24 meses (dif_meses)
        col_num = f'saldo_capital_total_c{i+1}'
        col_den = f'capital_c{i+1}'
        
        # Fecha de la columna actual
        fecha_columna = (fecha_max - relativedelta(months=i)).replace(day=1)
        nombre_col_real = fecha_columna.strftime('%Y-%m')

        if col_num in df.columns and col_den in df.columns:
            # Cálculo del ratio (Saldo / Capital Inicial)
            temp = df.groupby('mes_apertura_dt').apply(
                lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() != 0 else None
            )
            temp.name = nombre_col_real
            results.append(temp)

    if results:
        # Unimos las series
        matriz_final = pd.concat(results, axis=1)
        # Ordenamos columnas cronológicamente (Izquierda a Derecha)
        matriz_final = matriz_final.reindex(sorted(matriz_final.columns), axis=1)
        # Ordenamos filas (Arriba la más reciente)
        matriz_final = matriz_final.sort_index(ascending=False)

        # 3. Aplicar Filtro Triangular (Apertura <= Cierre)
        idx_dt = pd.to_datetime(matriz_final.index)
        cols_dt = pd.to_datetime(matriz_final.columns)

        for r_idx, row_date in enumerate(idx_dt):
            for c_idx, col_date in enumerate(cols_dt):
                if row_date > col_date:
                    matriz_final.iloc[r_idx, c_idx] = None

        # 4. Formatear índice para visualización
        matriz_final.index = matriz_final.index.strftime('%Y-%m')

        # 5. Mostrar la Matriz Limpia
        st.subheader("Ratio de Capital por Periodo")
        
        # Mostramos el dataframe sin estilos de color, solo formato de porcentaje
        st.dataframe(
            matriz_final.style.format("{:.2%}", na_rep="-"),
            use_container_width=True
        )

        st.caption(f"Nota: Datos calculados desde el cierre máximo de {fecha_max.strftime('%Y-%m')}.")

    else:
        st.error("No se encontraron las columnas requeridas (c1, c2, etc.).")

except Exception as e:
    st.error(f"Error: {e}")