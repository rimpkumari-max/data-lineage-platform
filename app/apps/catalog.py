"""App 1 - CDE Catalog and Lineage Registry.
Loads the lineage sheet, checks it for documentation gaps, and generates Mermaid lineage diagrams."""
import json, re
from pathlib import Path
from fastapi import FastAPI, HTTPException
from app import db, rules

app = FastAPI(title="1 - CDE Catalog", description="Lineage registry built from the CDE sheet, with documentation checks and Mermaid output.")
DATA = Path(__file__).resolve().parent.parent.parent / "data" / "cde_lineage.json"

VOCAB = set("""account number child ledger treatment interest outstanding balance bal settlement amount am cd in dt id nm chld ldgr
clrty gross charge off active closure reason code sale date file month source system pif sold onhand business group workout completed
yxy aoc mis servicing regulatory filemonth amt accountnumber pif2 dao""".split())
DERIVED_FROM = {"Settlement Amount": ["Outstanding Balance", "Interest Amount"]}
PIF_INPUTS_LABEL = "account_gross_balance_am, charge_off_in,<br/>active_in, closure_reason_cd"


def load():
    return json.loads(DATA.read_text(encoding="utf-8"))


def findings(cat):
    out = []
    de_by_hop = {h["key"]: {(l["hops"][h["key"]] or {}).get("de_name") for c in cat["cdes"] for l in c["lines"] if l["hops"][h["key"]]} for h in cat["hops"]}
    for c in cat["cdes"]:
        for l in c["lines"]:
            for hop, d in l["hops"].items():
                if not d:
                    continue
                de = d.get("de_name")
                if d.get("business_name") and not de:
                    out.append({"severity": "WARN", "cde": c["name"], "hop": hop, "issue": "Data element name is blank although the hop is documented"})
                if de:
                    bad = [t for t in re.split(r"[_\s]+", de.lower()) if t and t not in VOCAB]
                    if bad:
                        out.append({"severity": "WARN", "cde": c["name"], "hop": hop, "issue": f"Possible typo in data element name '{de}' (unrecognised: {', '.join(bad)})"})
                if d.get("manual_derived") and "Derived" in d["manual_derived"] and not d.get("transform_logic"):
                    out.append({"severity": "WARN", "cde": c["name"], "hop": hop, "issue": f"'{de}' is marked Derived but no transformation logic is documented"})
                logic = d.get("transform_logic")
                if logic and d.get("transformed") == "Yes" and "select" not in logic.lower():
                    refs = set(re.findall(r"[a-z_]+", logic.lower()))
                    known = {n.lower() for n in de_by_hop.get(hop, set()) if n}
                    for ref in sorted(refs - known):
                        out.append({"severity": "WARN", "cde": c["name"], "hop": hop,
                                    "issue": f"Logic '{logic}' references '{ref}', which is not a data element at {hop}. The app uses outstanding_bal + interest_amount instead"})
        if not c["lineage_flow"]:
            out.append({"severity": "INFO", "cde": c["name"], "hop": "-", "issue": "No lineage flow documented"})
        elif c["lineage_flow"].startswith("YXY") or c["lineage_flow"].startswith("AOC"):
            out.append({"severity": "INFO", "cde": c["name"], "hop": "DAO", "issue": "Not documented at DAO: lineage starts later (created downstream)"})
    seen, uniq = set(), []
    for x in out:
        k = (x["cde"], x["hop"], x["issue"])
        if k not in seen:
            seen.add(k)
            uniq.append(x)
    return uniq


def mermaid(cde_name=None):
    """Mermaid lineage for one CDE (with its derivation inputs) or for all CDEs."""
    if cde_name is None:
        wanted = [m["cde"] for m in rules.CDE_MAP]
    else:
        if cde_name not in {m["cde"] for m in rules.CDE_MAP}:
            raise HTTPException(404, "Unknown CDE")
        wanted = DERIVED_FROM.get(cde_name, []) + [cde_name]
    lines, ids = ["flowchart LR"], {}
    for m in rules.CDE_MAP:
        if m["cde"] not in wanted:
            continue
        prev = None
        for hop in ("dao", "yxy", "aoc", "mis"):
            f = m[hop]
            if not f:
                continue
            nid = f"{hop.upper()}_{len(ids)}"
            ids[(m["cde"], hop)] = nid
            lines.append(f'  {nid}["{hop.upper()}<br/>{f}"]')
            if prev:
                lines.append(f"  {prev} --> {nid}")
            prev = nid
    for target, inputs in DERIVED_FROM.items():
        if target in wanted:
            for i in inputs:
                lines.append(f"  {ids[(i, 'aoc')]} -->|input| {ids[(target, 'aoc')]}")
    if "PIF" in wanted:
        lines.append(f'  PIF_IN["DAO and YXY<br/>{PIF_INPUTS_LABEL}"]')
        lines.append(f"  PIF_IN -->|derive| {ids[('PIF', 'aoc')]}")
    return "\n".join(lines)


@app.post("/run")
def run():
    cat = load()
    f = findings(cat)
    db.set_kv("catalog", {"catalog": cat, "findings": f})
    n_lines = sum(len(c["lines"]) for c in cat["cdes"])
    return db.set_run("catalog", {"stage": "catalog", "run_at": db.now(), "rows_in": n_lines, "rows_out": len(cat["cdes"]),
                                  "rejected": sum(1 for x in f if x["severity"] in ("WARN", "FAIL")),
                                  "notes": [f"{x['severity']} {x['cde']} @ {x['hop']}: {x['issue']}" for x in f if x["severity"] != "INFO"]})


@app.get("/output")
def output():
    return db.get_kv("catalog", {})


@app.get("/mermaid")
def mermaid_all():
    return {"mermaid": mermaid(None)}


@app.get("/mermaid/{cde}")
def mermaid_one(cde: str):
    return {"mermaid": mermaid(cde)}
