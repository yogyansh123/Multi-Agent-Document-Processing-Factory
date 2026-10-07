"""
agents/extraction/schemas.py
============================
Document-type-specific Pydantic schemas for the Information Extraction Agent.

Design Principles:
- Strong typing throughout.
- All extracted fields default to None / empty list if not confidently detected.
- Never hallucinate or extrapolate missing information.
- Reusable sub-models for ContactInfo, line items, and key-values.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Union

from pydantic import BaseModel, Field

from app.core.enums import DocumentType


# ---------------------------------------------------------------------------
# Common Sub-Models
# ---------------------------------------------------------------------------

class ContactInfo(BaseModel):
    """Structured entity contact details (vendor, customer, buyer, supplier)."""

    name: str | None = Field(default=None, description="Entity or company name.")
    address: str | None = Field(default=None, description="Physical or billing address.")
    email: str | None = Field(default=None, description="Email address if present.")
    phone: str | None = Field(default=None, description="Phone number if present.")
    tax_id: str | None = Field(default=None, description="Tax ID / VAT number / EIN if present.")


class InvoiceLineItem(BaseModel):
    """Line item on an invoice."""

    description: str = Field(description="Description of item or service.")
    quantity: float | None = Field(default=None, description="Quantity or hours billed.")
    unit_price: float | None = Field(default=None, description="Price per unit.")
    tax: float | None = Field(default=None, description="Tax amount or rate for this item.")
    amount: float | None = Field(default=None, description="Total amount for this line.")
    total_amount: float | None = Field(default=None, description="Total amount for this line.")

    def model_post_init(self, __context: Any) -> None:
        if self.total_amount is not None and self.amount is None:
            self.amount = self.total_amount
        elif self.amount is not None and self.total_amount is None:
            self.total_amount = self.amount


class ReceiptItem(BaseModel):
    """Line item on a point-of-sale receipt."""

    description: str = Field(description="Description of purchased item.")
    quantity: float | None = Field(default=None, description="Quantity purchased.")
    unit_price: float | None = Field(default=None, description="Price per unit.")
    amount: float | None = Field(default=None, description="Total amount paid for this item.")


class PurchaseOrderLineItem(BaseModel):
    """Line item on a purchase order."""

    description: str = Field(description="Description of item requested.")
    quantity: float | None = Field(default=None, description="Quantity requested.")
    unit_price: float | None = Field(default=None, description="Expected unit price.")
    amount: float | None = Field(default=None, description="Total line cost.")


class KeyValueItem(BaseModel):
    """Explicit key-value pair extracted from a general business document."""

    key: str = Field(description="Name or label of the field.")
    value: str = Field(description="Associated value as explicitly stated.")


# ---------------------------------------------------------------------------
# Document-Type-Specific Schemas
# ---------------------------------------------------------------------------

class InvoiceExtraction(BaseModel):
    """Structured extraction schema for INVOICE documents."""

    invoice_number: str | None = Field(default=None, description="Invoice reference number.")
    invoice_date: str | None = Field(default=None, description="Date invoice was issued.")
    due_date: str | None = Field(default=None, description="Payment due date.")
    currency: str | None = Field(default=None, description="Currency symbol or code (e.g. USD, EUR, $).")
    vendor: ContactInfo | None = Field(default=None, description="Issuing vendor/supplier details.")
    customer: ContactInfo | None = Field(default=None, description="Billed client/customer details.")
    line_items: list[InvoiceLineItem] = Field(default_factory=list, description="Itemized billing lines.")
    subtotal: float | None = Field(default=None, description="Subtotal before taxes and discounts.")
    tax: float | None = Field(default=None, description="Total tax amount.")
    discount: float | None = Field(default=None, description="Discount amount applied.")
    total: float | None = Field(default=None, description="Grand total amount due.")
    total_amount: float | None = Field(default=None, description="Grand total amount due.")
    payment_terms: str | None = Field(default=None, description="Payment terms (e.g. 'Net 30').")

    def model_post_init(self, __context: Any) -> None:
        if self.total_amount is not None and self.total is None:
            self.total = self.total_amount
        elif self.total is not None and self.total_amount is None:
            self.total_amount = self.total



class ReceiptExtraction(BaseModel):
    """Structured extraction schema for RECEIPT documents."""

    receipt_number: str | None = Field(default=None, description="Receipt or transaction ID.")
    transaction_date: str | None = Field(default=None, description="Date/time of purchase.")
    merchant: str | None = Field(default=None, description="Merchant or store name.")
    merchant_address: str | None = Field(default=None, description="Merchant physical address.")
    currency: str | None = Field(default=None, description="Currency symbol or code.")
    items: list[ReceiptItem] = Field(default_factory=list, description="List of items purchased.")
    subtotal: float | None = Field(default=None, description="Subtotal before taxes.")
    tax: float | None = Field(default=None, description="Tax amount.")
    discount: float | None = Field(default=None, description="Discount applied.")
    total: float | None = Field(default=None, description="Total amount paid.")
    payment_method: str | None = Field(default=None, description="Payment method (e.g. 'Visa ****1234', 'Cash').")


class PurchaseOrderExtraction(BaseModel):
    """Structured extraction schema for PURCHASE_ORDER documents."""

    po_number: str | None = Field(default=None, description="Purchase order reference number.")
    po_date: str | None = Field(default=None, description="Date purchase order was issued.")
    delivery_date: str | None = Field(default=None, description="Expected delivery date.")
    currency: str | None = Field(default=None, description="Currency symbol or code.")
    buyer: ContactInfo | None = Field(default=None, description="Buyer/ordering organization.")
    supplier: ContactInfo | None = Field(default=None, description="Supplier/vendor fulfilling order.")
    shipping_address: str | None = Field(default=None, description="Delivery/shipping address.")
    billing_address: str | None = Field(default=None, description="Invoicing/billing address.")
    line_items: list[PurchaseOrderLineItem] = Field(default_factory=list, description="Items ordered.")
    subtotal: float | None = Field(default=None, description="Subtotal before taxes.")
    tax: float | None = Field(default=None, description="Tax amount.")
    total: float | None = Field(default=None, description="Total authorized amount.")
    payment_terms: str | None = Field(default=None, description="Agreed payment terms.")


class ContractExtraction(BaseModel):
    """Structured extraction schema for CONTRACT documents."""

    contract_title: str | None = Field(default=None, description="Title of the agreement.")
    contract_number: str | None = Field(default=None, description="Contract or agreement reference number.")
    effective_date: str | None = Field(default=None, description="Effective commencement date.")
    expiration_date: str | None = Field(default=None, description="Expiration or termination date.")
    parties: list[str] = Field(default_factory=list, description="Names of contracting parties.")
    governing_law: str | None = Field(default=None, description="Governing state or national law.")
    jurisdiction: str | None = Field(default=None, description="Agreed dispute jurisdiction or venue.")
    payment_terms: str | None = Field(default=None, description="Financial considerations or payment terms.")
    termination_terms: str | None = Field(default=None, description="Termination clauses and notice periods.")
    key_obligations: list[str] = Field(default_factory=list, description="Key obligations explicitly stipulated.")
    important_dates: list[str] = Field(default_factory=list, description="Milestones, renewal, or notice dates.")


class OtherExtraction(BaseModel):
    """Structured extraction schema for OTHER/general business documents."""

    title: str | None = Field(default=None, description="Document title or subject heading.")
    document_date: str | None = Field(default=None, description="Primary date identified in document.")
    entities: list[str] = Field(default_factory=list, description="Named entities (organizations, people) mentioned.")
    key_values: list[KeyValueItem] = Field(default_factory=list, description="Explicit key-value data points found.")
    summary: str | None = Field(default=None, description="Concise factual summary of document content.")


# Discriminated union of all supported extraction types
AnyExtractionData = Union[
    InvoiceExtraction,
    ReceiptExtraction,
    PurchaseOrderExtraction,
    ContractExtraction,
    OtherExtraction,
]


# ---------------------------------------------------------------------------
# Common Wrapper
# ---------------------------------------------------------------------------

class DocumentExtraction(BaseModel):
    """
    Common wrapper holding typed extraction results and execution metadata.
    """

    document_type: str = Field(description="Document category that drove schema selection.")
    extraction_version: str = Field(default="1.0.0", description="Version of extraction schema applied.")
    extracted_data: AnyExtractionData = Field(description="Document-specific structured payload.")
    extracted_at: datetime = Field(description="UTC timestamp of extraction.")


# ---------------------------------------------------------------------------
# Centralized Schema Registry
# ---------------------------------------------------------------------------

EXTRACTION_SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    DocumentType.INVOICE.value: InvoiceExtraction,
    DocumentType.RECEIPT.value: ReceiptExtraction,
    DocumentType.PURCHASE_ORDER.value: PurchaseOrderExtraction,
    DocumentType.CONTRACT.value: ContractExtraction,
    DocumentType.OTHER.value: OtherExtraction,
}


def get_extraction_schema(doc_type: str | DocumentType) -> type[BaseModel]:
    """
    Return the corresponding Pydantic extraction schema for a given document type.

    Falls back to OtherExtraction if unrecognised.
    """
    type_key = doc_type.value if isinstance(doc_type, DocumentType) else str(doc_type).upper()
    return EXTRACTION_SCHEMA_REGISTRY.get(type_key, OtherExtraction)
