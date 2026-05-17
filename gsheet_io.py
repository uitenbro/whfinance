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
TAB_COMBINATIONS    = "Scenario Combinations"
TAB_OUTPUT          = "Output"
TAB_MONTHLY_TIMING  = "Monthly Timing"
TAB_MONTHLY_PLAN    = "Monthly Plan"

INTEGER_ROWS = ("Dragonfly Units", "Ravenity Units", "Eterna Missions", "SparV Units", "Engineers")

# Maps Monthly Timing category names → df_result row names
WEIGHT_TO_ROW = {
    "Engineering Cost":    "Engineering Cost",
    "Business Dev":        "Business Dev Cost",
    "Other Costs":         "Other Costs",
    "Dragonfly Maturation": "Dragonfly Maturation",
    "Dragonfly COGS":      "Dragonfly Cost",
    "Dragonfly Revenue":   "Dragonfly Revenue",
    "Eterna Maturation":   "Eterna Maturation",
    "Eterna COGS":         "Eterna Cost",
    "Eterna Revenue":      "Eterna Revenue",
    "Ravenity Maturation": "Ravenity Maturation",
    "Ravenity COGS":       "Ravenity Cost",
    "Ravenity Revenue":    "Ravenity Revenue",
    "SparV Maturation":    "SparV Maturation",
    "SparV COGS":          "SparV Cost",
    "SparV Revenue":       "SparV Revenue",
    "Grant Revenue":       "Grant Revenue",
    "SW Dev Revenue":      "SW Dev Revenue",
}

MONTHLY_LINE_ITEMS = [
    "Engineering Cost", "Business Dev", "Other Costs",
    "Dragonfly Maturation", "Dragonfly COGS", "Dragonfly Revenue",
    "Eterna Maturation",    "Eterna COGS",    "Eterna Revenue",
    "Ravenity Maturation",  "Ravenity COGS",  "Ravenity Revenue",
    "SparV Maturation",     "SparV COGS",     "SparV Revenue",
    "Grant Revenue",  "SW Dev Revenue",
    "Total Cost", "Total Revenue", "Net",
    "Cumulative Net", "Capital Needed", "Cumulative Capital",
]


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
        "label":            r["label"],
        "price":            float(r["price"]),
        "cost":             float(r["cost"]),
        "initial_units":    int(r["initial_units"]),
        "growth":           float(r["growth"]),
        "maturation_year":  int(r["maturation_year"]),
        "first_sales_year": int(r["first_sales_year"]),
        "maturation_cost":  float(r["maturation_cost"]),
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
        "first_sales_year":        int(r["first_sales_year"]),
        "maturation_cost":         float(r["maturation_cost"]),
    } for r in _records_transposed(sh, TAB_ETERNA)]


def read_ravenity_scenarios(sh):
    return [{
        "label":            r["label"],
        "price":            float(r["price"]),
        "cost":             float(r["cost"]),
        "initial_units":    int(r["initial_units"]),
        "growth":           float(r["growth"]),
        "maturation_year":  int(r["maturation_year"]),
        "first_sales_year": int(r["first_sales_year"]),
        "maturation_cost":  float(r["maturation_cost"]),
    } for r in _records_transposed(sh, TAB_RAVENITY)]


def read_sparv_scenarios(sh):
    return [{
        "label":            r["label"],
        "price":            float(r["price"]),
        "cost":             float(r["cost"]),
        "initial_units":    int(r["initial_units"]),
        "growth":           float(r["growth"]),
        "maturation_year":  int(r["maturation_year"]),
        "first_sales_year": int(r["first_sales_year"]),
        "maturation_cost":  float(r["maturation_cost"]),
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


def read_monthly_timing(sh):
    """Read the Monthly Timing tab.

    Tab structure:
      Rows 1-3:  settings  → col A = key, col B = value
      Row 4+:    weights   → col A = category, cols B-Y = Mo 1..Mo 24 weights
      The weight section starts after a row whose col A is "category".

    Weights are normalized in two halves: Mo 1-12 (year 1) and Mo 13-24 (year 2)
    independently, so each half sums to 1. Years 3+ repeat the year-2 pattern.
    """
    values = _ws(sh, TAB_MONTHLY_TIMING).get_all_values()
    settings = {}
    weights = {}
    in_weights = False

    def _normalize_half(raw):
        total = sum(raw)
        return [w / total for w in raw] if total > 0 else [1 / 12] * 12

    for row in values:
        if not row or not row[0]:
            continue
        if row[0] == "category":
            in_weights = True
            continue
        if in_weights:
            raw = [float(row[i + 1]) if i + 1 < len(row) and row[i + 1] != "" else 0.0
                   for i in range(24)]
            weights[row[0]] = _normalize_half(raw[:12]) + _normalize_half(raw[12:])
        else:
            if len(row) >= 2 and row[1] != "":
                settings[row[0]] = row[1]

    return {
        "start_year":  int(settings.get("start_year",  2026)),
        "start_month": int(settings.get("start_month", 1)),
        "num_months":  int(settings.get("num_months",  24)),
        "weights":     weights,
    }


def write_monthly_plan(sh, results):
    """Write monthly plans to the Monthly Plan tab.

    results: list of (label, monthly_rows) where monthly_rows is a list of dicts.
    """
    ws = _ws(sh, TAB_MONTHLY_PLAN)
    ws.clear()

    all_rows = []
    for label, monthly_rows in results:
        month_labels = [r["Month"] for r in monthly_rows]
        all_rows.append([f"=== {label} ==="])
        all_rows.append(["Metric"] + month_labels)
        for col in MONTHLY_LINE_ITEMS:
            all_rows.append([col] + [round(r.get(col, 0)) for r in monthly_rows])
        all_rows.append([])
        all_rows.append([])

    if all_rows:
        ws.update("A1", all_rows)
