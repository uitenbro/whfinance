#!/usr/bin/env python3
"""One-time setup: creates the WHFinance Google Sheet and populates it with scenario data.

Run this once after setting up credentials.json (see GSHEET_SETUP.md).
Re-running will create a new spreadsheet and overwrite gsheet_config.json.
"""

import json
import gspread
from gsheet_io import (
    CREDENTIALS_FILE, TOKEN_FILE, CONFIG_FILE, TOTAL_YEARS,
    TAB_DRAGONFLY, TAB_ETERNA, TAB_RAVENITY, TAB_SPARV,
    TAB_FINANCE, TAB_COMBINATIONS, TAB_OUTPUT,
)

SPREADSHEET_TITLE = "WHFinance Scenarios"

# ── Seed data (mirrors current whfinance.py hardcoded values) ──────────────────

dragonfly_scenarios = [
    {
        "label": "Dragonfly 125+35%",
        "price": 45000,
        "cost": 10000,
        "initial_units": 125,
        "growth": 1.35,
        "maturation_year": 2,
        "maturation_cost": 4000000,
    },
]

eterna_service_scenarios = [
    {
        "label": "Eterna 1/wk+2/wk Services",
        "missions_per_year": 52,
        "mission_growth_per_year": 104,
        "avg_revenue_per_mission": 50000,
        "avg_cost_per_mission": 10000,
        "baseline_cost": 25000,
        "maturation_year": 3,
        "maturation_cost": 4000000,
    },
    {
        "label": "Eterna 4/wk Services DoD",
        "missions_per_year": 4 * 52,
        "mission_growth_per_year": 52,
        "avg_revenue_per_mission": 55000,
        "avg_cost_per_mission": 20000,
        "baseline_cost": 500000,
        "maturation_year": 2,
        "maturation_cost": 6 * 300000 + 2000000,
    },
    {
        "label": "Eterna 4/wk Services DoD yr 4",
        "missions_per_year": 4 * 52,
        "mission_growth_per_year": 52,
        "avg_revenue_per_mission": 55000,
        "avg_cost_per_mission": 20000,
        "baseline_cost": 500000,
        "maturation_year": 4,
        "maturation_cost": 6 * 300000 + 2000000,
    },
]

ravenity_scenarios = [
    {
        "label": "Ravenity 2500+35%",
        "price": 1500,
        "cost": 500,
        "initial_units": 2500,
        "growth": 1.35,
        "maturation_year": 1,
        "maturation_cost": 2000000,
    },
]

sparv_scenarios = [
    {
        "label": "SparV 1500+25%",
        "price": 5000,
        "cost": 2500,
        "initial_units": 1500,
        "growth": 1.25,
        "start_year": 1,
        "maturation_cost": 1500000,
    },
]

financial_scenarios = [
    {
        "label": "Scale to 22 Engr and $1.2M Other Costs",
        "fte_count_by_year": [5, 11, 18, 22, 22, 22, 22],
        "fte_cost_per": 212500,
        "business_dev_cost_year": [600000, 750000, 1000000, 1000000, 1000000, 1000000, 1000000],
        "sw_development_customers": [0, 3, 5, 5, 5, 5, 5],
        "sw_revenue_per_customer_per_year": 1880 * 150,
        "other_cost_by_year": [400000, 800000, 1200000, 1200000, 1200000, 1200000, 1200000],
        "grant_revenue": 100000,
    },
]

scenario_combinations = [
    {
        "dragonfly": "Dragonfly 125+35%",
        "eterna": "Eterna 4/wk Services DoD",
        "ravenity": "Ravenity 2500+35%",
        "sparv": "SparV 1500+25%",
        "finance": "Scale to 22 Engr and $1.2M Other Costs",
    },
]

# ── Populate helpers (transposed: col A = field names, subsequent cols = scenarios) ────

def _transpose(field_names, scenarios, val_fn):
    """Build a transposed row list: each row is [field_name, val_for_s1, val_for_s2, ...]."""
    return [[f] + [val_fn(s, f) for s in scenarios] for f in field_names]


def _populate_dragonfly(ws, scenarios):
    fields = ["label", "price", "cost", "initial_units", "growth", "maturation_year", "maturation_cost"]
    ws.update("A1", _transpose(fields, scenarios, lambda s, f: s[f]))


def _populate_eterna(ws, scenarios):
    fields = ["label", "missions_per_year", "mission_growth_per_year",
              "avg_revenue_per_mission", "avg_cost_per_mission",
              "baseline_cost", "maturation_year", "maturation_cost"]
    ws.update("A1", _transpose(fields, scenarios, lambda s, f: s[f]))


def _populate_ravenity(ws, scenarios):
    fields = ["label", "price", "cost", "initial_units", "growth", "maturation_year", "maturation_cost"]
    ws.update("A1", _transpose(fields, scenarios, lambda s, f: s[f]))


def _populate_sparv(ws, scenarios):
    fields = ["label", "price", "cost", "initial_units", "growth", "start_year", "maturation_cost"]
    ws.update("A1", _transpose(fields, scenarios, lambda s, f: s[f]))


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


def _populate_combinations(ws, combinations):
    fields = ["enabled", "dragonfly", "eterna", "ravenity", "sparv", "finance"]
    values = {
        "enabled":   [True] * len(combinations),
        "dragonfly": [c.get("dragonfly") or "" for c in combinations],
        "eterna":    [c.get("eterna")    or "" for c in combinations],
        "ravenity":  [c.get("ravenity")  or "" for c in combinations],
        "sparv":     [c.get("sparv")     or "" for c in combinations],
        "finance":   [c["finance"]            for c in combinations],
    }
    ws.update("A1", [[f] + values[f] for f in fields])


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    gc = gspread.oauth(
        credentials_filename=CREDENTIALS_FILE,
        authorized_user_filename=TOKEN_FILE,
    )

    sh = gc.create(SPREADSHEET_TITLE)
    print(f"Created spreadsheet: {sh.url}\n")

    sh.sheet1.update_title(TAB_DRAGONFLY)
    for title in [TAB_ETERNA, TAB_RAVENITY, TAB_SPARV, TAB_FINANCE, TAB_COMBINATIONS, TAB_OUTPUT]:
        sh.add_worksheet(title=title, rows=100, cols=40)

    print(f"Populating {TAB_DRAGONFLY}...")
    _populate_dragonfly(sh.worksheet(TAB_DRAGONFLY), dragonfly_scenarios)

    print(f"Populating {TAB_ETERNA}...")
    _populate_eterna(sh.worksheet(TAB_ETERNA), eterna_service_scenarios)

    print(f"Populating {TAB_RAVENITY}...")
    _populate_ravenity(sh.worksheet(TAB_RAVENITY), ravenity_scenarios)

    print(f"Populating {TAB_SPARV}...")
    _populate_sparv(sh.worksheet(TAB_SPARV), sparv_scenarios)

    print(f"Populating {TAB_FINANCE}...")
    _populate_finance(sh.worksheet(TAB_FINANCE), financial_scenarios)

    print(f"Populating {TAB_COMBINATIONS}...")
    _populate_combinations(sh.worksheet(TAB_COMBINATIONS), scenario_combinations)

    with open(CONFIG_FILE, "w") as f:
        json.dump({"spreadsheet_id": sh.id}, f, indent=2)

    print(f"\nDone. Spreadsheet ID saved to '{CONFIG_FILE}'.")
    print(f"Open your sheet: {sh.url}")


if __name__ == "__main__":
    main()
