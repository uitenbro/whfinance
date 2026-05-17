import calendar as _cal
import pandas as pd
import matplotlib.pyplot as plt
from gsheet_io import (
    TOTAL_YEARS,
    WEIGHT_TO_ROW,
    MONTHLY_LINE_ITEMS,
    open_spreadsheet,
    read_dragonfly_scenarios,
    read_eterna_scenarios,
    read_ravenity_scenarios,
    read_sparv_scenarios,
    read_finance_scenarios,
    read_scenario_combinations,
    read_monthly_timing,
    write_output,
    write_monthly_plan,
)


def run_simulation(df_scenario, eterna_scenario, ravenity_scenario, sparv_scenario, finance_scenario):
    rows = []
    cum_cashflow = 0.0
    cum_cost = 0.0
    cum_revenue = 0.0
    payback_year = None

    eterna_start_year = eterna_scenario["first_sales_year"] if eterna_scenario else None

    dragonfly_units_by_year = [0] * TOTAL_YEARS
    if df_scenario:
        units = 0
        for year in range(1, TOTAL_YEARS + 1):
            if year == df_scenario["first_sales_year"]:
                units = df_scenario["initial_units"]
            elif year > df_scenario["first_sales_year"]:
                units = int(units * df_scenario["growth"])
            dragonfly_units_by_year[year - 1] = units

    ravenity_units_by_year = [0] * TOTAL_YEARS
    if ravenity_scenario:
        units = 0
        for year in range(1, TOTAL_YEARS + 1):
            if year == ravenity_scenario["first_sales_year"]:
                units = ravenity_scenario["initial_units"]
            elif year > ravenity_scenario["first_sales_year"]:
                units = int(units * ravenity_scenario["growth"])
            ravenity_units_by_year[year - 1] = units

    sparv_units_by_year = [0] * TOTAL_YEARS
    if sparv_scenario:
        units = 0
        for year in range(1, TOTAL_YEARS + 1):
            if year == sparv_scenario["first_sales_year"]:
                units = sparv_scenario["initial_units"]
            elif year > sparv_scenario["first_sales_year"]:
                units = int(units * sparv_scenario["growth"])
            sparv_units_by_year[year - 1] = units

    for year in range(1, TOTAL_YEARS + 1):
        fte_count = finance_scenario["fte_count_by_year"][year - 1]
        fte_cost = fte_count * finance_scenario["fte_cost_per"]
        business_dev_cost = finance_scenario["business_dev_cost_year"][year - 1]
        other_cost = finance_scenario["other_cost_by_year"][year - 1]
        grant_revenue = finance_scenario["grant_revenue"]
        sw_development_revenue = (
            finance_scenario["sw_development_customers"][year - 1]
            * finance_scenario["sw_revenue_per_customer_per_year"]
        )

        maturation_cost = 0
        if ravenity_scenario and year == ravenity_scenario["maturation_year"]:
            maturation_cost += ravenity_scenario["maturation_cost"]
        if df_scenario and year == df_scenario["maturation_year"]:
            maturation_cost += df_scenario["maturation_cost"]
        if eterna_scenario and year == eterna_scenario["maturation_year"]:
            maturation_cost += eterna_scenario["maturation_cost"]
        if sparv_scenario and year == sparv_scenario["maturation_year"]:
            maturation_cost += sparv_scenario["maturation_cost"]

        uav_units = uav_revenue = uav_cost = 0
        if df_scenario:
            uav_units = dragonfly_units_by_year[year - 1]
            uav_revenue = uav_units * df_scenario["price"]
            uav_cost = uav_units * df_scenario["cost"]

        eterna_revenue = eterna_cost = missions = 0
        if eterna_scenario and year >= eterna_start_year:
            year_index = year - eterna_start_year
            missions = int(max(0, eterna_scenario["missions_per_year"] + eterna_scenario["mission_growth_per_year"] * year_index))
            eterna_revenue = missions * eterna_scenario["avg_revenue_per_mission"]
            eterna_cost = eterna_scenario["baseline_cost"] + missions * eterna_scenario["avg_cost_per_mission"]

        computer_units = computer_revenue = computer_cost = 0
        if ravenity_scenario:
            computer_units = ravenity_units_by_year[year - 1]
            computer_revenue = computer_units * ravenity_scenario["price"]
            computer_cost = computer_units * ravenity_scenario["cost"]

        sparv_units = sparv_revenue = sparv_cost = 0
        if sparv_scenario:
            sparv_units = sparv_units_by_year[year - 1]
            sparv_revenue = sparv_units * sparv_scenario["price"]
            sparv_cost = sparv_units * sparv_scenario["cost"]

        total_revenue = grant_revenue + uav_revenue + eterna_revenue + sw_development_revenue + computer_revenue + sparv_revenue
        total_cost = fte_cost + business_dev_cost + other_cost + uav_cost + eterna_cost + maturation_cost + computer_cost + sparv_cost
        net_cashflow = total_revenue - total_cost

        cum_cashflow += net_cashflow
        cum_cost += total_cost
        cum_revenue += total_revenue

        if payback_year is None and cum_cashflow > 0:
            payback_year = year

        rows.append({
            "Engineers": fte_count,
            "Total Engr Cost": fte_cost / 1e6,
            "Business Dev Cost": business_dev_cost / 1e6,
            "Other Costs": other_cost / 1e6,
            "Grant Revenue": grant_revenue / 1e6,
            "SW Dev Revenue": sw_development_revenue / 1e6,
            "Dragonfly Units": uav_units,
            "Dragonfly Cost": uav_cost / 1e6,
            "Dragonfly Revenue": uav_revenue / 1e6,
            "Eterna Missions": missions,
            "Eterna Cost": eterna_cost / 1e6,
            "Eterna Revenue": eterna_revenue / 1e6,
            "Ravenity Units": computer_units,
            "Ravenity Cost": computer_cost / 1e6,
            "Ravenity Revenue": computer_revenue / 1e6,
            "SparV Units": sparv_units,
            "SparV Cost": sparv_cost / 1e6,
            "SparV Revenue": sparv_revenue / 1e6,
            "Maturation Cost": maturation_cost / 1e6,
            "Total Cost": total_cost / 1e6,
            "Total Revenue": total_revenue / 1e6,
            "Oper Profit/Loss": net_cashflow / 1e6,
            "Cumul Cost": cum_cost / 1e6,
            "Cumul Revenue": cum_revenue / 1e6,
            "Cumul Oper P/L": cum_cashflow / 1e6,
        })

    df = pd.DataFrame(rows, index=["Year %d" % i for i in range(1, TOTAL_YEARS + 1)]).T

    overhead_costs = (df.loc["Total Engr Cost"] + df.loc["Business Dev Cost"]
                      + df.loc["Other Costs"] + df.loc["Maturation Cost"])
    product_cogs = (df.loc["Dragonfly Cost"] + df.loc["Eterna Cost"]
                    + df.loc["Ravenity Cost"] + df.loc["SparV Cost"])
    available_revenue = df.loc["Total Revenue"] - product_cogs

    carryover = 0.0
    yearly_investment = []
    for col in df.columns:
        oh = overhead_costs[col]
        av = available_revenue[col]
        inv_y = max(0.0, oh - carryover)
        yearly_investment.append(inv_y)
        carryover = max(0.0, carryover + inv_y - oh + av)
    df.loc["Capital Needed"] = yearly_investment

    total_investment = sum(yearly_investment)
    total_return = df.loc["Cumul Oper P/L"].iloc[-1]
    roi = (total_return / total_investment) if total_investment else 0.0
    moic = ((total_return + total_investment) / total_investment) if total_investment else 0.0

    return df, total_investment, total_return, roi, moic, payback_year


# === LOAD SCENARIOS FROM GOOGLE SHEETS ===

print("Reading scenarios from Google Sheets...")
sh = open_spreadsheet()
dragonfly_scenarios      = read_dragonfly_scenarios(sh)
eterna_service_scenarios = read_eterna_scenarios(sh)
ravenity_scenarios       = read_ravenity_scenarios(sh)
sparv_scenarios          = read_sparv_scenarios(sh)
financial_scenarios      = read_finance_scenarios(sh)
scenario_combinations    = read_scenario_combinations(sh)

print(f"Loaded {len(scenario_combinations)} combination(s) to run.\n")

# === RUN SELECTED COMBINATIONS ===

results_for_sheet = []

for combo in scenario_combinations:
    df_scenario      = next((d for d in dragonfly_scenarios      if combo["dragonfly"] and d["label"] == combo["dragonfly"]), None)
    eterna_scenario  = next((e for e in eterna_service_scenarios if combo["eterna"]    and e["label"] == combo["eterna"]),    None)
    ravenity_scenario = next((r for r in ravenity_scenarios      if combo["ravenity"]  and r["label"] == combo["ravenity"]),  None)
    sparv_scenario   = next((s for s in sparv_scenarios          if combo.get("sparv") and s["label"] == combo["sparv"]),     None)
    finance_scenario = next(f for f in financial_scenarios if f["label"] == combo["finance"])

    label = finance_scenario["label"]
    if df_scenario:       label += " + %s" % df_scenario["label"]
    if eterna_scenario:   label += " + %s" % eterna_scenario["label"]
    if ravenity_scenario: label += " + %s" % ravenity_scenario["label"]
    if sparv_scenario:    label += " + %s" % sparv_scenario["label"]

    df_result, investment, total_return, roi, moic, payback_year = run_simulation(
        df_scenario, eterna_scenario, ravenity_scenario, sparv_scenario, finance_scenario
    )

    results_for_sheet.append((label, df_result, investment, total_return, roi, moic, payback_year))

    print("\n--- Financial Summary Table (%s) ---" % label)
    if df_scenario:
        print("Dragonfly Price per Unit: $%s" % format(df_scenario["price"], ","))
        print("Dragonfly Cost per Unit:  $%s" % format(df_scenario["cost"], ","))
        print("Initial Dragonfly Units Sold (Year %s): %d" % (df_scenario["maturation_year"] + 1, df_scenario["initial_units"]))
        print("Dragonfly Sales Growth Rate: %d%%" % int((df_scenario["growth"] - 1) * 100))
    if eterna_scenario:
        es = eterna_scenario
        print("Eterna Start Year: Year %d" % eterna_scenario["first_sales_year"])
        print("Eterna Missions (Y%d): %d, +%d/yr" % (eterna_scenario["first_sales_year"], es["missions_per_year"], es["mission_growth_per_year"]))
        print("Eterna $/Mission: rev $%s, cost $%s (baseline $%s/yr)" % (
            format(es["avg_revenue_per_mission"], ","),
            format(es["avg_cost_per_mission"], ","),
            format(es["baseline_cost"], ","),
        ))
    if ravenity_scenario:
        print("Ravenity Price per Unit: $%s" % format(ravenity_scenario["price"], ","))
        print("Ravenity Cost per Unit:  $%s" % format(ravenity_scenario["cost"], ","))
        print("Initial Ravenity Units Sold (Year %s): %d" % (ravenity_scenario["maturation_year"] + 1, ravenity_scenario["initial_units"]))
        print("Ravenity Sales Growth Rate: %d%%" % int((ravenity_scenario["growth"] - 1) * 100))
    if sparv_scenario:
        print("SparV Price per Unit:    $%s" % format(sparv_scenario["price"], ","))
        print("SparV Cost per Unit:     $%s" % format(sparv_scenario["cost"], ","))
        print("Initial SparV Units Sold (Year %d): %d" % (sparv_scenario["first_sales_year"], sparv_scenario["initial_units"]))
        print("SparV Sales Growth Rate: %d%%" % int((sparv_scenario["growth"] - 1) * 100))

    print("\n--- Investor Summary Table (%s) ---" % label)
    print("Total Investment:   $%s" % format(investment * 1e6, ",.0f"))
    print("Total Return:       $%s" % format(total_return * 1e6, ",.0f"))
    print("ROI: %.2fx" % roi)
    print("MOIC: %.2fx" % moic)
    if payback_year:
        print("Payback Period: Year %d\n" % payback_year)
    else:
        print("Payback Period: Not achieved in %d years\n" % TOTAL_YEARS)

    with pd.option_context("display.float_format", "{:,.2f}".format):
        header = "%-19s" % "Phase"
        for col in df_result.columns:
            header += "%7s " % col
        print(header)
        for row in df_result.index:
            line = "%-19s" % row
            for col in df_result.columns:
                if row in ("Dragonfly Units", "Ravenity Units", "Eterna Missions", "SparV Units"):
                    line += "%7d " % int(df_result.loc[row, col])
                else:
                    line += "%7.2f " % df_result.loc[row, col]
            print(line)

    fig, ax = plt.subplots(figsize=(14, 8))
    plt.rcParams.update({"font.size": 16})

    df_result.T["Total Cost"].plot(kind="line", linewidth=2, ax=ax, grid=True, color="darkorange", label="Total Cost")
    df_result.T["Total Revenue"].plot(kind="line", linewidth=2, ax=ax, grid=True, color="darkblue", label="Total Revenue")
    df_result.T["Cumul Oper P/L"].plot(kind="bar", ax=ax, alpha=0.3, color="gray", label="Cumul Operating Profit/Loss")

    for idx, val in enumerate(df_result.T["Cumul Oper P/L"]):
        if val >= 0:
            ax.text(idx, val - 0.3, f"{val:.2f}", ha="center", va="top", fontsize=13, color="black")
        else:
            ax.text(idx, val + 0.3, f"{val:.2f}", ha="center", va="bottom", fontsize=13, color="black")

    ax.set_title(label + "\n", fontsize=12)
    ax.set_xlabel("Phase (Year)", fontsize=16)
    ax.set_ylabel("Millions $", fontsize=16)
    ax.set_xticks(range(len(df_result.columns)))
    ax.set_xticklabels(df_result.columns, rotation=45, fontsize=16)
    ax.tick_params(axis="y", labelsize=16)
    ax.legend(fontsize=16)
    ax.axhline(0, color="gray", alpha=0.3, linewidth=1)

    plt.show(block=False)
    plt.pause(0.5)

# === WRITE ANNUAL RESULTS TO GOOGLE SHEETS ===

print("\nWriting results to Output tab...")
write_output(sh, results_for_sheet)
print("Output written to Google Sheet.")

# === GENERATE MONTHLY SPENDING PLAN ===

print("\nReading monthly timing settings...")
monthly_timing = read_monthly_timing(sh)

def generate_monthly_plan(df_result, timing):
    start_year  = timing["start_year"]
    start_month = timing["start_month"]
    num_months  = timing["num_months"]
    weights     = timing["weights"]

    def get_weights(cat):
        return weights.get(cat, [1 / 12] * 12)

    monthly_rows = []
    cum_net = 0.0
    cum_investment = 0.0
    carryover = 0.0

    for m_idx in range(num_months):
        total_month   = (start_month - 1) + m_idx
        cal_year      = start_year + total_month // 12
        cal_month     = total_month % 12 + 1
        month_label   = f"{_cal.month_abbr[cal_month]} {cal_year}"
        model_year  = m_idx // 12 + 1
        weight_idx  = m_idx if m_idx < 24 else 12 + (m_idx % 12)  # years 3+ repeat yr-2 pattern

        if model_year > TOTAL_YEARS:
            break

        year_col = f"Year {model_year}"
        row = {"Month": month_label}

        for weight_cat, df_row in WEIGHT_TO_ROW.items():
            annual_val = df_result.loc[df_row, year_col] * 1e6
            row[weight_cat] = annual_val * get_weights(weight_cat)[weight_idx]

        total_cost    = (row["FTE Cost"] + row["Business Dev"] + row["Other Costs"] +
                         row["Maturation Cost"] + row["Dragonfly COGS"] + row["Eterna COGS"] +
                         row["Ravenity COGS"] + row["SparV COGS"])
        total_revenue = (row["Grant Revenue"] + row["SW Dev Revenue"] +
                         row["Dragonfly Revenue"] + row["Eterna Revenue"] +
                         row["Ravenity Revenue"] + row["SparV Revenue"])
        net = total_revenue - total_cost
        cum_net += net

        overhead      = row["FTE Cost"] + row["Business Dev"] + row["Other Costs"] + row["Maturation Cost"]
        product_cogs  = row["Dragonfly COGS"] + row["Eterna COGS"] + row["Ravenity COGS"] + row["SparV COGS"]
        available_rev = total_revenue - product_cogs

        inv = max(0.0, overhead - carryover)
        cum_investment += inv
        carryover = max(0.0, carryover + inv - overhead + available_rev)

        row["Total Cost"]        = total_cost
        row["Total Revenue"]     = total_revenue
        row["Net"]               = net
        row["Cumul Net"]         = cum_net
        row["Capital Needed"] = inv
        row["Cumulative Capital"]  = cum_investment
        monthly_rows.append(row)

    return monthly_rows


monthly_plan_results = [
    (label, generate_monthly_plan(df_result, monthly_timing))
    for (label, df_result, *_) in results_for_sheet
]

print("Writing monthly plan to Monthly Plan tab...")
write_monthly_plan(sh, monthly_plan_results)
print("Monthly plan written to Google Sheet.")

plt.show()
