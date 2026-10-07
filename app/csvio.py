"""CSV upload and download helpers for the two source tables."""
import csv, io

DAO_COLS = ["clrty_id", "filemonth_dt", "source_system_cd", "business_group_cd", "workout_completed_cd", "settlement_am",
            "account_gross_balance_am", "charge_off_in", "active_in", "closure_reason_cd", "sale_dt", "onhand_sold_cd"]
DAO_TYPES = {"clrty_id": int, "workout_completed_cd": int, "charge_off_in": int, "active_in": int, "closure_reason_cd": int,
             "onhand_sold_cd": int, "settlement_am": float, "account_gross_balance_am": float}
ACCOUNT_COLS = ["clrty_id", "account_nm", "chld_account_nm", "ldgr_account_nm", "interest_amt"]
ACCOUNT_TYPES = {"clrty_id": int, "account_nm": int, "chld_account_nm": int, "ldgr_account_nm": int, "interest_amt": float}


class CsvError(ValueError):
    pass


def parse(text, cols, types, required):
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise CsvError("The file is empty.")
    missing = [c for c in required if c not in reader.fieldnames]
    if missing:
        raise CsvError(f"Missing required column(s): {', '.join(missing)}. Expected columns: {', '.join(cols)}")
    rows = []
    for n, raw in enumerate(reader, start=2):
        row = {}
        for c in cols:
            v = (raw.get(c) or "").strip()
            if v == "":
                row[c] = None
                continue
            try:
                row[c] = types[c](v) if c in types else v
            except ValueError:
                raise CsvError(f"Row {n}: column '{c}' has value '{v}', expected {types[c].__name__}")
        if row.get("clrty_id") is None:
            raise CsvError(f"Row {n}: clrty_id is blank")
        rows.append(row)
    if not rows:
        raise CsvError("The file has a header but no data rows.")
    return rows


def parse_dao(text):
    return parse(text, DAO_COLS, DAO_TYPES, DAO_COLS)


def parse_accounts(text):
    return parse(text, ACCOUNT_COLS, ACCOUNT_TYPES, ACCOUNT_COLS)


def to_csv(rows, cols):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow(["" if r.get(c) is None else r.get(c) for c in cols])
    return buf.getvalue()
