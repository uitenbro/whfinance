import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from valuation import (
    build_input_scenario,
    initial_cap_table,
    plot_pie_charts,
)


st.set_page_config(page_title='WH Finance Cap Table', layout='wide')
st.title('Cap Table Investment Scenario', anchor=False)

input_col, amount_col, post_col, pre_col = st.columns([1, 1.2, 1, 1])
with input_col:
    investor_pct = st.number_input(
        'New investor ownership (%)',
        min_value=0.01,
        max_value=99.99,
        value=51.0,
        step=5.0,
        format='%.2f'
    )
with amount_col:
    investment_amount = st.number_input(
        'Investment amount ($)',
        min_value=1.0,
        value=2_000_000.0,
        step=500_000.0,
        format='%.2f'
    )

input_scenario_label, input_scenario = build_input_scenario(
    investor_pct,
    investment_amount
)
post_money = investment_amount / (investor_pct / 100.0)
pre_money = post_money - investment_amount

with post_col:
    st.metric('Post-money valuation', f'${post_money / 1_000_000:.2f}M')
with pre_col:
    st.metric('Pre-money valuation', f'${pre_money / 1_000_000:.2f}M')

chart_df = pd.DataFrame({
    'Pre-SAFE': initial_cap_table,
    input_scenario_label: input_scenario,
}).round(2)

figure = plot_pie_charts(
    chart_df,
    output_path='input_cap_table_pies.png',
    show_plot=False,
    figsize=(8.67, 5.06)
)
st.pyplot(figure, clear_figure=False)
plt.close(figure)