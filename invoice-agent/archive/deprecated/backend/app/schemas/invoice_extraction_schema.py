"""The exact JSON schema Claude/OpenAI/Gemini/etc. must return for Use Case 2
extraction (spec §19). Shared verbatim across every LLM provider so the
backend's downstream parsing/validation code never special-cases a provider.

SCHEMA_VERSION travels with every stored extraction row so a future prompt
or schema change never silently reinterprets old records.
"""

from __future__ import annotations

SCHEMA_VERSION = "1.0.0"

INVOICE_EXTRACTION_JSON_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "document_type",
        "issuer",
        "recipient",
        "invoice_details",
        "line_items",
        "totals",
        "field_confidence",
        "missing_or_unclear_fields",
        "document_observations",
        "suggested_recommendation",
        "recommendation_reason",
        "evidence",
    ],
    "properties": {
        "document_type": {
            "type": "string",
            "enum": ["INVOICE", "CREDIT_NOTE", "RECEIPT", "OTHER", "UNKNOWN"],
        },
        "language": {"type": ["string", "null"]},
        "issuer": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "legal_name": {"type": ["string", "null"]},
                "address": {"type": ["string", "null"]},
                "gstin": {"type": ["string", "null"]},
                "email": {"type": ["string", "null"]},
                "phone": {"type": ["string", "null"]},
            },
        },
        "recipient": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "legal_name": {"type": ["string", "null"]},
                "address": {"type": ["string", "null"]},
                "gstin": {"type": ["string", "null"]},
            },
        },
        "invoice_details": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "invoice_number": {"type": ["string", "null"]},
                "invoice_date": {"type": ["string", "null"]},
                "due_date": {"type": ["string", "null"]},
                "currency": {"type": ["string", "null"]},
                "purchase_order_reference": {"type": ["string", "null"]},
                "order_reference": {"type": ["string", "null"]},
                "contract_reference": {"type": ["string", "null"]},
                "place_of_supply": {"type": ["string", "null"]},
                "reverse_charge_applicable": {"type": ["boolean", "null"]},
            },
        },
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "line_number": {"type": "integer"},
                    "description": {"type": ["string", "null"]},
                    "hsn_or_sac_code": {"type": ["string", "null"]},
                    "quantity": {"type": ["number", "null"]},
                    "unit": {"type": ["string", "null"]},
                    "unit_price": {"type": ["number", "null"]},
                    "discount_amount": {"type": ["number", "null"]},
                    "taxable_value": {"type": ["number", "null"]},
                    "gst_rate": {"type": ["number", "null"]},
                    "cgst_amount": {"type": ["number", "null"]},
                    "sgst_amount": {"type": ["number", "null"]},
                    "igst_amount": {"type": ["number", "null"]},
                    "cess_amount": {"type": ["number", "null"]},
                    "line_total": {"type": ["number", "null"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "page_number": {"type": ["integer", "null"]},
                },
            },
        },
        "totals": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "subtotal": {"type": ["number", "null"]},
                "discount_total": {"type": ["number", "null"]},
                "taxable_total": {"type": ["number", "null"]},
                "cgst_total": {"type": ["number", "null"]},
                "sgst_total": {"type": ["number", "null"]},
                "igst_total": {"type": ["number", "null"]},
                "cess_total": {"type": ["number", "null"]},
                "grand_total": {"type": ["number", "null"]},
            },
        },
        "field_confidence": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "invoice_number": {"type": "number", "minimum": 0, "maximum": 1},
                "invoice_date": {"type": "number", "minimum": 0, "maximum": 1},
                "issuer_name": {"type": "number", "minimum": 0, "maximum": 1},
                "issuer_gstin": {"type": "number", "minimum": 0, "maximum": 1},
                "recipient_name": {"type": "number", "minimum": 0, "maximum": 1},
                "recipient_gstin": {"type": "number", "minimum": 0, "maximum": 1},
                "grand_total": {"type": "number", "minimum": 0, "maximum": 1},
            },
        },
        "missing_or_unclear_fields": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "field": {"type": "string"},
                    "reason": {"type": "string"},
                    "critical": {"type": "boolean"},
                },
                "required": ["field", "reason", "critical"],
            },
        },
        "document_observations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": [
                            "MISSING_FIELD",
                            "UNREADABLE_FIELD",
                            "FORMAT_ISSUE",
                            "POSSIBLE_ALTERATION",
                            "OTHER",
                        ],
                    },
                    "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
                    "page_number": {"type": ["integer", "null"]},
                    "description": {"type": "string"},
                },
                "required": ["type", "severity", "description"],
            },
        },
        "suggested_recommendation": {
            "type": "string",
            "enum": ["ACCEPT", "HOLD_FOR_REVIEW", "REJECT"],
        },
        "recommendation_reason": {"type": "string"},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "field": {"type": "string"},
                    "page_number": {"type": ["integer", "null"]},
                    "description": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["field", "description", "confidence"],
            },
        },
    },
}

CRITICAL_FIELDS = [
    "document_type",
    "issuer_name",
    "recipient_name",
    "invoice_number",
    "invoice_date",
    "currency",
    "grand_total",
]
