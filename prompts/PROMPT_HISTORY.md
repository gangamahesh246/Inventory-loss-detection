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

## Prompt 1 — Understand the Problem and Plan the Solution

I want to build an Inventory Loss Detection System based on the requirements I provided.

The main objective is to detect unusual inventory loss by comparing receipts, sales, transfers, adjustments, returns, and physical stock counts.

First, understand the complete business problem and explain how the system should work from beginning to end.

I want you to identify:

All required entities and their relationships.

How inventory transactions should be generated.

How expected stock balances should be calculated.

How physical stock counts should be compared with expected balances.

How unusual inventory loss should be detected.

How alerts and investigations should be created.

How ground-truth labels should be maintained.

What validation checks and evaluation metrics are required.

Before implementing anything, provide a clear implementation plan. Do not start coding yet.

---

## Prompt 2 — Define the Architecture and Implementation Approach

Based on the requirements, I want to implement this using Python with a simple and practical architecture.

Follow these instructions:

Use Python for synthetic data generation, inventory calculations, anomaly detection, and validation.

Use SQLite for database storage and SQL export.

Organize the code into separate modules for data generation, inventory calculations, detection logic, and validation.

Keep the implementation simple and understandable. Avoid unnecessary frameworks and complicated architecture.

Generate a small dataset by default for development and testing.

Provide an option to generate the complete required dataset when needed.

Use rule-based anomaly detection instead of machine learning because the detection decisions should be easy to explain.

Generate alerts with a score between 0 and 1 and include clear reasons for each alert.

Make sure the architecture supports all the required entities and business rules.

---

## Prompt 3 — Design the Database and Data Dictionary

Now design the database schema for all ten required entities:

Store

SKU

InventoryMovement

CycleCount

EmployeeRole

Shift

Promotion

Return

ShrinkageAlert

Investigation

For every entity, define its primary key, foreign keys, field names, data types, required and optional fields, allowed values, and validation rules.

Define the relationships between entities, including one-to-many and many-to-many relationships. Use bridge tables wherever necessary.

Follow the specified ID formats exactly:

STORE-000001

SKU-000001

MOV-2026-00000001

CNT-2026-000001

SHR-2026-000001

INV-2026-000001

Ensure that IDs are unique, immutable, and correctly referenced across all generated files.

Also, document the schema and data dictionary so that another developer can understand the database structure.

---

## Prompt 4 — Implement Synthetic Data Generation

Implement the data generator in Python.

I want the generation process to follow this order:

Generate master data such as stores, SKUs, employees, roles, and shifts.

Generate opening stock balances for each store and SKU.

Generate inventory movements such as receipts, sales, transfers, and adjustments.

Generate customer returns and promotions.

Generate physical cycle counts.

Generate shrinkage alerts and investigation records based on the business rules.

All dependent records must reference valid parent IDs.

Use realistic transaction dates, quantities, movement types, and relationships. Avoid generating completely random or unrelated records.

Use a fixed random seed of 20261022 so that the generated data can be reproduced.

Make the dataset size configurable:

Starter dataset for development and testing.

Full dataset with 100 stores, 5,000 SKUs, 1 million inventory movements, and 20,000 cycle counts.

Both configurations should use the same generation logic.

---

## Prompt 5 — Implement Inventory Calculation and Reconciliation

Implement the inventory calculation logic using the generated transaction records.

For each store and SKU, calculate the expected stock balance using:

Opening Stock + Receipts - Sales + Returns + Transfer In - Transfer Out + Adjustments.

Make sure adjustments use signed quantities and every movement is included only once.

For transfers, create linked outgoing and incoming records so that stock is reduced at the source store and increased at the destination store.

Compare the calculated expected stock with the actual physical stock recorded in cycle counts.

Calculate the variance as:

Actual Stock - Expected Stock.

Classify the result as:

Negative variance: Stock shortage.

Positive variance: Stock excess.

Zero variance: Stock matches.

Do not generate expected balances or variances independently. They must always be calculated from the source transaction records.

---

## Prompt 6 — Implement Anomaly Detection Rules

Now implement the main inventory loss detection logic.

I want a simple rule-based detection system instead of an ML model.

Consider the following patterns:

Unexplained stock shortages.

Repeated inventory adjustments by the same employee.

Adjustments without valid reasons.

Unusual inventory movement patterns.

Suspicious activity during specific employee shifts.

Differences between expected and physical stock.

Transfers that may have been incorrectly counted as inventory loss.

Assign an explainable score between 0 and 1 based on the evidence available.

For every detected anomaly, generate an alert containing:

Alert ID.

Store ID.

SKU ID.

Related movement or cycle count IDs.

Detected issue type.

Severity.

Detection score.

Explanation for why the alert was generated.

Current alert status.

Do not automatically classify every stock shortage as theft. Consider legitimate damage, returns, and other valid business explanations before generating alerts.

---

## Prompt 7 — Handle Required Edge Cases

Implement the four required negative scenarios separately so that they can be tested.

Wrong store reference: A movement refers to an incorrect or unrelated store. Flag it as a data integrity issue.

Missing adjustment reason: An adjustment has no required reason. Flag it for review.

Incorrect count timestamp: A cycle count occurs before relevant stock movements that should already have been included. Detect the timeline inconsistency.

Transfer counted as shrinkage twice: A transfer is incorrectly treated as a stock shortage at both the source and destination stores. Reconcile the transfer before raising shrinkage alerts.

Keep these cases identifiable using an issue type and ground-truth label.

Do not silently modify unrelated records to create anomalies. Preserve the original transaction history and make the exception cases traceable.

---

## Prompt 8 — Generate Ground Truth and Investigation Records

Create a separate ground-truth dataset containing the known anomaly cases and their expected classifications.

Generate the labels based on documented business rules rather than assigning labels randomly.

Include both:

Genuine anomalies that should be detected.

Normal business situations such as legitimate damage, returns, and valid adjustments.

Keep ground-truth labels separate from the input data so that the detection logic cannot access the expected answers.

Also, generate investigation records linked to the corresponding shrinkage alerts.

Maintain investigation status, assigned employee, evidence, findings, and final outcome.

Preserve event history instead of overwriting previous alert or investigation states.

---

## Prompt 9 — Implement Data Validation and Evaluation

Implement a validation module to check the generated data and detection results.

Include the following checks:

Primary key uniqueness.

Foreign key integrity.

Valid movement types and allowed enum values.

Correct date and timestamp ordering.

Inventory balance reconciliation.

Duplicate transaction detection.

Transfer consistency between stores.

Valid alert and investigation lifecycle transitions.

Correct ground-truth relationships.

Also calculate detection evaluation metrics:

Precision.

Recall.

F1-score.

False positive rate.

Reconciliation accuracy.

Compare the generated alerts with the separate ground-truth dataset.

The validation should identify errors clearly and produce a summary report.

---

## Prompt 10 — Export Data and Generate Documentation

Implement the final data export functionality.

Generate the following outputs:

CSV files for all required entities.

JSON files for generated records.

SQLite database containing the generated tables and relationships.

Separate ground-truth CSV or JSON.

Data dictionary.

Database schema documentation.

README with setup and execution instructions.

Source manifest and validation summary.

Use Python's built-in sqlite3 library for database creation and SQL export to avoid unnecessary dependencies.

Make sure all exported files contain consistent IDs and relationships.

Document the commands required to generate the starter dataset and the full dataset.

---

## Prompt 11 — Verify Reproducibility and Final Implementation

Now review the complete implementation against the original requirements.

Check whether:

All ten entities are implemented.

All primary and foreign keys are valid.

Inventory calculations follow the correct stock equation.

The required edge cases are included.

Anomaly detection produces explainable alerts.

Legitimate stock changes are not incorrectly classified as shrinkage.

Ground-truth labels are kept separate from detection inputs.

Validation and evaluation metrics work correctly.

All required CSV, JSON, and SQLite outputs are generated.

Documentation and execution instructions are complete.

Run the generator twice using the same seed and configuration. Compare row counts and file checksums to confirm reproducibility.

If any requirement is missing or any test fails, identify the issue, fix it, and run the relevant validation again.

Finally, provide a summary of the implemented features, generated outputs, validation results, and any remaining limitations.

---

## Notes

- The AI tool could not open the two YottaFlex PDF files directly (it does not
  support PDF input). So I pulled the text out of the PDFs myself using a
  Python library called `pdfplumber`, read the rules, and followed them.
- I did not use any other AI tool for this project.
