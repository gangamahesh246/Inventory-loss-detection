# AI Use Disclosure

As per the YottaFlex guidelines, this document explains how I used an LLM while building the Inventory Loss Detection System, which parts it helped me implement faster, what I reviewed and corrected myself, and how I verified the final solution.

## Tool Used

- **LLM:** GLM-5.2 via the OpenCode CLI.
- I did not use any other AI tool.
- My complete implementation prompts are available in [PROMPT_HISTORY.md](https://github.com/gangamahesh246/Inventory-loss-detection/blob/main/prompts/PROMPT_HISTORY.md).

## How I Directed the Implementation

I first studied the complete problem statement and identified the entities, relationships, business rules, data generation requirements, edge cases, and validation requirements.

I then defined the implementation approach and instructed the LLM to follow it step by step.

My main technical decisions were:

- **Programming language:** Python for data generation, inventory calculations, anomaly detection, and validation.
- **Database:** SQLite using Python's built-in `sqlite3` library.
- **Detection approach:** Rule-based detection with explainable scores between 0 and 1 instead of machine learning.
- **Data generation:** Generate master records first, followed by dependent transactions using valid parent IDs.
- **Dataset scale:** Use a small starter dataset by default and generate the full dataset only when requested.
- **Reproducibility:** Use a fixed random seed (`20261022`) for consistent data generation.
- **Ground truth:** Maintain a separate dataset for known anomalies and normal business cases.
- **Validation:** Check relationships, inventory reconciliation, edge cases, and detection performance.

I also provided specific instructions for implementing the inventory calculation, anomaly detection rules, exception handling, investigation records, exports, and final validation.

## Where the LLM Helped Me Go Faster

I used the LLM mainly to speed up implementation based on the requirements and technical approach I provided.

- **Project setup:** Helped create the project structure, configuration, and ID generation utilities.
- **Database and documentation:** Helped define entity structures, enums, relationships, and the data dictionary.
- **Data generation:** Helped implement synthetic data generation for stores, products, employees, movements, and cycle counts.
- **Inventory calculations:** Helped implement stock balance calculations and use Pandas operations such as `merge_asof`.
- **Reproducibility:** Helped implement separate random streams using NumPy's `SeedSequence.spawn`.
- **Detection logic:** Helped implement the rule-based anomaly detection and alert generation.
- **Validation and evaluation:** Helped write validation checks and calculate precision, recall, F1-score, and other metrics.
- **Documentation:** Helped prepare the README and project documentation.

## Where I Relied on the LLM More

I relied more on the LLM during the first implementation of the synthetic data generator and the initial versions of the main processing modules.

However, I did not accept the generated code without checking it. I reviewed the implementation, ran the pipeline, identified issues, and made corrections based on the actual business requirements.

## What I Reviewed and Changed Myself

After reviewing the generated implementation and running the pipeline, I identified and fixed several issues:

1. **Incorrect movement key:** The transfer-out configuration key did not match the key used in the code. I added the required mapping to make them consistent.

2. **Sorting issue:** The `merge_asof` operation required both datasets to be sorted correctly. I corrected the sorting logic and tested it again.

3. **Negative inventory:** Some generated sales exceeded available stock. I corrected the generator and validator so that inventory does not become negative.

4. **Missing destination field:** The detector needed `destination_store_id` to identify incorrect transfer destinations. I added the field and kept it empty for non-transfer movements.

5. **Incorrect legitimate cases:** Some damage and return records were linked to cycle counts from different stores or SKUs. I corrected the generation logic so that each case matches the same store and SKU within the required lookback period.

6. **Overlapping anomaly cases:** Two planted unexplained-loss cases were missed because transfers existed in the same detection window. I adjusted the rules to prevent these cases from overlapping.

7. **Full-scale data issue:** Some wrong-store transfer cases referenced stores that did not carry the related SKU. I corrected the generation logic so that the test isolates the intended wrong-destination issue.

8. **End-to-end verification:** I ran the pipeline at starter and full scale, reviewed the validation results, checked detection metrics, and verified reproducibility.

9. **Repository cleanup:** I added `.gitignore`, removed generated data and cache files, and checked that the pipeline still worked after cleanup.

## How I Verified the Solution

I ran the following commands and checked their results:

**Starter dataset**

- Command: `python run_all.py --scale starter`
- All four pipeline steps passed.
- F1-score: 1.0.

**Full dataset**

- Command: `python run_all.py --scale full`
- Generated 1,050,199 inventory movements and 20,080 cycle counts.
- All four pipeline steps passed.
- Precision: 1.0.
- Recall: 1.0.
- F1-score: 1.0.

**Reproducibility**

- Command: `python run_all.py --check-repro`
- Verified that all 10 CSV files produced matching SHA-256 checksums across two runs using seed `20261022`.

**Automated tests**

- Command: `python -m pytest tests/`
- Result: 15 out of 15 tests passed.

**Data validation**

- The validation report showed 46 out of 46 checks passing.

## Ownership and Understanding

I take responsibility for the final implementation and understand the main design decisions and business logic.

I can explain:

- How the ten entities are connected.
- How synthetic inventory data is generated.
- How expected stock balances and variances are calculated.
- How the rule-based detection system identifies unusual inventory loss.
- How ground-truth labels are separated from detection inputs.
- How validation and evaluation metrics are calculated.
- How fixed-seed generation ensures reproducibility.
- What limitations remain in the current solution.

I used the LLM as a development assistant to implement and review the solution based on the requirements, methods, and instructions I defined.
