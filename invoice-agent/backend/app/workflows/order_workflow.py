"""Use Case 1 order-processing workflow — Phase 2 scope: everything from
`PAID_ORDER_RECEIVED` through `INVOICE_PDF_GENERATED`. ERP sync, customer
email, and Operations notification are Phase 3 and are deliberately not
called from here yet (see docs/architecture.md's phase boundary).

Every transition writes exactly one AuditEvent. Nothing here calculates
tax, generates an invoice number, or renders a PDF outside the
deterministic services it calls — this module is orchestration only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem
from app.models.order import Order
from app.services.audit.service import record_event
from app.services.gst.calculator import (
    LineItemInput,
    amounts_match_within_tolerance,
    calculate_invoice_tax,
)
from app.services.gst.numbering import reserve_invoice_number
from app.services.invoice_pdf.renderer import InvoiceRenderContext, render_invoice_pdf
from app.services.storage.factory import get_storage_adapter


@dataclass
class WorkflowOutcome:
    invoice: Invoice
    halted_at_status: str | None = None


def _address_lines(address: dict) -> list[str]:
    parts = [address.get("line1"), address.get("line2"), address.get("city"), address.get("district")]
    parts = [p for p in parts if p]
    tail = f"{address.get('state', '')} {address.get('postal_code', '')}".strip()
    if tail:
        parts.append(tail)
    if address.get("country"):
        parts.append(address["country"])
    return parts


def _set_status(db: Session, invoice: Invoice, *, correlation_id: str, new_status: str, event_name: str, safe_payload: dict | None = None) -> None:
    previous = invoice.invoice_status
    invoice.invoice_status = new_status
    db.add(invoice)
    db.commit()
    record_event(
        db,
        correlation_id=correlation_id,
        entity_type="Invoice",
        entity_id=invoice.id,
        event_name=event_name,
        actor_type="SYSTEM",
        previous_state=previous,
        new_state=new_status,
        safe_payload=safe_payload or {},
    )


def process_paid_order(db: Session, order_id: str, settings: Settings) -> WorkflowOutcome:
    order = db.query(Order).filter_by(id=order_id).one()
    correlation_id = order.crm_order_id

    invoice = Invoice(
        invoice_type="SALES_INVOICE",
        order_id=order.id,
        customer_id=order.customer_id,
        currency=order.currency,
        invoice_status="PAID_ORDER_RECEIVED",
    )
    db.add(invoice)
    db.commit()
    record_event(
        db,
        correlation_id=correlation_id,
        entity_type="Invoice",
        entity_id=invoice.id,
        event_name="PAID_ORDER_RECEIVED",
        actor_type="SYSTEM",
        new_state="PAID_ORDER_RECEIVED",
        safe_payload={"order_id": order.crm_order_id},
    )

    missing_company_fields = settings.missing_live_invoicing_fields()
    if missing_company_fields:
        _set_status(
            db, invoice, correlation_id=correlation_id, new_status="VALIDATION_FAILED",
            event_name="VALIDATION_FAILED",
            safe_payload={"reason": "company_identity_not_configured", "missing_fields": missing_company_fields},
        )
        return WorkflowOutcome(invoice=invoice, halted_at_status="VALIDATION_FAILED")

    snapshot = order.order_snapshot_json
    customer_payload = snapshot.get("customer", {})
    items_payload = snapshot.get("items", [])
    pricing_payload = snapshot.get("pricing", {})

    validation_errors: list[str] = []
    if not customer_payload.get("name"):
        validation_errors.append("customer.name missing")
    if not customer_payload.get("email"):
        validation_errors.append("customer.email missing")
    if not customer_payload.get("billing_address", {}).get("state_code"):
        validation_errors.append("customer.billing_address.state_code missing")
    if not items_payload:
        validation_errors.append("items is empty")
    for idx, item in enumerate(items_payload):
        if not item.get("hsn_or_sac_code"):
            validation_errors.append(f"items[{idx}].hsn_or_sac_code missing")
        if item.get("gst_rate") is None:
            validation_errors.append(f"items[{idx}].gst_rate missing")

    if validation_errors:
        _set_status(
            db, invoice, correlation_id=correlation_id, new_status="VALIDATION_FAILED",
            event_name="VALIDATION_FAILED", safe_payload={"errors": validation_errors},
        )
        return WorkflowOutcome(invoice=invoice, halted_at_status="VALIDATION_FAILED")

    _set_status(db, invoice, correlation_id=correlation_id, new_status="ORDER_DATA_VALIDATED", event_name="ORDER_DATA_VALIDATED")

    try:
        line_inputs = [
            LineItemInput(
                description=item.get("description") or item["name"],
                hsn_or_sac_code=item["hsn_or_sac_code"],
                quantity=Decimal(str(item.get("quantity", 1))),
                unit=item.get("unit", "Nos"),
                unit_price=Decimal(str(item["unit_price"])),
                discount_amount=Decimal(str(item.get("discount_amount", 0))),
                gst_rate=Decimal(str(item["gst_rate"])),
                product_id=item.get("product_id"),
                sku=item.get("sku"),
            )
            for item in items_payload
        ]
        tax_result = calculate_invoice_tax(
            line_items=line_inputs,
            seller_state_code=settings.seller_state_code or "",
            customer_state_code=customer_payload["billing_address"]["state_code"],
            customer_state_name=customer_payload["billing_address"]["state"],
            tax_inclusive=bool(pricing_payload.get("tax_inclusive", False)),
        )
    except Exception as exc:  # noqa: BLE001 - isolate calc errors from the workflow
        _set_status(
            db, invoice, correlation_id=correlation_id, new_status="TAX_VALIDATION_FAILED",
            event_name="TAX_VALIDATION_FAILED", safe_payload={"error": str(exc)[:200]},
        )
        return WorkflowOutcome(invoice=invoice, halted_at_status="TAX_VALIDATION_FAILED")

    stated_grand_total = Decimal(str(pricing_payload.get("grand_total", 0)))
    tolerance = Decimal(str(settings.tax_mismatch_tolerance))
    if not amounts_match_within_tolerance(tax_result.grand_total, stated_grand_total, tolerance):
        _set_status(
            db, invoice, correlation_id=correlation_id, new_status="MANUAL_REVIEW_REQUIRED",
            event_name="TAX_MISMATCH_MANUAL_REVIEW",
            safe_payload={
                "computed_grand_total": str(tax_result.grand_total),
                "stated_grand_total": str(stated_grand_total),
                "tolerance": str(tolerance),
            },
        )
        return WorkflowOutcome(invoice=invoice, halted_at_status="MANUAL_REVIEW_REQUIRED")

    invoice.issuer_name = settings.company_legal_name
    invoice.issuer_gstin = settings.seller_gstin
    invoice.recipient_name = customer_payload["name"]
    invoice.recipient_gstin = customer_payload.get("gstin")
    invoice.subtotal = tax_result.subtotal
    invoice.discount_total = tax_result.discount_total
    invoice.taxable_total = tax_result.taxable_total
    invoice.cgst_total = tax_result.cgst_total
    invoice.sgst_total = tax_result.sgst_total
    invoice.igst_total = tax_result.igst_total
    invoice.cess_total = tax_result.cess_total
    invoice.grand_total = tax_result.grand_total
    invoice.place_of_supply = tax_result.place_of_supply_state
    db.add(invoice)
    db.commit()

    for idx, line in enumerate(tax_result.line_items, start=1):
        db.add(
            InvoiceLineItem(
                invoice_id=invoice.id,
                sequence=idx,
                external_product_reference=line.product_id,
                description=line.description,
                hsn_or_sac_code=line.hsn_or_sac_code,
                quantity=line.quantity,
                unit=line.unit,
                unit_price=line.unit_price,
                discount_amount=line.discount_amount,
                taxable_value=line.taxable_value,
                gst_rate=line.gst_rate,
                cgst_amount=line.cgst_amount,
                sgst_amount=line.sgst_amount,
                igst_amount=line.igst_amount,
                cess_amount=line.cess_amount,
                line_total=line.line_total,
            )
        )
    db.commit()

    _set_status(
        db, invoice, correlation_id=correlation_id, new_status="TAX_CALCULATED", event_name="TAX_CALCULATED",
        safe_payload={"grand_total": str(tax_result.grand_total), "is_inter_state": tax_result.is_inter_state},
    )

    invoice_date = date.today()
    invoice.invoice_number = reserve_invoice_number(db, settings, invoice_date)
    invoice.invoice_date = invoice_date
    invoice.template_version = None  # set once PDF is rendered below
    db.add(invoice)
    db.commit()

    _set_status(
        db, invoice, correlation_id=correlation_id, new_status="INVOICE_NUMBER_RESERVED",
        event_name="INVOICE_NUMBER_RESERVED", safe_payload={"invoice_number": invoice.invoice_number},
    )

    billing = customer_payload["billing_address"]
    shipping = customer_payload.get("shipping_address")
    render_ctx = InvoiceRenderContext(
        company_legal_name=settings.company_legal_name or "",
        company_registered_address=settings.company_registered_address or "",
        seller_gstin=settings.seller_gstin or "",
        support_email=settings.support_email,
        support_phone=settings.support_phone,
        logo_path=settings.invoice_logo_path,
        invoice_number=invoice.invoice_number,
        invoice_date=invoice_date,
        order_id=order.crm_order_id,
        payment_reference=order.payment_reference,
        internal_invoice_id=invoice.id,
        customer_name=customer_payload["name"],
        customer_gstin=customer_payload.get("gstin"),
        billing_address_lines=_address_lines(billing),
        shipping_address_lines=_address_lines(shipping) if shipping and shipping != billing else None,
        customer_state_code=billing["state_code"],
        currency=order.currency,
        tax_calc=tax_result,
    )
    pdf_bytes = render_invoice_pdf(render_ctx)
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()

    storage = get_storage_adapter(settings)
    storage_key = f"invoices/{invoice.id}.pdf"
    storage.save(storage_key, pdf_bytes, content_type="application/pdf")

    from app.services.invoice_pdf.renderer import TEMPLATE_VERSION

    invoice.pdf_storage_key = storage_key
    invoice.pdf_sha256 = pdf_sha256
    invoice.template_version = TEMPLATE_VERSION
    db.add(invoice)
    db.commit()

    _set_status(
        db, invoice, correlation_id=correlation_id, new_status="INVOICE_PDF_GENERATED",
        event_name="INVOICE_PDF_GENERATED", safe_payload={"pdf_sha256": pdf_sha256, "storage_key": storage_key},
    )

    return WorkflowOutcome(invoice=invoice)
