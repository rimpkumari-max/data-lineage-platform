# Data Lineage Platform

A Python and FastAPI application that turns a data lineage sheet into something that runs. One application hosts six small applications that move data through **DAO (SOO) → YXY (SOR) → AOC (APP) → MIS Report** and then prove the result is right.

| Mount | App | What it does |
|---|---|---|
| `/catalog` | CDE Catalog | Loads the lineage sheet (`data/cde_lineage.json`), flags documentation gaps, generates Mermaid |
| `/dao` | DAO (SOO) | Source extract using the real column names. Sample data, or your own CSV |
| `/yxy` | YXY (SOR) | Filters by business group and file month, removes duplicates, rejects bad rows, maps columns, adds account numbers |
| `/aoc` | AOC (APP) | Renames columns, derives `settlement_amount = outstanding_bal + interest_amount` and the `PIF` flag |
| `/mis` | MIS Report | Builds the report and exports `MIS_14MQ.xlsx` |
| `/controls` | Controls | Recomputes from the source and reconciles DAO to the report |

Tech: Python, FastAPI, SQLite, plain HTML/CSS/JavaScript, openpyxl, Mermaid, pytest.

## Run it

```
python -m venv venv
venv\Scripts\activate          # Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 and click **Run full pipeline**. Each app has Swagger docs at `/<app>/docs`.

## Test it

```
pip install pytest httpx
python -m pytest -q
```

## Use your own data

On the page, under **Source data and parameters**, download the sample CSVs to see the expected columns, then upload your own. Set the file month and business group to match your data.

## Things to confirm with the business

- **PIF rule.** The sheet marks PIF as derived but gives no logic. The rule in `app/rules.py` is an assumption.
- **Settlement logic.** The sheet says `settlement_amount+interest_amount`, but `settlement_amount` is not a field at AOC. The app uses `outstanding_bal + interest_amount`.
- **AOC names** for Child and Ledger account numbers are blank in the sheet. The app uses `child_account_number` and `ledger_account_number`.
- `data/cde_lineage.json` was recovered from a picture of the sheet. Verify it against the original.

## Notes

- All built-in data is made up. It uses the real column names but no client information.
- Results are stored in SQLite (`lineage.db`, not committed). For production volumes, use a proper database.


## Diagrams

Architecture and lineage diagrams (Mermaid, drawn by GitHub): [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
