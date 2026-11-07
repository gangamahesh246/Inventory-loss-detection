"""Evaluate detector alerts against the ground-truth labels.

The detector never reads ground_truth.csv; this script does. It matches each
alert to a planted label by (entity_id, issue_type) using the mapping in
enums.ISSUE_TO_ALERT, then computes precision / recall / F1 per issue type and
overall. Benign labels (expected_decision "no flag") are checked separately:
a good detector must NOT raise alerts for them.

Outputs:
  reports/evaluation_report.csv  - per-issue metrics + overall row
  reports/evaluation_report.json - same plus confusion counts and benign check

Run:
    python evaluate.py
"""
import json
import os
import pandas as pd

import enums

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
LABELS_DIR = os.path.join(ROOT, "labels")
REPORTS_DIR = os.path.join(ROOT, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)


def load():
    alerts = pd.read_csv(os.path.join(REPORTS_DIR, "alerts.csv"))
    gt = pd.read_csv(os.path.join(LABELS_DIR, "ground_truth.csv"))
    return alerts, gt


def safe_div(a, b):
    return round(a / b, 4) if b else 0.0


def evaluate(alerts, gt):
    # only the six anomaly issue types are scored
    anomaly_types = enums.ISSUE_TYPE
    alert_to_issue = {v: k for k, v in enums.ISSUE_TO_ALERT.items()}

    # split ground truth into anomaly labels and benign labels
    gt_anom = gt[gt["issue_type"].isin(anomaly_types)].copy()
    gt_benign = gt[gt["expected_decision"] == "no flag"].copy()

    # normalise alert issue_type to the ground-truth issue_type key
    alerts = alerts.copy()
    alerts["gt_issue_type"] = alerts["issue_type"].map(alert_to_issue)

    rows = []
    tp_all = fp_all = fn_all = 0
    for it in anomaly_types:
        gt_ids = set(gt_anom[gt_anom["issue_type"] == it]["entity_id"])
        al_ids = set(alerts[alerts["gt_issue_type"] == it]["entity_id"])
        tp = len(gt_ids & al_ids)
        fp = len(al_ids - gt_ids)
        fn = len(gt_ids - al_ids)
        precision = safe_div(tp, tp + fp)
        recall = safe_div(tp, tp + fn)
        f1 = safe_div(2 * precision * recall, precision + recall)
        rows.append({
            "issue_type": it, "support": len(gt_ids),
            "true_positives": tp, "false_positives": fp, "false_negatives": fn,
            "precision": precision, "recall": recall, "f1": f1,
        })
        tp_all += tp
        fp_all += fp
        fn_all += fn

    overall = {
        "issue_type": "OVERALL",
        "support": int(gt_anom["entity_id"].nunique()),
        "true_positives": tp_all, "false_positives": fp_all, "false_negatives": fn_all,
        "precision": safe_div(tp_all, tp_all + fp_all),
        "recall": safe_div(tp_all, tp_all + fn_all),
        "f1": safe_div(2 * safe_div(tp_all, tp_all + fp_all) * safe_div(tp_all, tp_all + fn_all),
                       safe_div(tp_all, tp_all + fp_all) + safe_div(tp_all, tp_all + fn_all)),
    }
    rows.append(overall)
    report = pd.DataFrame(rows)

    # benign check: how many benign labels were correctly NOT flagged?
    benign_ids = set(gt_benign["entity_id"])
    flagged_benign = set(alerts["entity_id"]) & benign_ids
    benign_correct = len(benign_ids) - len(flagged_benign)
    benign_summary = {
        "benign_total": len(benign_ids),
        "benign_correctly_not_flagged": benign_correct,
        "benign_wrongly_flagged": list(flagged_benign),
    }

    return report, benign_summary


def main():
    alerts, gt = load()
    report, benign_summary = evaluate(alerts, gt)
    report.to_csv(os.path.join(REPORTS_DIR, "evaluation_report.csv"), index=False)

    out = {
        "per_issue": report.to_dict(orient="records"),
        "confusion": {
            "true_positives": int(report.iloc[-1]["true_positives"]),
            "false_positives": int(report.iloc[-1]["false_positives"]),
            "false_negatives": int(report.iloc[-1]["false_negatives"]),
        },
        "benign": benign_summary,
        "alerts_total": int(len(alerts)),
        "ground_truth_anomalies": int((gt["issue_type"].isin(enums.ISSUE_TYPE)).sum()),
    }
    with open(os.path.join(REPORTS_DIR, "evaluation_report.json"), "w") as f:
        json.dump(out, f, indent=2)

    print("[evaluate] per-issue metrics:")
    print(report.to_string(index=False))
    print()
    print(f"[evaluate] benign: {benign_summary['benign_correctly_not_flagged']}/"
          f"{benign_summary['benign_total']} correctly NOT flagged")
    if benign_summary["benign_wrongly_flagged"]:
        print(f"[evaluate] WARN: benign wrongly flagged: {benign_summary['benign_wrongly_flagged']}")
    return report


if __name__ == "__main__":
    main()
