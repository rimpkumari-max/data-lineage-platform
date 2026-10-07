"""App 3 - YXY (System of Record).
1. FILTER   business_group_cd = <group> and filemonth_dt = <file month>   (sheet: YXY filtration logic)
2. DEDUPE   one row per clrty_id (first one wins)
3. VALIDATE amount present and not negative, PIF inputs present, account master row found
4. MAP      DAO columns -> YXY columns (workout_completed_cd -> treatment_cd, settlement_am -> outstanding_balance)
5. CREATE   account numbers and interest from the YXY account master ('Created / Database Inserted' in the sheet)"""
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from app import csvio, db, rules, sample_data as sd

app = FastAPI(title="3 - YXY (SOR)", description="Filter, validate, map and complete the DAO extract.")


@app.get("/source")
def source():
    s = db.get_kv("source_accounts")
    return {"kind": "uploaded" if s else "sample", "filename": s["filename"] if s else None, "rows": len(s["rows"]) if s else len(sd.account_master())}


@app.get("/account-master.csv")
def sample_csv():
    return Response(csvio.to_csv(sd.account_master(), csvio.ACCOUNT_COLS), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="account_master_sample.csv"'})


@app.post("/upload-account-master")
async def upload(file: UploadFile = File(...)):
    try:
        rows = csvio.parse_accounts((await file.read()).decode("utf-8-sig"))
    except (csvio.CsvError, UnicodeDecodeError) as e:
        raise HTTPException(422, str(e))
    db.set_kv("source_accounts", {"filename": file.filename, "rows": rows})
    return {"kind": "uploaded", "filename": file.filename, "rows": len(rows)}


@app.delete("/source")
def clear_source():
    db.del_kv("source_accounts")
    return source()


@app.post("/run")
def run():
    dao = db.get_rows("dao")
    if not dao:
        raise HTTPException(409, "DAO layer is empty. Run DAO first.")
    p = db.params()
    s = db.get_kv("source_accounts")
    accounts = {r["clrty_id"]: r for r in (s["rows"] if s else sd.account_master())}
    out, rejects, filtered, dups, seen = [], [], 0, 0, set()
    for r in dao:
        if r["business_group_cd"] != p["business_group"] or r["filemonth_dt"] != p["file_month"]:
            filtered += 1
            continue
        if r["clrty_id"] in seen:
            dups += 1
            continue
        seen.add(r["clrty_id"])
        reason = None
        if r["settlement_am"] is None:
            reason = "MISSING_SETTLEMENT_AM"
        elif r["settlement_am"] < 0:
            reason = "NEGATIVE_SETTLEMENT_AM"
        elif any(r[f] is None for f in rules.PIF_INPUTS):
            reason = "MISSING_PIF_INPUT"
        elif r["clrty_id"] not in accounts or accounts[r["clrty_id"]]["interest_amt"] is None:
            reason = "NO_ACCOUNT_MASTER_ROW"
        if reason:
            rejects.append({"clrty_id": r["clrty_id"], "reason": reason, "raw": r})
            continue
        row = {dst: r[src] for src, dst in rules.DAO_TO_YXY}
        row.update({k: accounts[r["clrty_id"]][k] for k in rules.YXY_CREATED})
        out.append(row)
    db.set_rows("yxy", out)
    db.set_rows("yxy_rejects", rejects)
    return db.set_run("yxy", {"stage": "yxy", "run_at": db.now(), "rows_in": len(dao), "rows_out": len(out), "rejected": len(rejects),
                              "filtered": filtered, "duplicates_removed": dups,
                              "notes": [f"Filter: business_group_cd = '{p['business_group']}' and filemonth_dt = {p['file_month']}: {filtered} rows filtered out",
                                        f"{dups} duplicate clrty_id removed"] + [f"Rejected {x['clrty_id']}: {x['reason']}" for x in rejects]})


@app.get("/output")
def output():
    return {"layer": "YXY", "rows": db.get_rows("yxy"), "rejects": db.get_rows("yxy_rejects")}
