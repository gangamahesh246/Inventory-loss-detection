"""Detect unusual inventory loss.

Rule-based detector. Each rule cites the exact records that triggered it
(evidence) so alerts are traceable. The detector never reads
labels/ground_truth.csv - that file is only used by evaluate.py.

The six rules:
  1. MissingReason          - Adjustment with no reason_code
  2. WrongStoreRef          - TransferIn store != TransferOut destination
  3. CountTimingConflict    - count dated before the store opened
  4. TransferDoubleShrink   - both ends of a transfer count in-transit qty
                              as shrinkage during the transit window
  5. RepeatedAdjustments    - same employee/sku/shift with many small negative
                              adjustments inside a short window
  6. UnexplainedLoss        - count variance below threshold with no
                              Damage/Return/Adjustment/Transfer to explain it
                              in the lookback window

Outputs:
  reports/alerts.csv         - one row per alert (SHR-2026-000001)
  reports/investigations.csv - auto-opened investigation per High alert
  reports/reconciliation.csv - per (store, sku) on-hand reconciliation

Run:
    python detect.py
"""
import os
import pandas as pd

import enums
import ids

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
REPORTS_DIR = os.path.join(ROOT, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def load(name):
    return pd.read_csv(os.path.join(DATA_DIR, name + ".csv"), low_memory=False)


def load_config():
    import yaml
    with open(os.path.join(ROOT, "config.yaml")) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Reconciliation: rebuild expected on-hand from movements + opening
# ---------------------------------------------------------------------------
def reconcile(movements, opening):
    """Per (store, sku): opening + sum(movements) = expected_on_hand.
    Returns one row per (store, sku) with the final reconciled balance."""
    g = movements.groupby(["store_id", "sku_id"])
    moved = g["quantity"].sum().reset_index().rename(columns={"quantity": "net_movement"})
    ob = opening[["store_id", "sku_id", "opening_qty"]]
    r = ob.merge(moved, on=["store_id", "sku_id"], how="left").fillna({"net_movement": 0})
    r["expected_on_hand"] = (r["opening_qty"] + r["net_movement"]).clip(lower=0).astype(int)
    return r[["store_id", "sku_id", "opening_qty", "net_movement", "expected_on_hand"]]


# ---------------------------------------------------------------------------
# Alert container
# ---------------------------------------------------------------------------
class Alerts:
    def __init__(self):
        self.rows = []
        self.seq = 1

    def add(self, store_id, sku_id, entity_type, entity_id, issue_type,
            severity, score, evidence):
        self.rows.append({
            "alert_id": ids.shr_id(self.seq),
            "store_id": store_id,
            "sku_id": sku_id if pd.notna(sku_id) else "",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "issue_type": issue_type,
            "severity": severity,
            "score": round(float(score), 3),
            "evidence": evidence,
            "created_at": "2026-11-01",
            "status": "Open",
        })
        self.seq += 1

    def to_df(self):
        return pd.DataFrame(self.rows, columns=ids.COLUMNS["shrinkage_alert"])


# ---------------------------------------------------------------------------
# Rule 1: MissingReason
# ---------------------------------------------------------------------------
def rule_missing_reason(movements, alerts):
    adj = movements[(movements["movement_type"] == "Adjustment")
                    & (movements["reason_code"].isna())]
    for _, r in adj.iterrows():
        evidence = (f"Adjustment {r['movement_id']} qty={r['quantity']} at "
                    f"{r['store_id']}/{r['sku_id']} has reason_code=NULL")
        alerts.add(r["store_id"], r["sku_id"], "Movement", r["movement_id"],
                   "MissingReason", "Medium", 0.8, evidence)
    return len(adj)


# ---------------------------------------------------------------------------
# Rule 2: WrongStoreRef
# ---------------------------------------------------------------------------
def rule_wrong_store_ref(movements, alerts):
    t_out = movements[movements["movement_type"] == "TransferOut"][
        ["movement_id", "store_id", "sku_id", "destination_store_id",
         "related_movement_id"]].copy()
    t_in = movements[movements["movement_type"] == "TransferIn"][
        ["movement_id", "store_id", "related_movement_id"]].copy()
    if t_out.empty or t_in.empty:
        return 0
    merged = t_in.merge(t_out, left_on="related_movement_id",
                        right_on="movement_id", suffixes=("_in", "_out"))
    wrong = merged[merged["store_id_in"] != merged["destination_store_id"]]
    for _, r in wrong.iterrows():
        evidence = (f"TransferIn {r['movement_id_in']} recorded at "
                    f"{r['store_id_in']} but TransferOut {r['movement_id_out']} "
                    f"declared destination {r['destination_store_id']}")
        alerts.add(r["store_id_in"], r["sku_id"], "Movement", r["movement_id_in"],
                   "WrongStoreRef", "High", 0.9, evidence)
    return len(wrong)


# ---------------------------------------------------------------------------
# Rule 3: CountTimingConflict
# ---------------------------------------------------------------------------
def rule_count_timing(counts, stores, alerts):
    s = stores[["store_id", "opened_on"]].copy()
    c = counts.merge(s, on="store_id", how="left")
    c["counted_at"] = pd.to_datetime(c["counted_at"])
    c["opened_on"] = pd.to_datetime(c["opened_on"])
    bad = c[c["counted_at"] < c["opened_on"]]
    for _, r in bad.iterrows():
        evidence = (f"Count {r['count_id']} at {r['store_id']}/{r['sku_id']} "
                    f"counted_at {pd.Timestamp(r['counted_at']).date()} precedes "
                    f"store opening {pd.Timestamp(r['opened_on']).date()}")
        alerts.add(r["store_id"], r["sku_id"], "CycleCount", r["count_id"],
                   "CountTimingConflict", "Medium", 0.7, evidence)
    return len(bad)


# ---------------------------------------------------------------------------
# Rule 4: TransferDoubleShrink
# ---------------------------------------------------------------------------
def rule_transfer_double_shrink(movements, counts, config, alerts):
    t_out = movements[movements["movement_type"] == "TransferOut"][
        ["movement_id", "store_id", "sku_id", "quantity", "occurred_at",
         "destination_store_id", "related_movement_id"]].copy()
    t_in = movements[movements["movement_type"] == "TransferIn"][
        ["movement_id", "store_id", "occurred_at", "related_movement_id"]].copy()
    if t_out.empty or t_in.empty:
        return 0
    pairs = t_out.merge(t_in, left_on="related_movement_id", right_on="movement_id",
                        suffixes=("_out", "_in"))
    pairs["occurred_at_out"] = pd.to_datetime(pairs["occurred_at_out"])
    pairs["occurred_at_in"] = pd.to_datetime(pairs["occurred_at_in"])
    c = counts[["count_id", "store_id", "sku_id", "variance", "counted_at"]].copy()
    c["counted_at"] = pd.to_datetime(c["counted_at"])
    tol = config["detection"]["transfer_variance_tolerance"]
    flagged = 0
    for _, p in pairs.iterrows():
        qty = abs(p["quantity"])
        window = c[(c["sku_id"] == p["sku_id"]) &
                   (c["counted_at"] > p["occurred_at_out"]) &
                   (c["counted_at"] < p["occurred_at_in"])]
        at_src = window[(window["store_id"] == p["store_id_out"]) &
                        (window["variance"] <= -qty + tol)]
        at_dst = window[(window["store_id"] == p["destination_store_id"]) &
                        (window["variance"] <= -qty + tol)]
        if not at_src.empty and not at_dst.empty:
            sc = at_src.iloc[0]["count_id"]
            dc = at_dst.iloc[0]["count_id"]
            evidence = (f"Transfer {p['movement_id_out']} qty={qty} in transit "
                        f"{p['occurred_at_out'].date()}->{p['occurred_at_in'].date()}; "
                        f"both ends counted as shrinkage (src count {sc}, dst count {dc})")
            alerts.add(p["store_id_out"], p["sku_id"], "Movement",
                       p["movement_id_out"], "TransferDoubleShrink", "High", 0.85, evidence)
            flagged += 1
    return flagged


# ---------------------------------------------------------------------------
# Rule 5: RepeatedAdjustments
# ---------------------------------------------------------------------------
def rule_repeated_adjustments(movements, config, alerts):
    adj = movements[(movements["movement_type"] == "Adjustment")
                    & (movements["quantity"] < 0)].copy()
    if adj.empty:
        return 0
    adj["occurred_at"] = pd.to_datetime(adj["occurred_at"])
    win_days = config["detection"]["repeated_adjustment_window_days"]
    threshold = config["detection"]["repeated_adjustment_min_count"]
    flagged = 0
    seen = set()
    for (emp, sku, shf), g in adj.groupby(["employee_id", "sku_id", "shift_id"]):
        g = g.sort_values("occurred_at")
        dates = g["occurred_at"].tolist()
        n = len(dates)
        if n < threshold:
            continue
        # sliding window: is there any window of win_days containing >= threshold?
        hit = False
        for i in range(n):
            j = i
            while j < n and (dates[j] - dates[i]).days <= win_days:
                j += 1
            if (j - i) >= threshold:
                hit = True
                break
        if hit and emp not in seen:
            seen.add(emp)
            total = int(g["quantity"].sum())
            evidence = (f"{n} negative adjustments by employee {emp} on {sku} "
                        f"shift {shf} totalling {total} units; span "
                        f"{(dates[-1] - dates[0]).days} days")
            alerts.add(g.iloc[0]["store_id"], sku, "Employee", emp,
                       "RepeatedAdjustments", "High", 0.9, evidence)
            flagged += 1
    return flagged


# ---------------------------------------------------------------------------
# Rule 6: UnexplainedLoss
# ---------------------------------------------------------------------------
def rule_unexplained_loss(counts, movements, config, alerts):
    threshold = config["detection"]["unexplained_loss_threshold"]
    lookback = config["detection"]["unexplained_lookback_days"]
    bad = counts[counts["variance"] <= threshold].copy()
    if bad.empty:
        return 0
    bad["counted_at"] = pd.to_datetime(bad["counted_at"])

    # precompute transfer transit windows per (store, sku) so we can skip
    # in-transit counts - those belong to the TransferDoubleShrink rule
    from collections import defaultdict
    t_out = movements[movements["movement_type"] == "TransferOut"][
        ["store_id", "sku_id", "occurred_at", "destination_store_id",
         "related_movement_id"]].copy()
    t_in_ts = movements[movements["movement_type"] == "TransferIn"].set_index(
        "movement_id")["occurred_at"]
    windows = defaultdict(list)
    for _, r in t_out.iterrows():
        in_at = t_in_ts.get(r["related_movement_id"])
        if pd.isna(in_at):
            continue
        out_at = pd.Timestamp(r["occurred_at"])
        in_at = pd.Timestamp(in_at)
        windows[(r["store_id"], r["sku_id"])].append((out_at, in_at))
        windows[(r["destination_store_id"], r["sku_id"])].append((out_at, in_at))

    expl_types = ["Damage", "Return", "Adjustment", "TransferOut", "TransferIn"]
    expl = movements[movements["movement_type"].isin(expl_types)][
        ["store_id", "sku_id", "occurred_at"]].copy()
    expl["occurred_at"] = pd.to_datetime(expl["occurred_at"])
    flagged = 0
    for _, c in bad.iterrows():
        key = (c["store_id"], c["sku_id"])
        in_transit = any(out_at < c["counted_at"] < in_at
                        for out_at, in_at in windows.get(key, []))
        if in_transit:
            continue  # handled by TransferDoubleShrink
        window_start = c["counted_at"] - pd.Timedelta(days=lookback)
        match = expl[(expl["store_id"] == c["store_id"]) &
                     (expl["sku_id"] == c["sku_id"]) &
                     (expl["occurred_at"] >= window_start) &
                     (expl["occurred_at"] <= c["counted_at"])]
        if match.empty:
            evidence = (f"Count {c['count_id']} at {c['store_id']}/{c['sku_id']} "
                        f"variance={c['variance']} with no Damage/Return/Adjustment/"
                        f"Transfer in the {lookback}-day lookback window")
            alerts.add(c["store_id"], c["sku_id"], "CycleCount", c["count_id"],
                       "UnexplainedLoss", "High", 0.8, evidence)
            flagged += 1
    return flagged


# ---------------------------------------------------------------------------
# Investigations: auto-open one per High-severity alert
# ---------------------------------------------------------------------------
def open_investigations(alerts_df):
    rows = []
    seq = 1
    high = alerts_df[alerts_df["severity"] == "High"]
    for _, a in high.iterrows():
        rows.append({
            "investigation_id": ids.inv_id(seq),
            "alert_id": a["alert_id"],
            "assigned_to": "Ops Manager",
            "status": "Open",
            "opened_at": "2026-11-01",
            "closed_at": "",
            "notes": f"Auto-opened for {a['issue_type']} at {a['store_id']}",
        })
        seq += 1
    return pd.DataFrame(rows, columns=ids.COLUMNS["investigation"])


# ---------------------------------------------------------------------------
def main():
    config = load_config()
    movements = load("movement")
    counts = load("cycle_count")
    stores = load("store")
    opening = load("opening_balance")

    print("[detect] reconciling stock...")
    recon = reconcile(movements, opening)
    recon.to_csv(os.path.join(REPORTS_DIR, "reconciliation.csv"), index=False)

    alerts = Alerts()
    n1 = rule_missing_reason(movements, alerts)
    n2 = rule_wrong_store_ref(movements, alerts)
    n3 = rule_count_timing(counts, stores, alerts)
    n4 = rule_transfer_double_shrink(movements, counts, config, alerts)
    n5 = rule_repeated_adjustments(movements, config, alerts)
    n6 = rule_unexplained_loss(counts, movements, config, alerts)

    alerts_df = alerts.to_df()
    alerts_df.to_csv(os.path.join(REPORTS_DIR, "alerts.csv"), index=False)
    inv = open_investigations(alerts_df)
    inv.to_csv(os.path.join(REPORTS_DIR, "investigations.csv"), index=False)

    print(f"[detect] alerts: total={len(alerts_df)}")
    print(f"  MissingReason={n1} WrongStoreRef={n2} CountTimingConflict={n3} "
          f"TransferDoubleShrink={n4} RepeatedAdjustments={n5} UnexplainedLoss={n6}")
    print(f"[detect] investigations opened: {len(inv)}")
    if not alerts_df.empty:
        print(alerts_df["issue_type"].value_counts().to_string())
    return alerts_df


if __name__ == "__main__":
    main()
