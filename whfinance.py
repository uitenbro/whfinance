import calendar as _cal
import pandas as pd
import matplotlib.pyplot as plt
from gsheet_io import (
    TOTAL_YEARS,
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


def run_model(df_scenario, eterna_scenario, ravenity_scenario, sparv_scenario, finance_scenario, timing):
    """Monthly-first financial model. All start months are plan-relative (1 = first month of plan).

    Returns (df_result, monthly_rows, total_investment, total_return, roi, moic, payback_year).
    """
    start_year  = timing["start_year"]
    start_month = timing["start_month"]
    num_months  = timing["num_months"]

    def _product_units(scenario, m):
        """Monthly units for a product-type scenario (Dragonfly/Ravenity/SparV)."""
        if not scenario or m < 1 or m < scenario["cogs_start_month"]:
            return 0.0
        yrs = (m - scenario["cogs_start_month"]) // 12
        return (scenario["initial_units"] / 12.0) * (scenario["growth"] ** yrs)

    def _missions(scenario, m):
        """Monthly missions for Eterna (linear annual growth)."""
        if not scenario or m < 1 or m < scenario["cogs_start_month"]:
            return 0.0
        yrs = (m - scenario["cogs_start_month"]) // 12
        return max(0.0, (scenario["missions_per_year"] + scenario["mission_growth_per_year"] * yrs) / 12.0)

    def _mat(scenario, m):
        """Maturation cost spread evenly over its duration window."""
        if not scenario:
            return 0.0
        ms  = scenario["maturation_start_month"]
        dur = scenario["maturation_duration_months"]
        return scenario["maturation_cost"] / dur if ms <= m < ms + dur else 0.0

    # Annual accumulation buckets (one per model year)
    _SUM_KEYS = [
        "Engineering Cost", "Business Dev Cost", "Other Costs",
        "Grant Revenue", "SW Dev Revenue",
        "Dragonfly Maturation", "Dragonfly COGS", "Dragonfly Revenue",
        "Eterna Maturation",    "Eterna COGS",    "Eterna Revenue",
        "Ravenity Maturation",  "Ravenity COGS",  "Ravenity Revenue",
        "SparV Maturation",     "SparV COGS",     "SparV Revenue",
        "Total Cost", "Total Revenue", "Capital Needed",
        "_df_units", "_rv_units", "_sv_units", "_et_missions",
    ]
    annual = [{k: 0.0 for k in _SUM_KEYS} | {"_fte": 0} for _ in range(TOTAL_YEARS)]

    monthly_rows = []
    cum_net      = 0.0
    cum_capital  = 0.0
    carryover    = 0.0

    df_lag = df_scenario["revenue_lag_months"]      if df_scenario      else 0
    et_lag = eterna_scenario["revenue_lag_months"]   if eterna_scenario  else 0
    rv_lag = ravenity_scenario["revenue_lag_months"] if ravenity_scenario else 0
    sv_lag = sparv_scenario["revenue_lag_months"]    if sparv_scenario   else 0

    for m in range(1, num_months + 1):
        yr_idx = min((m - 1) // 12, TOTAL_YEARS - 1)

        cal_off   = (start_month - 1) + (m - 1)
        cal_year  = start_year + cal_off // 12
        cal_month = cal_off % 12 + 1
        month_label = f"{_cal.month_abbr[cal_month]} {cal_year}"

        # Overhead — annual totals spread evenly across 12 months
        fte   = finance_scenario["fte_count_by_year"][yr_idx]
        eng   = fte * finance_scenario["fte_cost_per"] / 12
        biz   = finance_scenario["business_dev_cost_year"][yr_idx] / 12
        other = finance_scenario["other_cost_by_year"][yr_idx] / 12
        grant = finance_scenario["grant_revenue"] / 12
        sw_r  = (finance_scenario["sw_development_customers"][yr_idx]
                 * finance_scenario["sw_revenue_per_customer_per_year"] / 12)

        # Maturation costs
        df_mat = _mat(df_scenario, m)
        et_mat = _mat(eterna_scenario, m)
        rv_mat = _mat(ravenity_scenario, m)
        sv_mat = _mat(sparv_scenario, m)

        # COGS units/missions produced this month
        df_u  = _product_units(df_scenario, m)
        rv_u  = _product_units(ravenity_scenario, m)
        sv_u  = _product_units(sparv_scenario, m)
        et_ms = _missions(eterna_scenario, m)

        df_cogs = df_u * df_scenario["cost"]                        if df_scenario      else 0.0
        rv_cogs = rv_u * ravenity_scenario["cost"]                  if ravenity_scenario else 0.0
        sv_cogs = sv_u * sparv_scenario["cost"]                     if sparv_scenario   else 0.0
        et_base = (eterna_scenario["baseline_cost"] / 12
                   if eterna_scenario and m >= eterna_scenario["cogs_start_month"] else 0.0)
        et_cogs = (et_ms * eterna_scenario["avg_cost_per_mission"] + et_base) if eterna_scenario else 0.0

        # Revenue — booked revenue_lag_months after the corresponding COGS month
        df_rev = _product_units(df_scenario,      m - df_lag) * df_scenario["price"]                     if df_scenario      else 0.0
        rv_rev = _product_units(ravenity_scenario, m - rv_lag) * ravenity_scenario["price"]               if ravenity_scenario else 0.0
        sv_rev = _product_units(sparv_scenario,    m - sv_lag) * sparv_scenario["price"]                  if sparv_scenario   else 0.0
        et_rev = _missions(eterna_scenario,        m - et_lag) * eterna_scenario["avg_revenue_per_mission"] if eterna_scenario  else 0.0

        total_cost = eng + biz + other + df_mat + et_mat + rv_mat + sv_mat + df_cogs + rv_cogs + sv_cogs + et_cogs
        total_rev  = grant + sw_r + df_rev + rv_rev + sv_rev + et_rev
        net = total_rev - total_cost
        cum_net += net

        shortfall = total_cost - total_rev
        inv = max(0.0, shortfall - carryover)
        cum_capital += inv
        carryover = max(0.0, carryover + inv - shortfall)

        # Accumulate into annual bucket
        a = annual[yr_idx]
        a["Engineering Cost"]     += eng
        a["Business Dev Cost"]    += biz
        a["Other Costs"]          += other
        a["Grant Revenue"]        += grant
        a["SW Dev Revenue"]       += sw_r
        a["Dragonfly Maturation"] += df_mat
        a["Dragonfly COGS"]       += df_cogs
        a["Dragonfly Revenue"]    += df_rev
        a["Eterna Maturation"]    += et_mat
        a["Eterna COGS"]          += et_cogs
        a["Eterna Revenue"]       += et_rev
        a["Ravenity Maturation"]  += rv_mat
        a["Ravenity COGS"]        += rv_cogs
        a["Ravenity Revenue"]     += rv_rev
        a["SparV Maturation"]     += sv_mat
        a["SparV COGS"]           += sv_cogs
        a["SparV Revenue"]        += sv_rev
        a["Total Cost"]           += total_cost
        a["Total Revenue"]        += total_rev
        a["Capital Needed"]       += inv
        a["_df_units"]            += df_u
        a["_rv_units"]            += rv_u
        a["_sv_units"]            += sv_u
        a["_et_missions"]         += et_ms
        a["_fte"]                  = fte

        monthly_rows.append({
            "Month":               month_label,
            "Engineering Cost":    eng,
            "Business Dev Cost":   biz,
            "Other Costs":         other,
            "Grant Revenue":       grant,
            "SW Dev Revenue":      sw_r,
            "Dragonfly Maturation": df_mat,
            "Dragonfly COGS":      df_cogs,
            "Dragonfly Revenue":   df_rev,
            "Eterna Maturation":   et_mat,
            "Eterna COGS":         et_cogs,
            "Eterna Revenue":      et_rev,
            "Ravenity Maturation": rv_mat,
            "Ravenity COGS":       rv_cogs,
            "Ravenity Revenue":    rv_rev,
            "SparV Maturation":    sv_mat,
            "SparV COGS":          sv_cogs,
            "SparV Revenue":       sv_rev,
            "Total Cost":          total_cost,
            "Total Revenue":       total_rev,
            "Net":                 net,
            "Cumulative Net":      cum_net,
            "Capital Needed":      inv,
            "Cumulative Capital":  cum_capital,
        })

    # ── Build annual DataFrame from monthly rollup ─────────────────────────────────
    df_rows = []
    cum_cost_a = cum_rev_a = cum_pl_a = cum_cap_a = 0.0
    payback_year = None

    for yr_idx, a in enumerate(annual):
        net_pl = a["Total Revenue"] - a["Total Cost"]
        cum_cost_a += a["Total Cost"]
        cum_rev_a  += a["Total Revenue"]
        cum_pl_a   += net_pl
        cum_cap_a  += a["Capital Needed"]
        if payback_year is None and cum_pl_a > 0:
            payback_year = yr_idx + 1

        df_rows.append({
            "Engineers":            int(a["_fte"]),
            "Engineering Cost":     a["Engineering Cost"]     / 1e6,
            "Business Dev Cost":    a["Business Dev Cost"]    / 1e6,
            "Other Costs":          a["Other Costs"]          / 1e6,
            "Grant Revenue":        a["Grant Revenue"]        / 1e6,
            "SW Dev Revenue":       a["SW Dev Revenue"]       / 1e6,
            "Dragonfly Maturation": a["Dragonfly Maturation"] / 1e6,
            "Dragonfly Units":      a["_df_units"],
            "Dragonfly Cost":       a["Dragonfly COGS"]       / 1e6,
            "Dragonfly Revenue":    a["Dragonfly Revenue"]    / 1e6,
            "Eterna Maturation":    a["Eterna Maturation"]    / 1e6,
            "Eterna Missions":      a["_et_missions"],
            "Eterna Cost":          a["Eterna COGS"]          / 1e6,
            "Eterna Revenue":       a["Eterna Revenue"]       / 1e6,
            "Ravenity Maturation":  a["Ravenity Maturation"]  / 1e6,
            "Ravenity Units":       a["_rv_units"],
            "Ravenity Cost":        a["Ravenity COGS"]        / 1e6,
            "Ravenity Revenue":     a["Ravenity Revenue"]     / 1e6,
            "SparV Maturation":     a["SparV Maturation"]     / 1e6,
            "SparV Units":          a["_sv_units"],
            "SparV Cost":           a["SparV COGS"]           / 1e6,
            "SparV Revenue":        a["SparV Revenue"]        / 1e6,
            "Total Cost":           a["Total Cost"]           / 1e6,
            "Total Revenue":        a["Total Revenue"]        / 1e6,
            "Oper Profit/Loss":     net_pl                    / 1e6,
            "Cumulative Cost":      cum_cost_a                / 1e6,
            "Cumulative Revenue":   cum_rev_a                 / 1e6,
            "Cumulative Oper P/L":  cum_pl_a                  / 1e6,
            "Capital Needed":       a["Capital Needed"]       / 1e6,
            "Cumulative Capital":   cum_cap_a                 / 1e6,
        })

    df_result = pd.DataFrame(df_rows, index=[f"Year {i}" for i in range(1, TOTAL_YEARS + 1)]).T

    total_investment = cum_cap_a / 1e6
    total_return     = cum_pl_a  / 1e6
    roi  = total_return / total_investment if total_investment else 0.0
    moic = (total_return + total_investment) / total_investment if total_investment else 0.0

    return df_result, monthly_rows, total_investment, total_return, roi, moic, payback_year


# ── Load scenarios from Google Sheets ────────────────────────────────────────────

print("Reading scenarios from Google Sheets...")
sh = open_spreadsheet()
dragonfly_scenarios      = read_dragonfly_scenarios(sh)
eterna_service_scenarios = read_eterna_scenarios(sh)
ravenity_scenarios       = read_ravenity_scenarios(sh)
sparv_scenarios          = read_sparv_scenarios(sh)
financial_scenarios      = read_finance_scenarios(sh)
scenario_combinations    = read_scenario_combinations(sh)
monthly_timing           = read_monthly_timing(sh)

print(f"Loaded {len(scenario_combinations)} combination(s) to run.\n")

# ── Run all combinations ─────────────────────────────────────────────────────────

results_for_output       = []
results_for_monthly_plan = []

for combo in scenario_combinations:
    df_scenario       = next((d for d in dragonfly_scenarios      if combo["dragonfly"] and d["label"] == combo["dragonfly"]), None)
    eterna_scenario   = next((e for e in eterna_service_scenarios if combo["eterna"]    and e["label"] == combo["eterna"]),    None)
    ravenity_scenario = next((r for r in ravenity_scenarios       if combo["ravenity"]  and r["label"] == combo["ravenity"]),  None)
    sparv_scenario    = next((s for s in sparv_scenarios          if combo.get("sparv") and s["label"] == combo["sparv"]),     None)
    finance_scenario  = next(f for f in financial_scenarios if f["label"] == combo["finance"])

    label = finance_scenario["label"]
    if df_scenario:       label += " + %s" % df_scenario["label"]
    if eterna_scenario:   label += " + %s" % eterna_scenario["label"]
    if ravenity_scenario: label += " + %s" % ravenity_scenario["label"]
    if sparv_scenario:    label += " + %s" % sparv_scenario["label"]

    df_result, monthly_rows, investment, total_return, roi, moic, payback_year = run_model(
        df_scenario, eterna_scenario, ravenity_scenario, sparv_scenario,
        finance_scenario, monthly_timing,
    )

    results_for_output.append((label, df_result, investment, total_return, roi, moic, payback_year))
    results_for_monthly_plan.append((label, monthly_rows))

    # ── Terminal printout ──────────────────────────────────────────────────────────
    print("\n--- Scenario: %s ---" % label)
    if df_scenario:
        print("  Dragonfly price/unit: $%s  cost/unit: $%s  initial_units/yr: %d  growth: %d%%"
              % (format(df_scenario["price"], ","), format(df_scenario["cost"], ","),
                 df_scenario["initial_units"], int((df_scenario["growth"] - 1) * 100)))
        print("  Dragonfly maturation: month %d, %d-month spread  |  COGS start: month %d  |  rev lag: %d mo"
              % (df_scenario["maturation_start_month"], df_scenario["maturation_duration_months"],
                 df_scenario["cogs_start_month"], df_scenario["revenue_lag_months"]))
    if eterna_scenario:
        print("  Eterna missions/yr: %d + %d/yr growth  |  rev/mission: $%s  cost/mission: $%s"
              % (eterna_scenario["missions_per_year"], eterna_scenario["mission_growth_per_year"],
                 format(eterna_scenario["avg_revenue_per_mission"], ","),
                 format(eterna_scenario["avg_cost_per_mission"], ",")))
        print("  Eterna maturation: month %d, %d-month spread  |  COGS start: month %d  |  rev lag: %d mo"
              % (eterna_scenario["maturation_start_month"], eterna_scenario["maturation_duration_months"],
                 eterna_scenario["cogs_start_month"], eterna_scenario["revenue_lag_months"]))
    if ravenity_scenario:
        print("  Ravenity price/unit: $%s  cost/unit: $%s  initial_units/yr: %d  growth: %d%%"
              % (format(ravenity_scenario["price"], ","), format(ravenity_scenario["cost"], ","),
                 ravenity_scenario["initial_units"], int((ravenity_scenario["growth"] - 1) * 100)))
        print("  Ravenity maturation: month %d, %d-month spread  |  COGS start: month %d  |  rev lag: %d mo"
              % (ravenity_scenario["maturation_start_month"], ravenity_scenario["maturation_duration_months"],
                 ravenity_scenario["cogs_start_month"], ravenity_scenario["revenue_lag_months"]))
    if sparv_scenario:
        print("  SparV price/unit: $%s  cost/unit: $%s  initial_units/yr: %d  growth: %d%%"
              % (format(sparv_scenario["price"], ","), format(sparv_scenario["cost"], ","),
                 sparv_scenario["initial_units"], int((sparv_scenario["growth"] - 1) * 100)))
        print("  SparV maturation: month %d, %d-month spread  |  COGS start: month %d  |  rev lag: %d mo"
              % (sparv_scenario["maturation_start_month"], sparv_scenario["maturation_duration_months"],
                 sparv_scenario["cogs_start_month"], sparv_scenario["revenue_lag_months"]))

    print("\n  Total Investment:  $%s" % format(investment * 1e6, ",.0f"))
    print("  Total Return:      $%s" % format(total_return * 1e6, ",.0f"))
    print("  ROI: %.2fx  MOIC: %.2fx" % (roi, moic))
    if payback_year:
        print("  Payback Period: Year %d" % payback_year)
    else:
        print("  Payback Period: Not achieved in %d years" % TOTAL_YEARS)

    print()
    with pd.option_context("display.float_format", "{:,.2f}".format):
        header = "%-22s" % "Metric"
        for col in df_result.columns:
            header += "%8s " % col
        print(header)
        for row in df_result.index:
            line = "%-22s" % row
            for col in df_result.columns:
                val = df_result.loc[row, col]
                if row in ("Dragonfly Units", "Ravenity Units", "Eterna Missions", "SparV Units"):
                    line += "%8d " % int(val)
                else:
                    line += "%8.2f " % val
            print(line)

    fig, ax = plt.subplots(figsize=(14, 8))
    plt.rcParams.update({"font.size": 16})
    df_result.T["Total Cost"].plot(kind="line", linewidth=2, ax=ax, grid=True, color="darkorange", label="Total Cost")
    df_result.T["Total Revenue"].plot(kind="line", linewidth=2, ax=ax, grid=True, color="darkblue", label="Total Revenue")
    df_result.T["Cumulative Oper P/L"].plot(kind="bar", ax=ax, alpha=0.3, color="gray", label="Cumulative Operating Profit/Loss")
    for idx, val in enumerate(df_result.T["Cumulative Oper P/L"]):
        offset = -0.3 if val >= 0 else 0.3
        va     = "top"  if val >= 0 else "bottom"
        ax.text(idx, val + offset, f"{val:.2f}", ha="center", va=va, fontsize=13, color="black")
    ax.set_title(label + "\n", fontsize=12)
    ax.set_xlabel("Phase (Year)", fontsize=16)
    ax.set_ylabel("Millions $", fontsize=16)
    ax.set_xticks(range(len(df_result.columns)))
    ax.set_xticklabels(df_result.columns, rotation=45, fontsize=16)
    ax.tick_params(axis="y", labelsize=16)
    ax.legend(fontsize=16)
    ax.axhline(0, color="gray", alpha=0.3, linewidth=1)
    # plt.show(block=False)
    # plt.pause(0.5)

# ── Write results to Google Sheets ───────────────────────────────────────────────

print("\nWriting annual results to Output tab...")
write_output(sh, results_for_output)
print("Output tab written.")

print("Writing monthly plan to Monthly Plan tab...")
write_monthly_plan(sh, results_for_monthly_plan)
print("Monthly Plan tab written.")

# plt.show()
