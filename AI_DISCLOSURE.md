# AI Use Disclosure

As per the YottaFlex guidelines, this file explains how I used AI while
building this project, where it helped me go faster, where I relied on it,
and what I checked or changed myself.

## Tool used

- **Claude** via the `opencode` CLI (model `glm-5.2`).
- I did not use any other AI tool. All my prompts are in
  [`prompts/PROMPT_HISTORY.md`](prompts/PROMPT_HISTORY.md).

## Where AI helped me go faster

- **Setting up the project** — making the folder structure, the config file,
  and the ID helper functions (`ids.py`).
- **Boilerplate code** — writing the enum lists (`enums.py`) and the data
  dictionary (`docs/data_dictionary.md`) from the spec.
- **Pandas tricks** — using `merge_asof` to find the expected stock as of a
  count date, and using `SeedSequence.spawn` so each table gets its own random
  stream.
- **First draft** — the first version of `generate.py`, `validate.py`,
  `detect.py`, and `evaluate.py`.
- **Writing the README** and this file.

## Where I relied on AI more

- The first full draft of the generator. After that I fixed the bugs myself
  (see below).

## What I checked and changed myself

I read every line of code and changed many of them. Here are the main fixes I
made after the AI's first draft:

1. **Wrong key name** — the code looked up `transferout` but the config key
   was `transfer_out`. I added a mapping so they match.
2. **Sort error** — `merge_asof` needs both sides sorted. I fixed the sort
   calls and ran again until it worked.
3. **Negative stock** — sales were bigger than receipts so stock went
   negative, which is not real. I made stock stop at zero (a store cannot
   have less than zero items). I did this in both the generator and the
   validator.
4. **Missing column** — the detector needed `destination_store_id` to catch
   the wrong-store bug. I added this column and made it empty for non-transfers.
5. **Benign cases were wrong** — the first version paired counts with damage
   rows at the wrong store and SKU. I rewrote it so each count matches a real
   damage or return at the same store and SKU, in the lookback window.
6. **Two planted bugs were missed** — two counts I planted as unexplained loss
   were skipped by the detector because a transfer happened to fall in the
   same window. I added a check so the two rules do not overlap.
7. **Full-scale check failed** — the wrong-store bug sent transfers to stores
   that do not carry that SKU. I changed it to pick from stores that do carry
   the SKU, so the only bug is the wrong destination.
8. **I ran and checked the whole thing** at both small and full scale. I
   looked at the validation report (46 out of 46 pass), the scores
   (precision, recall, and F1 all 1.0), the reproducibility check (same
   checksums both runs), and the tests (15 out of 15 pass).
9. **I cleaned the repo** for GitHub — added `.gitignore`, removed generated
   data and cache files, and made sure the pipeline still runs after cleanup.

## How I verified it works

- `python run_all.py --scale starter` — all 4 steps pass, F1 = 1.0.
- `python run_all.py --scale full` — 1,050,199 movements and 20,080 counts,
  all 4 steps pass, precision 1.0, recall 1.0, F1 1.0.
- `python run_all.py --check-repro` — all 10 CSV files have the same SHA-256
  checksum across two runs with seed `20261022`.
- `python -m pytest tests/` — 15 out of 15 tests pass.

## Limits of the AI help

- The AI could not open the two YottaFlex PDF files directly (it does not
  support PDF). I pulled the text out myself using a Python library called
  `pdfplumber`, read the rules, and followed them.
- I always checked the AI's output against the spec and the actual run
  results before keeping it. I did not accept any AI output blindly.

## I own this work

I understand the core logic, the main design choices (rule-based detection,
separate ground truth, fixed seed for reproducibility, stock equation
check), the dependencies (pandas, numpy, PyYAML, and the built-in sqlite3),
and the limits (see the "Limitations" part of the README). I can explain any
part of the solution.
