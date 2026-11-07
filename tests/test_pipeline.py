import os
import sys

import pytest

# Make the project root importable so tests can import the modules.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import ids
import enums
import generate
import validate
import detect
import evaluate


# ---------------------------------------------------------------------------
# Fixtures: build a tiny dataset once for the test session.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def generated(tmp_path_factory):
    """Generate a starter dataset into a temp dir so tests do not clobber
    the real data/ folder."""
    import shutil
    tmp = tmp_path_factory.mktemp("ild")
    os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "labels"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "reports"), exist_ok=True)
    orig = (generate.DATA_DIR, generate.LABELS_DIR, generate.REPORTS_DIR)
    generate.DATA_DIR = os.path.join(tmp, "data")
    generate.LABELS_DIR = os.path.join(tmp, "labels")
    generate.REPORTS_DIR = os.path.join(tmp, "reports")
    try:
        dfs, gt = generate.run(scale="starter", seed=20261022)
    finally:
        generate.DATA_DIR, generate.LABELS_DIR, generate.REPORTS_DIR = orig
    return {"dfs": dfs, "gt": gt, "root": tmp}


@pytest.fixture(scope="session")
def detected(generated):
    # point detect/evaluate at the temp data
    orig_data = detect.DATA_DIR
    orig_labels = evaluate.LABELS_DIR
    detect.DATA_DIR = os.path.join(generated["root"], "data")
    evaluate.LABELS_DIR = os.path.join(generated["root"], "labels")
    try:
        movements = detect.load("movement")
        counts = detect.load("cycle_count")
        stores = detect.load("store")
        opening = detect.load("opening_balance")
        import yaml
        with open(os.path.join(ROOT, "config.yaml")) as f:
            config = yaml.safe_load(f)
        alerts = detect.Alerts()
        detect.rule_missing_reason(movements, alerts)
        detect.rule_wrong_store_ref(movements, alerts)
        detect.rule_count_timing(counts, stores, alerts)
        detect.rule_transfer_double_shrink(movements, counts, config, alerts)
        detect.rule_repeated_adjustments(movements, config, alerts)
        detect.rule_unexplained_loss(counts, movements, config, alerts)
        alerts_df = alerts.to_df()
    finally:
        detect.DATA_DIR = orig_data
        evaluate.LABELS_DIR = orig_labels
    return {"alerts": alerts_df, "gt": generated["gt"]}


# ---------------------------------------------------------------------------
# ID format tests
# ---------------------------------------------------------------------------
def test_store_id_format():
    assert ids.store_id(1) == "STORE-000001"
    assert ids.store_id(100) == "STORE-000100"


def test_mov_id_format():
    assert ids.mov_id(1) == "MOV-2026-00000001"
    assert ids.mov_id(42) == "MOV-2026-00000042"


def test_cnt_id_format():
    assert ids.cnt_id(1) == "CNT-2026-000001"
    assert ids.cnt_id(20) == "CNT-2026-000020"


def test_ids_are_immutable_strings():
    s = ids.store_id(5)
    assert isinstance(s, str)
    assert s == ids.store_id(5)  # deterministic


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------
def test_primary_keys_unique(generated):
    for t, col in [("store", "store_id"), ("sku", "sku_id"),
                   ("movement", "movement_id"), ("cycle_count", "count_id")]:
        df = generated["dfs"][t]
        assert df[col].is_unique, f"duplicate PK in {t}"


def test_movement_quantity_signs(generated):
    m = generated["dfs"]["movement"]
    assert (m[m["movement_type"].isin(["Receipt", "TransferIn", "Return"])]["quantity"] > 0).all()
    assert (m[m["movement_type"].isin(["Sale", "TransferOut", "Damage"])]["quantity"] < 0).all()


def test_variance_equals_counted_minus_expected(generated):
    c = generated["dfs"]["cycle_count"]
    assert (c["variance"] == c["counted_qty"] - c["expected_qty"]).all()


def test_expected_qty_non_negative(generated):
    c = generated["dfs"]["cycle_count"]
    assert (c["expected_qty"] >= 0).all(), "expected_qty must be floored at 0"


def test_no_duplicate_transfer_pairing(generated):
    m = generated["dfs"]["movement"]
    tin = m[m["movement_type"] == "TransferIn"]
    assert tin["related_movement_id"].is_unique


def test_adjustment_null_reason_is_planted(generated):
    """The only rows allowed to have null reason_code are Adjustments
    (the missing_reason anomaly)."""
    m = generated["dfs"]["movement"]
    null_reason = m[m["reason_code"].isna()]
    assert (null_reason["movement_type"] == "Adjustment").all()
    assert len(null_reason) > 0  # at least one planted


# ---------------------------------------------------------------------------
# Reconciliation test
# ---------------------------------------------------------------------------
def test_stock_reconciliation(generated):
    movements = generated["dfs"]["movement"]
    opening = generated["dfs"]["opening_balance"]
    recon = detect.reconcile(movements, opening)
    # expected_on_hand = max(0, opening + net_movement)
    assert (recon["expected_on_hand"] >= 0).all()
    assert ((recon["opening_qty"] + recon["net_movement"]).clip(lower=0).astype(int)
            == recon["expected_on_hand"]).all()


# ---------------------------------------------------------------------------
# Ground truth / detection tests
# ---------------------------------------------------------------------------
def test_ground_truth_has_all_six_issue_types(generated):
    gt = generated["gt"]
    for it in enums.ISSUE_TYPE:
        assert it in set(gt["issue_type"]), f"missing planted issue {it}"


def test_detector_finds_all_planted_anomalies(detected):
    gt = detected["gt"]
    alerts = detected["alerts"]
    alert_to_issue = {v: k for k, v in enums.ISSUE_TO_ALERT.items()}
    alerts["gt_issue"] = alerts["issue_type"].map(alert_to_issue)
    for it in enums.ISSUE_TYPE:
        gt_ids = set(gt[gt["issue_type"] == it]["entity_id"])
        al_ids = set(alerts[alerts["gt_issue"] == it]["entity_id"])
        assert gt_ids == al_ids, f"issue {it}: missed {gt_ids - al_ids}, extra {al_ids - gt_ids}"


def test_no_benign_flagged(detected):
    gt = detected["gt"]
    alerts = detected["alerts"]
    benign_ids = set(gt[gt["expected_decision"] == "no flag"]["entity_id"])
    flagged = set(alerts["entity_id"])
    assert benign_ids.isdisjoint(flagged), "a benign case was wrongly flagged"


# ---------------------------------------------------------------------------
# Reproducibility test (seed gives same row counts)
# ---------------------------------------------------------------------------
def test_reproducibility_same_row_counts(generated):
    """Two runs with the same seed must produce the same row counts. We
    compare against a fresh run in a temp dir."""
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmp, "data"), exist_ok=True)
    os.makedirs(os.path.join(tmp, "labels"), exist_ok=True)
    orig = (generate.DATA_DIR, generate.LABELS_DIR)
    generate.DATA_DIR = os.path.join(tmp, "data")
    generate.LABELS_DIR = os.path.join(tmp, "labels")
    try:
        dfs2, _ = generate.run(scale="starter", seed=20261022)
    finally:
        generate.DATA_DIR, generate.LABELS_DIR = orig
    for t in generated["dfs"]:
        assert len(generated["dfs"][t]) == len(dfs2[t]), f"row count differs for {t}"
    shutil.rmtree(tmp)
