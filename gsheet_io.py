"""Google Sheets I/O helpers for WHFinance."""

import json
import os
import gspread

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"
CONFIG_FILE = "gsheet_config.json"

TOTAL_YEARS = 7

TAB_DRAGONFLY    = "Dragonfly Scenarios"
TAB_ETERNA       = "Eterna Scenarios"
TAB_RAVENITY     = "Ravenity Scenarios"
TAB_SPARV        = "SparV Scenarios"
TAB_FINANCE      = "Finance Scenarios"
TAB_COMBINATIONS = "Scenario Combinations"
TAB_OUTPUT       = "Output"

INTEGER_ROWS = ("Dragonfly Units", "Ravenity Units", "Eterna Missions", "SparV Units", "Engineers")


def _get_client():
    return gspread.oauth(
        credentials_filename=CREDENTIALS_FILE,
        authorized_user_filename=TOKEN_FILE,
    )


def open_spreadsheet():
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(
            f"'{CONFIG_FILE}' not found. Run setup_gsheet.py first to create the spreadsheet."
        )
    with open(CONFIG_FILE) as f:
        cfg = json.load(f)
    return _get_client().open_by_key(cfg["spreadsheet_id"])


def _ws(sh, name):
    return sh.worksheet(name)


def _records_transposed(sh, tab, nonempty_key="label"):
    """Read a transposed tab: col A = field names, subsequent cols = one scenario each."""
    values = _ws(sh, tab).get_all_values()
    if not values:
        return []
    field_names = [row[0] for row in values if row]
    max_cols = max((len(row) for row in values), default=1)
    result = []
    for col_idx in range(1, max_cols):
        record = {
            field: (values[row_idx][col_idx] if col_idx < len(values[row_idx]) else "")
            for row_idx, field in enumerate(field_names)
        }
        if nonempty_key and not record.get(nonempty_key):
            continue
        result.append(record)
    return result


def read_dragonfly_scenarios(sh):
    return [{
        "label":           r["label"],
        "price":           float(r["price"]),
        "cost":            float(r["cost"]),
        "initial_units":   int(r["initial_units"]),
        "growth":          float(r["growth"]),
        "maturation_year": int(r["maturation_year"]),
        "maturation_cost": float(r["maturation_cost"]),
    } for r in _records_transposed(sh, TAB_DRAGONFLY)]


def read_eterna_scenarios(sh):
    return [{
        "label":                   r["label"],
        "missions_per_year":       int(r["missions_per_year"]),
        "mission_growth_per_year": int(r["mission_growth_per_year"]),
        "avg_revenue_per_mission": float(r["avg_revenue_per_mission"]),
        "avg_cost_per_mission":    float(r["avg_cost_per_mission"]),
        "baseline_cost":           float(r["baseline_cost"]),
        "maturation_year":         int(r["maturation_year"]),
        "maturation_cost":         float(r["maturation_cost"]),
    } for r in _records_transposed(sh, TAB_ETERNA)]


def read_ravenity_scenarios(sh):
    return [{
        "label":           r["label"],
        "price":           float(r["price"]),
        "cost":            float(r["cost"]),
        "initial_units":   int(r["initial_units"]),
        "growth":          float(r["growth"]),
        "maturation_year": int(r["maturation_year"]),
        "maturation_cost": float(r["maturation_cost"]),
    } for r in _records_transposed(sh, TAB_RAVENITY)]


def read_sparv_scenarios(sh):
    return [{
        "label":           r["label"],
        "price":           float(r["price"]),
        "cost":            float(r["cost"]),
        "initial_units":   int(r["initial_units"]),
        "growth":          float(r["growth"]),
        "start_year":      int(r["start_year"]),
        "maturation_cost": float(r["maturation_cost"]),
    } for r in _records_transposed(sh, TAB_SPARV)]


def read_finance_scenarios(sh):
    result = []
    for r in _records_transposed(sh, TAB_FINANCE):
        result.append({
            "label":                            r["label"],
            "fte_count_by_year":                [int(r[f"fte_count_yr{i}"]) for i in range(1, TOTAL_YEARS + 1)],
            "fte_cost_per":                     float(r["fte_cost_per"]),
            "business_dev_cost_year":           [float(r[f"biz_dev_cost_yr{i}"]) for i in range(1, TOTAL_YEARS + 1)],
            "sw_development_customers":         [int(r[f"sw_dev_customers_yr{i}"]) for i in range(1, TOTAL_YEARS + 1)],
            "sw_revenue_per_customer_per_year": float(r["sw_revenue_per_customer_per_year"]),
            "other_cost_by_year":               [float(r[f"other_cost_yr{i}"]) for i in range(1, TOTAL_YEARS + 1)],
            "grant_revenue":                    float(r["grant_revenue"]),
        })
    return result


def read_scenario_combinations(sh):
    result = []
    for r in _records_transposed(sh, TAB_COMBINATIONS, nonempty_key="finance"):
        enabled = r.get("enabled", "TRUE")
        if str(enabled).upper() in ("FALSE", "0", "NO", ""):
            continue
        result.append({
            "dragonfly": r.get("dragonfly") or None,
            "eterna":    r.get("eterna")    or None,
            "ravenity":  r.get("ravenity")  or None,
            "sparv":     r.get("sparv")     or None,
            "finance":   r["finance"],
        })
    return result


def write_output(sh, results):
    """Write all scenario results to the Output tab.

    results: list of (label, df_result, investment, total_return, roi, moic, payback_year)
    """
    ws = _ws(sh, TAB_OUTPUT)
    ws.clear()

    all_rows = []
    for (label, df_result, investment, total_return, roi, moic, payback_year) in results:
        payback_str = f"Year {payback_year}" if payback_year else f"Not achieved in {TOTAL_YEARS} years"

        all_rows.append([f"=== {label} ==="])
        all_rows.append(["Total Investment",  f"${investment * 1e6:,.0f}"])
        all_rows.append(["Total Return",      f"${total_return * 1e6:,.0f}"])
        all_rows.append(["ROI",               f"{roi:.2f}x"])
        all_rows.append(["MOIC",              f"{moic:.2f}x"])
        all_rows.append(["Payback Period",    payback_str])
        all_rows.append([])

        all_rows.append(["Metric"] + list(df_result.columns))
        for row_name in df_result.index:
            row_vals = [row_name]
            for col in df_result.columns:
                val = df_result.loc[row_name, col]
                row_vals.append(int(val) if row_name in INTEGER_ROWS else round(float(val), 2))
            all_rows.append(row_vals)

        all_rows.append([])
        all_rows.append([])

    if all_rows:
        ws.update("A1", all_rows)
