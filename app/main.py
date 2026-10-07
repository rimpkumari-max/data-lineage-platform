"""Data Lineage Platform: ONE FastAPI application hosting SIX applications.

  /catalog -> /dao -> /yxy -> /aoc -> /mis -> /controls      (each a FastAPI sub-app with its own /docs)
  /api/*   orchestration and trace endpoints used by the frontend
  /        frontend
"""
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db, rules
from app.apps import catalog, dao, yxy, aoc, mis, controls

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Data Lineage Platform", version="1.0")
APPS = {"catalog": catalog, "dao": dao, "yxy": yxy, "aoc": aoc, "mis": mis, "controls": controls}
for name, sub in APPS.items():
    app.mount(f"/{name}", sub.app)


@app.post("/api/run-all")
def run_all(inject_fault: bool = False, file_month: str | None = None, business_group: str | None = None):
    db.reset()
    db.set_kv("fault", inject_fault)
    p = {}
    if file_month:
        p["file_month"] = file_month
    if business_group:
        p["business_group"] = business_group
    if p:
        db.set_kv("params", {**db.get_kv("params", {}), **p})
    return {"runs": [APPS[n].run() for n in db.ORDER]}


@app.post("/api/reset")
def reset():
    db.reset()
    return {"status": "reset"}


@app.post("/api/reset-sources")
def reset_sources():
    db.del_kv("source_dao")
    db.del_kv("source_accounts")
    db.del_kv("params")
    return {"status": "sources reset to sample data"}


@app.get("/api/status")
def status():
    return {"runs": db.get_kv("runs", {}), "order": db.ORDER, "fault": db.get_kv("fault", False), "params": db.params(),
            "sources": {"dao": dao.source(), "accounts": yxy.source()}}


@app.get("/api/rules")
def get_rules():
    return {"pif_closure_codes": sorted(rules.PIF_CLOSURE_CODES), "cde_map": rules.CDE_MAP}


@app.get("/api/trace/{clrty_id}")
def trace(clrty_id: int):
    """One record, every hop, using the physical field names from the lineage sheet."""
    def first(layer, key="clrty_id"):
        return next((r for r in db.get_rows(layer) if r[key] == clrty_id), None)
    rec = {"dao": first("dao"), "yxy": first("yxy"), "aoc": first("aoc"), "mis": first("mis", "Clarity ID")}
    rej = [r for r in db.get_rows("yxy_rejects") if r["clrty_id"] == clrty_id]
    if not any(rec.values()):
        raise HTTPException(404, f"Clarity ID {clrty_id} not found. Run the pipeline first.")
    rows = [{"cde": m["cde"], "action": m["action"],
             **{h: ({"field": m[h], "value": (rec[h] or {}).get(m[h])} if m[h] else None) for h in ("dao", "yxy", "aoc", "mis")}}
            for m in rules.CDE_MAP]
    return {"clrty_id": clrty_id, "reached": [h for h in ("dao", "yxy", "aoc", "mis") if rec[h]], "rejected": rej, "rows": rows,
            "filtered_out": bool(rec["dao"]) and not rec["yxy"] and not rej}


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")
