"""Generate the synthetic inventory dataset.

Single-file, fresher-style generator. Each function builds one table;
run() wires them in dependency order. The same code produces the starter
and full datasets - only the counts in config.yaml change.

Design rules that keep validation clean:
  * expected_qty is ALWAYS derived from final movements + opening balance.
  * Anomalies only corrupt the "observed" side (counted_qty, counted_at,
    reason_code, store_id) so the stock equation still reconciles.
  * Ground-truth labels are written to labels/ and never leak into features.

Run:
    python generate.py                       # starter scale (default)
    python generate.py --scale full          # 100 stores / 5k SKUs / 1M moves
    python generate.py --scale starter --seed 20261022
    python generate.py --check-repro         # generate twice, compare checksums
"""
import argparse
import datetime as dt
import hashlib
import os
import shutil
import sqlite3

import numpy as np
import pandas as pd
import yaml

import ids
import enums

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
LABELS_DIR = os.path.join(ROOT, "labels")
REPORTS_DIR = os.path.join(ROOT, "reports")
for _d in (DATA_DIR, LABELS_DIR, REPORTS_DIR):
    os.makedirs(_d, exist_ok=True)


# ---------------------------------------------------------------------------
# Config + RNG
# ---------------------------------------------------------------------------
def load_config(path=None):
    path = path or os.path.join(ROOT, "config.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


def make_streams(seed):
    """Split the master seed into independent sub-streams so changing one
    table's count never shifts another table's output."""
    names = ["store", "sku", "emp", "shift", "promo", "catalog",
             "open", "move", "count", "anomaly", "benign", "gt"]
    sub = np.random.SeedSequence(seed).spawn(len(names))
    return {n: np.random.default_rng(s) for n, s in zip(names, sub)}


# ---------------------------------------------------------------------------
# 1. Master tables
# ---------------------------------------------------------------------------
def generate_stores(rng, n):
    formats, regions = enums.STORE_FORMAT, enums.STORE_REGION
    rows = []
    for i in range(1, n + 1):
        opened = dt.date(2026, 1, 1) - dt.timedelta(days=int(rng.integers(180, 720)))
        rows.append({
            "store_id": ids.store_id(i),
            "store_name": f"Store {i:04d}",
            "format": formats[int(rng.integers(0, len(formats)))],
            "region": regions[int(rng.integers(0, len(regions)))],
            "opened_on": opened.isoformat(),
            "status": "Active",
        })
    return pd.DataFrame(rows, columns=ids.COLUMNS["store"])


def generate_skus(rng, n):
    cats = enums.SKU_CATEGORY
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "sku_id": ids.sku_id(i),
            "sku_name": f"Product {i:05d}",
            "category": cats[int(rng.integers(0, len(cats)))],
            "unit_cost": round(float(rng.uniform(0.5, 120.0)), 2),
            "perishable": bool(rng.random() < 0.3),
            "active_from": "2026-01-01",
            "status": "Active",
        })
    return pd.DataFrame(rows, columns=ids.COLUMNS["sku"])


def generate_employees(rng, stores):
    rows = []
    i = 1
    roles = enums.EMPLOYEE_ROLE
    for _, st in stores.iterrows():
        headcount = 8 if st["format"] in ("Warehouse", "Supermarket") else 5
        for _ in range(headcount):
            hired = dt.date(2026, 1, 1) - dt.timedelta(days=int(rng.integers(60, 900)))
            rows.append({
                "employee_id": ids.emp_id(i),
                "store_id": st["store_id"],
                "employee_name": f"Employee {i:05d}",
                "role": roles[int(rng.integers(0, len(roles)))],
                "hired_on": hired.isoformat(),
                "status": "Active",
            })
            i += 1
    return pd.DataFrame(rows, columns=ids.COLUMNS["employee"])


def generate_shifts(stores):
    rows = []
    i = 1
    times = {"Morning": ("06:00", "14:00"),
             "Afternoon": ("14:00", "22:00"),
             "Night": ("22:00", "06:00")}
    for _, st in stores.iterrows():
        for name in enums.SHIFT_NAME:
            rows.append({
                "shift_id": ids.shf_id(i),
                "store_id": st["store_id"],
                "shift_name": name,
                "start_time": times[name][0],
                "end_time": times[name][1],
            })
            i += 1
    return pd.DataFrame(rows, columns=ids.COLUMNS["shift"])


def generate_promotions(rng, skus, n=50):
    rows, bridge = [], []
    start = dt.date(2026, 1, 1)
    for i in range(1, n + 1):
        s = start + dt.timedelta(days=int(rng.integers(0, 60)))
        e = s + dt.timedelta(days=int(rng.integers(7, 30)))
        rows.append({
            "promotion_id": ids.promo_id(i),
            "promotion_name": f"Promo {i:03d}",
            "start_date": s.isoformat(),
            "end_date": e.isoformat(),
            "discount_pct": float(rng.integers(5, 30)),
            "status": "Active" if s <= dt.date(2026, 6, 1) <= e else "Ended",
        })
        k = int(rng.integers(20, 120))
        chosen = skus["sku_id"].sample(k, random_state=int(rng.integers(0, 1 << 31))).tolist()
        bridge.extend({"promotion_id": ids.promo_id(i), "sku_id": sid} for sid in chosen)
    return (pd.DataFrame(rows, columns=ids.COLUMNS["promotion"]),
            pd.DataFrame(bridge, columns=ids.COLUMNS["promotion_sku"]))


# ---------------------------------------------------------------------------
# 2. Catalog + opening balances
# ---------------------------------------------------------------------------
def generate_catalog(rng, stores, skus, coverage):
    sku_list = skus["sku_id"].tolist()
    pairs = []
    for sid in stores["store_id"]:
        k = int(len(sku_list) * coverage)
        chosen = rng.choice(sku_list, size=k, replace=False)
        pairs.extend((sid, s) for s in chosen)
    return pd.DataFrame(pairs, columns=["store_id", "sku_id"])


def generate_opening_balances(rng, catalog):
    rows = []
    for _, r in catalog.iterrows():
        rows.append({
            "store_id": r["store_id"], "sku_id": r["sku_id"],
            "opening_qty": int(rng.integers(10, 60)),
            "as_of_date": "2026-01-01",
        })
    return pd.DataFrame(rows, columns=ids.COLUMNS["opening_balance"])


# ---------------------------------------------------------------------------
# 3. Movements
# ---------------------------------------------------------------------------
def _random_timestamps(rng, n, start, end):
    low = pd.Timestamp(start).value
    high = pd.Timestamp(end).value
    return pd.to_datetime(rng.integers(low, high, size=n))


def _pick_store_sku(rng, catalog, n):
    idx = rng.integers(0, len(catalog), size=n)
    return catalog.iloc[idx]["store_id"].values, catalog.iloc[idx]["sku_id"].values


def _pick_emp_shift(rng, employees, shifts, store_ids):
    emp_by_store = employees.groupby("store_id")["employee_id"].apply(list).to_dict()
    shf_by_store = shifts.groupby("store_id")["shift_id"].apply(list).to_dict()
    emps, shfs = [], []
    for s in store_ids:
        e = emp_by_store.get(s, [])
        f = shf_by_store.get(s, [])
        emps.append(e[int(rng.integers(0, len(e)))] if e else None)
        shfs.append(f[int(rng.integers(0, len(f)))] if f else None)
    return np.array(emps, dtype=object), np.array(shfs, dtype=object)


def generate_movements(rng, config, scale, catalog, employees, shifts,
                       skus, stores):
    """Build all movements. Returns (movements, return_events, transfer_pairs)
    where transfer_pairs = (transfer_out_df, transfer_in_df) with a
    destination_store_id column on the out frame."""
    mix = config["movement_mix"]
    total = config["scales"][scale]["movements"]
    n_tout = int(total * mix["transfer_out"])
    n_tin = n_tout
    rest = total - n_tin
    denom = mix["sale"] + mix["receipt"] + mix["return"] + mix["damage"] + mix["adjustment"]
    n_sale = int(rest * mix["sale"] / denom)
    n_receipt = int(rest * mix["receipt"] / denom)
    n_return = int(rest * mix["return"] / denom)
    n_damage = int(rest * mix["damage"] / denom)
    n_adjust = rest - n_sale - n_receipt - n_return - n_damage

    start, end = config["date_range"]["start"], config["date_range"]["end"]
    qr = config["quantity_ranges"]
    qr_key = {"sale": "sale", "receipt": "receipt", "transferout": "transfer_out",
              "transferin": "transfer_out", "return": "return",
              "damage": "damage", "adjustment": "adjustment"}
    sku_cost = skus.set_index("sku_id")["unit_cost"].to_dict()
    sku_stores = catalog.groupby("sku_id")["store_id"].apply(list).to_dict()
    all_stores = stores["store_id"].tolist()

    seq = [1]
    frames = []

    def base_rows(mtype, n, sign, reason_pool):
        if n == 0:
            return pd.DataFrame(columns=ids.COLUMNS["movement"])
        store_ids, sku_ids = _pick_store_sku(rng, catalog, n)
        emps, shfs = _pick_emp_shift(rng, employees, shifts, store_ids)
        occ = _random_timestamps(rng, n, start, end)
        rows = []
        for j in range(n):
            lo, hi = qr[qr_key[mtype.lower()]]
            qty = int(rng.integers(lo, hi + 1)) * sign
            if mtype == "Adjustment" and qty == 0:
                qty = -1
            reason = reason_pool[int(rng.integers(0, len(reason_pool)))] if reason_pool else None
            rows.append({
                "movement_id": ids.mov_id(seq[0]), "store_id": store_ids[j],
                "sku_id": sku_ids[j], "movement_type": mtype,
                "quantity": qty, "unit_cost": sku_cost[sku_ids[j]],
                "reason_code": reason, "occurred_at": occ[j],
                "recorded_at": occ[j] + pd.Timedelta(hours=int(rng.integers(0, 48))),
                "employee_id": emps[j], "shift_id": shfs[j],
                "related_movement_id": None, "reference": None, "status": "Posted",
            })
            seq[0] += 1
        return pd.DataFrame(rows, columns=ids.COLUMNS["movement"])

    # Sales
    sales = base_rows("Sale", n_sale, -1, enums.SALE_CHANNEL)
    sales["reason_code"] = "Sale"
    if not sales.empty:
        sales["reference"] = ["TXN-" + str(i).zfill(10) for i in range(len(sales))]
    frames.append(sales)

    # Receipts
    receipts = base_rows("Receipt", n_receipt, +1, enums.RECEIPT_REASON)
    if not receipts.empty:
        receipts["reference"] = ["PO-" + str(i).zfill(8) for i in range(len(receipts))]
    frames.append(receipts)

    # Transfers: out + paired in, destination must also carry the SKU
    t_out = base_rows("TransferOut", n_tout, -1, None)
    t_in = pd.DataFrame(columns=ids.COLUMNS["movement"])
    if not t_out.empty:
        src = t_out["store_id"].values
        sk = t_out["sku_id"].values
        dest = []
        for s, k in zip(src, sk):
            carriers = sku_stores.get(k, [])
            choices = [x for x in carriers if x != s] or [x for x in all_stores if x != s]
            dest.append(choices[int(rng.integers(0, len(choices)))])
        t_out["destination_store_id"] = dest
        t_out["reason_code"] = "TransferToStore"
        t_out["reference"] = ["TRF-" + str(i).zfill(8) for i in range(len(t_out))]
        in_rows = []
        for k, (_, r) in enumerate(t_out.iterrows()):
            occurred = r["occurred_at"] + pd.Timedelta(hours=int(rng.integers(24, 96)))
            in_rows.append({
                "movement_id": ids.mov_id(seq[0]), "store_id": dest[k],
                "sku_id": r["sku_id"], "movement_type": "TransferIn",
                "quantity": -r["quantity"], "unit_cost": r["unit_cost"],
                "reason_code": "TransferFromStore", "occurred_at": occurred,
                "recorded_at": occurred + pd.Timedelta(hours=int(rng.integers(0, 24))),
                "employee_id": None, "shift_id": None,
                "related_movement_id": r["movement_id"], "reference": r["reference"],
                "status": "Posted",
            })
            seq[0] += 1
            t_out.at[t_out.index[k], "related_movement_id"] = in_rows[-1]["movement_id"]
        t_in = pd.DataFrame(in_rows, columns=ids.COLUMNS["movement"])
        tin_emps, tin_shfs = _pick_emp_shift(rng, employees, shifts, t_in["store_id"].values)
        t_in["employee_id"] = tin_emps
        t_in["shift_id"] = tin_shfs
        frames.append(t_out)
        frames.append(t_in)
        pairs = (t_out, t_in)
    else:
        pairs = None

    # Damages
    frames.append(base_rows("Damage", n_damage, -1, enums.DAMAGE_REASON))

    # Adjustments (reason present by default; anomaly removes it later)
    frames.append(base_rows("Adjustment", n_adjust, +1, enums.ADJUSTMENT_REASON))

    # Returns derived from a subset of sales
    returns_df, return_events = _generate_returns(rng, sales, n_return, seq)
    frames.append(returns_df)

    movements = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    return movements, return_events, pairs


def _generate_returns(rng, sales, n_return, seq):
    if n_return == 0 or sales.empty:
        return (pd.DataFrame(columns=ids.COLUMNS["movement"]),
                pd.DataFrame(columns=ids.COLUMNS["return_event"]))
    pick = sales.sample(n=min(n_return, len(sales)),
                       random_state=int(rng.integers(0, 1 << 31))).copy()
    ret_rows, event_rows = [], []
    for i, (_, s) in enumerate(pick.iterrows()):
        ret_occurred = s["occurred_at"] + pd.Timedelta(days=int(rng.integers(1, 20)))
        qty = int(rng.integers(1, min(4, abs(s["quantity"]) or 1) + 1))
        mid = ids.mov_id(seq[0])
        reason = enums.RETURN_REASON[int(rng.integers(0, len(enums.RETURN_REASON)))]
        ret_rows.append({
            "movement_id": mid, "store_id": s["store_id"], "sku_id": s["sku_id"],
            "movement_type": "Return", "quantity": qty, "unit_cost": s["unit_cost"],
            "reason_code": reason, "occurred_at": ret_occurred,
            "recorded_at": ret_occurred + pd.Timedelta(hours=int(rng.integers(0, 24))),
            "employee_id": s["employee_id"], "shift_id": s["shift_id"],
            "related_movement_id": s["movement_id"], "reference": "RET-" + str(i).zfill(8),
            "status": "Posted",
        })
        event_rows.append({
            "return_id": ids.ret_id(i + 1), "sale_movement_id": s["movement_id"],
            "return_movement_id": mid, "store_id": s["store_id"], "sku_id": s["sku_id"],
            "return_reason": reason, "received_at": ret_occurred.isoformat(),
        })
        seq[0] += 1
    return (pd.DataFrame(ret_rows, columns=ids.COLUMNS["movement"]),
            pd.DataFrame(event_rows, columns=ids.COLUMNS["return_event"]))


# ---------------------------------------------------------------------------
# 4. Running on-hand + expected_qty helpers
# ---------------------------------------------------------------------------
def compute_running_on_hand(movements, opening_balances):
    mov = movements[["store_id", "sku_id", "occurred_at", "quantity"]].copy()
    mov = mov.sort_values(["store_id", "sku_id", "occurred_at"]).reset_index(drop=True)
    mov["cum_qty"] = mov.groupby(["store_id", "sku_id"])["quantity"].cumsum()
    ob = opening_balances[["store_id", "sku_id", "opening_qty"]].copy()
    mov = mov.merge(ob, on=["store_id", "sku_id"], how="left")
    mov["opening_qty"] = mov["opening_qty"].fillna(0)
    # floor at 0: a store cannot hold negative stock (stockout modelling)
    mov["on_hand"] = (mov["opening_qty"] + mov["cum_qty"]).clip(lower=0)
    return mov[["store_id", "sku_id", "occurred_at", "on_hand"]]


def recompute_expected(counts, running, opening_balances):
    """Set expected_qty = on_hand as of counted_at for every count."""
    ob = opening_balances[["store_id", "sku_id", "opening_qty"]].copy()
    c = counts.merge(ob, on=["store_id", "sku_id"], how="left")
    c["opening_qty"] = c["opening_qty"].fillna(0)
    r = running.sort_values("occurred_at")
    c = c.sort_values("counted_at")
    merged = pd.merge_asof(c, r, left_on="counted_at", right_on="occurred_at",
                          by=["store_id", "sku_id"], direction="backward")
    merged["expected_qty"] = merged["on_hand"].fillna(merged["opening_qty"]).astype(int)
    # restore original column order
    out = merged[counts.columns].copy()
    out["expected_qty"] = merged["expected_qty"].values
    return out


def recompute_variance(counts):
    counts = counts.copy()
    counts["variance"] = counts["counted_qty"] - counts["expected_qty"]
    return counts


# ---------------------------------------------------------------------------
# 5. Cycle counts (base)
# ---------------------------------------------------------------------------
def generate_cycle_counts(rng, config, scale, catalog, employees, shifts,
                           running, opening):
    n = config["scales"][scale]["cycle_counts"]
    start, end = config["date_range"]["start"], config["date_range"]["end"]
    store_ids, sku_ids = _pick_store_sku(rng, catalog, n)
    emps, shfs = _pick_emp_shift(rng, employees, shifts, store_ids)
    counted = _random_timestamps(rng, n, start, end)
    base = pd.DataFrame({
        "count_id": [ids.cnt_id(i + 1) for i in range(n)],
        "store_id": store_ids, "sku_id": sku_ids,
        "counted_qty": 0, "expected_qty": 0, "variance": 0,
        "counted_at": counted,
        "recorded_at": counted + pd.Timedelta(hours=1),
        "counted_by_employee_id": emps, "shift_id": shfs,
        "count_status": "Posted", "notes": "",
    })
    base = recompute_expected(base, running, opening)
    # normal noise: most counts exact or off by 1
    noise = rng.choice([-1, 0, 0, 0, 0, 1], size=n)
    base["counted_qty"] = (base["expected_qty"] + noise).clip(lower=0)
    base = recompute_variance(base)
    return base[ids.COLUMNS["cycle_count"]]


# ---------------------------------------------------------------------------
# 6. Anomaly injection
# ---------------------------------------------------------------------------
def _next_mov_id(movements, seq):
    """Next movement id, continuing from the highest existing numeric suffix."""
    if seq[0] == 0:
        nums = movements["movement_id"].astype(str).str.split("-").str[-1].astype(int)
        seq[0] = int(nums.max()) + 1 if len(nums) else 1
    mid = ids.mov_id(seq[0])
    seq[0] += 1
    return mid


def inject_movement_anomalies(rng, config, scale, movements, transfer_pairs,
                              employees, shifts, catalog, stores, seq):
    """Anomalies that mutate/add movements. Run BEFORE counts so expected_qty
    stays consistent. Returns (movements, labels, transfer_pairs)."""
    ac = config["anomaly_counts"][scale]
    movements = movements.copy()
    labels = []

    # 1. wrong_store_ref: TransferIn.store_id != TransferOut.destination
    if transfer_pairs is not None:
        t_out, t_in = transfer_pairs
        t_out = t_out.copy()
        t_in = t_in.copy()
        dest_map = dict(zip(t_out["movement_id"], t_out["destination_store_id"]))
        # choose the wrong store from stores that also carry the SKU, so the
        # only thing wrong is the store reference (keeps opening-balance
        # coverage clean; the anomaly is still the destination mismatch).
        sku_stores = catalog.groupby("sku_id")["store_id"].apply(list).to_dict()
        all_stores = stores["store_id"].tolist()
        k = min(ac["wrong_store_ref"], len(t_in))
        if k > 0:
            sel = t_in.sample(k, random_state=int(rng.integers(0, 1 << 31))).copy()
            for _, row in sel.iterrows():
                dest = dest_map.get(row["related_movement_id"])
                if dest is None:
                    continue
                carriers = [s for s in sku_stores.get(row["sku_id"], all_stores) if s != dest]
                pool = carriers if carriers else [s for s in all_stores if s != dest]
                wrong = pool[int(rng.integers(0, len(pool)))]
                movements.loc[movements["movement_id"] == row["movement_id"], "store_id"] = wrong
                labels.append({"entity_type": "Movement", "entity_id": row["movement_id"],
                               "issue_type": "wrong_store_ref",
                               "description": f"TransferIn store {wrong} != TransferOut destination {dest}",
                               "expected_decision": "flag WrongStoreRef"})

    # 2. missing_reason: Adjustment rows with reason_code = None
    adj_idx = movements[movements["movement_type"] == "Adjustment"].index
    k = min(ac["missing_reason"], len(adj_idx))
    if k > 0:
        chosen = rng.choice(adj_idx.to_numpy(), size=k, replace=False)
        movements.loc[chosen, "reason_code"] = None
        for i in chosen:
            labels.append({"entity_type": "Movement",
                           "entity_id": movements.loc[i, "movement_id"],
                           "issue_type": "missing_reason",
                           "description": "Adjustment has no reason_code",
                           "expected_decision": "flag MissingReason"})

    # 5. repeated_adjustments: same employee/sku/shift, many small negatives
    for _ in range(ac["repeated_adjustments"]):
        pair = catalog.sample(1, random_state=int(rng.integers(0, 1 << 31))).iloc[0]
        st, sk = pair["store_id"], pair["sku_id"]
        emps_in = employees[employees["store_id"] == st]
        if emps_in.empty:
            continue
        emp = emps_in.sample(1, random_state=int(rng.integers(0, 1 << 31))).iloc[0]["employee_id"]
        shf = shifts[shifts["store_id"] == st].sample(1, random_state=int(rng.integers(0, 1 << 31))).iloc[0]["shift_id"]
        n_adj = int(rng.integers(config["detection"]["repeated_adjustment_min_count"],
                                 config["detection"]["repeated_adjustment_min_count"] + 4))
        base_day = pd.Timestamp("2026-07-01") + pd.Timedelta(days=int(rng.integers(0, 60)))
        new_rows = []
        for j in range(n_adj):
            occ = base_day + pd.Timedelta(days=j)
            new_rows.append({
                "movement_id": _next_mov_id(movements, seq), "store_id": st, "sku_id": sk,
                "movement_type": "Adjustment", "quantity": -int(rng.integers(1, 3)),
                "unit_cost": float(rng.uniform(1, 20)), "reason_code": "StockCorrection",
                "occurred_at": occ, "recorded_at": occ + pd.Timedelta(hours=1),
                "employee_id": emp, "shift_id": shf, "related_movement_id": None,
                "reference": None, "status": "Posted",
            })
        movements = pd.concat([movements, pd.DataFrame(new_rows)], ignore_index=True)
        labels.append({"entity_type": "Employee", "entity_id": emp,
                       "issue_type": "repeated_adjustments",
                       "description": f"{n_adj} small negative adjustments by {emp} on {sk} within {n_adj} days",
                       "expected_decision": "flag RepeatedAdjustments"})

    return movements, labels, transfer_pairs


def _expected_at(store, sku, ts, movements_dt, opening_map):
    """on_hand = max(0, opening + sum(quantity for movements before ts))."""
    ob = opening_map.get((store, sku), 0)
    sub = movements_dt[(movements_dt["store_id"] == store)
                      & (movements_dt["sku_id"] == sku)
                      & (movements_dt["occurred_at"] <= ts)]
    return max(0, int(ob + sub["quantity"].sum()))


def inject_count_anomalies(rng, config, scale, movements, counts, transfer_pairs,
                           stores, opening, seq):
    """Anomalies that touch counted_at/counted_qty only. Run AFTER expected
    recompute so expected_qty stays correct."""
    ac = config["anomaly_counts"][scale]
    counts = counts.copy()
    labels = []
    labelled = set()  # count_ids already used by an anomaly

    # prep for on-hand lookups (used by transfer_double_shrink)
    movements_dt = movements.copy()
    movements_dt["occurred_at"] = pd.to_datetime(movements_dt["occurred_at"])
    opening_map = opening.set_index(["store_id", "sku_id"])["opening_qty"].to_dict()

    # 3. count_timing_conflict: counted_at before store opening
    store_open = stores.set_index("store_id")["opened_on"].to_dict()
    k = min(ac["count_timing_conflict"], len(counts))
    if k > 0:
        sel = counts.sample(k, random_state=int(rng.integers(0, 1 << 31))).copy()
        for _, row in sel.iterrows():
            opened = pd.Timestamp(store_open.get(row["store_id"], "2026-01-01"))
            bad = opened - pd.Timedelta(days=int(rng.integers(20, 60)))
            counts.loc[counts["count_id"] == row["count_id"], "counted_at"] = bad
            counts.loc[counts["count_id"] == row["count_id"], "counted_qty"] = 0
            counts.loc[counts["count_id"] == row["count_id"], "notes"] = "counted before opening date"
            labelled.add(row["count_id"])
            labels.append({"entity_type": "CycleCount", "entity_id": row["count_id"],
                           "issue_type": "count_timing_conflict",
                           "description": f"counted_at {bad.date()} precedes store opening {opened.date()}",
                           "expected_decision": "flag CountTimingConflict"})

    # 4. transfer_double_shrink: both ends count in-transit qty as shrinkage.
    #    Only plant when both ends have enough stock (expected >= qty) so the
    #    loss actually shows as a negative variance at both ends.
    if transfer_pairs is not None and ac["transfer_double_shrink"] > 0:
        t_out, t_in = transfer_pairs
        in_lookup = t_in.set_index("movement_id")
        order = rng.permutation(len(t_out))
        planted = 0
        for idx in order:
            if planted >= ac["transfer_double_shrink"]:
                break
            row = t_out.iloc[idx]
            if row["related_movement_id"] not in in_lookup.index:
                continue
            in_row = in_lookup.loc[row["related_movement_id"]]
            out_at = pd.Timestamp(row["occurred_at"])
            in_at = pd.Timestamp(in_row["occurred_at"])
            mid = out_at + (in_at - out_at) / 2
            qty = abs(row["quantity"])
            dest_store = row["destination_store_id"]
            exp_src = _expected_at(row["store_id"], row["sku_id"], mid, movements_dt, opening_map)
            exp_dst = _expected_at(dest_store, row["sku_id"], mid, movements_dt, opening_map)
            if exp_src < qty or exp_dst < qty:
                continue  # not enough stock to show the in-transit loss
            for st, exp in [(row["store_id"], exp_src), (dest_store, exp_dst)]:
                cid = ids.cnt_id(len(counts) + 1)
                counts.loc[len(counts)] = {
                    "count_id": cid, "store_id": st, "sku_id": row["sku_id"],
                    "counted_qty": exp - qty, "expected_qty": exp, "variance": -qty,
                    "counted_at": mid, "recorded_at": mid + pd.Timedelta(hours=1),
                    "counted_by_employee_id": None, "shift_id": None,
                    "count_status": "Posted", "notes": "in-transit counted as shrinkage",
                }
                labelled.add(cid)
            labels.append({"entity_type": "Movement", "entity_id": row["movement_id"],
                           "issue_type": "transfer_double_shrink",
                           "description": f"both ends of transfer {row['movement_id']} counted {qty} as shrinkage in transit",
                           "expected_decision": "flag TransferDoubleShrink"})
            planted += 1

    # 6. unexplained_loss: big negative variance with no explanation.
    # Pick counts not already labelled, currently variance ~ 0, with enough
    # stock, no explanatory movement in the lookback window, AND not inside
    # a transfer transit window (the detector hands those to
    # TransferDoubleShrink, so they would be skipped here -> false negative).
    expl_types = ["Damage", "Return", "Adjustment", "TransferOut", "TransferIn"]
    expl_mv = movements_dt[movements_dt["movement_type"].isin(expl_types)][
        ["store_id", "sku_id", "occurred_at"]].copy()
    lookback = pd.Timedelta(days=config["detection"]["unexplained_lookback_days"])

    # build transfer transit windows per (store, sku)
    from collections import defaultdict
    t_out_mv = movements_dt[movements_dt["movement_type"] == "TransferOut"][
        ["store_id", "sku_id", "occurred_at", "destination_store_id",
         "related_movement_id"]].copy()
    t_in_ts = movements_dt[movements_dt["movement_type"] == "TransferIn"].set_index(
        "movement_id")["occurred_at"]
    transit = defaultdict(list)
    for _, r in t_out_mv.iterrows():
        in_at = t_in_ts.get(r["related_movement_id"])
        if pd.isna(in_at):
            continue
        out_at = pd.Timestamp(r["occurred_at"])
        in_at = pd.Timestamp(in_at)
        transit[(r["store_id"], r["sku_id"])].append((out_at, in_at))
        transit[(r["destination_store_id"], r["sku_id"])].append((out_at, in_at))

    def has_explanation(store, sku, counted_at):
        win = expl_mv[(expl_mv["store_id"] == store) & (expl_mv["sku_id"] == sku)
                      & (expl_mv["occurred_at"] <= counted_at)
                      & (counted_at - expl_mv["occurred_at"] <= lookback)]
        if not win.empty:
            return True
        # also skip if inside a transfer transit window
        for out_at, in_at in transit.get((store, sku), []):
            if out_at < counted_at < in_at:
                return True
        return False

    cand = counts[(~counts["count_id"].isin(labelled)) & (counts["variance"].abs() <= 1)
                 & (counts["expected_qty"] >= 10)].copy()
    cand["counted_at"] = pd.to_datetime(cand["counted_at"])
    cand = cand[~cand.apply(lambda r: has_explanation(r["store_id"], r["sku_id"],
                                                      r["counted_at"]), axis=1)]
    k = min(ac["unexplained_loss"], len(cand))
    if k > 0:
        sel = cand.sample(k, random_state=int(rng.integers(0, 1 << 31))).copy()
        for _, row in sel.iterrows():
            loss = int(rng.integers(6, 20))
            new_counted = max(row["expected_qty"] - loss, 0)
            counts.loc[counts["count_id"] == row["count_id"], "counted_qty"] = new_counted
            counts.loc[counts["count_id"] == row["count_id"], "notes"] = "unexplained loss"
            labels.append({"entity_type": "CycleCount", "entity_id": row["count_id"],
                           "issue_type": "unexplained_loss",
                           "description": f"variance {new_counted - row['expected_qty']} with no damage/return/transfer explanation",
                           "expected_decision": "flag UnexplainedLoss"})

    return counts, labels


def inject_benign(rng, config, scale, counts, movements, opening):
    """Legitimate variances that should NOT be flagged (true negatives).

    For each chosen count, find a real Damage/Return/Adjustment/Transfer
    movement at the SAME (store, sku) inside the lookback window and set the
    counted_qty so the variance matches that movement. The detector must
    find the explanation and NOT flag the count."""
    bc = config["benign_counts"][scale]
    labels_neg = []
    counts = counts.copy()
    counts["counted_at"] = pd.to_datetime(counts["counted_at"])

    expl_types = ["Damage", "Return", "Adjustment", "TransferOut", "TransferIn"]
    expl = movements[movements["movement_type"].isin(expl_types)][
        ["store_id", "sku_id", "occurred_at", "quantity", "movement_type"]].copy()
    expl["occurred_at"] = pd.to_datetime(expl["occurred_at"])

    cand = counts[counts["notes"] == ""].copy()
    merged = cand.merge(expl, on=["store_id", "sku_id"])
    window = pd.Timedelta(days=config["detection"]["unexplained_lookback_days"])
    merged = merged[(merged["occurred_at"] <= merged["counted_at"]) &
                    (merged["counted_at"] - merged["occurred_at"] <= window)]
    if len(merged) == 0:
        return counts, labels_neg

    uniq = merged["count_id"].drop_duplicates()
    k = min(bc["explained_damage"], len(uniq))
    chosen = uniq.sample(k, random_state=int(rng.integers(0, 1 << 31))).tolist()
    for cid in chosen:
        rows = merged[merged["count_id"] == cid]
        pick = rows.sample(1, random_state=int(rng.integers(0, 1 << 31))).iloc[0]
        new_counted = max(int(pick["expected_qty"]) + int(pick["quantity"]), 0)
        counts.loc[counts["count_id"] == cid, "counted_qty"] = new_counted
        counts.loc[counts["count_id"] == cid, "notes"] = f"explained by {pick['movement_type']}"
        labels_neg.append({"entity_type": "CycleCount", "entity_id": cid,
                           "issue_type": "benign_explained",
                           "description": f"variance explained by {pick['movement_type']} movement in lookback",
                           "expected_decision": "no flag"})
    return counts, labels_neg


# ---------------------------------------------------------------------------
# 7. Ground truth + outputs
# ---------------------------------------------------------------------------
def build_ground_truth(labels, labels_neg):
    rows = []
    for i, l in enumerate(labels, 1):
        rows.append({"label_id": f"GT-{i:06d}", **l, "planted_step": "anomaly_injection"})
    base = len(rows)
    for i, l in enumerate(labels_neg, 1):
        rows.append({"label_id": f"GT-{base + i:06d}", **l, "planted_step": "benign_injection"})
    return pd.DataFrame(rows, columns=["label_id", "entity_type", "entity_id",
                                       "issue_type", "description",
                                       "expected_decision", "planted_step"])


def write_csv(dfs):
    for name, df in dfs.items():
        df.to_csv(os.path.join(DATA_DIR, name + ".csv"), index=False)


def write_json(dfs):
    small = ["store", "sku", "employee", "shift", "promotion", "promotion_sku",
             "opening_balance", "return_event"]
    for name in small:
        if name in dfs:
            df = dfs[name].copy()
            for c in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[c]):
                    df[c] = df[c].astype(str)
            df.to_json(os.path.join(DATA_DIR, name + ".json"), orient="records", indent=2)


def write_sql(dfs):
    db_path = os.path.join(DATA_DIR, "seed.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    for name, df in dfs.items():
        clean = df.copy()
        for c in clean.columns:
            if pd.api.types.is_datetime64_any_dtype(clean[c]):
                clean[c] = clean[c].astype(str)
        clean.to_sql(name, conn, if_exists="replace", index=False)
    with open(os.path.join(DATA_DIR, "seed.sql"), "w") as f:
        for line in conn.iterdump():
            f.write(line + "\n")
    conn.close()


def write_ground_truth(gt):
    gt.to_csv(os.path.join(LABELS_DIR, "ground_truth.csv"), index=False)
    gt.to_json(os.path.join(LABELS_DIR, "ground_truth.json"), orient="records", indent=2)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def write_source_manifest(dfs, gt):
    rows = []
    for name, df in dfs.items():
        path = os.path.join(DATA_DIR, name + ".csv")
        rows.append({"file": os.path.basename(path), "rows": len(df),
                     "bytes": os.path.getsize(path), "sha256": _sha256(path)})
    path = os.path.join(LABELS_DIR, "ground_truth.csv")
    rows.append({"file": "ground_truth.csv", "rows": len(gt),
                 "bytes": os.path.getsize(path), "sha256": _sha256(path)})
    pd.DataFrame(rows).to_csv(os.path.join(REPORTS_DIR, "source_manifest.csv"), index=False)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------
def run(scale="starter", seed=20261022, config_path=None):
    config = load_config(config_path)
    rng = make_streams(seed)
    seq = [0]

    print(f"[generate] scale={scale} seed={seed}")
    stores = generate_stores(rng["store"], config["scales"][scale]["stores"])
    skus = generate_skus(rng["sku"], config["scales"][scale]["skus"])
    employees = generate_employees(rng["emp"], stores)
    shifts = generate_shifts(stores)
    promotions, promo_sku = generate_promotions(rng["promo"], skus)
    catalog = generate_catalog(rng["catalog"], stores, skus, config["catalog_coverage"])
    opening = generate_opening_balances(rng["open"], catalog)
    print(f"[generate] master: stores={len(stores)} skus={len(skus)} "
          f"employees={len(employees)} catalog={len(catalog)}")

    movements, return_events, transfer_pairs = generate_movements(
        rng["move"], config, scale, catalog, employees, shifts, skus, stores)

    # movement-affecting anomalies BEFORE counts so expected stays consistent
    movements, move_labels, transfer_pairs = inject_movement_anomalies(
        rng["anomaly"], config, scale, movements, transfer_pairs,
        employees, shifts, catalog, stores, seq)
    print(f"[generate] movements={len(movements)} (after movement anomalies)")

    running = compute_running_on_hand(movements, opening)
    counts = generate_cycle_counts(rng["count"], config, scale, catalog,
                                   employees, shifts, running, opening)
    print(f"[generate] cycle_counts={len(counts)}")

    # count-affecting anomalies touch counted_at/counted_qty only
    counts, count_labels = inject_count_anomalies(
        rng["anomaly"], config, scale, movements, counts, transfer_pairs,
        stores, opening, seq)

    # recompute expected + variance from final movements for every count.
    # transfer_double_shrink counted_qty was already set during injection
    # (= expected - transfer qty), so variance = -qty after recompute.
    running = compute_running_on_hand(movements, opening)
    counts = recompute_expected(counts, running, opening)
    counts = recompute_variance(counts)

    # count_timing_conflict: counted before opening -> expected = opening_qty.
    # Set counted_qty = expected so variance 0 (the flaw is the date, not qty).
    ct = counts[counts["notes"] == "counted before opening date"]
    if not ct.empty:
        for cid in ct["count_id"]:
            exp = int(counts.loc[counts["count_id"] == cid, "expected_qty"].iloc[0])
            counts.loc[counts["count_id"] == cid, "counted_qty"] = exp
    counts = recompute_variance(counts)

    # benign variances
    counts, labels_neg = inject_benign(rng["benign"], config, scale, counts, movements, opening)
    counts = recompute_variance(counts)
    print(f"[generate] cycle_counts after anomalies/benign={len(counts)}")

    gt = build_ground_truth(move_labels + count_labels, labels_neg)
    print(f"[generate] ground_truth labels={len(move_labels) + len(count_labels)} benign={len(labels_neg)}")

    dfs = {"store": stores, "sku": skus, "employee": employees, "shift": shifts,
           "promotion": promotions, "promotion_sku": promo_sku,
           "opening_balance": opening, "movement": movements,
           "cycle_count": counts, "return_event": return_events}
    write_csv(dfs)
    write_json(dfs)
    write_sql(dfs)
    write_ground_truth(gt)
    write_source_manifest(dfs, gt)
    print(f"[generate] wrote CSV/JSON/SQL to {DATA_DIR}")
    return dfs, gt


def check_repro(seed):
    tmp1 = os.path.join(os.environ.get("TEMP", "/tmp"), "ild_repro_1")
    tmp2 = os.path.join(os.environ.get("TEMP", "/tmp"), "ild_repro_2")
    for d in (tmp1, tmp2):
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(os.path.join(d, "data"), exist_ok=True)
        os.makedirs(os.path.join(d, "labels"), exist_ok=True)
    global DATA_DIR, LABELS_DIR
    orig_data, orig_labels = DATA_DIR, LABELS_DIR
    for d in (tmp1, tmp2):
        DATA_DIR = os.path.join(d, "data")
        LABELS_DIR = os.path.join(d, "labels")
        run(scale="starter", seed=seed)
    DATA_DIR, LABELS_DIR = orig_data, orig_labels
    files = [f for f in os.listdir(os.path.join(tmp1, "data")) if f.endswith(".csv")]
    rows, ok = [], True
    for f in files:
        h1 = _sha256(os.path.join(tmp1, "data", f))
        h2 = _sha256(os.path.join(tmp2, "data", f))
        ok = ok and (h1 == h2)
        rows.append({"file": f, "sha256_run1": h1[:16], "sha256_run2": h2[:16],
                     "identical": h1 == h2})
    rep = pd.DataFrame(rows)
    rep.to_csv(os.path.join(REPORTS_DIR, "reproducibility_report.csv"), index=False)
    print("[repro] identical" if ok else "[repro] MISMATCH")
    print(rep.to_string(index=False))
    shutil.rmtree(tmp1)
    shutil.rmtree(tmp2)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="starter", choices=["starter", "full"])
    ap.add_argument("--seed", type=int, default=20261022)
    ap.add_argument("--check-repro", action="store_true")
    args = ap.parse_args()
    if args.check_repro:
        return check_repro(args.seed)
    run(scale=args.scale, seed=args.seed)


if __name__ == "__main__":
    main()
