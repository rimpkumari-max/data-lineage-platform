"""SQLite persistence. Each pipeline layer is stored as rows, so results survive a restart.
The database file is lineage.db in the project folder (override with the LINEAGE_DB environment variable)."""
import json, os, sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "lineage.db"
PIPELINE_LAYERS = ["dao", "yxy", "yxy_rejects", "aoc", "mis"]
ORDER = ["catalog", "dao", "yxy", "aoc", "mis", "controls"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _conn():
    c = sqlite3.connect(os.environ.get("LINEAGE_DB", str(DEFAULT_PATH)))
    c.execute("create table if not exists rows(layer text, seq integer, data text, primary key(layer, seq))")
    c.execute("create table if not exists kv(k text primary key, v text)")
    return c


def set_rows(layer, rows):
    c = _conn()
    with c:
        c.execute("delete from rows where layer=?", (layer,))
        c.executemany("insert into rows values (?,?,?)", [(layer, i, json.dumps(r)) for i, r in enumerate(rows)])
    c.close()


def get_rows(layer):
    c = _conn()
    out = [json.loads(d) for (d,) in c.execute("select data from rows where layer=? order by seq", (layer,))]
    c.close()
    return out


def set_kv(key, value):
    c = _conn()
    with c:
        c.execute("insert or replace into kv values (?,?)", (key, json.dumps(value)))
    c.close()


def get_kv(key, default=None):
    c = _conn()
    r = c.execute("select v from kv where k=?", (key,)).fetchone()
    c.close()
    return json.loads(r[0]) if r else default


def del_kv(key):
    c = _conn()
    with c:
        c.execute("delete from kv where k=?", (key,))
    c.close()


def set_run(stage, summary):
    runs = get_kv("runs", {})
    runs[stage] = summary
    set_kv("runs", runs)
    return summary


def reset():
    """Clear pipeline results. Uploaded sources and parameters are kept."""
    c = _conn()
    with c:
        c.execute(f"delete from rows where layer in ({','.join('?' * len(PIPELINE_LAYERS))})", PIPELINE_LAYERS)
        c.execute("delete from kv where k in ('runs','controls','catalog')")
    c.close()


def params():
    """Run parameters: the file month and business group used by the YXY filter."""
    from app import rules
    return {**rules.DEFAULT_PARAMS, **get_kv("params", {})}
