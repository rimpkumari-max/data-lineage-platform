"""Made-up sample data using the real physical column names. No client data.
Problems are planted on purpose so every transformation and control has something to catch."""
import copy, random

FILE_MONTH = "2026-09-01"


def _build():
    rnd = random.Random(42)

    def row(i, **over):
        pif_case = i % 4 == 0
        r = {
            "clrty_id": 100000 + i, "filemonth_dt": FILE_MONTH, "source_system_cd": "SRV01", "business_group_cd": "WFF",
            "workout_completed_cd": rnd.choice([1, 2, 3, 4, 5]),
            "settlement_am": round(rnd.uniform(5000, 250000), 2),
            "account_gross_balance_am": 0.0 if pif_case else round(rnd.uniform(1000, 90000), 2),
            "charge_off_in": 0 if pif_case else rnd.choice([0, 0, 1]),
            "active_in": 0 if pif_case else rnd.choice([0, 1, 1]),
            "closure_reason_cd": 1 if pif_case else rnd.choice([0, 2, 3]),
            "sale_dt": None if rnd.random() < 0.6 else "2026-08-%02d" % rnd.randint(1, 28),
            "onhand_sold_cd": rnd.choice([0, 1]),
        }
        r.update(over)
        return r

    dao = [row(i) for i in range(1, 25)]
    dao += [
        row(25, business_group_cd="CIB"), row(26, business_group_cd="CIB"),        # wrong business group: filtered
        row(27, filemonth_dt="2026-08-01"), row(28, filemonth_dt="2026-08-01"),    # wrong file month: filtered
        dict(dao[2]),                                                              # duplicate clrty_id: removed
        row(29, settlement_am=None),                                               # missing amount: rejected
        row(30, settlement_am=-1500.00),                                           # negative amount: rejected
        row(31),                                                                   # no account master row: rejected
    ]
    accounts, seen = [], set()
    for r in dao:
        if r["clrty_id"] == 100031 or r["clrty_id"] in seen:
            continue
        seen.add(r["clrty_id"])
        accounts.append({"clrty_id": r["clrty_id"], "account_nm": 5000000 + r["clrty_id"], "chld_account_nm": 6000000 + r["clrty_id"],
                         "ldgr_account_nm": 7000000 + r["clrty_id"],
                         "interest_amt": round((r["settlement_am"] or 1000) * rnd.uniform(0.004, 0.02), 2)})
    return dao, accounts


_DAO, _ACCOUNTS = _build()


def dao_extract():
    return copy.deepcopy(_DAO)


def account_master():
    return copy.deepcopy(_ACCOUNTS)
