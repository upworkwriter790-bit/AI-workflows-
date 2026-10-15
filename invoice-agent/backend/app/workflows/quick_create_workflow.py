"""Mode B1 — Quick Create. Turns a minimal payment snapshot into a
prefilled draft using deterministic exact-match lookups plus an AI
router that only ever picks among the candidates the backend already
found (or asks one clarification question) — it never invents a
customer, product, price, HSN/SAC, or GST rate. See
app/services/matching/ for the deterministic side and
app/prompts/invoice_prefill_system.txt for what the AI is told.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.customer import Customer
from app.models.product_catalog_item import ProductCatalogItem
from app.schemas.ai_prefill_output import AIPrefillOutput
from app.schemas.generated_invoice_request import GeneratedInvoiceDeliveryRequest
from app.schemas.quick_create import QuickCreateInput
from app.services.ai.factory import get_ai_provider
from app.services.ai.mock import MockAIProvider
from app.services.invoicing.calculator import LineItemInput, calculate_invoice_tax
from app.services.matching.customer_matching import find_candidate_customers
from app.services.matching.product_matching import find_candidate_products

ALLOWED_CHANNELS = {"email", "whatsapp"}


class QuickCreateNotReadyError(Exception):
    """Raised by build_request_from_resolution if called while the
    resolution outcome isn't READY_FOR_DRAFT — the caller should show
    the clarification question / detailed-form fallback instead.
    """

    def __init__(self, outcome: str) -> None:
        self.outcome = outcome
        super().__init__(f"quick-create input is not ready for a draft (outcome: {outcome})")


@dataclass
class QuickCreateResolution:
    outcome: str
    customer: dict | None
    product: dict | None
    missing_critical_fields: list[str]
    clarification: dict | None
    warnings: list[str]
    reviewer_summary: str


def _open_prompt_file(name: str):
    from pathlib import Path

    prompts_dir = Path(__file__).resolve().parents[1] / "prompts"
    return open(prompts_dir / name, encoding="utf-8")


def resolve_quick_create(db: Session, settings: Settings, payload: QuickCreateInput) -> QuickCreateResolution:
    customer_candidates = find_candidate_customers(db, email=payload.customer_email, phone=payload.customer_phone)
    product_candidates = find_candidate_products(
        db, item_reference=payload.item_reference, free_text=payload.product_text
    )

    provider = get_ai_provider(settings) or MockAIProvider()
    with _open_prompt_file("invoice_prefill_system.txt") as f:
        system_prompt = f.read()

    context = {
        "minimal_input": {
            "customer_email": payload.customer_email,
            "customer_phone": payload.customer_phone,
            "customer_name": payload.customer_name,
            "amount_paid": str(payload.amount_paid),
            "payment_reference": payload.payment_reference,
            "product_text": payload.product_text,
        },
        "customer_candidates": customer_candidates,
        "product_candidates": product_candidates,
    }
    raw = provider.generate_prefill(system_prompt=system_prompt, context=context)
    parsed = AIPrefillOutput.model_validate(raw)

    # Defense in depth: never trust an id the model returns unless it's
    # actually one of the candidates we gave it.
    candidate_customer_ids = {c["id"] for c in customer_candidates}
    candidate_product_ids = {c["id"] for c in product_candidates}
    customer_id = parsed.customer_match.customer_id
    if customer_id is not None and customer_id not in candidate_customer_ids:
        customer_id = None
    product_id = parsed.product_match.catalog_item_id
    if product_id is not None and product_id not in candidate_product_ids:
        product_id = None

    customer_row = db.query(Customer).filter_by(id=customer_id).one_or_none() if customer_id else None
    product_row = db.query(ProductCatalogItem).filter_by(id=product_id).one_or_none() if product_id else None

    customer_dict = (
        {
            "id": customer_row.id, "display_name": customer_row.display_name, "email": customer_row.email,
            "phone": customer_row.phone, "gstin": customer_row.gstin,
            "billing_address": customer_row.billing_address_json,
            "state_name": customer_row.state_name, "state_code": customer_row.state_code,
        }
        if customer_row
        else None
    )
    product_dict = (
        {
            "id": product_row.id, "internal_reference": product_row.internal_reference,
            "display_description": product_row.display_description,
            "product_type": product_row.product_type, "hsn_or_sac_code": product_row.hsn_or_sac_code,
            "unit": product_row.unit, "gst_rate": str(product_row.gst_rate),
        }
        if product_row
        else None
    )

    # Billing state is the one piece of required GST data the minimal
    # input can't carry on its own — resolve it from the matched
    # customer, or from an explicit clarification answer, else it's a
    # missing critical field (spec §6's "place of supply" requirement).
    missing = list(parsed.missing_critical_fields)
    state_code = (customer_dict or {}).get("state_code") or payload.billing_state_code
    state_name = (customer_dict or {}).get("state_name") or payload.billing_state_name
    if not state_code or not state_name:
        if "billing_state" not in missing:
            missing.append("billing_state")

    recipient_name = (customer_dict or {}).get("display_name") or payload.customer_name
    if not recipient_name:
        if "recipient_identity" not in missing:
            missing.append("recipient_identity")

    clarification = (
        parsed.single_clarification_question.model_dump(mode="json")
        if parsed.single_clarification_question
        else None
    )

    if missing and clarification is None:
        if "billing_state" in missing and recipient_name and product_dict:
            clarification = {
                "question": "Which state should this be billed to (for GST)?",
                "field_needed": "billing_state",
                "answer_type": "TEXT",
                "options": [],
            }
        elif "recipient_identity" in missing:
            clarification = {
                "question": "What is the customer's name?",
                "field_needed": "recipient_identity",
                "answer_type": "TEXT",
                "options": [],
            }

    if missing:
        outcome = "NEEDS_ONE_QUESTION" if clarification else "NEEDS_DETAILED_FORM"
    else:
        outcome = "READY_FOR_DRAFT"

    return QuickCreateResolution(
        outcome=outcome,
        customer=customer_dict,
        product=product_dict,
        missing_critical_fields=missing,
        clarification=clarification,
        warnings=parsed.warnings,
        reviewer_summary=parsed.reviewer_summary,
    )


def build_request_from_resolution(
    settings: Settings, payload: QuickCreateInput, resolution: QuickCreateResolution
) -> GeneratedInvoiceDeliveryRequest:
    if resolution.outcome != "READY_FOR_DRAFT":
        raise QuickCreateNotReadyError(resolution.outcome)

    from decimal import Decimal

    customer = resolution.customer or {}
    product = resolution.product
    assert product is not None  # READY_FOR_DRAFT implies a resolved product

    recipient_name = customer.get("display_name") or payload.customer_name
    state_code = customer.get("state_code") or payload.billing_state_code
    billing_address = customer.get("billing_address") or {
        "line1": "Address on file pending",
        "city": "",
        "state": customer.get("state_name") or payload.billing_state_name,
        "state_code": state_code,
        "postal_code": "000000",
        "country": "India",
    }

    channels = [c for c in payload.delivery_channels if c in ALLOWED_CHANNELS] or ["email"]

    # amount_paid is the one fact the user actually asserted — treat it
    # as the tax-inclusive grand total for a single line item and let
    # the same deterministic calculator used everywhere else derive the
    # subtotal/tax split, so the stated-vs-computed tolerance check in
    # create_draft_generated_invoice trivially agrees with itself.
    tax_result = calculate_invoice_tax(
        line_items=[
            LineItemInput(
                description=product["display_description"], product_type=product["product_type"],
                hsn_or_sac_code=product["hsn_or_sac_code"], quantity=Decimal(1), unit=product["unit"],
                unit_price=payload.amount_paid, discount_amount=Decimal(0),
                gst_rate=Decimal(product["gst_rate"]), item_reference=product.get("internal_reference"),
            )
        ],
        seller_state_code=settings.seller_state_code or "",
        recipient_state_code=state_code or "",
        place_of_supply_state_name=billing_address.get("state") or "",
        tax_inclusive=True,
        rounding_mode=settings.rounding_mode,
    )

    idempotency_key = (
        "quickcreate:"
        + hashlib.sha256(
            f"{payload.payment_reference}:{payload.customer_email or payload.customer_phone}".encode()
        ).hexdigest()[:32]
    )

    return GeneratedInvoiceDeliveryRequest.model_validate(
        {
            "idempotency_key": idempotency_key,
            "external_reference": payload.external_reference or payload.payment_reference,
            "recipient": {
                "name": recipient_name,
                "email": payload.customer_email or customer.get("email"),
                "phone": payload.customer_phone or customer.get("phone"),
                "gstin": customer.get("gstin"),
                "billing_address": billing_address,
            },
            "payment_or_order_details": {
                "payment_reference": payload.payment_reference,
                "payment_date": payload.payment_date.isoformat(),
                "currency": "INR",
                "tax_inclusive": True,
                "subtotal": str(tax_result.subtotal),
                "discount_total": str(tax_result.discount_total),
                "tax_total": str(tax_result.tax_total),
                "grand_total": str(tax_result.grand_total),
                "payment_status": "PAID",
            },
            "items": [
                {
                    "item_reference": product.get("internal_reference"),
                    "description": product["display_description"],
                    "product_type": product["product_type"],
                    "hsn_or_sac_code": product["hsn_or_sac_code"],
                    "quantity": "1",
                    "unit": product["unit"],
                    "unit_price": str(payload.amount_paid),
                    "gst_rate": product["gst_rate"],
                }
            ],
            "delivery": {"requested_channels": channels},
            "notes": payload.notes,
        }
    )
