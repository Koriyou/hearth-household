# Hearth — household management

A local household app based on the architecture of `Beyond/campaign_app`: Streamlit UI, a separate SQLite storage module, explicit creation/deletion actions, recurring records, and portable backups. The implementation is independent of Beyond and does not import campaign records, credentials, or integrations.

## Start on Windows

Install dependencies once:

```powershell
python -m pip install -r requirements.txt
```

Double-click **Household App.bat**, or run:

```powershell
python -m streamlit run household_app/app.py --server.port 8502
```

Open http://localhost:8502. Port 8502 lets this app run alongside Beyond on 8501. The server listens on this computer only.

## What is included

- Overview of due chores, unpaid bills, shopping, and low stock.
- Chores with household assignments, due dates, notes, editing, completion history, and recurrence in days.
- Bills with amounts, due dates, notes, paid history, and monthly recurrence. Amounts are stored in integer cents. Payments are recorded manually.
- Shopping grouped by category, purchased history, and a downloadable text list.
- Inventory with quantities, units, locations, restock thresholds, and add-to-shopping actions.
- Searchable, editable household notes.
- Household members, currency label (MAD initially), and complete database downloads.

The app starts empty. Add members in **Household & backups**, then use the add panels on each page. Changes require Save/Add; deletions require confirmation. Chore completion creates the next occurrence after today, skipping missed occurrences. Paying a monthly bill creates the next calendar month's occurrence, clamping the date for shorter months. Subsequent occurrences use that clamped date. Completed and paid history remain visible through the page's checkbox. Shopping purchases do not automatically change inventory quantities.

## Data and backups

Records live in `data/household.sqlite3` and survive restarts. `HOUSEHOLD_DB` can override the database path. Dates use Africa/Casablanca time. This is a local app with one shared household; it has no sign-in, cloud sync, notifications, or external account connections.

Download a consistent SQLite backup from **Household & backups**. To restore:

1. Stop the app (Ctrl+C in its terminal).
2. Keep a copy of the current `data/household.sqlite3`.
3. Copy the downloaded backup to `data/household.sqlite3`, replacing the file.
4. Restart the app.

Keep database copies private; they contain your household information. The `data` directory is excluded from Git.

## Verification

```powershell
python -m unittest discover -s tests -v
```

Tests cover recurrence, duplicate completion, money persistence, validation, backups, page rendering, and adding/completing a chore. UI and domain code are separated in `household_app/app.py` and `household_app/store.py`.
