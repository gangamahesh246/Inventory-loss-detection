# Data Dictionary

Every field's type, required/optional, allowed values, and validation rule.
Types: `str`, `int`, `float`, `bool`, `date` (ISO `YYYY-MM-DD`),
`timestamp` (`YYYY-MM-DD HH:MM:SS`).

IDs are immutable, zero-padded, and exactly consistent across files.

---

## store.csv
| field | type | req | allowed / rule |
|---|---|---|---|
| store_id | str | Y | `STORE-\d{6}`, unique PK |
| store_name | str | Y | non-empty |
| format | str | Y | Warehouse / Supermarket / Convenience / Express |
| region | str | Y | North / South / East / West / Central |
| opened_on | date | Y | <= 2026-01-01 (store opened on/before period start) |
| status | str | Y | Active / Closed / Remodeling |

## sku.csv
| field | type | req | allowed / rule |
|---|---|---|---|
| sku_id | str | Y | `SKU-\d{6}`, unique PK |
| sku_name | str | Y | non-empty |
| category | str | Y | Grocery / Beverage / Household / Personal Care / Electronics / Apparel / Frozen / Produce |
| unit_cost | float | Y | > 0 |
| perishable | bool | Y | true / false |
| active_from | date | Y | 2026-01-01 |
| status | str | Y | Active / Discontinued |

## employee.csv
| field | type | req | allowed / rule |
|---|---|---|---|
| employee_id | str | Y | `EMP-\d{6}`, unique PK |
| store_id | str | Y | FK -> store.store_id |
| employee_name | str | Y | non-empty |
| role | str | Y | Cashier / Stocker / Supervisor / Manager / Auditor |
| hired_on | date | Y | <= opened_on of the store |
| status | str | Y | Active / Suspended / Terminated |

## shift.csv
| field | type | req | allowed / rule |
|---|---|---|---|
| shift_id | str | Y | `SHF-\d{6}`, unique PK |
| store_id | str | Y | FK -> store.store_id |
| shift_name | str | Y | Morning / Afternoon / Night |
| start_time | str | Y | HH:MM |
| end_time | str | Y | HH:MM |

## promotion.csv
| field | type | req | allowed / rule |
|---|---|---|---|
| promotion_id | str | Y | `PROMO-\d{6}`, unique PK |
| promotion_name | str | Y | non-empty |
| start_date | date | Y | within 2026 |
| end_date | date | Y | >= start_date |
| discount_pct | float | Y | 5..30 |
| status | str | Y | Planned / Active / Ended |

## promotion_sku.csv (bridge - N:M promotion <-> sku)
| field | type | req | allowed / rule |
|---|---|---|---|
| promotion_id | str | Y | FK -> promotion.promotion_id |
| sku_id | str | Y | FK -> sku.sku_id |
PK = (promotion_id, sku_id).

## opening_balance.csv (snapshot - never overwritten)
| field | type | req | allowed / rule |
|---|---|---|---|
| store_id | str | Y | FK -> store.store_id |
| sku_id | str | Y | FK -> sku.sku_id |
| opening_qty | int | Y | 10..60 |
| as_of_date | date | Y | 2026-01-01 |
PK = (store_id, sku_id).

## movement.csv (event history - append-only)
| field | type | req | allowed / rule |
|---|---|---|---|
| movement_id | str | Y | `MOV-2026-\d{8}`, unique PK |
| store_id | str | Y | FK -> store.store_id |
| sku_id | str | Y | FK -> sku.sku_id |
| movement_type | str | Y | Receipt / Sale / TransferOut / TransferIn / Return / Damage / Adjustment |
| quantity | int | Y | signed: in +, out -. Non-zero. inbound > 0, outbound < 0 |
| unit_cost | float | Y | > 0 |
| reason_code | str | N | enum per type; NULL only allowed for Adjustment (anomaly) |
| occurred_at | timestamp | Y | within 2026-01-01..2026-10-31 |
| recorded_at | timestamp | Y | >= occurred_at |
| employee_id | str | N | FK -> employee.employee_id (nullable for generated TransferIn before assignment) |
| shift_id | str | N | FK -> shift.shift_id |
| related_movement_id | str | N | self-FK; links transfer out/in pairs and return->sale |
| destination_store_id | str | N | set only for TransferOut; FK -> store.store_id |
| reference | str | N | PO / TXN / TRF / RET number |
| status | str | Y | Recorded / Posted / Reversed |

reason_code allowed values by type:
- Sale: "Sale"; Receipt: PurchaseOrder / VendorDelivery
- Damage: Spoilage / Breakage / Expired / DamagedFound
- Return: Defective / CustomerReturn / WrongItem / ChangedMind
- Adjustment: StockCorrection / DamagedFound / FoundStock / SystemCorrection / RecountAdjustment (or NULL = anomaly)
- TransferOut: TransferToStore; TransferIn: TransferFromStore

## cycle_count.csv
| field | type | req | allowed / rule |
|---|---|---|---|
| count_id | str | Y | `CNT-2026-\d{6}`, unique PK |
| store_id | str | Y | FK -> store.store_id |
| sku_id | str | Y | FK -> sku.sku_id |
| counted_qty | int | Y | >= 0 (observed) |
| expected_qty | int | Y | >= 0; derived = max(0, opening + cumulative movements as of counted_at) |
| variance | int | Y | = counted_qty - expected_qty (derived) |
| counted_at | timestamp | Y | within period, OR before opened_on (anomaly) |
| recorded_at | timestamp | Y | >= counted_at |
| counted_by_employee_id | str | N | FK -> employee.employee_id |
| shift_id | str | N | FK -> shift.shift_id |
| count_status | str | Y | Draft / Posted / Recounted / Adjusted |
| notes | str | N | free text; planted anomalies carry a hint, normal counts are empty |

## return_event.csv
| field | type | req | allowed / rule |
|---|---|---|---|
| return_id | str | Y | `RET-2026-\d{6}`, unique PK |
| sale_movement_id | str | Y | FK -> movement.movement_id (the original Sale) |
| return_movement_id | str | Y | FK -> movement.movement_id (the Return) |
| store_id | str | Y | FK -> store.store_id |
| sku_id | str | Y | FK -> sku.sku_id |
| return_reason | str | Y | Defective / CustomerReturn / WrongItem / ChangedMind |
| received_at | timestamp | Y | = return movement occurred_at |

## labels/ground_truth.csv (kept separate - never an input feature)
| field | type | req | allowed / rule |
|---|---|---|---|
| label_id | str | Y | `GT-\d{6}`, unique PK |
| entity_type | str | Y | Movement / CycleCount / Employee |
| entity_id | str | Y | the id of the planted-anomaly record |
| issue_type | str | Y | wrong_store_ref / missing_reason / count_timing_conflict / transfer_double_shrink / repeated_adjustments / unexplained_loss / benign_explained |
| description | str | Y | human-readable |
| expected_decision | str | Y | "flag <RuleName>" or "no flag" (benign) |
| planted_step | str | Y | anomaly_injection / benign_injection |

## reports/shrinkage_alert.csv (detector output)
| field | type | req | allowed / rule |
|---|---|---|---|
| alert_id | str | Y | `SHR-2026-\d{6}`, unique PK |
| store_id | str | Y | FK -> store.store_id |
| sku_id | str | N | FK or empty |
| entity_type | str | Y | Movement / CycleCount / Employee |
| entity_id | str | Y | the flagged record id |
| issue_type | str | Y | MissingReason / WrongStoreRef / CountTimingConflict / TransferDoubleShrink / RepeatedAdjustments / UnexplainedLoss |
| severity | str | Y | Low / Medium / High |
| score | float | Y | 0..1 |
| evidence | str | Y | cites the exact records |
| created_at | date | Y | 2026-11-01 |
| status | str | Y | Open / Investigating / Resolved / FalsePositive |

## reports/investigation.csv
| field | type | req | allowed / rule |
|---|---|---|---|
| investigation_id | str | Y | `INV-2026-\d{6}`, unique PK |
| alert_id | str | Y | FK -> shrinkage_alert.alert_id |
| assigned_to | str | Y | non-empty |
| status | str | Y | Open / InReview / Closed-Substantiated / Closed-Unsubstantiated |
| opened_at | date | Y | 2026-11-01 |
| closed_at | date | N | empty if still open |
| notes | str | N | free text |
