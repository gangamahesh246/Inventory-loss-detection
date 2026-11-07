# Prompt History

Per the YottaFlex AI Candidate Project FAQ (item #6) and Submission
Guidelines (item #3), this file records **every prompt I submitted to an AI
tool** while building this project. AI responses are not included (they are
optional per the FAQ). All work is my own; AI was used as a coding aid, not
as a source of completed solutions.

**AI tool used:** Claude (via opencode CLI, model `glm-5.2`).
**Session date:** 2026-11-07.

Prompts are listed in the order they were sent. Spelling and wording are
preserved as submitted. Prompts that were follow-up answers to the tool's
multiple-choice questions are marked `(selection)`.

---

## Prompt 1 — Initial problem statement

> Business Context / Problem
> Detect unusual inventory loss by comparing receipts, sales, transfers, adjustments, returns and counts.
>
> Objective and Scope
> Build a working solution for this end-to-end workflow: Detect unusual inventory loss by comparing receipts, sales, transfers, adjustments, returns and counts. The solution should expose key decisions and exceptions, preserve traceability, and produce measurable outputs. Medium complexity means multiple related entities, conditional rules, at least one exception path and meaningful evaluation metrics.
>
> Primary Actors / Systems
> Customer, store/warehouse operator, merchandising/e-commerce analyst and operations manager
>
> Business Workflow and Rules
> 1. Generate/reference master data first: Store, SKU, InventoryMovement, CycleCount, EmployeeRole.
> 2. Generate dependent transaction/event records using valid parent IDs.
> 3. Apply business logic: Create store/SKU opening balances; generate sales and movement events; create cycle counts and variances; link movements to authorized users/roles and shifts; inject selected patterns such as repeated adjustments or unexplained losses; create alerts with ground-truth labels.
> 4. Persist state changes as explicit records/events where relevant; do not overwrite history.
> 5. Generate outcomes and ground-truth labels from documented rules, not independent random assignment.
>
> Entities and Relationships
> Core entities: Store, SKU, InventoryMovement, CycleCount, EmployeeRole, Shift, Promotion, Return, ShrinkageAlert, Investigation. Define a primary key for every entity and foreign keys for every relationship. Document cardinality (1:1, 1:N, N:M), optional relationships, effective dates and lifecycle states. Use bridge tables for many-to-many relationships; retain event history for state changes; validate all joins. For deliberate anomaly cases, keep an issue_type/ground_truth label rather than silently corrupting unrelated rows.
>
> ID / Nomenclature Conventions
> STORE-000001; SKU-000001; MOV-2026-00000001; CNT-2026-000001; SHR-2026-000001; INV-2026-000001.
>
> Synthetic Data Generation Instructions (Granular)
> Step 1 — Write a data dictionary for: Store, SKU, InventoryMovement, CycleCount, EmployeeRole, Shift, Promotion, Return, ShrinkageAlert, Investigation. For each field specify type, required/optional, allowed values, units, uniqueness and validation rule.
> Step 2 — Create parent/master tables first, then child and event tables. Apply this domain-specific generation logic: Create store/SKU opening balances; generate sales and movement events; create cycle counts and variances; link movements to authorized users/roles and shifts; inject selected patterns such as repeated adjustments or unexplained losses; create alerts with ground-truth labels.
> Step 3 — Apply deterministic IDs and naming: STORE-000001; SKU-000001; MOV-2026-00000001; CNT-2026-000001; SHR-2026-000001; INV-2026-000001. Keep counters zero-padded, IDs immutable, and referenced IDs exactly consistent across files.
> Step 4 — Generate the baseline volume: Generate 100 stores, 5,000 SKUs, 1 million movements and 20,000 cycle counts. Include legitimate damage/returns and planted anomalies to avoid treating every variance as theft. Use a fixed seed (e.g. 20261022) and parameterize scale so starter and full datasets use the same generator.
> Step 5 — Generate valid baseline records first, then inject labelled edge cases: Movement refers to wrong store; adjustment lacks reason; count timestamp precedes stock movements incorrectly; transfer counted as shrinkage at both ends.
> Step 6 — Calculate derived values (totals, balances, scores, statuses and dates) from source records rather than generating them independently.
> Step 7 — Produce a separate ground_truth.csv/json for known anomalies, expected decisions or labels; never leak it into input features.
> Step 8 — Run validation: primary-key uniqueness, foreign-key integrity, allowed enums, date ordering, arithmetic reconciliation, lifecycle transitions and duplicate checks.
> Step 9 — Export CSV/JSON/SQL seed data plus README, schema/data dictionary, generator command, fixed seed, source manifest and validation summary.
> Step 10 — Regenerate twice with the same seed and compare row counts/checksums to demonstrate reproducibility.
>
> Suggested Volume and Coverage
> Generate 100 stores, 5,000 SKUs, 1 million movements and 20,000 cycle counts. Include legitimate damage/returns and planted anomalies to avoid treating every variance as theft.
>
> Required Edge Cases / Negative Scenarios
> Movement refers to wrong store; adjustment lacks reason; count timestamp precedes stock movements incorrectly; transfer counted as shrinkage at both ends.
>
> Validation Rules / Acceptance Criteria
> Stock equation reconciles; alert reasons are evidence-based; planted patterns can be evaluated; benign explanations are represented.
>
> Evaluation Focus for Generated Data
> Review: (a) realistic distributions and meaningful variation; (b) consistent IDs and valid joins; (c) dependency/lifecycle consistency across entities; (d) correct derived values and reconciliation; (e) normal, boundary, failure and exception coverage; (f) separate ground truth; (g) fixed-seed reproducibility, documentation and lawful provenance.
>
> Public Data Guidance / Lawful Use
> External data is optional. If used, record source URL, dataset/version, retrieval date, license/terms, attribution, transformations and fields discarded. Use only data you are legally permitted to access and redistribute; do not bypass access controls or collect confidential/personal information. If licensing or suitability is unclear, use synthetic data and cite public reference data only for schema inspiration.  - plan this one

---

## Prompt 2 — Direction on approach

> implement the solution realistically, and dont use complex methods. just code/implement the solution how the fresher work on this one. because this is the task for fresher role. dont implement till i said, and give what you understand on this problem?

---

## Prompt 3 — Approval to start building

> plan was good, now work on it.

---

## Prompt 4 — Answers to design questions `(selection)`

> Default scale: Starter default, full on flag
> Detection approach: Rule-based with scoring
> SQL export format: sqlite3 dump (stdlib, zero-install)

---

## Prompt 5 — Status check

> completed?

---

## Prompt 6 — Repo cleanup for GitHub

> i need to push this folder to github, so clean this one. should only contains problem/task related files and add dependencies files into giitignore

---

## Prompt 7 — Offer to share GitHub link for push

> i will share the github origin link to you run and push this folder

---

## Prompt 8 — GitHub remote + git identity + commit message

> https://github.com/gangamahesh246/Inventory-loss-detection.git. user.name: Mahesh, user.email: gangamahesh809@gmail.com. use commit msg this one only - Inventory loss detection

---

## Prompt 9 — Confirmed account removal

> i removed gang007s account from my windows

---

## Prompt 10 — Follow the two PDF guides

> "C:\Users\ganga\Downloads\YottaFlex AI Candidate Project-FAQ.pdf" "C:\Users\ganga\Downloads\YottaFlex AI Candidate Project Submission Guidelines.pdf" - follow these 2

---

## Notes on AI tool limitations

- The AI tool could not read the two PDF guidance documents directly (the
  model does not accept PDF input). I extracted their text locally using the
  `pdfplumber` Python library and then acted on the extracted requirements.
- No prompts were exported from any other AI tool. No other AI tool was used
  for this project.
