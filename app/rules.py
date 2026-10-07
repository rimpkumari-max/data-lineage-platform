"""Single source of truth for the transformation rules.
Each rule says where it comes from in the 'Data Lineage Information CDE Details' sheet, or that it is an ASSUMPTION."""

DEFAULT_PARAMS = {
    "file_month": "2026-09-01",     # @P_STARTDATE in the sheet's YXY filter
    "business_group": "WFF",        # business_group_cd = 'WFF' in the sheet's YXY filter
}
TOLERANCE = 0.005

# ASSUMPTION: the sheet marks PIF (Paid in Full) as 'Derived' at AOC but documents NO logic.
# Rule used: inactive, not charged off, fully paid down, and closed with a paid-in-full code.
# Confirm with the business owner, then edit PIF_CLOSURE_CODES or pif_flag() below.
PIF_CLOSURE_CODES = {1}
PIF_INPUTS = ["active_in", "charge_off_in", "closure_reason_cd", "account_gross_balance_am"]

# DAO physical column -> YXY physical column (sheet: Treatment, Settlement Amount and the PIF sub-DE rows)
DAO_TO_YXY = [
    ("clrty_id", "clrty_id"), ("filemonth_dt", "filemonth_dt"), ("source_system_cd", "source_system_cd"),
    ("workout_completed_cd", "treatment_cd"),
    ("settlement_am", "outstanding_balance"),
    ("account_gross_balance_am", "account_gross_balance_am"), ("charge_off_in", "charge_off_in"),
    ("active_in", "active_in"), ("closure_reason_cd", "closure_reason_cd"),
    ("sale_dt", "sale_dt"), ("onhand_sold_cd", "onhand_sold_cd"),
]
# Created at YXY ('Created / Database Inserted' in the sheet)
YXY_CREATED = ["account_nm", "chld_account_nm", "ldgr_account_nm", "interest_amt"]

YXY_TO_AOC = {
    "treatment_cd": "Treatment",
    "outstanding_balance": "outstanding_bal",
    "interest_amt": "interest_amount",
    "account_nm": "account_number",
    "chld_account_nm": "child_account_number",    # ASSUMPTION: the sheet leaves this AOC name blank
    "ldgr_account_nm": "ledger_account_number",   # ASSUMPTION: the sheet leaves this AOC name blank
}
AOC_TO_MIS = [
    ("clrty_id", "Clarity ID"), ("filemonth_dt", "File Month"),
    ("account_number", "Account Number"), ("child_account_number", "Child_AccountNumber"),
    ("ledger_account_number", "Ledger_AccountNumber"), ("Treatment", "Treatment"), ("PIF", "PIF"),
    ("outstanding_bal", "Outstanding Balance"), ("interest_amount", "Interest Amount"),
    ("settlement_amount", "Settlement Amount"),
]

CDE_MAP = [
    {"cde": "Treatment", "dao": "workout_completed_cd", "yxy": "treatment_cd", "aoc": "Treatment", "mis": "Treatment", "action": "Passed through, renamed"},
    {"cde": "Outstanding Balance", "dao": "settlement_am", "yxy": "outstanding_balance", "aoc": "outstanding_bal", "mis": "Outstanding Balance", "action": "Passed through, renamed"},
    {"cde": "Interest Amount", "dao": None, "yxy": "interest_amt", "aoc": "interest_amount", "mis": "Interest Amount", "action": "Created at YXY, passed on"},
    {"cde": "Settlement Amount", "dao": None, "yxy": None, "aoc": "settlement_amount", "mis": "Settlement Amount", "action": "DERIVED at AOC: outstanding_bal + interest_amount"},
    {"cde": "Account Number", "dao": None, "yxy": "account_nm", "aoc": "account_number", "mis": "Account Number", "action": "Created at YXY, renamed"},
    {"cde": "Child_AccountNumber", "dao": None, "yxy": "chld_account_nm", "aoc": "child_account_number", "mis": "Child_AccountNumber", "action": "Created at YXY, renamed"},
    {"cde": "Ledger_AccountNumber", "dao": None, "yxy": "ldgr_account_nm", "aoc": "ledger_account_number", "mis": "Ledger_AccountNumber", "action": "Created at YXY, renamed"},
    {"cde": "PIF", "dao": None, "yxy": None, "aoc": "PIF", "mis": "PIF", "action": "DERIVED at AOC from the PIF sub-fields (rule is an assumption)"},
]


def pif_flag(active_in, charge_off_in, closure_reason_cd, gross_balance):
    return int(active_in == 0 and charge_off_in == 0 and closure_reason_cd in PIF_CLOSURE_CODES and abs(gross_balance) < TOLERANCE)


def settlement_amount(outstanding_bal, interest_amount):
    """Sheet, AOC hop, 'Transformation Logic': settlement_amount+interest_amount."""
    return round(outstanding_bal + interest_amount, 2)
