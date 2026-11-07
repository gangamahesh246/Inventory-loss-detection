"""Validate the generated dataset.

Runs a set of simple checks and writes one row per check to
reports/validation_summary.csv. Each check is PASS/FAIL with a count of
violations. A check that finds zero violations is a PASS.

Run:
    python validate.py
"""
import os
import pandas as pd

import enums

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
REPORTS_DIR = os.path.join(ROOT, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def load(name):
    return pd.read_csv(os.path.join(DATA_DIR, name + ".csv"), low_memory=False)


class Result:
    def __init__(self):
        self.rows = []

    def add(self, check, status, violations, detail=""):
        self.rows.append({"check": check, "status": status,
                          "violations": int(violations), "detail": detail})

    def to_df(self):
        return pd.DataFrame(self.rows)


# ---------------------------------------------------------------------------
# individual checks (each returns violation count)
# ---------------------------------------------------------------------------
def check_pk_unique(res, dfs):
    pks = {"store": "store_id", "sku": "sku_id", "employee": "employee_id",
           "shift": "shift_id", "promotion": "promotion_id",
           "movement": "movement_id", "cycle_count": "count_id",
           "return_event": "return_id"}
    for t, col in pks.items():
        n = dfs[t][col].duplicated().sum()
        res.add(f"pk_unique:{t}", "PASS" if n == 0 else "FAIL", n)


def check_id_format(res, dfs):
    import re
    patterns = {
        "store": (r"^STORE-\d{6}$", "store_id"),
        "sku": (r"^SKU-\d{6}$", "sku_id"),
        "movement": (r"^MOV-2026-\d{8}$", "movement_id"),
        "cycle_count": (r"^CNT-2026-\d{6}$", "count_id"),
        "return_event": (r"^RET-2026-\d{6}$", "return_id"),
    }
    for t, (pat, col) in patterns.items():
        n = (~dfs[t][col].astype(str).str.match(pat)).sum()
        res.add(f"id_format:{t}", "PASS" if n == 0 else "FAIL", n)


def check_fk_integrity(res, dfs):
    store_ids = set(dfs["store"]["store_id"])
    sku_ids = set(dfs["sku"]["sku_id"])
    emp_ids = set(dfs["employee"]["employee_id"])
    shf_ids = set(dfs["shift"]["shift_id"])

    def fk(df, col, valid, name, allow_null=True):
        if col not in df.columns:
            res.add(f"fk:{name}", "PASS", 0, "column absent")
            return
        s = df[col].dropna() if allow_null else df[col]
        n = (~s.isin(valid)).sum()
        res.add(f"fk:{name}", "PASS" if n == 0 else "FAIL", n)

    fk(dfs["movement"], "store_id", store_ids, "movement.store_id", False)
    fk(dfs["movement"], "sku_id", sku_ids, "movement.sku_id", False)
    fk(dfs["movement"], "employee_id", emp_ids, "movement.employee_id", True)
    fk(dfs["movement"], "shift_id", shf_ids, "movement.shift_id", True)
    fk(dfs["cycle_count"], "store_id", store_ids, "count.store_id", False)
    fk(dfs["cycle_count"], "sku_id", sku_ids, "count.sku_id", False)
    fk(dfs["cycle_count"], "counted_by_employee_id", emp_ids, "count.employee_id", True)
    fk(dfs["employee"], "store_id", store_ids, "employee.store_id", False)
    fk(dfs["shift"], "store_id", store_ids, "shift.store_id", False)
    fk(dfs["opening_balance"], "store_id", store_ids, "opening.store_id", False)
    fk(dfs["opening_balance"], "sku_id", sku_ids, "opening.sku_id", False)

    # promotion_sku bridge
    promo_ids = set(dfs["promotion"]["promotion_id"])
    fk(dfs["promotion_sku"], "promotion_id", promo_ids, "promo_sku.promo_id", False)
    fk(dfs["promotion_sku"], "sku_id", sku_ids, "promo_sku.sku_id", False)

    # transfer pairing: TransferIn.related_movement_id must point to a TransferOut
    outs = dfs["movement"][dfs["movement"]["movement_type"] == "TransferOut"]["movement_id"]
    out_set = set(outs)
    tin = dfs["movement"][dfs["movement"]["movement_type"] == "TransferIn"]
    n = (~tin["related_movement_id"].isin(out_set)).sum() if not tin.empty else 0
    res.add("fk:transfer_in.related_movement_id", "PASS" if n == 0 else "FAIL", n)


def check_enums(res, dfs):
    checks = [
        ("store", "status", enums.STORE_STATUS, False),
        ("store", "format", enums.STORE_FORMAT, False),
        ("sku", "status", enums.SKU_STATUS, False),
        ("employee", "role", enums.EMPLOYEE_ROLE, False),
        ("employee", "status", enums.EMPLOYEE_STATUS, False),
        ("shift", "shift_name", enums.SHIFT_NAME, False),
        ("promotion", "status", enums.PROMO_STATUS, False),
        ("movement", "movement_type", enums.MOVEMENT_TYPE, False),
        ("movement", "status", enums.MOVEMENT_STATUS, False),
        ("cycle_count", "count_status", enums.COUNT_STATUS, False),
    ]
    for t, col, allowed, allow_null in checks:
        s = dfs[t][col].dropna() if allow_null else dfs[t][col]
        n = (~s.isin(allowed)).sum()
        res.add(f"enum:{t}.{col}", "PASS" if n == 0 else "FAIL", n)

    # adjustment reason must be in ADJUSTMENT_REASON OR null (null = anomaly)
    adj = dfs["movement"][dfs["movement"]["movement_type"] == "Adjustment"]
    bad = adj["reason_code"].dropna()
    n = (~bad.isin(enums.ADJUSTMENT_REASON)).sum()
    res.add("enum:adjustment.reason_code", "PASS" if n == 0 else "FAIL", n)


def check_dates(res, dfs):
    m = dfs["movement"].copy()
    m["occurred_at"] = pd.to_datetime(m["occurred_at"])
    m["recorded_at"] = pd.to_datetime(m["recorded_at"])
    # recorded_at >= occurred_at
    n = (m["recorded_at"] < m["occurred_at"]).sum()
    res.add("date:movement.recorded>=occurred", "PASS" if n == 0 else "FAIL", n)

    c = dfs["cycle_count"].copy()
    c["counted_at"] = pd.to_datetime(c["counted_at"])
    c["recorded_at"] = pd.to_datetime(c["recorded_at"])
    n = (c["recorded_at"] < c["counted_at"]).sum()
    res.add("date:count.recorded>=counted", "PASS" if n == 0 else "FAIL", n)


def check_quantity_signs(res, dfs):
    m = dfs["movement"]
    # inbound types must be positive, outbound negative
    inbound = {"Receipt", "TransferIn", "Return"}
    outbound = {"Sale", "TransferOut", "Damage"}
    n = (m[m["movement_type"].isin(inbound)]["quantity"] <= 0).sum()
    res.add("arith:inbound_positive", "PASS" if n == 0 else "FAIL", n)
    n = (m[m["movement_type"].isin(outbound)]["quantity"] >= 0).sum()
    res.add("arith:outbound_negative", "PASS" if n == 0 else "FAIL", n)


def check_stock_equation(res, dfs):
    """opening + sum(movements) per (store,sku) == on_hand. We can't observe
    on_hand directly, so we check that every (store,sku) that has movements
    also has an opening balance, and that cycle-count expected_qty equals
    opening + cumulative movements as of counted_at."""
    ob = dfs["opening_balance"]
    m = dfs["movement"]
    pairs_with_moves = set(map(tuple, m[["store_id", "sku_id"]].values))
    pairs_with_open = set(map(tuple, ob[["store_id", "sku_id"]].values))
    missing = pairs_with_moves - pairs_with_open
    res.add("arith:opening_balance_coverage", "PASS" if not missing else "FAIL",
            len(missing),
            "movements exist for (store,sku) with no opening balance")

    # recompute expected_qty for a sample of counts and compare
    c = dfs["cycle_count"].copy()
    c["counted_at"] = pd.to_datetime(c["counted_at"])
    running = m[["store_id", "sku_id", "occurred_at", "quantity"]].copy()
    running["occurred_at"] = pd.to_datetime(running["occurred_at"])
    running = running.sort_values("occurred_at")
    running["cum"] = running.groupby(["store_id", "sku_id"])["quantity"].cumsum()
    ob_map = ob.set_index(["store_id", "sku_id"])["opening_qty"]
    merged = c.merge(ob_map.rename("opening_qty"),
                     on=["store_id", "sku_id"], how="left")
    merged["opening_qty"] = merged["opening_qty"].fillna(0)
    merged = merged.sort_values("counted_at")
    asof = pd.merge_asof(merged, running[["store_id", "sku_id", "occurred_at", "cum"]],
                         left_on="counted_at", right_on="occurred_at",
                         by=["store_id", "sku_id"], direction="backward")
    asof["cum"] = asof["cum"].fillna(0)
    # floor at 0 to match the generator's stockout modelling
    asof["calc_expected"] = (asof["opening_qty"] + asof["cum"]).clip(lower=0).astype(int)
    # compare only counts whose expected_qty was set by the generator (notes
    # empty OR contains "unexplained"/"in-transit" which still use expected)
    n = (asof["calc_expected"] != asof["expected_qty"]).sum()
    res.add("arith:expected_qty_matches", "PASS" if n == 0 else "FAIL", n,
            "expected_qty must equal opening + cumulative movements as of counted_at")


def check_variance(res, dfs):
    c = dfs["cycle_count"]
    n = (c["variance"] != (c["counted_qty"] - c["expected_qty"])).sum()
    res.add("arith:variance=counted-expected", "PASS" if n == 0 else "FAIL", n)


def check_duplicates(res, dfs):
    m = dfs["movement"]
    # a transfer out should reference a unique transfer in and vice versa
    tin = m[m["movement_type"] == "TransferIn"]
    n = tin["related_movement_id"].duplicated().sum()
    res.add("dup:transfer_in.related_unique", "PASS" if n == 0 else "FAIL", n)


# ---------------------------------------------------------------------------
def main():
    names = ["store", "sku", "employee", "shift", "promotion", "promotion_sku",
             "opening_balance", "movement", "cycle_count", "return_event"]
    dfs = {n: load(n) for n in names}

    res = Result()
    check_pk_unique(res, dfs)
    check_id_format(res, dfs)
    check_fk_integrity(res, dfs)
    check_enums(res, dfs)
    check_dates(res, dfs)
    check_quantity_signs(res, dfs)
    check_stock_equation(res, dfs)
    check_variance(res, dfs)
    check_duplicates(res, dfs)

    df = res.to_df()
    df.to_csv(os.path.join(REPORTS_DIR, "validation_summary.csv"), index=False)

    fails = df[df["status"] == "FAIL"]
    print(f"[validate] {len(df)} checks, {len(fails)} failures")
    if len(fails):
        print(fails.to_string(index=False))
    else:
        print("[validate] ALL CHECKS PASSED")
    return len(fails) == 0


if __name__ == "__main__":
    ok = main()
    raise SystemExit(0 if ok else 1)
