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

# ==============================================================================
# 1. INITIAL CAP TABLE (PRE-SAFE)
# ==============================================================================
# Initial ownership distribution across founders, advisors, and team members.
# Dilutable pool total = Matt (52) + Nate (20) + Luke (1) + Casey (1) + JB (1) = 75%
# Non-dilutable pool total = Fred (15) + O-Star (10) = 25%
initial_cap_table = {
    'Matt': 52.0,
    'Nate': 20.0,
    'Fred': 15.0,        # Non-dilutable
    'O-Star': 10.0,      # Non-dilutable
    'Luke': 1.0,
    'Casey': 1.0,
    'JB': 1.0,
    'SAFEs': 0.0,
    'New Investor': 0.0
}

# ==============================================================================
# 2. POST-SAFE BASELINE CALCULATION ($10M Valuation Cap)
# ==============================================================================
# SAFEs Total: $150,000 ($100k Soares + $50k Shamburger) at a $10M Post-Money Cap.
# Baseline SAFE Ownership % = $150,000 / $10,000,000 = 1.50%
safe_baseline_pct = 1.50
fixed_non_dilutable_pct = 25.0  # Fred (15%) + O-Star (10%)

# Equity remaining for the dilutable pool after Fred, O-Star, and baseline SAFEs:
# Remaining = 100% - 25.0% (Non-dilutable) - 1.5% (SAFEs) = 73.50%
rem_equity_post_safe = 100.0 - fixed_non_dilutable_pct - safe_baseline_pct

# Scale factor to reduce the dilutable pool from 75% down to 73.50%:
post_safe_scale = rem_equity_post_safe / 75.0

post_safe_cap_table = {}
for stakeholder, pct in initial_cap_table.items():
    if stakeholder in ['Fred', 'O-Star']:
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
pre_money_valuations = [2500000, 3500000, 4000000, 4500000, 4750000, 5000000, 5250000, 5500000, 5750000, 6000000, 6500000, 7000000, 7500000, 8000000]
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
    scenario_scale_factor = remaining_dilutable_equity / 75.0
    
    # Formula 5: Populate individual stakeholder percentages
    current_scenario = {}
    for stakeholder, initial_pct in initial_cap_table.items():
        if stakeholder in ['Fred', 'O-Star']:
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

# Round all output values to 2 decimal places for clean percentage presentation
df_formatted = df.round(2)

# Display the final table
print(df_formatted.to_string())