#!/usr/bin/env python3
"""One-time setup: creates the WHFinance Google Sheet and populates it with scenario data.

Run this once after setting up credentials.json (see GSHEET_SETUP.md).
Re-running will create a new spreadsheet and overwrite gsheet_config.json.

All start months in scenario tabs are plan-relative (1 = first month of the plan).
"""

import json
import os
import gspread
from gsheet_io import (
    CREDENTIALS_FILE, TOKEN_FILE, CONFIG_FILE, TOTAL_YEARS,
    TAB_DRAGONFLY, TAB_ETERNA, TAB_RAVENITY, TAB_SPARV, TAB_ELECTRONICS,
    TAB_FINANCE, TAB_COMBINATIONS, TAB_OUTPUT,
    TAB_MONTHLY_TIMING, TAB_MONTHLY_PLAN,
)

SPREADSHEET_TITLE = "WHFinance Scenarios"

# ── Seed data ─────────────────────────────────────────────────────────────────────
# All *_start_month values are plan-relative: 1 = first month of the plan (e.g. Jan 2026).
# maturation_duration_months: cost is spread evenly over this many months.
# revenue_lag_months: cash received this many months after the COGS month.

dragonfly_scenarios = [
    {
        "label":                      "Dragonfly 125+35%",
        "price":                      45000,
        "cost":                       10000,
        "initial_units":              125,
        "growth":                     1.35,
        "maturation_cost":            4000000,
        "maturation_start_month":     13,   # month 13 = start of plan year 2
        "maturation_duration_months": 12,
        "cogs_start_month":           25,   # month 25 = start of plan year 3
        "revenue_lag_months":         0,
    },
]

eterna_service_scenarios = [
    {
        "label":                      "Eterna 1/wk+2/wk Services",
        "missions_per_year":          52,
        "mission_growth_per_year":    104,
        "avg_revenue_per_mission":    50000,
        "avg_cost_per_mission":       10000,
        "baseline_cost":              25000,
        "maturation_cost":            4000000,
        "maturation_start_month":     25,   # month 25 = start of plan year 3
        "maturation_duration_months": 12,
        "cogs_start_month":           37,   # month 37 = start of plan year 4
        "revenue_lag_months":         0,
    },
    {
        "label":                      "Eterna 4/wk Services DoD",
        "missions_per_year":          4 * 52,
        "mission_growth_per_year":    52,
        "avg_revenue_per_mission":    55000,
        "avg_cost_per_mission":       20000,
        "baseline_cost":              500000,
        "maturation_cost":            6 * 300000 + 2000000,
        "maturation_start_month":     13,   # month 13 = start of plan year 2
        "maturation_duration_months": 12,
        "cogs_start_month":           25,   # month 25 = start of plan year 3
        "revenue_lag_months":         0,
    },
    {
        "label":                      "Eterna 4/wk Services DoD yr 4",
        "missions_per_year":          4 * 52,
        "mission_growth_per_year":    52,
        "avg_revenue_per_mission":    55000,
        "avg_cost_per_mission":       20000,
        "baseline_cost":              500000,
        "maturation_cost":            6 * 300000 + 2000000,
        "maturation_start_month":     37,   # month 37 = start of plan year 4
        "maturation_duration_months": 12,
        "cogs_start_month":           49,   # month 49 = start of plan year 5
        "revenue_lag_months":         0,
    },
]

ravenity_scenarios = [
    {
        "label":                      "Ravenity 2500+35%",
        "price":                      1500,
        "cost":                       500,
        "initial_units":              2500,
        "growth":                     1.35,
        "maturation_cost":            2000000,
        "maturation_start_month":     1,    # month 1 = start of plan year 1
        "maturation_duration_months": 12,
        "cogs_start_month":           13,   # month 13 = start of plan year 2
        "revenue_lag_months":         0,
    },
]

sparv_scenarios = [
    {
        "label":                      "SparV 1500+25%",
        "price":                      5000,
        "cost":                       2500,
        "initial_units":              1500,
        "growth":                     1.25,
        "maturation_cost":            1500000,
        "maturation_start_month":     1,    # month 1 = start of plan year 1
        "maturation_duration_months": 12,
        "cogs_start_month":           1,    # COGS begin same month as maturation
        "revenue_lag_months":         0,
    },
]

# Electronics Scenarios — row-per-product catalog.
# Defaults apply to any product row that leaves a field blank.
electronics_defaults = {
    "default_price":                      "",
    "default_cost":                       "",
    "default_initial_units":              "",
    "default_growth":                     1.10,
    "default_maturation_start_month":     1,
    "default_maturation_cost":            0,
    "default_maturation_duration_months": 12,
    "default_cogs_start_month":           13,
    "default_revenue_lag_months":         1,
    "default_production_per_tech_daily":  1,
}

# Seed with one disabled example row so the format is visible without affecting the model.
electronics_product_seeds = [
    {
        "include":                    False,
        "label":                      "Example Component",
        "price":                      500,
        "cost":                       150,
        "initial_units":              500,
        "growth":                     "",   # blank → inherits default_growth
        "production_per_tech_daily":  "",   # blank → inherits default
        "maturation_cost":            50000,
        "maturation_start_month":     "",   # blank → inherits default
        "maturation_duration_months": "",   # blank → inherits default
        "cogs_start_month":           "",   # blank → inherits default
        "revenue_lag_months":         "",   # blank → inherits default
    },
]

financial_scenarios = [
    {
        "label":                          "Scale to 22 Engr and $1.2M Other Costs",
        "fte_count_by_year":              [5, 11, 18, 22, 22, 22, 22],
        "fte_cost_per":                   212500,
        "business_dev_cost_year":         [600000, 750000, 1000000, 1000000, 1000000, 1000000, 1000000],
        "sw_development_customers":       [0, 3, 5, 5, 5, 5, 5],
        "sw_revenue_per_customer_per_year": 1880 * 150,
        "other_cost_by_year":             [400000, 800000, 1200000, 1200000, 1200000, 1200000, 1200000],
        "grant_revenue":                  100000,
    },
]

scenario_combinations = [
    {
        "label":       "Base Case",
        "dragonfly":   "Dragonfly 125+35%",
        "eterna":      "Eterna 4/wk Services DoD",
        "ravenity":    "Ravenity 2500+35%",
        "sparv":       "SparV 1500+25%",
        "electronics": True,
        "finance":     "Scale to 22 Engr and $1.2M Other Costs",
    },
]

# ── Populate helpers ──────────────────────────────────────────────────────────────

def _transpose(field_names, scenarios, val_fn):
    """Build transposed rows: each row is [field_name, val_s1, val_s2, ...]."""
    return [[f] + [val_fn(s, f) for s in scenarios] for f in field_names]


def _populate_dragonfly(ws, scenarios):
    fields = [
        "label", "price", "cost", "initial_units", "growth",
        "maturation_cost", "maturation_start_month", "maturation_duration_months",
        "cogs_start_month", "revenue_lag_months",
    ]
    ws.update("A1", _transpose(fields, scenarios, lambda s, f: s[f]))


def _populate_eterna(ws, scenarios):
    fields = [
        "label", "missions_per_year", "mission_growth_per_year",
        "avg_revenue_per_mission", "avg_cost_per_mission", "baseline_cost",
        "maturation_cost", "maturation_start_month", "maturation_duration_months",
        "cogs_start_month", "revenue_lag_months",
    ]
    ws.update("A1", _transpose(fields, scenarios, lambda s, f: s[f]))


def _populate_ravenity(ws, scenarios):
    fields = [
        "label", "price", "cost", "initial_units", "growth",
        "maturation_cost", "maturation_start_month", "maturation_duration_months",
        "cogs_start_month", "revenue_lag_months",
    ]
    ws.update("A1", _transpose(fields, scenarios, lambda s, f: s[f]))


def _populate_sparv(ws, scenarios):
    fields = [
        "label", "price", "cost", "initial_units", "growth",
        "maturation_cost", "maturation_start_month", "maturation_duration_months",
        "cogs_start_month", "revenue_lag_months",
    ]
    ws.update("A1", _transpose(fields, scenarios, lambda s, f: s[f]))


def _populate_electronics(ws, defaults, products):
    _PRODUCT_FIELDS = [
        "include", "label", "price", "cost", "initial_units", "growth",
        "production_per_tech_daily", "maturation_cost", "maturation_start_month",
        "maturation_duration_months", "cogs_start_month", "revenue_lag_months",
    ]
    rows = []
    for key, val in defaults.items():
        rows.append([key, val])
    rows.append([])             # blank row for visual separation
    rows.append(["Products"])   # sentinel — parser starts product table on the next row
    rows.append(_PRODUCT_FIELDS)
    for p in products:
        rows.append(
            ["TRUE" if p["include"] else "FALSE"] + [p.get(f, "") for f in _PRODUCT_FIELDS[1:]]
        )
    ws.update("A1", rows)


def _populate_finance(ws, scenarios):
    yr_list_fields = {
        **{f"fte_count_yr{i}":        ("fte_count_by_year",        i - 1) for i in range(1, TOTAL_YEARS + 1)},
        **{f"biz_dev_cost_yr{i}":     ("business_dev_cost_year",   i - 1) for i in range(1, TOTAL_YEARS + 1)},
        **{f"sw_dev_customers_yr{i}": ("sw_development_customers", i - 1) for i in range(1, TOTAL_YEARS + 1)},
        **{f"other_cost_yr{i}":       ("other_cost_by_year",       i - 1) for i in range(1, TOTAL_YEARS + 1)},
    }
    scalar_fields = ["label", "fte_cost_per", "sw_revenue_per_customer_per_year", "grant_revenue"]
    all_fields = scalar_fields + list(yr_list_fields)

    def val(s, f):
        if f in yr_list_fields:
            list_key, idx = yr_list_fields[f]
            return s[list_key][idx]
        return s[f]

    ws.update("A1", _transpose(all_fields, scenarios, val))


def _populate_monthly_timing(ws):
    ws.update("A1", [
        ["start_year",  2026],
        ["start_month", 1],
        ["num_months",  TOTAL_YEARS * 12],
    ])


def _populate_combinations(ws, combinations):
    fields = ["enabled", "label", "dragonfly", "eterna", "ravenity", "sparv", "electronics", "finance"]
    values = {
        "enabled":     [True] * len(combinations),
        "label":       [c.get("label")                  or "" for c in combinations],
        "dragonfly":   [c.get("dragonfly")              or "" for c in combinations],
        "eterna":      [c.get("eterna")                 or "" for c in combinations],
        "ravenity":    [c.get("ravenity")               or "" for c in combinations],
        "sparv":       [c.get("sparv")                  or "" for c in combinations],
        "electronics": [c.get("electronics", True)           for c in combinations],
        "finance":     [c["finance"]                         for c in combinations],
    }
    ws.update("A1", [[f] + values[f] for f in fields])


# ── Main ──────────────────────────────────────────────────────────────────────────

def main():
    gc = gspread.oauth(
        credentials_filename=CREDENTIALS_FILE,
        authorized_user_filename=TOKEN_FILE,
    )

    sh = gc.create(SPREADSHEET_TITLE)
    print(f"Created spreadsheet: {sh.url}\n")

    sh.sheet1.update_title(TAB_DRAGONFLY)
    for title in [TAB_ETERNA, TAB_RAVENITY, TAB_SPARV, TAB_ELECTRONICS, TAB_FINANCE,
                  TAB_COMBINATIONS, TAB_OUTPUT, TAB_MONTHLY_TIMING, TAB_MONTHLY_PLAN]:
        sh.add_worksheet(title=title, rows=100, cols=40)

    print(f"Populating {TAB_DRAGONFLY}...")
    _populate_dragonfly(sh.worksheet(TAB_DRAGONFLY), dragonfly_scenarios)

    print(f"Populating {TAB_ETERNA}...")
    _populate_eterna(sh.worksheet(TAB_ETERNA), eterna_service_scenarios)

    print(f"Populating {TAB_RAVENITY}...")
    _populate_ravenity(sh.worksheet(TAB_RAVENITY), ravenity_scenarios)

    print(f"Populating {TAB_SPARV}...")
    _populate_sparv(sh.worksheet(TAB_SPARV), sparv_scenarios)

    print(f"Populating {TAB_ELECTRONICS}...")
    _populate_electronics(sh.worksheet(TAB_ELECTRONICS), electronics_defaults, electronics_product_seeds)

    print(f"Populating {TAB_FINANCE}...")
    _populate_finance(sh.worksheet(TAB_FINANCE), financial_scenarios)

    print(f"Populating {TAB_COMBINATIONS}...")
    _populate_combinations(sh.worksheet(TAB_COMBINATIONS), scenario_combinations)

    print(f"Populating {TAB_MONTHLY_TIMING}...")
    _populate_monthly_timing(sh.worksheet(TAB_MONTHLY_TIMING))

    # Load existing config to carry forward history
    history = []
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            old = json.load(f)
        if old.get("spreadsheet_id"):
            history = old.get("history", [])
            history.append({
                "spreadsheet_id": old["spreadsheet_id"],
                "url":            old.get("url", ""),
                "created_at":     old.get("created_at", ""),
            })

    from datetime import datetime, timezone
    config = {
        "spreadsheet_id": sh.id,
        "url":            sh.url,
        "created_at":     datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "history":        history,
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\nDone. Spreadsheet ID saved to '{CONFIG_FILE}'.")
    print(f"Open your sheet: {sh.url}")


if __name__ == "__main__":
    main()
