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

3. SAFE Conversion Ownership % (two SAFEs, $10,000,000 cap each):
   Mike ($100,000, MFN clause) = Amount / MIN(Post-Money, Cap) * 100
   * Down-round protected: benefits if Post-Money < Cap, floored at his cap %
   Noah ($50,000, no MFN clause) = Amount / Cap * 100 (always fixed at 0.50%)

   Example (Mike + Noah at $5M Pre / $7M Post, both below the $10M cap):
   Mike % = ($100,000 / $7,000,000) * 100 = 1.43%
   Noah % = ($50,000 / $10,000,000) * 100 = 0.50%
   SAFE % = 1.43% + 0.50% = 1.93%

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
    # 'Fred-non-dilutable': 0.0,        # Non-dilutable
    'Fred--dilutable': 15.0,        
    'O-Star': 10.0,                   # Non-dilutable
    'Luke': 1.0,
    'Casey': 1.0,
    'JB': 1.0,
    'Mike (SAFE)': 0.0,
    'Noah (SAFE)': 0.0,
    'ASI Investor': 0.0
}
# These stakeholders retain their initial percentages regardless of dilution.
non_dilutable = ['O-Star'] 

# ==============================================================================
# 2. POST-SAFE BASELINE CALCULATION ($10M Valuation Cap)
# ==============================================================================
# Two SAFEs, both at a $10M Post-Money Cap, but only Mike's carries an MFN
# (most-favored-nation) clause:
#   - Mike:  $100,000, MFN -> converts at whichever is better for him: his
#            cap or the round's actual (lower) post-money valuation.
#   - Noah:  $50,000, no MFN -> always converts at his fixed cap-based %,
#            regardless of how the round is priced.
mike_safe_amount = 100_000
mike_safe_cap = 10_000_000
noah_safe_amount = 50_000
noah_safe_cap = 10_000_000

# Fixed cap-based baseline %, used directly for Noah and as Mike's baseline
# (pre-round) and worst-case (round priced above his cap) percentage.
mike_baseline_pct = (mike_safe_amount / mike_safe_cap) * 100.0   # 1.00%
noah_baseline_pct = (noah_safe_amount / noah_safe_cap) * 100.0   # 0.50%
safe_baseline_pct = mike_baseline_pct + noah_baseline_pct        # 1.50%

# Set to False to model the SAFEs NOT converting to equity (e.g. repaid in cash
# or otherwise settled outside the cap table). When False, SAFE holders get 0%
# equity and the dilutable pool is not reduced by the SAFE amount.
SAFES_CONVERT = True

fixed_non_dilutable_pct = sum(
    initial_cap_table[stakeholder] for stakeholder in non_dilutable
)
dilutable_initial_pct = sum(
    pct for stakeholder, pct in initial_cap_table.items()
    if stakeholder not in non_dilutable
    and stakeholder not in ['Mike (SAFE)', 'Noah (SAFE)', 'ASI Investor']
)

if not SAFES_CONVERT:
    mike_baseline_pct = 0.0
    noah_baseline_pct = 0.0
    safe_baseline_pct = 0.0

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
    elif stakeholder == 'Mike (SAFE)':
        post_safe_cap_table[stakeholder] = mike_baseline_pct
    elif stakeholder == 'Noah (SAFE)':
        post_safe_cap_table[stakeholder] = noah_baseline_pct
    elif stakeholder == 'ASI Investor':
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


scenarios = {}

for pre_money in pre_money_valuations:
    # Formula 1: Post-Money Valuation
    post_money = pre_money + investment_amount

    # Formula 2: New Investor Ownership %
    investor_pct = (investment_amount / post_money) * 100.0

    # Formula 3: SAFE Conversion Ownership %
    # Mike (MFN): converts at whichever valuation is lower -- his $10M cap or
    # the round's actual post-money -- so he never does worse than his cap.
    # Noah (no MFN): always converts at his fixed cap-based %, unaffected by
    # how this round is priced.
    # If SAFES_CONVERT is False, neither SAFE converts to equity (e.g. they
    # are repaid in cash) and both take 0% of the cap table.
    if SAFES_CONVERT:
        mike_pct = (mike_safe_amount / min(post_money, mike_safe_cap)) * 100.0
        noah_pct = noah_baseline_pct
    else:
        mike_pct = 0.0
        noah_pct = 0.0
    safe_pct = mike_pct + noah_pct

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
        elif stakeholder == 'Mike (SAFE)':
            current_scenario[stakeholder] = mike_pct
        elif stakeholder == 'Noah (SAFE)':
            current_scenario[stakeholder] = noah_pct
        elif stakeholder == 'ASI Investor':
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
        'ASI Investor': scenario['ASI Investor']
    })

ownership_summary_df = pd.DataFrame(summary_rows).set_index('Valuation')
ownership_summary_df = ownership_summary_df[['Nate + Matt', 'ASI Investor']].round(2)

# Round all output values to 2 decimal places for clean percentage presentation
df_formatted = df.round(2)

# Display the final tables
print('COMPLETE CAP TABLE')
print(df_formatted.to_string())
print('\nNATE + MATT vs ASI INVESTOR')
print(ownership_summary_df.to_string())


# ==============================================================================
# 5. PIE CHARTS: Pre-SAFE and $1.92M scenario
# ==============================================================================
def plot_pie_charts(
    df: pd.DataFrame,
    output_path: str = "cap_table_pies.png",
    show_plot: bool = True,
    figsize: tuple[float, float] = (18, 6.5)
):
    selected_columns = list(df.columns[:2])
    chart_df = df[selected_columns]
    fig = plt.figure(figsize=figsize)
    # One row: [pie, table, pie, table] so each chart sits next to its table.
    grid = fig.add_gridspec(1, 4, width_ratios=[1.0, 1.1, 1.0, 1.1], wspace=0.15)
    pie_axes = [fig.add_subplot(grid[0, column]) for column in (0, 2)]
    table_axes = [fig.add_subplot(grid[0, column]) for column in (1, 3)]

    # Prepare colors mapped to stakeholders so the same color is used across pies
    stakeholders = list(chart_df.index)
    cmap = plt.get_cmap('tab20')
    palette = [cmap(i) for i in range(len(stakeholders))]
    color_map = dict(zip(stakeholders, palette))

    for pie_ax, table_ax, (_, series) in zip(pie_axes, table_axes, chart_df.items()):
        labels = list(series.index)
        sizes = list(series.values.astype(float))

        total = sum(sizes)
        if total <= 0:
            pie_ax.text(0.5, 0.5, 'No data', horizontalalignment='center', verticalalignment='center')
            pie_ax.axis('off')
            continue

        pie_colors = [color_map.get(lbl, (0.7, 0.7, 0.7)) for lbl in labels]

        def show_large_slice_pct(pct):
            return f'{pct:.1f}%' if pct >= 3.5 else ''

        _, _, autotexts = pie_ax.pie(
            sizes,
            labels=None,
            colors=pie_colors,
            autopct=show_large_slice_pct,
            startangle=90,
            textprops={'fontsize': 14}
        )
        for t in autotexts:
            t.set_fontsize(14)
        pie_ax.axis('equal')

        table_ax.axis('off')
        table = table_ax.table(
            cellText=[[label, f'{value:.2f}%'] for label, value in zip(labels, sizes)],
            colLabels=['Stakeholder', 'Ownership'],
            colWidths=[0.58, 0.42],
            cellLoc='left',
            loc='center'
        )
        table.auto_set_font_size(False)
        table.set_fontsize(14)
        table.scale(1, 2.2)
        for row in range(1, len(labels) + 1):
            table[(row, 0)].set_facecolor(color_map[labels[row - 1]])
            table[(row, 0)].get_text().set_color('white')
        table[(0, 0)].set_facecolor('#444444')
        table[(0, 1)].set_facecolor('#444444')
        table[(0, 0)].get_text().set_color('white')
        table[(0, 1)].get_text().set_color('white')
        for row in range(0, len(labels) + 1):
            cell = table[(row, 1)]
            cell.get_text().set_ha('right')
            cell.PAD = 0.05

    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    if show_plot:
        try:
            plt.show()
        except Exception:
            pass
    return fig


def build_input_scenario(
    investor_pct: float,
    investment_amount: float,
    safes_convert: bool = SAFES_CONVERT
) -> tuple[str, dict]:
    """Build a cap table from a new investor percentage and investment amount."""
    post_money = investment_amount / (investor_pct / 100.0)
    pre_money = post_money - investment_amount
    if safes_convert:
        mike_pct = (mike_safe_amount / min(post_money, mike_safe_cap)) * 100.0
        noah_pct = noah_baseline_pct
    else:
        mike_pct = 0.0
        noah_pct = 0.0
    safe_pct = mike_pct + noah_pct
    remaining_dilutable_equity = (
        100.0 - fixed_non_dilutable_pct - investor_pct - safe_pct
    )
    scenario_scale_factor = remaining_dilutable_equity / dilutable_initial_pct

    scenario = {}
    for stakeholder, initial_pct in initial_cap_table.items():
        if stakeholder in non_dilutable:
            scenario[stakeholder] = initial_pct
        elif stakeholder == 'Mike (SAFE)':
            scenario[stakeholder] = mike_pct
        elif stakeholder == 'Noah (SAFE)':
            scenario[stakeholder] = noah_pct
        elif stakeholder == 'ASI Investor':
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