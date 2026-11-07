# Inventory Loss Detection

Detect unusual inventory loss by comparing **receipts, sales, transfers,
adjustments, returns and counts**. The pipeline generates a labelled
synthetic dataset, runs a rule-based detector that reconciles stock and
flags unusual loss with evidence, and evaluates the alerts against a
separate ground-truth file.

This is a fresher-style solution: plain Python + pandas + numpy, simple
functions, one job per file, no ML libraries.

---

## Quick start

```bash
# default = starter scale (fast, ~seconds)
python run_all.py

# full requested volume: 100 stores, 5,000 SKUs, 1M movements, 20k counts
python run_all.py --scale full

# prove the same seed gives identical output (generates twice, compares SHA-256)
python run_all.py --check-repro
```

Each step can also be run on its own:

```bash
python generate.py --scale starter      # build the dataset
python validate.py                      # 46 integrity/reconciliation checks
python detect.py                        # 6 rule-based detectors -> alerts
python evaluate.py                      # precision / recall / F1 vs ground truth
```

---

## The problem in one sentence

> Compare what stock **should be** (from movements) vs what stock **actually
> is** (from cycle counts), and flag the gaps that have no legitimate
> explanation.

### The stock equation

```
opening_balance
  + receipts + transfer_in + returns
  - sales    - transfer_out - damage
  = expected_on_hand

variance = counted_qty (cycle count) - expected_on_hand
```

- `variance == 0` -> fine
- `variance != 0` **with** a reason (posted damage, in-transit, recount)
  -> benign
- `variance != 0` **without** a reason -> suspicious -> alert

On-hand is floored at 0 (a store cannot hold negative stock - stockout
modelling).

---

## Project layout

```
Inventory_Loss_Detection/
  config.yaml            seed, scales, movement mix, anomaly + detection params
  ids.py                 zero-padded immutable ID helpers + column lists
  enums.py               allowed enum values for every field
  generate.py            synthetic data + anomaly injection + ground truth
  validate.py            46 integrity & reconciliation checks
  detect.py              6 rule-based detectors + investigations
  evaluate.py            precision / recall / F1 vs ground truth
  run_all.py             orchestrator + reproducibility check
  requirements.txt
  data/                  CSV (all tables) + JSON (master tables) + seed.sql/seed.db
  labels/                ground_truth.csv / .json  (NEVER read by the detector)
  reports/               validation_summary, alerts, investigations,
                         reconciliation, evaluation_report, source_manifest,
                         reproducibility_report
  tests/                 pytest: ids, validation, reproducibility, reconciliation
  docs/data_dictionary.md
```

---

## Entities and IDs

| Entity | PK pattern | Key FKs | Cardinality |
|---|---|---|---|
| store | STORE-000001 | - | 1:N employee, shift, movement, count |
| sku | SKU-000001 | - | 1:N movement, count, return |
| employee | EMP-000001 | store_id | N:1 store |
| shift | SHF-000001 | store_id | N:1 store |
| promotion | PROMO-000001 | - | N:M sku via promotion_sku |
| promotion_sku | (promotion_id, sku_id) | both | bridge table |
| opening_balance | (store_id, sku_id) | both | 1:1 store-sku snapshot |
| movement | MOV-2026-00000001 | store, sku, employee, shift, related_movement_id (self) | event history (append-only) |
| cycle_count | CNT-2026-000001 | store, sku, counted_by_employee_id | 1 per count |
| return_event | RET-2026-000001 | sale_movement_id, return_movement_id | 1:1 return movement |
| shrinkage_alert | SHR-2026-000001 | store, sku, entity_id | detector output |
| investigation | INV-2026-000001 | alert_id | 1:1 alert (High severity) |

Movement self-reference `related_movement_id` links transfer out/in pairs and
returns to their original sale. IDs are immutable and zero-padded.

---

## The six detector rules (each cites exact records as evidence)

| Rule | What it flags | Signal |
|---|---|---|
| MissingReason | Adjustment with `reason_code IS NULL` | null check |
| WrongStoreRef | TransferIn store != TransferOut destination | transfer-pair mismatch |
| CountTimingConflict | count dated before the store opened | `counted_at < opened_on` |
| TransferDoubleShrink | both ends of a transfer count in-transit qty as shrinkage | both ends have a count in the transit window with negative variance ~= -transfer qty |
| RepeatedAdjustments | same employee/sku/shift with many small negative adjustments in a short window | concentration pattern |
| UnexplainedLoss | count variance below threshold with no Damage/Return/Adjustment/Transfer in the lookback window | variance + no explanation |

`UnexplainedLoss` deliberately skips counts that fall inside a transfer's
transit window (those belong to `TransferDoubleShrink`), so a count is not
double-flagged.

Each alert row carries an `evidence` string citing the exact movement/count
IDs, a 0-1 `score`, and a `severity`. High-severity alerts auto-open an
`Investigation`.

---

## Planted anomalies + benign cases (ground truth)

The four mandatory edge cases plus two extra patterns are planted with the
flaw visible in the data; only the **label** goes to `labels/ground_truth.csv`
(which the detector never reads):

| issue_type | how it appears in the data |
|---|---|
| wrong_store_ref | TransferIn.store_id != the paired TransferOut.destination_store_id |
| missing_reason | Adjustment rows with `reason_code = NULL` |
| count_timing_conflict | `counted_at` set before the store's `opened_on` date |
| transfer_double_shrink | both ends of a transfer get a count during transit with variance = -transfer qty |
| repeated_adjustments | one employee/sku/shift gets many small negative adjustments on consecutive days |
| unexplained_loss | a count gets a large negative variance with no explanatory movement nearby |

Benign cases (legitimate damage / returns / transfers whose variance IS
explained) are also planted so the detector is rewarded for NOT flagging
them. They are recorded in ground truth with `expected_decision = "no flag"`.

---

## Outputs in reports/

- `validation_summary.csv` - 46 checks, each PASS/FAIL with violation count
- `alerts.csv` - one row per alert with evidence, score, severity
- `investigations.csv` - auto-opened investigation per High-severity alert
- `reconciliation.csv` - per (store, sku) opening + net movement = expected_on_hand
- `evaluation_report.csv` / `.json` - precision/recall/F1 per issue type + benign check
- `source_manifest.csv` - per-file rows, bytes, SHA-256
- `reproducibility_report.csv` - SHA-256 of two runs with the same seed

---

## Reproducibility

A single master seed `20261022` is split into independent sub-streams with
`numpy.random.SeedSequence.spawn`, one per table. Changing one table's count
never shifts another table's output. `--check-repro` generates twice and
confirms every CSV has an identical SHA-256.

---

## Lawful use / provenance

All data is fully synthetic, generated locally with a fixed seed. No
external or personal data is used. `source_manifest.csv` records the file
name, row count, byte size and SHA-256 of every output for traceability.
