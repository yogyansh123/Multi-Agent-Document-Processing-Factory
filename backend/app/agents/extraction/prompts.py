"""
agents/extraction/prompts.py
============================
Versioned prompts for the Information Extraction Agent.
"""

from __future__ import annotations

from app.core.enums import DocumentType

EXTRACTION_PROMPT_VERSION = "1.0.0"

_COMMON_RULES = """
CRITICAL EXTRACTION RULES:
1. Extract ONLY information explicitly present in the provided document text.
2. NEVER invent, infer, or hallucinate missing information.
3. If a field or value cannot be found or is uncertain, leave it as null (None).
4. Preserve numerical values and currency exactly as printed.
5. Preserve dates in their original textual or ISO form where possible.
6. Preserve line items separately — do not lump multiple items together.
7. Do not perform calculations (e.g. tax, totals) unless the calculation is explicitly shown on the document.
"""

INVOICE_EXTRACTION_PROMPT = f"""You are an expert invoice data extraction engine.
Your task is to accurately extract structured financial and billing data from an invoice.

{_COMMON_RULES}

Specific extraction targets:
- Invoice number / reference
- Invoice date, due date, payment terms (e.g. Net 30)
- Currency (symbol or code like USD, EUR, $)
- Vendor / supplier contact details (name, address, email, phone, tax ID)
- Customer / client contact details (name, address, email, phone, tax ID)
- Itemized line items: description, quantity, unit price, tax, and line amount
- Financial totals: subtotal, tax, discounts, total amount due
"""

RECEIPT_EXTRACTION_PROMPT = f"""You are an expert receipt data extraction engine.
Your task is to accurately extract point-of-sale transaction details from a receipt.

{_COMMON_RULES}

Specific extraction targets:
- Receipt / transaction number
- Transaction date and time
- Merchant name and address
- Currency
- Purchased items: description, quantity, unit price, item amount
- Financial totals: subtotal, tax, discount, total amount paid
- Payment method (cash, card brand with last 4 digits)
"""

PURCHASE_ORDER_EXTRACTION_PROMPT = f"""You are an expert purchase order data extraction engine.
Your task is to accurately extract procurement and order details from a purchase order.

{_COMMON_RULES}

Specific extraction targets:
- Purchase order number (PO #)
- Order issue date and expected delivery date
- Currency
- Buyer / ordering entity details (name, address, contact)
- Supplier / vendor details
- Shipping / delivery address and billing address
- Ordered line items: description, quantity, unit price, line total
- Financial totals: subtotal, tax, total authorized amount
- Payment and delivery terms
"""

CONTRACT_EXTRACTION_PROMPT = f"""You are an expert legal contract information extraction engine.
Your task is to extract key business, legal, and operational terms from an agreement.
Do NOT attempt to summarize or reproduce full legal clauses.

{_COMMON_RULES}

Specific extraction targets:
- Contract title and reference/agreement number
- Effective commencement date and expiration/termination date
- Contracting parties (clean company or individual names)
- Governing law and jurisdiction/venue
- Payment terms and financial commitments
- Termination terms (notice periods, grounds for termination)
- Key obligations (bullet points of core commitments)
- Important dates (renewal deadlines, milestones, notice dates)
"""

OTHER_EXTRACTION_PROMPT = f"""You are an expert business document information extraction engine.
Your task is to extract key factual entities, structured key-value pairs, and a concise summary from a general business document (including certificates, credentials, licenses, resumes, letters, and general business records).

{_COMMON_RULES}

Specific extraction targets:
- Document title, credential name, or main subject header (the primary title, certification name, topic, or heading of the document)
- Primary document date (issue date, effective date, or date of document)
- Key entities mentioned (organizations, issuing bodies, recipients, people, departments)
- Meaningful key-value pairs explicitly stated (labels, identifiers, credential codes, and their values)
- Concise factual summary (2-3 sentences based strictly on the text)
"""

_PROMPT_REGISTRY: dict[str, str] = {
    DocumentType.INVOICE.value: INVOICE_EXTRACTION_PROMPT,
    DocumentType.RECEIPT.value: RECEIPT_EXTRACTION_PROMPT,
    DocumentType.PURCHASE_ORDER.value: PURCHASE_ORDER_EXTRACTION_PROMPT,
    DocumentType.CONTRACT.value: CONTRACT_EXTRACTION_PROMPT,
    DocumentType.OTHER.value: OTHER_EXTRACTION_PROMPT,
}


def get_extraction_prompt(doc_type: str | DocumentType) -> str:
    """Return the system prompt for the specified document type."""
    type_key = doc_type.value if isinstance(doc_type, DocumentType) else str(doc_type).upper()
    return _PROMPT_REGISTRY.get(type_key, OTHER_EXTRACTION_PROMPT)


def build_extraction_user_prompt(document_text: str, doc_type: str) -> str:
    """Format user prompt containing the document text and classification context."""
    cleaned_text = document_text.strip()
    if not cleaned_text:
        cleaned_text = "[EMPTY DOCUMENT / NO TEXT EXTRACTED]"
    return (
        f"DOCUMENT TYPE: {doc_type}\n\n"
        f"DOCUMENT TEXT TO EXTRACT FROM:\n"
        f"```\n{cleaned_text}\n```\n\n"
        f"Extract all supported fields strictly adhering to the schema. "
        f"Return null for any field not explicitly found."
    )
