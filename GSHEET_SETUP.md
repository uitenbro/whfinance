# Google Sheets Setup Guide

## 1. Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Click **New Project**, give it a name (e.g. `whfinance`), click **Create**
3. Make sure your new project is selected in the top-left dropdown

## 2. Enable APIs

1. Go to **APIs & Services → Enable APIs & Services**
2. Search for and enable both:
   - **Google Sheets API**
   - **Google Drive API**

## 3. Configure the OAuth Consent Screen

1. Go to **APIs & Services → OAuth consent screen**
2. Choose **External**, click **Create**
3. Fill in:
   - App name: `whfinance`
   - User support email: your email
   - Developer contact email: your email
4. Click **Save and Continue** through the remaining steps (defaults are fine)
5. On the **Test users** step, add your Google account email, then **Save and Continue**

## 4. Create OAuth Credentials

1. Go to **APIs & Services → Credentials**
2. Click **+ Create Credentials → OAuth client ID**
3. Application type: **Desktop app**
4. Name: `whfinance` (or anything)
5. Click **Create**
6. Click **Download JSON** on the confirmation dialog
7. **Rename the downloaded file to `credentials.json`** and place it in this project directory

## 5. Install Python Dependencies

```bash
pip install -r requirements.txt
```

## 6. Create the Google Sheet (one-time)

```bash
python setup_gsheet.py
```

This will:
- Open a browser tab asking you to authorize the app with your Google account
- Create a new Google Sheet called **"WHFinance Scenarios"** in your Drive
- Populate all scenario tabs with the current data
- Save the spreadsheet ID to `gsheet_config.json`

## 7. Run the Financial Model

```bash
python whfinance.py
```

Each run:
1. Reads all scenario data from the Google Sheet
2. Runs simulations for all enabled combinations
3. Prints results to the terminal and shows charts
4. Writes all results to the **Output** tab of the sheet

---

## Sheet Structure

| Tab | Purpose |
|-----|---------|
| Dragonfly Scenarios | UAV product scenarios |
| Eterna Scenarios | Service mission scenarios |
| Ravenity Scenarios | Flight computer scenarios |
| SparV Scenarios | SparV product scenarios |
| Finance Scenarios | FTE counts, costs, and revenue by year |
| Scenario Combinations | Which scenarios to combine and run |
| Output | Results written by the script (do not edit) |

## Scenario Combinations Tab

| Column | Notes |
|--------|-------|
| `enabled` | Set to `FALSE` to skip a row without deleting it |
| `dragonfly` | Exact label from Dragonfly Scenarios tab, or leave blank |
| `eterna` | Exact label from Eterna Scenarios tab, or leave blank |
| `ravenity` | Exact label from Ravenity Scenarios tab, or leave blank |
| `sparv` | Exact label from SparV Scenarios tab, or leave blank |
| `finance` | Exact label from Finance Scenarios tab (required) |

## Finance Scenarios Tab

Year-by-year columns use the naming `fte_count_yr1` through `fte_count_yr7` (and similarly for `biz_dev_cost_yrN`, `sw_dev_customers_yrN`, `other_cost_yrN`). To change the number of years, update `TOTAL_YEARS` in `gsheet_io.py` and re-run `setup_gsheet.py`.

## Security Notes

The following files contain sensitive credentials and are excluded from git:

- `credentials.json` — OAuth client secret (keep private)
- `token.json` — cached OAuth token (auto-generated on first run)
- `gsheet_config.json` — spreadsheet ID
