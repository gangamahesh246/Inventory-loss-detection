"""Allowed enum values used by the generator, validator and detector.

Every field that has a fixed set of allowed values is listed here. The
validator checks that every value in the data is a member of the matching
list (or NULL where allowed).
"""

# --- Store / SKU lifecycle -------------------------------------------------
STORE_STATUS = ["Active", "Closed", "Remodeling"]
STORE_FORMAT = ["Warehouse", "Supermarket", "Convenience", "Express"]
STORE_REGION = ["North", "South", "East", "West", "Central"]

SKU_STATUS = ["Active", "Discontinued"]
SKU_CATEGORY = ["Grocery", "Beverage", "Household", "Personal Care",
                "Electronics", "Apparel", "Frozen", "Produce"]

# --- Employee / Shift -----------------------------------------------------
EMPLOYEE_ROLE = ["Cashier", "Stocker", "Supervisor", "Manager", "Auditor"]
EMPLOYEE_STATUS = ["Active", "Suspended", "Terminated"]

SHIFT_NAME = ["Morning", "Afternoon", "Night"]

# --- Promotion ------------------------------------------------------------
PROMO_STATUS = ["Planned", "Active", "Ended"]

# --- Movement -------------------------------------------------------------
MOVEMENT_TYPE = ["Receipt", "Sale", "TransferOut", "TransferIn", "Return",
                 "Damage", "Adjustment"]
MOVEMENT_STATUS = ["Recorded", "Posted", "Reversed"]

# reason_code is nullable for Adjustment (the missing_reason anomaly relies
# on this). For other movement types a reason is expected.
ADJUSTMENT_REASON = ["StockCorrection", "DamagedFound", "FoundStock",
                     "SystemCorrection", "RecountAdjustment"]
DAMAGE_REASON = ["Spoilage", "Breakage", "Expired", "DamagedFound"]
RETURN_REASON = ["Defective", "CustomerReturn", "WrongItem", "ChangedMind"]
SALE_CHANNEL = ["InStore", "Online", "Wholesale"]
RECEIPT_REASON = ["PurchaseOrder", "VendorDelivery"]

# --- Cycle count ----------------------------------------------------------
COUNT_STATUS = ["Draft", "Posted", "Recounted", "Adjusted"]

# --- Alerts / Investigations ----------------------------------------------
ALERT_TYPE = ["MissingReason", "WrongStoreRef", "CountTimingConflict",
              "TransferDoubleShrink", "RepeatedAdjustments", "UnexplainedLoss"]
ALERT_SEVERITY = ["Low", "Medium", "High"]
ALERT_STATUS = ["Open", "Investigating", "Resolved", "FalsePositive"]

INVESTIGATION_STATUS = ["Open", "InReview", "Closed-Substantiated",
                        "Closed-Unsubstantiated"]

# --- Ground-truth issue types (kept separate from alert enums on purpose) -
ISSUE_TYPE = ["wrong_store_ref", "missing_reason", "count_timing_conflict",
              "transfer_double_shrink", "repeated_adjustments",
              "unexplained_loss"]

# Map a ground-truth issue_type to the matching alert issue_type label.
ISSUE_TO_ALERT = {
    "wrong_store_ref": "WrongStoreRef",
    "missing_reason": "MissingReason",
    "count_timing_conflict": "CountTimingConflict",
    "transfer_double_shrink": "TransferDoubleShrink",
    "repeated_adjustments": "RepeatedAdjustments",
    "unexplained_loss": "UnexplainedLoss",
}
