"""ID helpers - zero-padded, immutable, deterministic nomenclature.

Conventions (from the brief):
  STORE-000001 ; SKU-000001 ; MOV-2026-00000001 ; CNT-2026-000001 ;
  SHR-2026-000001 ; INV-2026-000001
Employees, shifts and promotions use the same zero-pad style:
  EMP-000001 ; SHF-000001 ; PROMO-000001 ; RET-2026-000001
"""


def store_id(i):
    return f"STORE-{i:06d}"


def sku_id(i):
    return f"SKU-{i:06d}"


def emp_id(i):
    return f"EMP-{i:06d}"


def shf_id(i):
    return f"SHF-{i:06d}"


def promo_id(i):
    return f"PROMO-{i:06d}"


def mov_id(i):
    return f"MOV-2026-{i:08d}"


def cnt_id(i):
    return f"CNT-2026-{i:06d}"


def ret_id(i):
    return f"RET-2026-{i:06d}"


def shr_id(i):
    return f"SHR-2026-{i:06d}"


def inv_id(i):
    return f"INV-2026-{i:06d}"


# Names of the columns each generator writes. Kept here so every module
# agrees on the schema.
COLUMNS = {
    "store": ["store_id", "store_name", "format", "region", "opened_on", "status"],
    "sku": ["sku_id", "sku_name", "category", "unit_cost", "perishable",
            "active_from", "status"],
    "employee": ["employee_id", "store_id", "employee_name", "role",
                 "hired_on", "status"],
    "shift": ["shift_id", "store_id", "shift_name", "start_time", "end_time"],
    "promotion": ["promotion_id", "promotion_name", "start_date", "end_date",
                   "discount_pct", "status"],
    "promotion_sku": ["promotion_id", "sku_id"],
    "opening_balance": ["store_id", "sku_id", "opening_qty", "as_of_date"],
    "movement": ["movement_id", "store_id", "sku_id", "movement_type",
                 "quantity", "unit_cost", "reason_code", "occurred_at",
                 "recorded_at", "employee_id", "shift_id", "related_movement_id",
                 "destination_store_id", "reference", "status"],
    "cycle_count": ["count_id", "store_id", "sku_id", "counted_qty",
                    "expected_qty", "variance", "counted_at", "recorded_at",
                    "counted_by_employee_id", "shift_id", "count_status", "notes"],
    "return_event": ["return_id", "sale_movement_id", "return_movement_id",
                     "store_id", "sku_id", "return_reason", "received_at"],
    "shrinkage_alert": ["alert_id", "store_id", "sku_id", "entity_type",
                        "entity_id", "issue_type", "severity", "score",
                        "evidence", "created_at", "status"],
    "investigation": ["investigation_id", "alert_id", "assigned_to", "status",
                       "opened_at", "closed_at", "notes"],
}
