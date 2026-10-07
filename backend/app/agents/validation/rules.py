"""
agents/validation/rules.py
==========================
Deterministic rule engine for document validation.

Enforces document-type-specific arithmetic, date consistency, required field,
and currency sanity checks without calling external APIs or LLMs.
"""

from __future__ import annotations

import datetime
from typing import Any

from app.agents.validation.schemas import ValidationIssue
from app.core.config import settings
from app.core.enums import ValidationSeverity


def _parse_date(date_str: str | None) -> datetime.date | None:
    """Best-effort parser for common date formats."""
    if not date_str or not isinstance(date_str, str):
        return None
    cleaned = date_str.strip()
    # Try ISO YYYY-MM-DD
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.date.fromisoformat(cleaned[:10])
    except ValueError:
        return None


def _validate_invoice_rules(
    data: dict[str, Any],
    tolerance: float,
) -> tuple[list[ValidationIssue], list[str]]:
    issues: list[ValidationIssue] = []
    rules: list[str] = []

    # 1. Required fields
    rules.append("INV_REQUIRED_FIELDS")
    if not data.get("invoice_number"):
        issues.append(
            ValidationIssue(
                code="MISSING_INVOICE_NUMBER",
                field="invoice_number",
                message="Invoice is missing an invoice number.",
                severity=ValidationSeverity.ERROR,
            )
        )
    vendor = data.get("vendor")
    if not vendor or not isinstance(vendor, dict) or not vendor.get("name"):
        issues.append(
            ValidationIssue(
                code="MISSING_VENDOR",
                field="vendor.name",
                message="Invoice is missing vendor name.",
                severity=ValidationSeverity.WARNING,
            )
        )
    total_amount = data.get("total_amount") if data.get("total_amount") is not None else data.get("total")
    if total_amount is None:
        issues.append(
            ValidationIssue(
                code="MISSING_TOTAL_AMOUNT",
                field="total_amount",
                message="Invoice is missing total amount.",
                severity=ValidationSeverity.ERROR,
            )
        )

    # 2. Line item arithmetic
    rules.append("INV_LINE_ITEM_ARITHMETIC")
    line_items = data.get("line_items") or []
    if isinstance(line_items, list):
        for idx, item in enumerate(line_items):
            if not isinstance(item, dict):
                continue
            qty = item.get("quantity")
            price = item.get("unit_price")
            item_total = item.get("total_amount") if item.get("total_amount") is not None else item.get("amount")
            if qty is not None and price is not None and item_total is not None:
                expected = round(float(qty) * float(price), 2)
                actual = round(float(item_total), 2)
                if abs(expected - actual) > tolerance:
                    issues.append(
                        ValidationIssue(
                            code="LINE_ITEM_ARITHMETIC_MISMATCH",
                            field=f"line_items[{idx}].total_amount",
                            message=f"Line item {idx + 1} total ({actual}) does not match quantity * unit_price ({expected}).",
                            severity=ValidationSeverity.ERROR,
                            actual_value=actual,
                            expected_value=expected,
                        )
                    )

    # 3. Subtotal arithmetic
    rules.append("INV_SUBTOTAL_ARITHMETIC")
    subtotal = data.get("subtotal")
    if subtotal is not None and isinstance(line_items, list) and len(line_items) > 0:
        item_amounts = [
            float(item.get("total_amount") if item.get("total_amount") is not None else item.get("amount", 0))
            for item in line_items
            if isinstance(item, dict) and (item.get("total_amount") is not None or item.get("amount") is not None)
        ]
        if len(item_amounts) == len(line_items):
            expected_subtotal = round(sum(item_amounts), 2)
            actual_subtotal = round(float(subtotal), 2)
            if abs(expected_subtotal - actual_subtotal) > tolerance:
                issues.append(
                    ValidationIssue(
                        code="SUBTOTAL_ARITHMETIC_MISMATCH",
                        field="subtotal",
                        message=f"Subtotal ({actual_subtotal}) does not match sum of line items ({expected_subtotal}).",
                        severity=ValidationSeverity.ERROR,
                        actual_value=actual_subtotal,
                        expected_value=expected_subtotal,
                    )
                )

    # 4. Total arithmetic
    rules.append("INV_TOTAL_ARITHMETIC")
    tax_amount = data.get("tax_amount") if data.get("tax_amount") is not None else (data.get("tax") or 0.0)
    discount = data.get("discount") or 0.0
    if subtotal is not None and total_amount is not None:
        expected_total = round(float(subtotal) + float(tax_amount) - float(discount), 2)
        actual_total = round(float(total_amount), 2)
        if abs(expected_total - actual_total) > tolerance:
            issues.append(
                ValidationIssue(
                    code="TOTAL_ARITHMETIC_MISMATCH",
                    field="total_amount",
                    message=f"Total amount ({actual_total}) does not match subtotal + tax - discount ({expected_total}).",
                    severity=ValidationSeverity.ERROR,
                    actual_value=actual_total,
                    expected_value=expected_total,
                )
            )

    # 5. Date consistency
    rules.append("INV_DATE_CONSISTENCY")
    inv_date = _parse_date(data.get("invoice_date"))
    due_date = _parse_date(data.get("due_date"))
    if inv_date and due_date:
        if due_date < inv_date:
            issues.append(
                ValidationIssue(
                    code="DATE_ORDER_INVALID",
                    field="due_date",
                    message=f"Due date ({due_date}) is earlier than invoice date ({inv_date}).",
                    severity=ValidationSeverity.ERROR,
                    actual_value=str(due_date),
                    expected_value=f">= {inv_date}",
                )
            )

    # 6. Currency consistency
    rules.append("INV_CURRENCY_CHECK")
    currency = data.get("currency")
    if currency and isinstance(currency, str):
        if len(currency.strip()) > 5:
            issues.append(
                ValidationIssue(
                    code="INVALID_CURRENCY_CODE",
                    field="currency",
                    message=f"Currency '{currency}' appears invalid or malformed.",
                    severity=ValidationSeverity.WARNING,
                    actual_value=currency,
                )
            )

    # 7. Non-negative checks
    rules.append("INV_NON_NEGATIVE_VALUES")
    for field_name in ("subtotal", "total_amount", "tax_amount"):
        val = data.get(field_name)
        if val is not None and float(val) < 0:
            issues.append(
                ValidationIssue(
                    code="NEGATIVE_VALUE",
                    field=field_name,
                    message=f"{field_name} must not be negative ({val}).",
                    severity=ValidationSeverity.ERROR,
                    actual_value=val,
                    expected_value=">= 0",
                )
            )

    return issues, rules


def _validate_receipt_rules(
    data: dict[str, Any],
    tolerance: float,
) -> tuple[list[ValidationIssue], list[str]]:
    issues: list[ValidationIssue] = []
    rules: list[str] = []

    # 1. Merchant presence
    rules.append("REC_MERCHANT_CHECK")
    if not data.get("merchant"):
        issues.append(
            ValidationIssue(
                code="MISSING_MERCHANT",
                field="merchant",
                message="Receipt does not identify a merchant name.",
                severity=ValidationSeverity.WARNING,
            )
        )

    # 2. Total amount presence
    rules.append("REC_TOTAL_CHECK")
    total_amount = data.get("total_amount")
    if total_amount is None:
        issues.append(
            ValidationIssue(
                code="MISSING_TOTAL_AMOUNT",
                field="total_amount",
                message="Receipt is missing total amount.",
                severity=ValidationSeverity.ERROR,
            )
        )

    # 3. Item arithmetic
    rules.append("REC_ITEM_ARITHMETIC")
    items = data.get("items") or []
    if isinstance(items, list):
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            qty = item.get("quantity")
            price = item.get("unit_price")
            amount = item.get("amount")
            if qty is not None and price is not None and amount is not None:
                expected = round(float(qty) * float(price), 2)
                actual = round(float(amount), 2)
                if abs(expected - actual) > tolerance:
                    issues.append(
                        ValidationIssue(
                            code="ITEM_ARITHMETIC_MISMATCH",
                            field=f"items[{idx}].amount",
                            message=f"Receipt item {idx + 1} amount ({actual}) does not match qty * unit_price ({expected}).",
                            severity=ValidationSeverity.ERROR,
                            actual_value=actual,
                            expected_value=expected,
                        )
                    )

    # 4. Subtotal & Total arithmetic
    rules.append("REC_TOTAL_ARITHMETIC")
    subtotal = data.get("subtotal")
    tax_amount = data.get("tax_amount") or 0.0
    discount = data.get("discount") or 0.0
    if subtotal is not None and total_amount is not None:
        expected_total = round(float(subtotal) + float(tax_amount) - float(discount), 2)
        actual_total = round(float(total_amount), 2)
        if abs(expected_total - actual_total) > tolerance:
            issues.append(
                ValidationIssue(
                    code="TOTAL_ARITHMETIC_MISMATCH",
                    field="total_amount",
                    message=f"Total ({actual_total}) does not equal subtotal + tax - discount ({expected_total}).",
                    severity=ValidationSeverity.ERROR,
                    actual_value=actual_total,
                    expected_value=expected_total,
                )
            )

    # 5. Future date check
    rules.append("REC_DATE_VALIDITY")
    tx_date = _parse_date(data.get("transaction_date"))
    if tx_date:
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        if tx_date > tomorrow:
            issues.append(
                ValidationIssue(
                    code="FUTURE_TRANSACTION_DATE",
                    field="transaction_date",
                    message=f"Transaction date ({tx_date}) is in the future.",
                    severity=ValidationSeverity.WARNING,
                    actual_value=str(tx_date),
                    expected_value=f"<= {tomorrow}",
                )
            )

    # 6. Non-negative check
    rules.append("REC_NON_NEGATIVE_VALUES")
    for field_name in ("subtotal", "total_amount", "tax_amount"):
        val = data.get(field_name)
        if val is not None and float(val) < 0:
            issues.append(
                ValidationIssue(
                    code="NEGATIVE_VALUE",
                    field=field_name,
                    message=f"{field_name} must not be negative ({val}).",
                    severity=ValidationSeverity.ERROR,
                    actual_value=val,
                )
            )

    return issues, rules


def _validate_purchase_order_rules(
    data: dict[str, Any],
    tolerance: float,
) -> tuple[list[ValidationIssue], list[str]]:
    issues: list[ValidationIssue] = []
    rules: list[str] = []

    # 1. PO number presence
    rules.append("PO_NUMBER_CHECK")
    if not data.get("po_number"):
        issues.append(
            ValidationIssue(
                code="MISSING_PO_NUMBER",
                field="po_number",
                message="Purchase order is missing a PO number.",
                severity=ValidationSeverity.ERROR,
            )
        )

    # 2. Supplier / Buyer presence
    rules.append("PO_PARTIES_CHECK")
    buyer = data.get("buyer")
    supplier = data.get("supplier") or data.get("vendor")
    if not buyer:
        issues.append(
            ValidationIssue(
                code="MISSING_PO_BUYER",
                field="buyer",
                message="Purchase order does not specify buyer details.",
                severity=ValidationSeverity.WARNING,
            )
        )
    if not supplier:
        issues.append(
            ValidationIssue(
                code="MISSING_PO_SUPPLIER",
                field="supplier",
                message="Purchase order does not specify supplier/vendor details.",
                severity=ValidationSeverity.WARNING,
            )
        )

    # 3. Line item arithmetic
    rules.append("PO_LINE_ITEM_ARITHMETIC")
    line_items = data.get("line_items") or []
    if isinstance(line_items, list):
        for idx, item in enumerate(line_items):
            if not isinstance(item, dict):
                continue
            qty = item.get("quantity")
            price = item.get("unit_price")
            item_total = item.get("total_amount")
            if qty is not None and price is not None and item_total is not None:
                expected = round(float(qty) * float(price), 2)
                actual = round(float(item_total), 2)
                if abs(expected - actual) > tolerance:
                    issues.append(
                        ValidationIssue(
                            code="LINE_ITEM_ARITHMETIC_MISMATCH",
                            field=f"line_items[{idx}].total_amount",
                            message=f"PO line item {idx + 1} total ({actual}) does not match quantity * unit_price ({expected}).",
                            severity=ValidationSeverity.ERROR,
                            actual_value=actual,
                            expected_value=expected,
                        )
                    )

    # 4. Subtotal and total checks
    rules.append("PO_TOTAL_ARITHMETIC")
    subtotal = data.get("subtotal")
    total_amount = data.get("total_amount")
    tax_amount = data.get("tax_amount") or 0.0
    if subtotal is not None and total_amount is not None:
        expected_total = round(float(subtotal) + float(tax_amount), 2)
        actual_total = round(float(total_amount), 2)
        if abs(expected_total - actual_total) > tolerance:
            issues.append(
                ValidationIssue(
                    code="TOTAL_ARITHMETIC_MISMATCH",
                    field="total_amount",
                    message=f"PO total ({actual_total}) does not match subtotal + tax ({expected_total}).",
                    severity=ValidationSeverity.ERROR,
                    actual_value=actual_total,
                    expected_value=expected_total,
                )
            )

    # 5. Delivery date consistency
    rules.append("PO_DATE_CONSISTENCY")
    po_date = _parse_date(data.get("po_date"))
    delivery_date = _parse_date(data.get("delivery_date"))
    if po_date and delivery_date:
        if delivery_date < po_date:
            issues.append(
                ValidationIssue(
                    code="DATE_ORDER_INVALID",
                    field="delivery_date",
                    message=f"Delivery date ({delivery_date}) is earlier than PO date ({po_date}).",
                    severity=ValidationSeverity.ERROR,
                    actual_value=str(delivery_date),
                    expected_value=f">= {po_date}",
                )
            )

    # 6. Non-negative checks
    rules.append("PO_NON_NEGATIVE_VALUES")
    for field_name in ("subtotal", "total_amount", "tax_amount"):
        val = data.get(field_name)
        if val is not None and float(val) < 0:
            issues.append(
                ValidationIssue(
                    code="NEGATIVE_VALUE",
                    field=field_name,
                    message=f"PO {field_name} must not be negative ({val}).",
                    severity=ValidationSeverity.ERROR,
                    actual_value=val,
                )
            )

    return issues, rules


def _validate_contract_rules(
    data: dict[str, Any],
    tolerance: float,
) -> tuple[list[ValidationIssue], list[str]]:
    issues: list[ValidationIssue] = []
    rules: list[str] = []

    # 1. Title / identifying info
    rules.append("CONTRACT_TITLE_CHECK")
    if not data.get("contract_title") and not data.get("contract_number"):
        issues.append(
            ValidationIssue(
                code="MISSING_CONTRACT_IDENTIFIER",
                field="contract_title",
                message="Contract has neither a title nor a contract number.",
                severity=ValidationSeverity.WARNING,
            )
        )

    # 2. Parties presence
    rules.append("CONTRACT_PARTIES_CHECK")
    parties = data.get("parties") or []
    if not isinstance(parties, list) or len(parties) == 0:
        issues.append(
            ValidationIssue(
                code="MISSING_CONTRACT_PARTIES",
                field="parties",
                message="Contract does not identify any contracting parties.",
                severity=ValidationSeverity.ERROR,
            )
        )
    elif len(parties) < 2:
        issues.append(
            ValidationIssue(
                code="INSUFFICIENT_PARTIES",
                field="parties",
                message="Contracts typically involve at least 2 distinct parties.",
                severity=ValidationSeverity.WARNING,
                actual_value=len(parties),
                expected_value=">= 2",
            )
        )

    # 3. Date consistency
    rules.append("CONTRACT_DATE_CONSISTENCY")
    eff_date = _parse_date(data.get("effective_date"))
    exp_date = _parse_date(data.get("expiration_date"))
    if eff_date and exp_date:
        if exp_date < eff_date:
            issues.append(
                ValidationIssue(
                    code="DATE_ORDER_INVALID",
                    field="expiration_date",
                    message=f"Expiration date ({exp_date}) is earlier than effective date ({eff_date}).",
                    severity=ValidationSeverity.ERROR,
                    actual_value=str(exp_date),
                    expected_value=f">= {eff_date}",
                )
            )

    return issues, rules


def _validate_other_rules(
    data: dict[str, Any],
    tolerance: float,
) -> tuple[list[ValidationIssue], list[str]]:
    issues: list[ValidationIssue] = []
    rules: list[str] = []

    rules.append("OTHER_IDENTIFICATION_CHECK")
    title = data.get("title")
    summary = data.get("summary")
    if not title and not summary:
        issues.append(
            ValidationIssue(
                code="MISSING_DOCUMENT_SUMMARY",
                field="summary",
                message="Document lacks both title and summary.",
                severity=ValidationSeverity.WARNING,
            )
        )

    rules.append("OTHER_KEY_VALUES_CHECK")
    key_values = data.get("key_values") or []
    if isinstance(key_values, list):
        for idx, kv in enumerate(key_values):
            if isinstance(kv, dict) and not kv.get("key"):
                issues.append(
                    ValidationIssue(
                        code="EMPTY_KEY_NAME",
                        field=f"key_values[{idx}].key",
                        message=f"Key-value pair {idx + 1} has an empty key.",
                        severity=ValidationSeverity.WARNING,
                    )
                )

    return issues, rules


def validate_deterministic(
    document_type: str,
    extracted_data: dict[str, Any],
    tolerance: float | None = None,
) -> tuple[list[ValidationIssue], list[str]]:
    """
    Execute deterministic validation rules based on document type.

    Returns:
        tuple of (issues: list[ValidationIssue], rules_checked: list[str])
    """
    tol = tolerance if tolerance is not None else settings.ARITHMETIC_TOLERANCE
    doc_type_upper = (document_type or "OTHER").upper()

    if doc_type_upper == "INVOICE":
        return _validate_invoice_rules(extracted_data, tol)
    elif doc_type_upper == "RECEIPT":
        return _validate_receipt_rules(extracted_data, tol)
    elif doc_type_upper == "PURCHASE_ORDER":
        return _validate_purchase_order_rules(extracted_data, tol)
    elif doc_type_upper == "CONTRACT":
        return _validate_contract_rules(extracted_data, tol)
    else:
        return _validate_other_rules(extracted_data, tol)
