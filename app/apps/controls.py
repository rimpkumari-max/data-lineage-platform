"""App 6 - Lineage Controls. Independently re-checks the pipeline end to end:
record counts, pass-through fields, derived fields (recomputed from the source), and documentation coverage."""
from fastapi import FastAPI, HTTPException
from app import db, rules

app = FastAPI(title="6 - Lineage Controls", description="Reconciles DAO to the MIS Report and flags breaks.")


def close(a, b):
    return a is not None and b is not None and abs(a - b) <= rules.TOLERANCE


def control(cid, name, checked, breaks, warn=False):
    status = "PASS" if not breaks else ("WARN" if warn else "FAIL")
    return {"id": cid, "name": name, "checked": checked, "failed": len(breaks), "status": status, "breaks": breaks[:25]}


@app.post("/run")
def run():
    mis = db.get_rows("mis")
    if not mis:
        raise HTTPException(409, "MIS layer is empty. Run the pipeline first.")
    p = db.params()
    dao = {r["clrty_id"]: r for r in db.get_rows("dao") if r["business_group_cd"] == p["business_group"] and r["filemonth_dt"] == p["file_month"]}
    yxy_rows, aoc_rows = db.get_rows("yxy"), db.get_rows("aoc")
    yxy = {r["clrty_id"]: r for r in yxy_rows}
    y = db.get_kv("runs", {})["yxy"]
    out = []

    br = []
    if y["rows_in"] != y["filtered"] + y["duplicates_removed"] + y["rejected"] + y["rows_out"]:
        br.append({"issue": "DAO rows are not fully accounted for at YXY (filtered + duplicates + rejected + passed)"})
    for a, b, an, bn in ((yxy_rows, aoc_rows, "YXY", "AOC"), (aoc_rows, mis, "AOC", "MIS")):
        if len(a) != len(b):
            br.append({"issue": f"{an} has {len(a)} rows but {bn} has {len(b)}"})
    out.append(control("C1", "Record counts reconcile DAO to MIS Report", 3, br))

    br, n = [], 0
    for m in mis:
        cid = m["Clarity ID"]
        d, yx = dao.get(cid), yxy.get(cid)
        if not d or not yx:
            br.append({"clrty_id": cid, "issue": "Report row has no source row"})
            continue
        for label, got, exp in (("Treatment", m["Treatment"], d["workout_completed_cd"]),
                                ("Outstanding Balance", m["Outstanding Balance"], d["settlement_am"]),
                                ("Account Number", m["Account Number"], yx["account_nm"]),
                                ("Child_AccountNumber", m["Child_AccountNumber"], yx["chld_account_nm"]),
                                ("Ledger_AccountNumber", m["Ledger_AccountNumber"], yx["ldgr_account_nm"]),
                                ("Interest Amount", m["Interest Amount"], yx["interest_amt"])):
            n += 1
            if not (close(got, exp) if isinstance(exp, float) else got == exp):
                br.append({"clrty_id": cid, "field": label, "report": got, "source": exp})
    out.append(control("C2", "Pass-through fields unchanged from source to report", n, br))

    br = []
    for m in mis:
        d, yx = dao.get(m["Clarity ID"]), yxy.get(m["Clarity ID"])
        if d and yx:
            exp = rules.settlement_amount(d["settlement_am"], yx["interest_amt"])
            if not close(m["Settlement Amount"], exp):
                br.append({"clrty_id": m["Clarity ID"], "report": m["Settlement Amount"], "recomputed": exp})
    out.append(control("C3", "Settlement Amount = settlement + interest, recomputed from source", len(mis), br))

    br = []
    for m in mis:
        d = dao.get(m["Clarity ID"])
        if d:
            exp = rules.pif_flag(d["active_in"], d["charge_off_in"], d["closure_reason_cd"], d["account_gross_balance_am"])
            if m["PIF"] != exp:
                br.append({"clrty_id": m["Clarity ID"], "report": m["PIF"], "recomputed": exp})
    out.append(control("C4", "PIF flag recomputed from source sub-fields", len(mis), br))

    br = []
    cat = (db.get_kv("catalog") or {}).get("catalog")
    if cat:
        documented = {(l["hops"]["MIS"] or {}).get("de_name") for c in cat["cdes"] for l in c["lines"]}
        for _, col in rules.AOC_TO_MIS:
            if col not in documented:
                br.append({"column": col, "issue": "Report column is not documented at the MIS hop in the lineage sheet"})
    out.append(control("C5", "Report columns documented in the lineage sheet", len(rules.AOC_TO_MIS), br, warn=True))

    summary = {"passed": sum(c["status"] == "PASS" for c in out), "warnings": sum(c["status"] == "WARN" for c in out),
               "failed": sum(c["status"] == "FAIL" for c in out)}
    db.set_kv("controls", {"controls": out, "summary": summary, "generated_at": db.now()})
    return db.set_run("controls", {"stage": "controls", "run_at": db.now(), "rows_in": len(mis), "rows_out": len(out), "rejected": summary["failed"],
                                   "notes": [f"{c['id']} {c['status']}: {c['name']} ({c['failed']} of {c['checked']})" for c in out]})


@app.get("/output")
def output():
    return db.get_kv("controls", {})
