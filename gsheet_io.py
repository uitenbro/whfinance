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
TAB_ELECTRONICS  = "Electronics Scenarios"
TAB_FINANCE      = "Finance Scenarios"
TAB_COMBINATIONS    = "Scenario Combinations"
TAB_OUTPUT          = "Annual Cash Flow"
TAB_MONTHLY_TIMING  = "Timing"
TAB_MONTHLY_PLAN    = "Monthly Cash Flow"
TAB_PL_ANNUAL       = "Annual P&L"
TAB_PL_MONTHLY      = "Monthly P&L"

INTEGER_ROWS = ("Dragonfly Units", "Ravenity Units", "Eterna Missions", "SparV Units", "Electronics Units", "Engineers",
                "Dragonfly Techs", "Eterna Techs", "Ravenity Techs", "SparV Techs", "Electronics Techs", "Total Techs")

MONTHLY_LINE_ITEMS = [
    "Engineering Cost", "Business Dev Cost", "Other Costs",
    "Dragonfly Maturation", "Dragonfly Expenses", "Dragonfly Revenue",
    "Eterna Maturation",    "Eterna Expenses",    "Eterna Revenue",
    "Ravenity Maturation",  "Ravenity Expenses",  "Ravenity Revenue",
    "SparV Maturation",     "SparV Expenses",     "SparV Revenue",
    "Electronics Maturation", "Electronics Expenses", "Electronics Revenue",
    "Dragonfly Units", "Eterna Missions", "Ravenity Units", "SparV Units", "Electronics Units",
    "Dragonfly Techs", "Eterna Techs", "Ravenity Techs", "SparV Techs", "Electronics Techs", "Total Techs",
    "Grant Revenue", "SW Dev Revenue",
    "Total Expenses", "Total Revenue", "Net Cashflow",
    "Cumulative Cashflow", "Capital Needed", "Cumulative Capital",
]

MONTHLY_PL_LINE_ITEMS = [
    "Dragonfly Units Sold", "Eterna Missions Sold", "Ravenity Units Sold", "SparV Units Sold",
    "Electronics Units Sold",
    "Grant Revenue", "SW Dev Revenue",
    "Dragonfly Revenue", "Eterna Revenue", "Ravenity Revenue", "SparV Revenue", "Electronics Revenue",
    "Total Revenue",
    "Dragonfly COGS", "Eterna COGS", "Ravenity COGS", "SparV COGS", "Electronics COGS",
    "Total COGS",
    "Gross Profit",
    "Engineering Cost", "Business Dev Cost", "Other Costs",
    "Dragonfly Maturation", "Eterna Maturation", "Ravenity Maturation", "SparV Maturation",
    "Electronics Maturation",
    "Total OpEx",
    "Net Operating Income",
    "Cumulative NOI",
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


def _int(v):
    return int(float(v))


def read_dragonfly_scenarios(sh):
    return [{
        "label":                      r["label"],
        "price":                      float(r["price"]),
        "cost":                       float(r["cost"]),
        "initial_units":              _int(r["initial_units"]),
        "growth":                     float(r["growth"]),
        "production_per_tech_daily":  float(r.get("production_per_tech_daily") or 0),
        "maturation_cost":            float(r["maturation_cost"]),
        "maturation_start_month":     _int(r["maturation_start_month"]),
        "maturation_duration_months": _int(r["maturation_duration_months"]),
        "cogs_start_month":           _int(r["cogs_start_month"]),
        "revenue_lag_months":         _int(r["revenue_lag_months"]),
    } for r in _records_transposed(sh, TAB_DRAGONFLY)]


def read_eterna_scenarios(sh):
    return [{
        "label":                      r["label"],
        "missions_per_year":          _int(r["missions_per_year"]),
        "mission_growth_per_year":    _int(r["mission_growth_per_year"]),
        "avg_revenue_per_mission":    float(r["avg_revenue_per_mission"]),
        "avg_cost_per_mission":       float(r["avg_cost_per_mission"]),
        "baseline_cost":              float(r["baseline_cost"]),
        "production_per_tech_daily":  float(r.get("production_per_tech_daily") or 0),
        "maturation_cost":            float(r["maturation_cost"]),
        "maturation_start_month":     _int(r["maturation_start_month"]),
        "maturation_duration_months": _int(r["maturation_duration_months"]),
        "cogs_start_month":           _int(r["cogs_start_month"]),
        "revenue_lag_months":         _int(r["revenue_lag_months"]),
    } for r in _records_transposed(sh, TAB_ETERNA)]


def read_ravenity_scenarios(sh):
    return [{
        "label":                      r["label"],
        "price":                      float(r["price"]),
        "cost":                       float(r["cost"]),
        "initial_units":              _int(r["initial_units"]),
        "growth":                     float(r["growth"]),
        "production_per_tech_daily":  float(r.get("production_per_tech_daily") or 0),
        "maturation_cost":            float(r["maturation_cost"]),
        "maturation_start_month":     _int(r["maturation_start_month"]),
        "maturation_duration_months": _int(r["maturation_duration_months"]),
        "cogs_start_month":           _int(r["cogs_start_month"]),
        "revenue_lag_months":         _int(r["revenue_lag_months"]),
    } for r in _records_transposed(sh, TAB_RAVENITY)]


def read_sparv_scenarios(sh):
    return [{
        "label":                      r["label"],
        "price":                      float(r["price"]),
        "cost":                       float(r["cost"]),
        "initial_units":              _int(r["initial_units"]),
        "growth":                     float(r["growth"]),
        "production_per_tech_daily":  float(r.get("production_per_tech_daily") or 0),
        "maturation_cost":            float(r["maturation_cost"]),
        "maturation_start_month":     _int(r["maturation_start_month"]),
        "maturation_duration_months": _int(r["maturation_duration_months"]),
        "cogs_start_month":           _int(r["cogs_start_month"]),
        "revenue_lag_months":         _int(r["revenue_lag_months"]),
    } for r in _records_transposed(sh, TAB_SPARV)]


def read_electronics_products(sh):
    """Read the Electronics Scenarios tab. Returns a list of enabled product dicts.

    Tab layout:
      Top section  — key/value rows: col A = setting name, col B = value.
                     Any field can have a default: default_price, default_cost, etc.
      Separator    — a row with "Products" in col A signals the end of defaults;
                     the very next row is the column-header row (include, label, price, …).
      Product rows — one product per row after the header; blank cells inherit the
                     matching global default.
    """
    try:
        values = _ws(sh, TAB_ELECTRONICS).get_all_values()
    except Exception:
        return []
    if not values:
        return []

    # Scan for global defaults; stop at the "Products" sentinel row.
    defaults = {}
    header_idx = None
    for i, row in enumerate(values):
        if not row or not row[0].strip():
            continue
        if row[0].strip().lower() == "products":
            # The column-header row (include, label, …) is immediately after.
            if i + 1 < len(values):
                header_idx = i + 1
            break
        if len(row) >= 2 and row[1].strip():
            defaults[row[0].strip()] = row[1].strip()

    if header_idx is None:
        return []

    headers = [h.strip() for h in values[header_idx]]

    def _v(record, key, default_key=None):
        """Return the cell value, falling back to a global default if blank."""
        val = record.get(key, "").strip()
        if not val and default_key:
            val = defaults.get(default_key, "").strip()
        return val

    products = []
    for row in values[header_idx + 1:]:
        if not row or not row[0].strip():
            continue
        record = {headers[j]: (row[j].strip() if j < len(row) else "") for j in range(len(headers))}

        if str(record.get("include", "")).upper() not in ("TRUE", "YES", "1", "Y"):
            continue

        products.append({
            "label":                      record.get("label", "").strip(),
            "price":                      float(_v(record, "price",                      "default_price")                      or 0),
            "cost":                       float(_v(record, "cost",                       "default_cost")                       or 0),
            "initial_units":              _int(_v(record,  "initial_units",              "default_initial_units")              or 0),
            "growth":                     float(_v(record, "growth",                     "default_growth")                     or 1.0),
            "maturation_cost":            float(_v(record, "maturation_cost",            "default_maturation_cost")            or 0),
            "maturation_start_month":     _int(_v(record,  "maturation_start_month",     "default_maturation_start_month")     or 1),
            "maturation_duration_months": max(1, _int(_v(record, "maturation_duration_months", "default_maturation_duration_months") or 1)),
            "cogs_start_month":           _int(_v(record,  "cogs_start_month",           "default_cogs_start_month")           or 1),
            "revenue_lag_months":         _int(_v(record,  "revenue_lag_months",         "default_revenue_lag_months")         or 0),
            "production_per_tech_daily":  float(_v(record, "production_per_tech_daily",  "default_production_per_tech_daily")  or 0),
        })

    return products


def read_finance_scenarios(sh):
    result = []
    for r in _records_transposed(sh, TAB_FINANCE):
        result.append({
            "label":                            r["label"],
            "fte_count_by_year":                [_int(r[f"fte_count_yr{i}"]) for i in range(1, TOTAL_YEARS + 1)],
            "fte_cost_per":                     float(r["fte_cost_per"]),
            "business_dev_cost_year":           [float(r[f"biz_dev_cost_yr{i}"]) for i in range(1, TOTAL_YEARS + 1)],
            "sw_development_customers":         [_int(r[f"sw_dev_customers_yr{i}"]) for i in range(1, TOTAL_YEARS + 1)],
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
        el = r.get("electronics", "TRUE")
        result.append({
            "label":       r.get("label") or None,
            "dragonfly":   r.get("dragonfly") or None,
            "eterna":      r.get("eterna")    or None,
            "ravenity":    r.get("ravenity")  or None,
            "sparv":       r.get("sparv")     or None,
            "electronics": str(el).upper() not in ("FALSE", "0", "NO"),
            "finance":     r["finance"],
        })
    return result


def write_output(sh, results):
    """Write all scenario results to the Output tab."""
    ws = _ws(sh, TAB_OUTPUT)
    ws.clear()

    all_rows = []
    for (label, df_result, investment, total_return, roi, moic, payback_year) in results:
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
    """Read start_year, start_month, num_months from the Monthly Timing tab settings rows."""
    values = _ws(sh, TAB_MONTHLY_TIMING).get_all_values()
    settings = {}
    for row in values:
        if not row or not row[0] or row[0] == "category":
            break
        if len(row) >= 2 and row[1] != "":
            settings[row[0]] = row[1]
    return {
        "start_year":  _int(settings.get("start_year",  2026)),
        "start_month": _int(settings.get("start_month", 1)),
        "num_months":  _int(settings.get("num_months",  TOTAL_YEARS * 12)),
    }


def write_monthly_plan(sh, results):
    """Write monthly cash flow plans to the Monthly Cash Flow tab."""
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


def write_pl_output(sh, results):
    """Write P&L annual results to the Annual P&L tab."""
    ws = _ws(sh, TAB_PL_ANNUAL)
    ws.clear()

    all_rows = []
    for (label, pl_df_result, investment, total_return, roi, moic, payback_year) in results:
        all_rows.append([f"=== {label} ==="])
        all_rows.append(["Metric"] + list(pl_df_result.columns))
        for row_name in pl_df_result.index:
            row_vals = [row_name]
            for col in pl_df_result.columns:
                val = pl_df_result.loc[row_name, col]
                row_vals.append(int(val) if row_name in INTEGER_ROWS else round(float(val), 2))
            all_rows.append(row_vals)
        all_rows.append([])
        all_rows.append([])

    if all_rows:
        ws.update("A1", all_rows)


def write_pl_monthly(sh, results):
    """Write P&L monthly plans to the Monthly P&L tab."""
    ws = _ws(sh, TAB_PL_MONTHLY)
    ws.clear()

    all_rows = []
    for label, pl_monthly_rows in results:
        month_labels = [r["Month"] for r in pl_monthly_rows]
        all_rows.append([f"=== {label} ==="])
        all_rows.append(["Metric"] + month_labels)
        for col in MONTHLY_PL_LINE_ITEMS:
            all_rows.append([col] + [round(r.get(col, 0)) for r in pl_monthly_rows])
        all_rows.append([])
        all_rows.append([])

    if all_rows:
        ws.update("A1", all_rows)
