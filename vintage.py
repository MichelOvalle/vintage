import streamlit as st
import pandas as pd
from dateutil.relativedelta import relativedelta

# Configuración de la página
st.set_page_config(page_title="Matriz Vintage Heatmap", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_parquet("vintage_acum.parquet")
    if 'mes_apertura' in df.columns:
        df['mes_apertura'] = pd.to_datetime(df['mes_apertura'])
    return df

try:
    df_raw = load_data()

    st.title("📊 Matriz de Capital con Mapa de Calor")
    st.markdown("El color se aplica únicamente a las celdas con valores numéricos.")

    # 1. Definir la fecha base (Máximo de mes_apertura)
    fecha_max = df_raw['mes_apertura'].max()
    
    # Filtro de filas: Últimas 24 cosechas
    fecha_inicio_filas = fecha_max - pd.DateOffset(months=24)
    df = df_raw[df_raw['mes_apertura'] >= fecha_inicio_filas].copy()
    df['mes_apertura_str'] = df['mes_apertura'].dt.strftime('%Y-%m')

    # 2. Construcción de la Matriz
    results = []

    for i in range(25):  # Generamos columnas de 0 a 24 meses
        col_num = f'saldo_capital_total_c{i+1}'
        col_den = f'capital_c{i+1}'
        
        # Calcular nombre de la columna (Fecha de cierre)
        fecha_columna = fecha_max - relativedelta(months=i)
        nombre_col_real = fecha_columna.strftime('%Y-%m')

        if col_num in df.columns and col_den in df.columns:
            # Cálculo del ratio (Saldo / Capital Inicial)
            # Nota: Usamos groupby para asegurar que cada mes_apertura tenga su valor
            temp = df.groupby('mes_apertura_str').apply(
                lambda x: x[col_num].sum() / x[col_den].sum() if x[col_den].sum() != 0 else None
            )
            temp.name = nombre_col_real
            results.append(temp)

    if results:
        # Unimos las series en un DataFrame
        matriz_final = pd.concat(results, axis=1)
        
        # --- APLICANDO EL ORDEN SOLICITADO ---
        
        # 1. Filas: Orden ASCENDENTE (de la más antigua arriba a la más reciente abajo)
        matriz_final = matriz_final.sort_index(ascending=True)
        
        # 2. Columnas: Orden DESCENDENTE (de la más reciente izquierda a la más antigua derecha)
        cols_ordenadas = sorted(matriz_final.columns, reverse=True)
        matriz_final = matriz_final.reindex(columns=cols_ordenadas)

        # 3. Mostrar la Matriz con Heatmap en Streamlit
        st.subheader("Visualización de Ratios de Capital")
        
        # Aplicamos el estilo:
        # - format: Porcentaje con 2 decimales y nulos como vacío ""
        # - background_gradient: Mapa de calor que ignora nulos automáticamente
        # - axis=None: El gradiente se calcula sobre toda la tabla (no columna por columna)
        st.dataframe(
            matriz_final.style.format("{:.2%}", na_rep="")
            .background_gradient(cmap='RdYlGn', axis=None), 
            use_container_width=True
        )

        st.info("💡 **Tip:** Las celdas en blanco representan periodos donde no existen datos o el tiempo aún no ha transcurrido.")

    else:
        st.error("No se encontraron las columnas necesarias (c1, c2, etc.).")

except Exception as e:
    st.error(f"Error técnico: {e}")