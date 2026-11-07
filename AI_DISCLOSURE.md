# AI Use Disclosure

Per the YottaFlex AI Candidate Project Submission Guidelines (item #3) and
FAQ (items #5, #6, #7), this file explains how I used AI while building this
project, where it accelerated my work, where I relied on it, and what I
personally reviewed, changed, or validated.

## Tool used

- **Claude** via the `opencode` CLI (model `glm-5.2`).
- No other AI tool was used. The full prompt history is in
  [`prompts/PROMPT_HISTORY.md`](prompts/PROMPT_HISTORY.md).

## Where AI accelerated my work

- **Project scaffolding** — generating the initial folder layout, the
  `config.yaml` structure, and the zero-padded ID helpers (`ids.py`).
- **Boilerplate** — writing the enum tables (`enums.py`) and the data
  dictionary (`docs/data_dictionary.md`) from the spec.
- **Pandas patterns** — the `merge_asof` usage for "expected on-hand as of a
  count date" and the `SeedSequence.spawn` pattern for independent per-table
  RNG streams.
- **First-pass implementation** — the initial draft of `generate.py`,
  `validate.py`, `detect.py`, and `evaluate.py`.
- **Writing the README** and this disclosure file.

## Where I relied more heavily on AI

- The first end-to-end draft of the generator. I then debugged it myself
  (see below).

## What I personally reviewed, changed, or validated

Every line of code was reviewed and many were rewritten by me. Concrete
examples of changes I made after the AI's first draft:

1. **Fixed the quantity-range key mismatch** — `mtype.lower()` produced
   `transferout` but the config key was `transfer_out`; I added a mapping
   dict so the lookup matched.
2. **Fixed `merge_asof` sort errors** — the API requires both left and right
   keys globally sorted; I corrected the sort calls and re-ran until it
   worked.
3. **Fixed `expected_qty` going negative** — sales outpacing receipts made
   on-hand negative, which is unrealistic. I floored on-hand at 0 (stockout
   modelling) in both `generate.py` and `validate.py`, and excluded
   low-stock counts from `unexplained_loss` candidates.
4. **Caught a missing `destination_store_id` column** — the detector needs
   this to find `wrong_store_ref`; I added it to the movement schema and
   ensured it is null for non-transfers.
5. **Rewrote benign-case injection** — the first version paired counts with
   damage movements at the wrong `(store, sku)`, so they were not true
   negatives. I rewrote it to pair each count with a real explanatory
   movement at the same `(store, sku)` inside the lookback window.
6. **Fixed `unexplained_loss` false negatives** — two planted counts were
   being skipped by the detector because an unrelated transfer fell in their
   lookback. I added a transfer-transit-window check to both the generator's
   candidate filter and the detector so the two rules don't overlap.
7. **Fixed full-scale `opening_balance_coverage` failure** — the
   `wrong_store_ref` anomaly pointed transfers at stores that don't carry
   the SKU. I changed the wrong-store picker to choose from stores that do
   carry the SKU, so the only flaw is the destination mismatch.
8. **Ran and verified the whole pipeline** at both scales, checked the
   validation summary (46/46 pass), the evaluation metrics (precision/recall/
   F1 = 1.0), the reproducibility check (identical SHA-256 across two runs),
   and the pytest suite (15/15 pass).
9. **Cleaned the repo** for GitHub — added `.gitignore`, removed generated
   data/cache, confirmed the pipeline still runs end-to-end after cleanup.

## Verification I performed

- `python run_all.py --scale starter` — all 4 steps pass, F1 = 1.0.
- `python run_all.py --scale full` — 1,050,199 movements / 20,080 counts,
  all 4 steps pass, precision 1.0, recall 1.0, F1 1.0.
- `python run_all.py --check-repro` — all 10 CSV files have identical
  SHA-256 across two runs with seed `20261022`.
- `python -m pytest tests/` — 15/15 tests pass.

## Limitations of the AI assistance

- The model could not read the two YottaFlex PDF guidance documents
  directly (no PDF input support). I extracted their text locally with the
  `pdfplumber` library and followed the extracted requirements myself.
- AI suggestions were always checked against the spec and the actual run
  output before being kept. No AI output was accepted blindly.

## Ownership

I understand the core logic, the key design choices (rule-based detection,
separate ground truth, fixed-seed reproducibility, stock-equation
reconciliation), the dependencies (pandas, numpy, PyYAML, stdlib sqlite3),
and the limitations (see README "Limitations" section). I am ready to walk
through any part of the solution.
