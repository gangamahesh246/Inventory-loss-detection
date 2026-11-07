# Inventory Loss Detection

Detect unusual inventory loss by comparing **receipts, sales, transfers,
adjustments, returns and counts**. The pipeline generates a labelled
synthetic dataset, runs a rule-based detector that reconciles stock and
flags unusual loss with evidence, and evaluates the alerts against a
separate ground-truth file.

This is a fresher-style solution: plain Python + pandas + numpy, simple
functions, one job per file, no ML libraries. See
[`AI_DISCLOSURE.md`](AI_DISCLOSURE.md) for how AI was used and what I
validated myself.

---

## Setup

**Environment:** Python 3.10+ (developed and verified on Python 3.14.6,
Windows 10). No external services, no network access, no GPU.

**Install dependencies:**
```bash
pip install -r requirements.txt
```
Dependencies (all free, locally runnable, small): `pandas`, `numpy`,
`PyYAML`. Tests use `pytest` (optional — only needed to run the test suite).

> No secrets, credentials, or personal data are used. All data is synthetic
> and generated locally with a fixed seed.

## Run

```bash
# default = starter scale (fast, ~seconds)
python run_all.py

# full requested volume: 100 stores, 5,000 SKUs, 1M movements, 20k counts (~few min)
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

## Verify

After `python run_all.py --scale starter` you should see:
- `[validate] 46 checks, 0 failures` — `reports/validation_summary.csv`
- `[detect] alerts: total=37` — `reports/alerts.csv`, `reports/investigations.csv`
- `OVERALL ... precision 1.0 recall 1.0 f1 1.0` — `reports/evaluation_report.csv`
- `benign: 15/15 correctly NOT flagged`

Run the automated tests:
```bash
python -m pytest tests/ -v
# expected: 15 passed
```

Confirm reproducibility:
```bash
python run_all.py --check-repro
# expected: [repro] identical  (all CSV SHA-256 match across two runs)
```

## How I verified the core functionality

- **Stock equation reconciles** — `validate.py` checks `opening + net
  movement == expected_on_hand` (floored at 0) for every count; 46/46 pass.
- **Alerts are evidence-based** — every row in `reports/alerts.csv` carries
  an `evidence` string citing the exact movement/count IDs.
- **Planted patterns are evaluated** — `reports/evaluation_report.csv`
  reports precision/recall/F1 per issue type against `labels/ground_truth.csv`.
- **Benign explanations are represented** — 15/15 benign counts correctly
  NOT flagged.
- **Reproducible** — `--check-repro` confirms identical SHA-256 across two
  runs with seed `20261022`.

---

## Assumptions

1. **No external data** — everything is synthetic, generated with a fixed
   seed. This satisfies the "lawful use" guidance (no licensing risk).
2. **Starter scale is the default** — the full 1M-movement dataset takes a
   few minutes and ~500 MB of disk, so starter (10 stores / 500 SKUs / 50k
   movements / 1k counts) is the default for fast iteration. The same
   generator produces both; only counts in `config.yaml` change.
3. **Rule-based detection, no ML** — the brief asks to "expose key decisions
   and exceptions". Deterministic rules with cited evidence are more
   explainable than an ML model and need no training step.
4. **On-hand is floored at 0** — a store cannot hold negative stock
   (stockout modelling). Sales that exceed available stock reduce on-hand
   to 0, not below.
5. **Detector never reads ground truth** — `labels/ground_truth.csv` is only
   read by `evaluate.py`. This prevents label leakage.
6. **TransferIn `employee_id` may be null** — for generated transfer-in rows
   the employee at the destination is assigned during generation; the
   validator treats `employee_id` as nullable.
7. **`reason_code` is nullable only for Adjustments** — the `missing_reason`
   anomaly relies on this. All other movement types have a reason.

## Key decisions and trade-offs

- **`SeedSequence.spawn` for per-table RNG streams** — each table draws from
  an independent sub-stream, so changing one table's row count never shifts
  another table's output. Trade-off: slightly more setup than a single RNG,
  but much better reproducibility isolation.
- **Append-only event history** — movements are never overwritten; transfers
  link out/in via `related_movement_id`. Trade-off: more rows, but full
  traceability.
- **Anomalies corrupt the "observed" side only** — `expected_qty` is always
  derived from final movements, so the stock equation always reconciles.
  Anomalies only touch `counted_qty`, `counted_at`, `reason_code`, or
  `store_id`. Trade-off: the generator is more complex, but validation stays
  clean.
- **`UnexplainedLoss` skips in-transit counts** — counts inside a transfer's
  transit window belong to `TransferDoubleShrink`, so a count is not
  double-flagged. Trade-off: the two rules are coupled, but alert
  deduplication is cleaner.
- **sqlite3 stdlib for SQL export** — zero-install, no DuckDB dependency.
  Trade-off: smaller ecosystem than DuckDB, but no extra pip install.

## Testing approach

- **Unit tests** (`tests/test_pipeline.py`, 15 tests via `pytest`) cover ID
  formats, primary-key uniqueness, movement quantity signs, variance
  arithmetic, expected_qty flooring, transfer pairing, the planted
  null-reason anomaly, stock reconciliation, ground-truth coverage, detector
  recall, benign non-flagging, and reproducibility by row count.
- **Data validation** (`validate.py`, 46 checks) covers PK uniqueness, FK
  integrity, ID format regex, enum membership, date ordering, quantity
  signs, the stock equation, variance arithmetic, and duplicate transfer
  pairing — written as both pandas checks and SQL assertions.
- **End-to-end runs** at starter and full scale confirm the whole pipeline
  produces the expected row counts and metrics.

## Limitations

- **Detector precision is 1.0 by construction** — because I plant the
  anomalies and write the rules, the detector is tuned to find exactly them.
  On real (non-synthetic) data, precision would be lower; the rules would
  need threshold tuning per retailer.
- **No time-series seasonality** — sales are sampled uniformly across the
  date range; real sales have day-of-week and holiday peaks.
- **No multi-store transfer chains** — a transfer goes from one store
  directly to one other store; no hub-and-spoke or multi-leg routing.
- **Single currency, single country** — `unit_cost` is one currency; no
  FX or regional pricing.
- **No employee collusion modelling** — `repeated_adjustments` targets one
  employee; real fraud often involves two or more.
- **PDF guidance docs could not be read by the AI directly** — I extracted
  their text with `pdfplumber` and followed the requirements myself; see
  `AI_DISCLOSURE.md`.

## What is incomplete / next steps

- Everything in the original brief is implemented and verified; there is no
  incomplete core functionality.
- Possible next steps (out of scope for this submission): ML baseline for
  comparison, multi-leg transfers, seasonality in sales, a simple CLI to
  recompute alerts for a single store/sku, and a small dashboard for
  investigations.

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
  AI_DISCLOSURE.md        where/how AI was used, what I validated
  README.md
  data/                  CSV (all tables) + JSON (master tables) + seed.sql/seed.db
  labels/                ground_truth.csv / .json  (NEVER read by the detector)
  reports/               validation_summary, alerts, investigations,
                         reconciliation, evaluation_report, source_manifest,
                         reproducibility_report
  tests/                 pytest: ids, validation, reproducibility, reconciliation
  prompts/PROMPT_HISTORY.md   every prompt I sent to the AI tool
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
