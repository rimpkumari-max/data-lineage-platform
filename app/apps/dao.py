"""App 2 - DAO (System of Origination). Holds the source extract using the real DAO column names.
Uses the built-in sample unless a CSV has been uploaded."""
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from app import csvio, db, sample_data as sd

app = FastAPI(title="2 - DAO (SOO)", description="Source system extract. Loaded as-is, nothing is cleaned here.")


@app.get("/source")
def source():
    s = db.get_kv("source_dao")
    return {"kind": "uploaded" if s else "sample", "filename": s["filename"] if s else None, "rows": len(s["rows"]) if s else len(sd.dao_extract())}


@app.get("/sample.csv")
def sample_csv():
    return Response(csvio.to_csv(sd.dao_extract(), csvio.DAO_COLS), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="dao_sample.csv"'})


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    try:
        rows = csvio.parse_dao((await file.read()).decode("utf-8-sig"))
    except (csvio.CsvError, UnicodeDecodeError) as e:
        raise HTTPException(422, str(e))
    db.set_kv("source_dao", {"filename": file.filename, "rows": rows})
    return {"kind": "uploaded", "filename": file.filename, "rows": len(rows)}


@app.delete("/source")
def clear_source():
    db.del_kv("source_dao")
    return source()


@app.post("/run")
def run():
    s = db.get_kv("source_dao")
    rows = s["rows"] if s else sd.dao_extract()
    db.set_rows("dao", rows)
    return db.set_run("dao", {"stage": "dao", "run_at": db.now(), "rows_in": len(rows), "rows_out": len(rows), "rejected": 0,
                              "notes": [f"Source: {'uploaded file ' + s['filename'] if s else 'built-in sample data'}"]})


@app.get("/output")
def output():
    return {"layer": "DAO", "rows": db.get_rows("dao")}
