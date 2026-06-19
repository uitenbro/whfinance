import calendar as _cal
import math
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
    read_electronics_products,
    read_finance_scenarios,
    read_scenario_combinations,
    read_monthly_timing,
    write_output,
    write_monthly_plan,
    write_pl_output,
    write_pl_monthly,
)


def run_model(df_scenario, eterna_scenario, ravenity_scenario, sparv_scenario, finance_scenario, timing, electronics_products=None):
    """Monthly-first financial model. All start months are plan-relative (1 = first month of plan).

    Returns (df_result, monthly_rows, total_investment, total_return, roi, moic, payback_year).
    """
    electronics_products = electronics_products or []

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
        "Dragonfly Maturation",    "Dragonfly COGS",    "Dragonfly Revenue",
        "Eterna Maturation",       "Eterna COGS",       "Eterna Revenue",
        "Ravenity Maturation",     "Ravenity COGS",     "Ravenity Revenue",
        "SparV Maturation",        "SparV COGS",        "SparV Revenue",
        "Electronics Maturation",  "Electronics COGS",  "Electronics Revenue",
        "Total Cost", "Total Revenue", "Capital Needed",
        "_df_units", "_rv_units", "_sv_units", "_et_missions", "_el_units",
    ]
    _WD = 20  # working days per month used to convert daily rate to monthly headcount

    annual = [{k: 0.0 for k in _SUM_KEYS} | {"_fte": 0, "_df_techs": 0, "_rv_techs": 0, "_sv_techs": 0, "_et_techs": 0, "_el_techs": 0} for _ in range(TOTAL_YEARS)]

    _PL_KEYS = [
        "Engineering Cost", "Business Dev Cost", "Other Costs",
        "Grant Revenue", "SW Dev Revenue",
        "Dragonfly Maturation", "Eterna Maturation", "Ravenity Maturation", "SparV Maturation",
        "Electronics Maturation",
        "Dragonfly Revenue", "Eterna Revenue", "Ravenity Revenue", "SparV Revenue",
        "Electronics Revenue",
        "Dragonfly COGS", "Eterna COGS", "Ravenity COGS", "SparV COGS",
        "Electronics COGS",
        "Total Revenue", "Total COGS", "Total OpEx",
    ]
    pl_annual = [{k: 0.0 for k in _PL_KEYS} | {"_fte": 0, "_df_techs": 0, "_rv_techs": 0, "_sv_techs": 0, "_et_techs": 0, "_el_techs": 0} for _ in range(TOTAL_YEARS)]

    monthly_rows    = []
    pl_monthly_rows = []
    cum_net      = 0.0
    cum_noi      = 0.0
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

        def _techs(units_or_missions, scenario):
            rate = scenario["production_per_tech_daily"] if scenario else 0.0
            return math.ceil(units_or_missions / (rate * _WD)) if rate > 0 and units_or_missions > 0 else 0

        df_techs    = _techs(df_u,  df_scenario)
        rv_techs    = _techs(rv_u,  ravenity_scenario)
        sv_techs    = _techs(sv_u,  sparv_scenario)
        et_techs    = _techs(et_ms, eterna_scenario)

        # Electronics products — compute per-product units once, then aggregate
        el_mat   = sum(_mat(p, m) for p in electronics_products)
        _el_pu   = [(_product_units(p, m), p) for p in electronics_products]
        el_u     = sum(u        for u, _ in _el_pu)
        el_cogs  = sum(u * p["cost"]  for u, p in _el_pu)
        el_techs = math.ceil(
            sum(u / (p["production_per_tech_daily"] * _WD)
                for u, p in _el_pu
                if p.get("production_per_tech_daily", 0) > 0)
        ) if el_u > 0 else 0
        el_rev   = sum(_product_units(p, m - p["revenue_lag_months"]) * p["price"] for p in electronics_products)

        total_techs = df_techs + rv_techs + sv_techs + et_techs + el_techs

        # Cash flow COGS — based on units/missions produced this month
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

        # P&L COGS — tied strictly to units/missions sold (same period as revenue)
        df_units_sold    = _product_units(df_scenario,       m - df_lag) if df_scenario       else 0.0
        rv_units_sold    = _product_units(ravenity_scenario,  m - rv_lag) if ravenity_scenario else 0.0
        sv_units_sold    = _product_units(sparv_scenario,     m - sv_lag) if sparv_scenario    else 0.0
        et_missions_sold = _missions(eterna_scenario,         m - et_lag) if eterna_scenario   else 0.0

        df_cogs_pl = df_units_sold * df_scenario["cost"]                         if df_scenario       else 0.0
        rv_cogs_pl = rv_units_sold * ravenity_scenario["cost"]                   if ravenity_scenario else 0.0
        sv_cogs_pl = sv_units_sold * sparv_scenario["cost"]                      if sparv_scenario    else 0.0
        et_base_pl = (eterna_scenario["baseline_cost"] / 12
                      if eterna_scenario and (m - et_lag) >= eterna_scenario["cogs_start_month"] else 0.0)
        et_cogs_pl = (et_missions_sold * eterna_scenario["avg_cost_per_mission"] + et_base_pl) if eterna_scenario else 0.0

        # Electronics P&L COGS — tied to units sold per product (each with its own lag)
        _el_pu_sold   = [(_product_units(p, m - p["revenue_lag_months"]), p) for p in electronics_products]
        el_units_sold = sum(u             for u, _ in _el_pu_sold)
        el_cogs_pl    = sum(u * p["cost"] for u, p in _el_pu_sold)

        total_cogs_pl = df_cogs_pl + rv_cogs_pl + sv_cogs_pl + et_cogs_pl + el_cogs_pl
        total_opex    = eng + biz + other + df_mat + et_mat + rv_mat + sv_mat + el_mat

        total_cost   = eng + biz + other + df_mat + et_mat + rv_mat + sv_mat + el_mat + df_cogs + rv_cogs + sv_cogs + et_cogs + el_cogs
        total_rev    = grant + sw_r + df_rev + rv_rev + sv_rev + et_rev + el_rev
        gross_profit = total_rev - total_cogs_pl
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
        a["SparV Maturation"]        += sv_mat
        a["SparV COGS"]              += sv_cogs
        a["SparV Revenue"]           += sv_rev
        a["Electronics Maturation"]  += el_mat
        a["Electronics COGS"]        += el_cogs
        a["Electronics Revenue"]     += el_rev
        a["Total Cost"]              += total_cost
        a["Total Revenue"]           += total_rev
        a["Capital Needed"]          += inv
        a["_df_units"]               += df_u
        a["_rv_units"]               += rv_u
        a["_sv_units"]               += sv_u
        a["_et_missions"]            += et_ms
        a["_el_units"]               += el_u
        a["_fte"]                     = fte
        a["_df_techs"]                = max(a["_df_techs"], df_techs)
        a["_rv_techs"]                = max(a["_rv_techs"], rv_techs)
        a["_sv_techs"]                = max(a["_sv_techs"], sv_techs)
        a["_et_techs"]                = max(a["_et_techs"], et_techs)
        a["_el_techs"]                = max(a["_el_techs"], el_techs)

        monthly_rows.append({
            "Month":               month_label,
            "Engineering Cost":    eng,
            "Business Dev Cost":   biz,
            "Other Costs":         other,
            "Grant Revenue":       grant,
            "SW Dev Revenue":      sw_r,
            "Dragonfly Maturation":  df_mat,
            "Dragonfly Expenses":    df_cogs,
            "Dragonfly Revenue":     df_rev,
            "Eterna Maturation":     et_mat,
            "Eterna Expenses":       et_cogs,
            "Eterna Revenue":        et_rev,
            "Ravenity Maturation":   rv_mat,
            "Ravenity Expenses":     rv_cogs,
            "Ravenity Revenue":      rv_rev,
            "SparV Maturation":        sv_mat,
            "SparV Expenses":          sv_cogs,
            "SparV Revenue":           sv_rev,
            "Electronics Maturation":  el_mat,
            "Electronics Expenses":    el_cogs,
            "Electronics Revenue":     el_rev,
            "Dragonfly Units":     df_u,
            "Eterna Missions":     et_ms,
            "Ravenity Units":      rv_u,
            "SparV Units":         sv_u,
            "Electronics Units":   el_u,
            "Dragonfly Techs":     df_techs,
            "Eterna Techs":        et_techs,
            "Ravenity Techs":      rv_techs,
            "SparV Techs":         sv_techs,
            "Electronics Techs":   el_techs,
            "Total Techs":         total_techs,
            "Total Expenses":      total_cost,
            "Total Revenue":       total_rev,
            "Net Cashflow":        net,
            "Cumulative Cashflow": cum_net,
            "Capital Needed":      inv,
            "Cumulative Capital":  cum_capital,
        })

        pa = pl_annual[yr_idx]
        pa["Engineering Cost"]     += eng
        pa["Business Dev Cost"]    += biz
        pa["Other Costs"]          += other
        pa["Grant Revenue"]        += grant
        pa["SW Dev Revenue"]       += sw_r
        pa["Dragonfly Maturation"] += df_mat
        pa["Eterna Maturation"]    += et_mat
        pa["Ravenity Maturation"]  += rv_mat
        pa["SparV Maturation"]        += sv_mat
        pa["Electronics Maturation"]  += el_mat
        pa["Dragonfly Revenue"]       += df_rev
        pa["Eterna Revenue"]          += et_rev
        pa["Ravenity Revenue"]        += rv_rev
        pa["SparV Revenue"]           += sv_rev
        pa["Electronics Revenue"]     += el_rev
        pa["Dragonfly COGS"]          += df_cogs_pl
        pa["Eterna COGS"]             += et_cogs_pl
        pa["Ravenity COGS"]           += rv_cogs_pl
        pa["SparV COGS"]              += sv_cogs_pl
        pa["Electronics COGS"]        += el_cogs_pl
        pa["Total Revenue"]           += total_rev
        pa["Total COGS"]              += total_cogs_pl
        pa["Total OpEx"]              += total_opex
        pa["_fte"]                     = fte
        pa["_df_techs"]                = max(pa["_df_techs"], df_techs)
        pa["_rv_techs"]                = max(pa["_rv_techs"], rv_techs)
        pa["_sv_techs"]                = max(pa["_sv_techs"], sv_techs)
        pa["_et_techs"]                = max(pa["_et_techs"], et_techs)
        pa["_el_techs"]                = max(pa["_el_techs"], el_techs)

        pl_monthly_rows.append({
            "Month":                  month_label,
            "Dragonfly Units Sold":   df_units_sold,
            "Eterna Missions Sold":   et_missions_sold,
            "Ravenity Units Sold":    rv_units_sold,
            "SparV Units Sold":       sv_units_sold,
            "Electronics Units Sold": el_units_sold,
            "Grant Revenue":       grant,
            "SW Dev Revenue":      sw_r,
            "Dragonfly Revenue":   df_rev,
            "Eterna Revenue":      et_rev,
            "Ravenity Revenue":    rv_rev,
            "SparV Revenue":       sv_rev,
            "Electronics Revenue": el_rev,
            "Total Revenue":       total_rev,
            "Dragonfly COGS":      df_cogs_pl,
            "Eterna COGS":         et_cogs_pl,
            "Ravenity COGS":       rv_cogs_pl,
            "SparV COGS":          sv_cogs_pl,
            "Electronics COGS":    el_cogs_pl,
            "Total COGS":          total_cogs_pl,
            "Gross Profit":        gross_profit,
            "Engineering Cost":    eng,
            "Business Dev Cost":   biz,
            "Other Costs":         other,
            "Dragonfly Maturation":    df_mat,
            "Eterna Maturation":       et_mat,
            "Ravenity Maturation":     rv_mat,
            "SparV Maturation":        sv_mat,
            "Electronics Maturation":  el_mat,
            "Total OpEx":          total_opex,
            "Net Operating Income": gross_profit - total_opex,
            "Cumulative NOI":      cum_noi + (gross_profit - total_opex),
        })
        cum_noi += gross_profit - total_opex

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
            "Engineers":              int(a["_fte"]),
            "Dragonfly Techs":        int(a["_df_techs"]),
            "Eterna Techs":           int(a["_et_techs"]),
            "Ravenity Techs":         int(a["_rv_techs"]),
            "SparV Techs":            int(a["_sv_techs"]),
            "Electronics Techs":      int(a["_el_techs"]),
            "Total Techs":            int(a["_df_techs"] + a["_rv_techs"] + a["_sv_techs"] + a["_et_techs"] + a["_el_techs"]),
            "Engineering Cost":       a["Engineering Cost"]       / 1e6,
            "Business Dev Cost":      a["Business Dev Cost"]      / 1e6,
            "Other Costs":            a["Other Costs"]            / 1e6,
            "Grant Revenue":          a["Grant Revenue"]          / 1e6,
            "SW Dev Revenue":         a["SW Dev Revenue"]         / 1e6,
            "Dragonfly Maturation":   a["Dragonfly Maturation"]   / 1e6,
            "Dragonfly Units":        a["_df_units"],
            "Dragonfly Cost":         a["Dragonfly COGS"]         / 1e6,
            "Dragonfly Revenue":      a["Dragonfly Revenue"]      / 1e6,
            "Eterna Maturation":      a["Eterna Maturation"]      / 1e6,
            "Eterna Missions":        a["_et_missions"],
            "Eterna Cost":            a["Eterna COGS"]            / 1e6,
            "Eterna Revenue":         a["Eterna Revenue"]         / 1e6,
            "Ravenity Maturation":    a["Ravenity Maturation"]    / 1e6,
            "Ravenity Units":         a["_rv_units"],
            "Ravenity Cost":          a["Ravenity COGS"]          / 1e6,
            "Ravenity Revenue":       a["Ravenity Revenue"]       / 1e6,
            "SparV Maturation":       a["SparV Maturation"]       / 1e6,
            "SparV Units":            a["_sv_units"],
            "SparV Cost":             a["SparV COGS"]             / 1e6,
            "SparV Revenue":          a["SparV Revenue"]          / 1e6,
            "Electronics Maturation": a["Electronics Maturation"] / 1e6,
            "Electronics Units":      a["_el_units"],
            "Electronics Cost":       a["Electronics COGS"]       / 1e6,
            "Electronics Revenue":    a["Electronics Revenue"]    / 1e6,
            "Total Expenses":         a["Total Cost"]             / 1e6,
            "Total Revenue":        a["Total Revenue"]        / 1e6,
            "Net Cashflow":         net_pl                    / 1e6,
            "Cumulative Cost":      cum_cost_a                / 1e6,
            "Cumulative Revenue":   cum_rev_a                 / 1e6,
            "Cumulative Cashflow":  cum_pl_a                  / 1e6,
            "Capital Needed":       a["Capital Needed"]       / 1e6,
            "Cumulative Capital":   cum_cap_a                 / 1e6,
        })

    df_result = pd.DataFrame(df_rows, index=[f"Year {i}" for i in range(1, TOTAL_YEARS + 1)]).T

    # ── Build annual P&L DataFrame from P&L monthly rollup ────────────────────────
    pl_df_rows  = []
    cum_noi_a   = 0.0
    for yr_idx, pa in enumerate(pl_annual):
        gp  = pa["Total Revenue"] - pa["Total COGS"]
        noi = gp - pa["Total OpEx"]
        cum_noi_a += noi
        pl_df_rows.append({
            "Engineers":              int(pa["_fte"]),
            "Dragonfly Techs":        int(pa["_df_techs"]),
            "Eterna Techs":           int(pa["_et_techs"]),
            "Ravenity Techs":         int(pa["_rv_techs"]),
            "SparV Techs":            int(pa["_sv_techs"]),
            "Electronics Techs":      int(pa["_el_techs"]),
            "Total Techs":            int(pa["_df_techs"] + pa["_rv_techs"] + pa["_sv_techs"] + pa["_et_techs"] + pa["_el_techs"]),
            "Grant Revenue":          pa["Grant Revenue"]          / 1e6,
            "SW Dev Revenue":         pa["SW Dev Revenue"]         / 1e6,
            "Dragonfly Revenue":      pa["Dragonfly Revenue"]      / 1e6,
            "Eterna Revenue":         pa["Eterna Revenue"]         / 1e6,
            "Ravenity Revenue":       pa["Ravenity Revenue"]       / 1e6,
            "SparV Revenue":          pa["SparV Revenue"]          / 1e6,
            "Electronics Revenue":    pa["Electronics Revenue"]    / 1e6,
            "Total Revenue":          pa["Total Revenue"]          / 1e6,
            "Dragonfly COGS":         pa["Dragonfly COGS"]         / 1e6,
            "Eterna COGS":            pa["Eterna COGS"]            / 1e6,
            "Ravenity COGS":          pa["Ravenity COGS"]          / 1e6,
            "SparV COGS":             pa["SparV COGS"]             / 1e6,
            "Electronics COGS":       pa["Electronics COGS"]       / 1e6,
            "Total COGS":             pa["Total COGS"]             / 1e6,
            "Gross Profit":           gp                           / 1e6,
            "Engineering Cost":       pa["Engineering Cost"]       / 1e6,
            "Business Dev Cost":      pa["Business Dev Cost"]      / 1e6,
            "Other Costs":            pa["Other Costs"]            / 1e6,
            "Dragonfly Maturation":   pa["Dragonfly Maturation"]   / 1e6,
            "Eterna Maturation":      pa["Eterna Maturation"]      / 1e6,
            "Ravenity Maturation":    pa["Ravenity Maturation"]    / 1e6,
            "SparV Maturation":       pa["SparV Maturation"]       / 1e6,
            "Electronics Maturation": pa["Electronics Maturation"] / 1e6,
            "Total OpEx":             pa["Total OpEx"]             / 1e6,
            "Net Oper Income":      noi                        / 1e6,
            "Cumulative NOI":       cum_noi_a                  / 1e6,
        })
    pl_df_result = pd.DataFrame(pl_df_rows, index=[f"Year {i}" for i in range(1, TOTAL_YEARS + 1)]).T

    total_investment = cum_cap_a / 1e6
    total_return     = cum_pl_a  / 1e6
    roi  = total_return / total_investment if total_investment else 0.0
    moic = (total_return + total_investment) / total_investment if total_investment else 0.0

    return df_result, monthly_rows, pl_monthly_rows, pl_df_result, total_investment, total_return, roi, moic, payback_year


# ── Load scenarios from Google Sheets ────────────────────────────────────────────

print("Reading scenarios from Google Sheets...")
sh = open_spreadsheet()
dragonfly_scenarios      = read_dragonfly_scenarios(sh)
eterna_service_scenarios = read_eterna_scenarios(sh)
ravenity_scenarios       = read_ravenity_scenarios(sh)
sparv_scenarios          = read_sparv_scenarios(sh)
electronics_products     = read_electronics_products(sh)
financial_scenarios      = read_finance_scenarios(sh)
scenario_combinations    = read_scenario_combinations(sh)
monthly_timing           = read_monthly_timing(sh)

print(f"Electronics: {len(electronics_products)} product(s) enabled.")

print(f"Loaded {len(scenario_combinations)} combination(s) to run.\n")

# ── Run all combinations ─────────────────────────────────────────────────────────

results_for_output       = []
results_for_monthly_plan = []
results_for_pl_output    = []
results_for_pl_monthly   = []

for combo in scenario_combinations:
    df_scenario       = next((d for d in dragonfly_scenarios      if combo["dragonfly"] and d["label"] == combo["dragonfly"]), None)
    eterna_scenario   = next((e for e in eterna_service_scenarios if combo["eterna"]    and e["label"] == combo["eterna"]),    None)
    ravenity_scenario = next((r for r in ravenity_scenarios       if combo["ravenity"]  and r["label"] == combo["ravenity"]),  None)
    sparv_scenario    = next((s for s in sparv_scenarios          if combo.get("sparv") and s["label"] == combo["sparv"]),     None)
    finance_scenario  = next(f for f in financial_scenarios if f["label"] == combo["finance"])

    if combo.get("label"):
        label = combo["label"]
    else:
        label = finance_scenario["label"]
        if df_scenario:       label += " + %s" % df_scenario["label"]
        if eterna_scenario:   label += " + %s" % eterna_scenario["label"]
        if ravenity_scenario: label += " + %s" % ravenity_scenario["label"]
        if sparv_scenario:    label += " + %s" % sparv_scenario["label"]

    combo_electronics = electronics_products if combo.get("electronics", True) else []

    df_result, monthly_rows, pl_monthly_rows, pl_df_result, investment, total_return, roi, moic, payback_year = run_model(
        df_scenario, eterna_scenario, ravenity_scenario, sparv_scenario,
        finance_scenario, monthly_timing,
        electronics_products=combo_electronics,
    )

    results_for_output.append((label, df_result, investment, total_return, roi, moic, payback_year))
    results_for_monthly_plan.append((label, monthly_rows))
    results_for_pl_output.append((label, pl_df_result, investment, total_return, roi, moic, payback_year))
    results_for_pl_monthly.append((label, pl_monthly_rows))

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
    if electronics_products:
        print("  Electronics (%d product(s)):" % len(electronics_products))
        for p in electronics_products:
            print("    %-30s price: $%s  cost: $%s  units/yr: %d  growth: %d%%  COGS start: mo %d"
                  % (p["label"], format(p["price"], ","), format(p["cost"], ","),
                     p["initial_units"], int((p["growth"] - 1) * 100), p["cogs_start_month"]))

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
                if row in ("Dragonfly Units", "Ravenity Units", "Eterna Missions", "SparV Units", "Electronics Units",
                           "Dragonfly Techs", "Eterna Techs", "Ravenity Techs", "SparV Techs", "Electronics Techs", "Total Techs",
                           "Engineers"):
                    line += "%8d " % int(val)
                else:
                    line += "%8.2f " % val
            print(line)

    fig, ax = plt.subplots(figsize=(14, 8))
    plt.rcParams.update({"font.size": 16})
    df_result.T["Total Expenses"].plot(kind="line", linewidth=2, ax=ax, grid=True, color="darkorange", label="Total Expenses")
    df_result.T["Total Revenue"].plot(kind="line", linewidth=2, ax=ax, grid=True, color="darkblue", label="Total Revenue")
    df_result.T["Cumulative Cashflow"].plot(kind="bar", ax=ax, alpha=0.3, color="gray", label="Cumulative Cashflow")
    for idx, val in enumerate(df_result.T["Cumulative Cashflow"]):
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

print("\nWriting annual cash flow to Annual Cash Flow tab...")
write_output(sh, results_for_output)
print("Annual Cash Flow tab written.")

print("Writing monthly cash flow to Monthly Cash Flow tab...")
write_monthly_plan(sh, results_for_monthly_plan)
print("Monthly Cash Flow tab written.")

print("Writing annual P&L to Annual P&L tab...")
write_pl_output(sh, results_for_pl_output)
print("Annual P&L tab written.")

print("Writing monthly P&L to Monthly P&L tab...")
write_pl_monthly(sh, results_for_pl_monthly)
print("Monthly P&L tab written.")

# plt.show()
