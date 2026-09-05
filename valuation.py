"""
==============================================================================
CAP TABLE DILUTION MODEL & MATHEMATICAL FORMULAS
==============================================================================

1. Post-Money Valuation:
   Post-Money Valuation = Pre-Money Valuation + Investment Amount

2. New Investor Ownership %:
   New Investor % = (Investment Amount / Post-Money Valuation) * 100
   
   Example ($2M Investment at $5M Pre / $7M Post):
   New Investor % = ($2,000,000 / $7,000,000) * 100 = 28.57%

3. SAFE Conversion Ownership % (Down-Round Protection):
   SAFE % = (Total SAFE Amount / Post-Money Valuation) * 100
   * Applies whenever Post-Money Valuation <= $10,000,000 Valuation Cap
   
   Example ($150,000 SAFEs at $5M Pre / $7M Post):
   SAFE % = ($150,000 / $7,000,000) * 100 = 2.14%

4. Dilutable Pool Scale Factor:
   Dilutable Scale Factor = (100% - Non-Dilutable % - Investor % - SAFE %) / Initial Dilutable Base %
   
   Example ($5M Pre / $7M Post):
   Dilutable Scale Factor = (100% - 25.00% - 28.57% - 2.14%) / 75.00%
                          = 44.29% / 75.00% = 0.59053

5. Individual Dilutable Stakeholder Ownership %:
   Stakeholder Ownership % = Initial Stakeholder % * Dilutable Scale Factor
   
   Example for Matt (52% Initial):
   Matt % = 52.0% * 0.59053 = 30.70%
==============================================================================
"""

import pandas as pd
import matplotlib.pyplot as plt
import math

# ==============================================================================
# 1. INITIAL CAP TABLE (PRE-SAFE)
# ==============================================================================
# Initial ownership distribution across founders, advisors, and team members.
# Dilutable pool total = Matt (52) + Nate (20) + Luke (1) + Casey (1) + JB (1) = 75%
# Non-dilutable stakeholders are selected by the non_dilutable array below.
initial_cap_table = {
    'Matt': 52.0,
    'Nate': 20.0,
    'Fred-non-dilutable': 0.0,        # Non-dilutable
    'Fred--dilutable': 15.0,        
    'O-Star': 10.0,                   # Non-dilutable
    'Luke': 1.0,
    'Casey': 1.0,
    'JB': 1.0,
    'SAFEs': 0.0,
    'New Investor': 0.0
}
# These stakeholders retain their initial percentages regardless of dilution.
non_dilutable = ['Fred-non-dilutable', 'O-Star'] 

# ==============================================================================
# 2. POST-SAFE BASELINE CALCULATION ($10M Valuation Cap)
# ==============================================================================
# SAFEs Total: $150,000 ($100k Soares + $50k Shamburger) at a $10M Post-Money Cap.
# Baseline SAFE Ownership % = $150,000 / $10,000,000 = 1.50%
safe_baseline_pct = 1.50

fixed_non_dilutable_pct = sum(
    initial_cap_table[stakeholder] for stakeholder in non_dilutable
)
dilutable_initial_pct = sum(
    pct for stakeholder, pct in initial_cap_table.items()
    if stakeholder not in non_dilutable and stakeholder not in ['SAFEs', 'New Investor']
)

# Equity remaining for the dilutable pool after non-dilutable stakeholders and
# baseline SAFEs:
rem_equity_post_safe = 100.0 - fixed_non_dilutable_pct - safe_baseline_pct

# Scale factor to reduce the dilutable pool to the remaining equity:
post_safe_scale = rem_equity_post_safe / dilutable_initial_pct

post_safe_cap_table = {}
for stakeholder, pct in initial_cap_table.items():
    if stakeholder in non_dilutable:
        # Non-dilutable stakeholders retain their exact initial percentage
        post_safe_cap_table[stakeholder] = pct
    elif stakeholder == 'SAFEs':
        post_safe_cap_table[stakeholder] = safe_baseline_pct
    elif stakeholder == 'New Investor':
        post_safe_cap_table[stakeholder] = 0.0
    else:
        # Dilutable stakeholders are scaled down proportionally
        post_safe_cap_table[stakeholder] = pct * post_safe_scale


# ==============================================================================
# 3. SCENARIO MODELING: $2M NEW INVESTMENT AT $2M TO $8M PRE-MONEY
# ==============================================================================
pre_money_valuations = [1000000, 1500000, 2000000, 2500000, 3000000, 1920000, 4000000, 5000000, 6000000, 7000000, 8000000]

# Ensure scenarios are processed from high to low valuation
pre_money_valuations = sorted(pre_money_valuations, reverse=True)
investment_amount = 2000000
total_safes_amount = 150000


scenarios = {}

for pre_money in pre_money_valuations:
    # Formula 1: Post-Money Valuation
    post_money = pre_money + investment_amount
    
    # Formula 2: New Investor Ownership %
    investor_pct = (investment_amount / post_money) * 100.0
    
    # Formula 3: SAFE Conversion Ownership %
    # Under YC Post-Money SAFE rules, if the round's post-money valuation is 
    # <= the $10M cap, SAFEs convert at the round's lower post-money price:
    # $150,000 / Post-Money Valuation
    safe_pct = (total_safes_amount / post_money) * 100.0
    
    # Formula 4: Remaining dilutable equity and scale factor calculation
    # Total (100%) - Non-dilutable (25%) - New Investor % - SAFE %
    remaining_dilutable_equity = 100.0 - fixed_non_dilutable_pct - investor_pct - safe_pct
    scenario_scale_factor = remaining_dilutable_equity / dilutable_initial_pct
    
    # Formula 5: Populate individual stakeholder percentages
    current_scenario = {}
    for stakeholder, initial_pct in initial_cap_table.items():
        if stakeholder in non_dilutable:
            # Non-dilutable: percentage stays locked
            current_scenario[stakeholder] = initial_pct
        elif stakeholder == 'SAFEs':
            current_scenario[stakeholder] = safe_pct
        elif stakeholder == 'New Investor':
            current_scenario[stakeholder] = investor_pct
        else:
            # Dilutable: scale down based on remaining available equity
            current_scenario[stakeholder] = initial_pct * scenario_scale_factor
            
    # Key label for DataFrame column (e.g., "$2M", "$3M", etc.)
    val_in_millions = pre_money / 1_000_000
    col_label = f"${val_in_millions:g}M"
    scenarios[col_label] = current_scenario

# ==============================================================================
# 4. DATAFRAME CREATION AND FORMATTING
# ==============================================================================
df = pd.DataFrame({
    'Pre-SAFE': initial_cap_table, 
    'Post-SAFE': post_safe_cap_table
})

# Append each valuation scenario column
for label, scenario_data in scenarios.items():
    df[label] = pd.Series(scenario_data)

# Create a compact summary table with the valuation as the row index and
# Nate + Matt ownership side-by-side with the new investor ownership.
summary_rows = []
for label in [f"${pre / 1_000_000:g}M" for pre in sorted(pre_money_valuations, reverse=True)]:
    scenario = scenarios[label]
    summary_rows.append({
        'Valuation': label,
        'Nate + Matt': scenario['Nate'] + scenario['Matt'],
        'New Investor': scenario['New Investor']
    })

ownership_summary_df = pd.DataFrame(summary_rows).set_index('Valuation')
ownership_summary_df = ownership_summary_df[['Nate + Matt', 'New Investor']].round(2)

# Round all output values to 2 decimal places for clean percentage presentation
df_formatted = df.round(2)

# Display the final tables
print('COMPLETE CAP TABLE')
print(df_formatted.to_string())
print('\nNATE + MATT vs NEW INVESTOR')
print(ownership_summary_df.to_string())


# ==============================================================================
# 5. PIE CHARTS: Pre-SAFE and $1.92M scenario
# ==============================================================================
def plot_pie_charts(
    df: pd.DataFrame,
    output_path: str = "cap_table_pies.png",
    show_plot: bool = True,
    figsize: tuple[float, float] = (12, 10)
):
    selected_columns = list(df.columns[:2])
    chart_df = df[selected_columns]
    fig = plt.figure(figsize=figsize)
    grid = fig.add_gridspec(2, 2, height_ratios=[2.6, 2.0], hspace=0.04, wspace=0.28)
    pie_axes = [fig.add_subplot(grid[0, column]) for column in range(2)]
    table_axes = [fig.add_subplot(grid[1, column]) for column in range(2)]

    # Prepare colors mapped to stakeholders so the same color is used across pies
    stakeholders = list(chart_df.index)
    cmap = plt.get_cmap('tab20')
    palette = [cmap(i) for i in range(len(stakeholders))]
    color_map = dict(zip(stakeholders, palette))

    for pie_ax, table_ax, (col, series) in zip(pie_axes, table_axes, chart_df.items()):
        labels = list(series.index)
        sizes = list(series.values.astype(float))

        total = sum(sizes)
        if total <= 0:
            pie_ax.text(0.5, 0.5, 'No data', horizontalalignment='center', verticalalignment='center')
            pie_ax.set_title(col)
            pie_ax.axis('off')
            continue

        pie_colors = [color_map.get(lbl, (0.7, 0.7, 0.7)) for lbl in labels]

        def show_large_slice_pct(pct):
            return f'{pct:.1f}%' if pct >= 5.0 else ''

        _, _, autotexts = pie_ax.pie(
            sizes,
            labels=None,
            colors=pie_colors,
            autopct=show_large_slice_pct,
            startangle=90,
            textprops={'fontsize': 6}
        )
        for t in autotexts:
            t.set_fontsize(6)
        pie_ax.axis('equal')

        table_ax.axis('off')
        table = table_ax.table(
            cellText=[[label, f'{value:.2f}%'] for label, value in zip(labels, sizes)],
            colLabels=['Stakeholder', 'Ownership'],
            colWidths=[0.68, 0.32],
            cellLoc='left',
            loc='center'
        )
        table.auto_set_font_size(False)
        table.set_fontsize(5.2)
        table.scale(1, 1.0)
        for row in range(1, len(labels) + 1):
            table[(row, 0)].set_facecolor(color_map[labels[row - 1]])
            table[(row, 0)].get_text().set_color('white')
        table[(0, 0)].set_facecolor('#444444')
        table[(0, 1)].set_facecolor('#444444')
        table[(0, 0)].get_text().set_color('white')
        table[(0, 1)].get_text().set_color('white')

    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    if show_plot:
        try:
            plt.show()
        except Exception:
            pass
    return fig


def build_input_scenario(investor_pct: float, investment_amount: float) -> tuple[str, dict]:
    """Build a cap table from a new investor percentage and investment amount."""
    post_money = investment_amount / (investor_pct / 100.0)
    pre_money = post_money - investment_amount
    safe_pct = (total_safes_amount / post_money) * 100.0
    remaining_dilutable_equity = (
        100.0 - fixed_non_dilutable_pct - investor_pct - safe_pct
    )
    scenario_scale_factor = remaining_dilutable_equity / dilutable_initial_pct

    scenario = {}
    for stakeholder, initial_pct in initial_cap_table.items():
        if stakeholder in non_dilutable:
            scenario[stakeholder] = initial_pct
        elif stakeholder == 'SAFEs':
            scenario[stakeholder] = safe_pct
        elif stakeholder == 'New Investor':
            scenario[stakeholder] = investor_pct
        else:
            scenario[stakeholder] = initial_pct * scenario_scale_factor

    label = (
        f'Invest: ${investment_amount / 1_000_000:.2f}M | {investor_pct:.2f}%\n'
        f'Valuation: ${post_money / 1_000_000:.2f}M  |  ${pre_money / 1_000_000:.2f}M'
    )
    return label, scenario


if __name__ == '__main__':
    new_investor_pct = 51.00
    new_investment_amount = 2_000_000
    input_scenario_label, input_scenario = build_input_scenario(
        new_investor_pct,
        new_investment_amount
    )
    input_chart_df = pd.DataFrame({
        'Pre-SAFE': initial_cap_table,
        input_scenario_label: input_scenario
    }).round(2)

    print('\nVALUES SHOWN IN INPUT SCENARIO PIE CHARTS')
    print(input_chart_df.to_string())
    plot_pie_charts(input_chart_df, output_path='input_cap_table_pies.png')