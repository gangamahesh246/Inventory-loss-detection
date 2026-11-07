# Prompt History

As per the YottaFlex guidelines, this file has all the prompts I sent to the
AI tool while building this project. I am writing them in my own simple words
so it is clear what I asked the AI to do at each step. AI responses are not
included (that is optional per the FAQ).

**AI tool used:** Claude (via opencode CLI, model `glm-5.2`).
**Date:** 2026-11-07.

Only the problem-related prompts are listed below. I have not included the
short messages about git and pushing to GitHub, because those are not about
the actual problem.

---

## Prompt 1 — I shared the full problem and asked for a plan

I pasted the complete project brief about detecting unusual inventory loss by
comparing receipts, sales, transfers, adjustments, returns and counts. The
brief had these main parts:

- The business problem and what it should do.
- The actors involved (customer, store operator, analyst, operations manager).
- The workflow and rules (make master data first, then transactions, then
  apply business logic, keep history, make ground-truth labels from rules).
- The ten entities (Store, SKU, InventoryMovement, CycleCount, EmployeeRole,
  Shift, Promotion, Return, ShrinkageAlert, Investigation) and how they link.
- The ID naming rules (STORE-000001, SKU-000001, MOV-2026-00000001, etc.).
- Ten steps for generating the data (data dictionary, master tables first,
  fixed IDs, 100 stores / 5000 SKUs / 1 million movements / 20000 counts,
  inject edge cases, derive values from source rows, separate ground truth,
  run validation, export CSV/JSON/SQL, prove reproducibility).
- The four required edge cases (wrong store, missing reason, count before
  movements, transfer counted as shrink at both ends).
- The validation and acceptance rules.
- The lawful use guidance (use synthetic data if unsure about licenses).

I asked the AI to **plan** this first, not build it yet.

---

## Prompt 2 — I told the AI how to work on it

I told the AI to:

- Implement the solution in a realistic and simple way.
- Not use complex methods or fancy tools.
- Code it the way a fresher would, because this is a fresher role task.
- Not start coding until I say so.
- First tell me what it understood about the problem.

---

## Prompt 3 — I approved the plan and told it to start

I said the plan looked good and told the AI to start building the solution.

---

## Prompt 4 — I picked the design choices

The AI asked me three questions about how to build it. I picked these:

- **Default scale:** Use the small starter dataset by default (fast to run),
  and make the full 1-million-movement dataset only when a flag is passed.
- **Detection method:** Use simple rules with a score (0 to 1), not ML.
  This is easy to explain and shows the reasons for each alert.
- **SQL export:** Use Python's built-in sqlite3 to make the SQL file, so no
  extra install is needed.

---

## Prompt 5 — I asked if the work was done

I asked the AI if the work was completed.

---

## Notes

- The AI tool could not open the two YottaFlex PDF files directly (it does not
  support PDF input). So I pulled the text out of the PDFs myself using a
  Python library called `pdfplumber`, read the rules, and followed them.
- I did not use any other AI tool for this project.
