"""App 4 - AOC (Authorized Provisioning Point). Renames to AOC names and DERIVES two business measures.
  settlement_amount = outstanding_bal + interest_amount        (sheet: AOC transformation logic)
  PIF               = paid-in-full flag from the sub-fields    (rule is an ASSUMPTION, see rules.py)"""
from fastapi import FastAPI, HTTPException
from app import db, rules

app = FastAPI(title="4 - AOC (APP)", description="Provisioning layer: renames and derives Settlement Amount and PIF.")


@app.post("/run")
def run():
    yxy = db.get_rows("yxy")
    if not yxy:
        raise HTTPException(409, "YXY layer is empty. Run YXY first.")
    out = []
    for r in yxy:
        row = {"clrty_id": r["clrty_id"], "filemonth_dt": r["filemonth_dt"]}
        row.update({dst: r[src] for src, dst in rules.YXY_TO_AOC.items()})
        row["settlement_amount"] = rules.settlement_amount(row["outstanding_bal"], row["interest_amount"])
        row["PIF"] = rules.pif_flag(r["active_in"], r["charge_off_in"], r["closure_reason_cd"], r["account_gross_balance_am"])
        out.append(row)
    fault = db.get_kv("fault", False)
    if fault and len(out) > 6:       # simulate a broken ETL so the controls have something to catch
        out[1]["settlement_amount"] = round(out[1]["settlement_amount"] + 100, 2)
        out[3]["Treatment"] = (out[3]["Treatment"] or 0) + 1
        out[5]["PIF"] = 1 - out[5]["PIF"]
    db.set_rows("aoc", out)
    return db.set_run("aoc", {"stage": "aoc", "run_at": db.now(), "rows_in": len(yxy), "rows_out": len(out), "rejected": 0,
                              "notes": ["Derived settlement_amount = outstanding_bal + interest_amount",
                                        "Derived PIF flag from active_in, charge_off_in, closure_reason_cd, account_gross_balance_am"]
                                       + (["FAULT INJECTED into 3 AOC records (demo)"] if fault else [])})


@app.get("/output")
def output():
    return {"layer": "AOC", "rows": db.get_rows("aoc")}
