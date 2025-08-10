import pandas as pd
import matplotlib.pyplot as plt
import time

# === SCENARIO DEFINITIONS ===
# Keep "Low Price High Volume" identical to the original reference scenario
# so outputs remain comparable when Eterna is disabled.
dragonfly_scenarios = [
    {
        "label": "Dragonfly 100+25%",
        "price": 45000,             # $ per unit revenue
        "cost": 10000,               # $ per unit cost
        "initial_units": 100,       # units sold in first sales year
        "growth": 1.25,             # multiplicative growth factor (compounded, int-rounded each year)
        "maturation_year": 2,       # year when validation is complete
        "maturation_cost": 4000000, # $ cost in maturation year
    },
]

# Eterna services use whole missions. Growth is an integer number of missions added per year.
eterna_service_scenarios = [
    {
        "label": "Eterna 1/wk+2/wk Services",
        "missions_per_year": 52,            # missions in first Eterna service year
        "mission_growth_per_year": 104,      # +missions each subsequent year (integer)
        "avg_revenue_per_mission": 50000, # $ per mission revenue
        "avg_cost_per_mission": 10000,     # $ per mission variable cost
        "baseline_cost": 25000,           # $ fixed annual ops cost (overhead) for Eterna
        "maturation_year": 3,       # year when validation is complete
        "maturation_cost": 4000000, # $ cost in maturation year
    }
]

# Finance & maturation inputs
financial_scenarios = [
    {
        "label": "Scale to 11 FTE",
        # FTEs by year (10 years)
        "fte_count_by_year": [5, 9, 11, 11, 11, 11, 11, 11, 11, 11],
        "fte_cost_per": 212500,    # $/FTE/year (fully loaded)
        "sw_development_customers": [0, 3, 5, 5, 5, 5, 5, 5, 5, 5], # customers by year
        "sw_revenue_per_customer_per_year": 1880 * 150, # one developer per customer, $150/hr for year
        "other_cost": 400000,      # $/year
        "grant_revenue": 100000,   # $/year
        # Maturation costs applied in their specified years
        "maturation_year_avionics": 2, # year when avionics validation is complete
        "maturation_cost_avionics": 2000000, # $ cost in maturation year 
    } 
]

# Choose which combo(s) to run (no comprehensive looping required)
scenario_combinations = [
    # {
    #     "dragonfly": "Dragonfly Blue 150+20%", # set to None to disable Dragonfly
    #     "eterna": "Eterna 2+2 Services",  # set to None to disable Eterna
    #     "finance": "Scale to 11 FTE",
    # },
    # {
    #     "dragonfly": None,
    #     "eterna": "Eterna 1/wk+2/wk Services",  # set to None to disable Eterna
    #     "finance": "Scale to 11 FTE",
    # },
    {
        "dragonfly": "Dragonfly 100+25%", # set to None to disable Dragonfly
        "eterna": None, #"Eterna 2+2 Services",  # set to None to disable Eterna
        "finance": "Scale to 11 FTE",
    },
]

TOTAL_YEARS = 10


def run_simulation(df_scenario, eterna_scenario, finance_scenario):
    rows = []
    cum_cashflow = 0.0
    cum_cost = 0.0
    cum_revenue = 0.0
    payback_year = None

    # Eterna starts the year AFTER its maturation year, if configured
    eterna_start_year = None
    if eterna_scenario:
        eterna_start_year = eterna_scenario["maturation_year"] + 1 

    # Pre-compute Dragonfly units per year using original compounding & int rounding logic
    dragonfly_units_by_year = [0] * TOTAL_YEARS
    if df_scenario:
        units = 0
        for year in range(1, TOTAL_YEARS + 1):
            if year == df_scenario["maturation_year"] + 1:  # first sales year after maturation
                units = df_scenario["initial_units"]
            elif year > df_scenario["maturation_year"] + 1:  # subsequent sales years
                units = int(units * df_scenario["growth"])
            dragonfly_units_by_year[year - 1] = units

    for year in range(1, TOTAL_YEARS + 1):
        # Base OPEX / grants
        fte_count = finance_scenario["fte_count_by_year"][year - 1]
        fte_cost = fte_count * finance_scenario["fte_cost_per"]
        other_cost = finance_scenario["other_cost"]
        grant_revenue = finance_scenario["grant_revenue"]
        sw_development_revenue = finance_scenario["sw_development_customers"][year - 1] * finance_scenario["sw_revenue_per_customer_per_year"]

        # Maturation in specified years
        maturation_cost = 0
        if year == finance_scenario["maturation_year_avionics"]:
            maturation_cost += finance_scenario["maturation_cost_avionics"]
        if df_scenario:
            if year == df_scenario["maturation_year"]:
                maturation_cost += df_scenario["maturation_cost"]
        if eterna_scenario:
            if year == eterna_scenario["maturation_year"]:
                maturation_cost += eterna_scenario["maturation_cost"]

        # Dragonfly sales
        uav_units = 0
        uav_revenue = 0
        uav_cost = 0
        if df_scenario:
            uav_units = dragonfly_units_by_year[year - 1]
            uav_revenue = uav_units * df_scenario["price"]
            uav_cost = uav_units * df_scenario["cost"]

        # Eterna services (integer missions, linear growth by +N per year)
        eterna_revenue = 0
        eterna_cost = 0
        if eterna_scenario and year >= eterna_start_year:
            year_index = year - eterna_start_year  # 0 in first service year
            missions = eterna_scenario["missions_per_year"] + eterna_scenario["mission_growth_per_year"] * year_index
            missions = int(max(0, missions))  # whole, non-negative
            eterna_revenue = missions * eterna_scenario["avg_revenue_per_mission"]
            eterna_cost = eterna_scenario["baseline_cost"] + missions * eterna_scenario["avg_cost_per_mission"]

        total_revenue = grant_revenue + uav_revenue + eterna_revenue + sw_development_revenue
        total_cost = fte_cost + other_cost + uav_cost + eterna_cost + maturation_cost
        net_cashflow = total_revenue - total_cost

        cum_cashflow += net_cashflow
        cum_cost += total_cost
        cum_revenue += total_revenue

        if payback_year is None and cum_cashflow > 0:
            payback_year = year

        rows.append({
            "FTEs": fte_count,
            "Total FTE Cost": fte_cost / 1e6,
            "Other Costs": other_cost / 1e6,
            "Grant Revenue": grant_revenue / 1e6,
            "SW Dev Revenue": sw_development_revenue / 1e6,
            "Dragonfly Units": uav_units,
            "Dragonfly Cost": uav_cost / 1e6,
            "Dragonfly Revenue": uav_revenue / 1e6,
            "Eterna Missions": (missions if eterna_scenario and year >= eterna_start_year else 0),
            "Eterna Cost": eterna_cost / 1e6,
            "Eterna Revenue": eterna_revenue / 1e6,
            "Maturation Cost": maturation_cost / 1e6,
            "Total Cost": total_cost / 1e6,
            "Total Revenue": total_revenue / 1e6,
            "Net Cash Flow": net_cashflow / 1e6,
            "Cumulative Cost": cum_cost / 1e6,
            "Cumulative Revenue": cum_revenue / 1e6,
            "Cumulative Cashflow": cum_cashflow / 1e6,
        })

    # Build table with metrics as rows, years as columns
    df = pd.DataFrame(rows, index=["Year %d" % i for i in range(1, TOTAL_YEARS + 1)]).T

    # Investment / Return metrics derived from cumulative cashflow
    total_investment = -min(0, df.loc["Cumulative Cashflow"].min())
    total_return = df.loc["Cumulative Cashflow"].iloc[-1]
    roi = (total_return / total_investment) if total_investment else 0.0
    moic = ((total_return + total_investment) / total_investment) if total_investment else 0.0

    return df, total_investment, total_return, roi, moic, payback_year


# === RUN SELECTED COMBINATIONS ===
for combo in scenario_combinations:
    df_scenario =     next((d for d in dragonfly_scenarios      if combo["dragonfly"] and d["label"] == combo["dragonfly"]), None)
    eterna_scenario = next((e for e in eterna_service_scenarios if combo["eterna"]    and e["label"] == combo["eterna"]), None)
    finance_scenario = next(f for f in financial_scenarios if f["label"] == combo["finance"])

    label = finance_scenario['label']
    if df_scenario:
        label += " + %s" % (df_scenario['label'])
    if eterna_scenario:
        label += " + %s" % eterna_scenario['label']

    df_result, investment, total_return, roi, moic, payback_year = run_simulation(df_scenario, eterna_scenario, finance_scenario)

    # --- Summary header (keep concise, include key inputs) ---
    print("\n--- Financial Summary Table (%s) ---" % label)
    if df_scenario:
        print("Dragonfly Price per Unit: $%s" % format(df_scenario['price'], ","))
        print("Dragonfly Cost per Unit:  $%s" % format(df_scenario['cost'], ","))
        print("Initial Dragonfly Units Sold (Year %s): %d" % (df_scenario['maturation_year'] + 1, df_scenario['initial_units']))
        print("Dragonfly Sales Growth Rate: %d%%" % int((df_scenario['growth'] - 1) * 100))
    if eterna_scenario:
        es = eterna_scenario
        start_year = eterna_scenario['maturation_year'] + 1
        print("Eterna Start Year: Year %d" % start_year)
        print("Eterna Missions (Y%d): %d, +%d/yr" % (start_year, es['missions_per_year'], es['mission_growth_per_year']))
        print("Eterna $/Mission: rev $%s, cost $%s (baseline $%s/yr)" % (
            format(es['avg_revenue_per_mission'], ","),
            format(es['avg_cost_per_mission'], ","),
            format(es['baseline_cost'], ",")
        ))
    print("\n--- Investor Summary Table (%s) ---" % label)
    print("Total Investment:   $%s" % format(investment * 1e6, ",.0f"))
    print("Total Return:       $%s" % format(total_return * 1e6, ",.0f"))
    print("ROI: %.2fx" % roi)
    print("MOIC: %.2fx" % moic)
    if payback_year:
        print("Payback Period: Year %d\n" % payback_year)
    else:
        print("Payback Period: Not achieved in %d years\n" % TOTAL_YEARS)

    # --- Print table (metrics down, years across) ---
    with pd.option_context("display.float_format", "{:,.2f}".format):
        header = "%-19s" % "Phase"
        for col in df_result.columns:
            header += "%7s " % col
        print(header)

        for row in df_result.index:
            line = "%-19s" % row
            for col in df_result.columns:
                if row in ("Dragonfly Units", "Eterna Missions"):
                    line += "%7d " % int(df_result.loc[row, col])
                else:
                    line += "%7.2f " % df_result.loc[row, col]
            print(line)

    # --- Plot (lines for Total Cost/Revenue; bars for Cumulative Cashflow) ---
    fig, ax = plt.subplots(figsize=(14, 7)) 
    plt.rcParams.update({'font.size': 16})

    df_result.T[["Total Cost", "Total Revenue"]].plot(
        kind="line",
        linewidth=2,
        ax=ax,
        grid=True,
        label=["Total Cost", "Total Revenue"],
    )

    df_result.T["Cumulative Cashflow"].plot(
        kind="bar",
        ax=ax,
        alpha=0.3,
        color="gray",
        label="Cumulative Cashflow"
    )

    # Bar labels inside bars (handle positive/negative)
    for idx, val in enumerate(df_result.T["Cumulative Cashflow"]):
        if val >= 0:
            y_pos = val - 0.3
            va = 'top'
        else:
            y_pos = val + 0.3
            va = 'bottom'
        ax.text(idx, y_pos, f"{val:.2f}", ha='center', va=va, fontsize=13, color="black")

    ax.set_title(label)
    ax.set_xlabel("Phase (Year)", fontsize=16)
    ax.set_ylabel("Millions $", fontsize=16)
    ax.set_xticks(range(len(df_result.columns)))
    ax.set_xticklabels(df_result.columns, rotation=45, fontsize=16)
    ax.tick_params(axis='y', labelsize=16)  # <-- Y-axis labels to 16pt
    ax.legend(fontsize=16)
    # Draw a horizontal line at y=0 across the whole width
    ax.axhline(0, color='gray', alpha=0.3, linewidth=1)
   
    plt.show(block=False)  # Use block=False to allow multiple plots in a row
    plt.pause(0.5)   # Keep window open long enough to render

plt.show()  # Show all plots at the end
