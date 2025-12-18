# --- GRÁFICA DE BARRAS CORREGIDA ---
        st.divider()
        st.subheader("Exposición por Origen Limpio (PR)")
        
        if not df_pr.empty:
            # Agrupamos por Mes y Origen usando el saldo_capital_total
            df_stack = df_pr.groupby(['mes_apertura_str', 'PR_Origen_Limpio'])['saldo_capital_total_c1'].sum().reset_index()
            df_stack.columns = ['Mes Apertura', 'Origen', 'Saldo Capital']

            # Creamos la gráfica con Plotly Express
            fig_stack = px.bar(
                df_stack, 
                x='Mes Apertura', 
                y='Saldo Capital', 
                color='Origen',
                title="Evolución del Saldo Capital Total 30-150 por Canal (PR)",
                labels={'Saldo Capital': 'Saldo Total ($)'},
                color_discrete_map={'Fisico': '#1f77b4', 'Digital': '#ff7f0e'},
                text_auto=',.0s'  # Esto añade los montos sobre las barras
            )
            
            fig_stack.update_layout(
                barmode='stack', 
                plot_bgcolor='white', 
                paper_bgcolor='white',
                xaxis={'categoryorder':'category ascending'},
                yaxis_tickprefix="$", 
                yaxis_tickformat=",.0s"
            )
            
            # Forzamos que los ejes se vean negros para consistencia
            fig_stack.update_xaxes(showline=True, linewidth=1, linecolor='black', gridcolor='#f0f0f0')
            fig_stack.update_yaxes(showline=True, linewidth=1, linecolor='black', gridcolor='#f0f0f0')

            st.plotly_chart(fig_stack, use_container_width=True)
        else:
            st.warning("No se encontraron datos para generar la gráfica de barras con los filtros actuales.")