"""Method B workflow — spec §6: payment/order details in, a generated
invoice PDF queued for delivery out, through the same pipeline Method A
uses once a PDF exists (spec §2 "Important").

Idempotency design: `GeneratedInvoice.idempotency_key` is a DB-unique
column. The workflow inserts a `REQUEST_RECEIVED` row for a brand-new key
and relies on the unique-constraint violation (not a separate
idempotency-service lookup) to detect a repeat — simpler than double-
bookkeeping through the generic `IdempotencyRecord` table for this one
endpoint. A repeat call with the same key always returns the ORIGINAL
outcome, success or failure — if the original request failed validation,
fix the data and submit again under a NEW idempotency_key; reusing the
same key on purpose means "this is the same logical request," not "retry
with different data."
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.generated_invoice import GeneratedInvoice
from app.models.generated_invoice_line_item import GeneratedInvoiceLineItem
from app.models.invoice_document import InvoiceDocument
from app.models.product_catalog_item import ProductCatalogItem
from app.schemas.delivery_request import InvoiceDeliveryRequestFields
from app.schemas.generated_invoice_request import GeneratedInvoiceDeliveryRequest
from app.services.audit.service import record_event
from app.services.invoicing.calculator import (
    LineItemInput,
    amounts_match_within_tolerance,
    calculate_invoice_tax,
)
from app.services.invoicing.numbering import reserve_invoice_number
from app.services.invoicing.pdf_renderer import InvoiceRenderContext, render_invoice_pdf
from app.services.storage.factory import get_storage_adapter
from app.workflows.delivery_workflow import create_delivery


class GeneratedInvoiceValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class TotalMismatchError(Exception):
    def __init__(self, mismatches: list[str]) -> None:
        self.mismatches = mismatches
        super().__init__("; ".join(mismatches))


@dataclass
class GeneratedInvoiceOutcome:
    generated_invoice: GeneratedInvoice
    invoice_document: InvoiceDocument | None
    delivery_id: str | None
    is_duplicate_replay: bool = False


def _dec(value) -> Decimal:
    return Decimal(str(value))


def _address_lines(address: dict) -> list[str]:
    parts = [address.get("line1"), address.get("line2"), address.get("city"), address.get("district")]
    parts = [p for p in parts if p]
    tail = f"{address.get('state', '')} {address.get('postal_code', '')}".strip()
    if tail:
        parts.append(tail)
    if address.get("country"):
        parts.append(address["country"])
    return parts


def _validate_against_catalog(db: Session, request: GeneratedInvoiceDeliveryRequest) -> list[str]:
    errors = []
    for item in request.items:
        if not item.item_reference:
            continue
        catalog_entry = (
            db.query(ProductCatalogItem)
            .filter_by(internal_reference=item.item_reference, active=True)
            .one_or_none()
        )
        if catalog_entry is None:
            errors.append(f"item_reference {item.item_reference!r} not found in the active product catalog")
            continue
        if catalog_entry.hsn_or_sac_code != item.hsn_or_sac_code:
            errors.append(
                f"item_reference {item.item_reference!r}: submitted hsn_or_sac_code "
                f"{item.hsn_or_sac_code!r} does not match catalog value {catalog_entry.hsn_or_sac_code!r}"
            )
        if Decimal(str(catalog_entry.gst_rate)) != item.gst_rate:
            errors.append(
                f"item_reference {item.item_reference!r}: submitted gst_rate {item.gst_rate} "
                f"does not match catalog value {catalog_entry.gst_rate}"
            )
    return errors


def process_generated_invoice_request(
    db: Session, settings: Settings, request: GeneratedInvoiceDeliveryRequest, created_by_user_id: str
) -> GeneratedInvoiceOutcome:
    existing = db.query(GeneratedInvoice).filter_by(idempotency_key=request.idempotency_key).one_or_none()
    if existing is not None:
        document = (
            db.query(InvoiceDocument).filter_by(id=existing.invoice_document_id).one_or_none()
            if existing.invoice_document_id
            else None
        )
        delivery_id = None
        if document is not None:
            from app.models.invoice_delivery import InvoiceDelivery

            delivery = db.query(InvoiceDelivery).filter_by(document_id=document.id).one_or_none()
            delivery_id = delivery.id if delivery else None
        return GeneratedInvoiceOutcome(
            generated_invoice=existing, invoice_document=document, delivery_id=delivery_id,
            is_duplicate_replay=True,
        )

    correlation_id = f"corr_{hashlib.sha256(request.idempotency_key.encode()).hexdigest()[:16]}"

    generated_invoice = GeneratedInvoice(
        external_reference=request.external_reference,
        payment_reference=request.payment_or_order_details.payment_reference,
        payment_date=request.payment_or_order_details.payment_date,
        payment_status=request.payment_or_order_details.payment_status,
        currency=request.payment_or_order_details.currency,
        tax_inclusive=request.payment_or_order_details.tax_inclusive,
        seller_legal_name="", seller_registered_address="", seller_gstin="",
        seller_state_name="", seller_state_code="",
        recipient_name=request.recipient.name,
        recipient_email=request.recipient.email,
        recipient_phone=request.recipient.phone,
        recipient_gstin=request.recipient.gstin,
        billing_address_json=request.recipient.billing_address.model_dump(mode="json"),
        shipping_address_json=(
            request.recipient.shipping_address.model_dump(mode="json")
            if request.recipient.shipping_address
            else None
        ),
        place_of_supply="",
        subtotal=Decimal(0), taxable_total=Decimal(0), tax_total=Decimal(0), grand_total=Decimal(0),
        amount_in_words="",
        status="REQUEST_RECEIVED",
        idempotency_key=request.idempotency_key,
        correlation_id=correlation_id,
        created_by_user_id=created_by_user_id,
    )
    db.add(generated_invoice)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(GeneratedInvoice).filter_by(idempotency_key=request.idempotency_key).one_or_none()
        if existing is not None:
            return GeneratedInvoiceOutcome(
                generated_invoice=existing, invoice_document=None, delivery_id=None, is_duplicate_replay=True
            )
        # The idempotency_key itself was new — the conflict is on the
        # separate (external_reference, payment_reference) uniqueness
        # rule (spec §5): a different idempotency_key must not resubmit
        # the same transaction under a new key.
        raise GeneratedInvoiceValidationError(
            [
                f"external_reference {request.external_reference!r} + payment_reference "
                f"{request.payment_or_order_details.payment_reference!r} already has an active "
                "generated invoice — use the original idempotency_key to retrieve it, or submit a "
                "documented correction/credit-note instead"
            ]
        ) from None

    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="REQUEST_RECEIVED", actor_type="USER", actor_id=created_by_user_id,
        new_state="REQUEST_RECEIVED", safe_payload={"external_reference": request.external_reference},
    )

    def _fail(status: str, errors: list[str]):
        generated_invoice.status = status
        db.add(generated_invoice)
        db.commit()
        record_event(
            db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
            event_name=status, actor_type="SYSTEM", new_state=status, safe_payload={"errors": errors},
        )
        raise GeneratedInvoiceValidationError(errors)

    contact_errors = request.require_channel_contact_info()
    if contact_errors:
        return _fail("INVALID_REQUEST", contact_errors)

    catalog_errors = _validate_against_catalog(db, request)
    if catalog_errors:
        return _fail("INVALID_REQUEST", catalog_errors)

    missing_seller_fields = settings.missing_seller_identity_fields()
    if missing_seller_fields:
        return _fail(
            "INVALID_REQUEST",
            [f"server is not configured with seller identity: {missing_seller_fields}"],
        )

    generated_invoice.status = "REQUEST_VALIDATED"
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="REQUEST_VALIDATED", actor_type="SYSTEM", new_state="REQUEST_VALIDATED",
    )

    recipient_state_code = request.recipient.billing_address.state_code
    line_inputs = [
        LineItemInput(
            description=item.description, product_type=item.product_type,
            hsn_or_sac_code=item.hsn_or_sac_code, quantity=item.quantity, unit=item.unit,
            unit_price=item.unit_price, discount_amount=item.discount_amount, gst_rate=item.gst_rate,
            item_reference=item.item_reference,
        )
        for item in request.items
    ]
    tax_result = calculate_invoice_tax(
        line_items=line_inputs,
        seller_state_code=settings.seller_state_code,
        recipient_state_code=recipient_state_code,
        place_of_supply_state_name=request.recipient.billing_address.state,
        tax_inclusive=request.payment_or_order_details.tax_inclusive,
        rounding_mode=settings.rounding_mode,
    )

    generated_invoice.status = "AMOUNTS_CALCULATED"
    generated_invoice.calculation_snapshot_json = tax_result.snapshot()
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="AMOUNTS_CALCULATED", actor_type="SYSTEM", new_state="AMOUNTS_CALCULATED",
    )

    tolerance = _dec(settings.tax_tolerance_amount)
    stated = request.payment_or_order_details
    mismatches = []
    if not amounts_match_within_tolerance(tax_result.subtotal, stated.subtotal, tolerance):
        mismatches.append(f"subtotal: computed {tax_result.subtotal} vs submitted {stated.subtotal}")
    if not amounts_match_within_tolerance(tax_result.discount_total, stated.discount_total, tolerance):
        mismatches.append(f"discount_total: computed {tax_result.discount_total} vs submitted {stated.discount_total}")
    if not amounts_match_within_tolerance(tax_result.tax_total, stated.tax_total, tolerance):
        mismatches.append(f"tax_total: computed {tax_result.tax_total} vs submitted {stated.tax_total}")
    if not amounts_match_within_tolerance(tax_result.grand_total, stated.grand_total, tolerance):
        mismatches.append(f"grand_total: computed {tax_result.grand_total} vs submitted {stated.grand_total}")

    if mismatches:
        generated_invoice.status = "TOTAL_MISMATCH"
        db.add(generated_invoice)
        db.commit()
        record_event(
            db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
            event_name="TOTAL_MISMATCH", actor_type="SYSTEM", new_state="TOTAL_MISMATCH",
            safe_payload={"mismatches": mismatches},
        )
        raise TotalMismatchError(mismatches)

    generated_invoice.status = "TOTALS_VALIDATED"
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="TOTALS_VALIDATED", actor_type="SYSTEM", new_state="TOTALS_VALIDATED",
    )

    invoice_date = date.today()
    invoice_number = reserve_invoice_number(db, settings, invoice_date)
    generated_invoice.invoice_number = invoice_number
    generated_invoice.invoice_date = invoice_date
    generated_invoice.status = "INVOICE_NUMBER_RESERVED"
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="INVOICE_NUMBER_RESERVED", actor_type="SYSTEM", new_state="INVOICE_NUMBER_RESERVED",
        safe_payload={"invoice_number": invoice_number},
    )

    billing = request.recipient.billing_address
    shipping = request.recipient.shipping_address
    shipping_lines = None
    if shipping and not shipping.same_as_billing and shipping.line1:
        shipping_lines = _address_lines(shipping.model_dump(mode="json"))

    render_ctx = InvoiceRenderContext(
        seller_legal_name=settings.company_legal_name,
        seller_registered_address=settings.company_registered_address,
        seller_gstin=settings.seller_gstin,
        support_email=settings.support_email,
        support_phone=settings.support_phone,
        logo_url=settings.company_logo_url,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        payment_reference=request.payment_or_order_details.payment_reference,
        external_reference=request.external_reference,
        recipient_name=request.recipient.name,
        recipient_gstin=request.recipient.gstin,
        billing_address_lines=_address_lines(billing.model_dump(mode="json")),
        shipping_address_lines=shipping_lines,
        currency=request.payment_or_order_details.currency,
        tax_calc=tax_result,
        template_version=settings.invoice_template_version,
        reverse_charge_applicable=settings.reverse_charge_applicable,
    )

    try:
        pdf_bytes = render_invoice_pdf(render_ctx, settings)
    except Exception as exc:  # noqa: BLE001 - isolate render failures
        generated_invoice.status = "PDF_RENDER_FAILED"
        db.add(generated_invoice)
        db.commit()
        record_event(
            db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
            event_name="PDF_RENDER_FAILED", actor_type="SYSTEM", new_state="PDF_RENDER_FAILED",
            safe_payload={"error": str(exc)[:200]},
        )
        raise

    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    generated_invoice.status = "PDF_RENDERED"
    generated_invoice.pdf_sha256 = pdf_sha256
    generated_invoice.template_version = settings.invoice_template_version
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="PDF_RENDERED", actor_type="SYSTEM", new_state="PDF_RENDERED",
    )

    sanitized_filename = f"{invoice_number.replace('/', '_')}.pdf"
    storage_key = f"invoice-documents/{generated_invoice.id}/{sanitized_filename}"
    try:
        storage = get_storage_adapter(settings)
        storage.save(storage_key, pdf_bytes, content_type="application/pdf")
    except Exception as exc:  # noqa: BLE001
        generated_invoice.status = "STORAGE_FAILED"
        db.add(generated_invoice)
        db.commit()
        record_event(
            db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
            event_name="STORAGE_FAILED", actor_type="SYSTEM", new_state="STORAGE_FAILED",
            safe_payload={"error": str(exc)[:200]},
        )
        raise

    generated_invoice.status = "PDF_STORED"
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="PDF_STORED", actor_type="SYSTEM", new_state="PDF_STORED",
    )

    invoice_document = InvoiceDocument(
        original_filename=sanitized_filename,
        sanitized_filename=sanitized_filename,
        mime_type="application/pdf",
        byte_size=len(pdf_bytes),
        sha256=pdf_sha256,
        storage_key=storage_key,
        uploaded_by_user_id=created_by_user_id,
        external_reference=request.external_reference,
        invoice_number=invoice_number,
        source="API",
    )
    db.add(invoice_document)
    db.commit()

    generated_invoice.invoice_document_id = invoice_document.id
    generated_invoice.seller_legal_name = settings.company_legal_name
    generated_invoice.seller_registered_address = settings.company_registered_address
    generated_invoice.seller_gstin = settings.seller_gstin
    generated_invoice.seller_state_name = settings.seller_state_name
    generated_invoice.seller_state_code = settings.seller_state_code
    generated_invoice.place_of_supply = tax_result.place_of_supply_state
    generated_invoice.subtotal = tax_result.subtotal
    generated_invoice.discount_total = tax_result.discount_total
    generated_invoice.taxable_total = tax_result.taxable_total
    generated_invoice.cgst_total = tax_result.cgst_total
    generated_invoice.sgst_total = tax_result.sgst_total
    generated_invoice.igst_total = tax_result.igst_total
    generated_invoice.cess_total = tax_result.cess_total
    generated_invoice.tax_total = tax_result.tax_total
    generated_invoice.grand_total = tax_result.grand_total
    from app.services.invoicing.amount_in_words import amount_in_words

    generated_invoice.amount_in_words = amount_in_words(tax_result.grand_total)
    generated_invoice.status = "INVOICE_DOCUMENT_CREATED"
    generated_invoice.generated_at = datetime.now(timezone.utc)
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="INVOICE_DOCUMENT_CREATED", actor_type="SYSTEM", new_state="INVOICE_DOCUMENT_CREATED",
        safe_payload={"invoice_document_id": invoice_document.id},
    )

    for idx, line in enumerate(tax_result.line_items, start=1):
        db.add(
            GeneratedInvoiceLineItem(
                generated_invoice_id=generated_invoice.id,
                line_number=idx,
                item_reference=line.item_reference,
                description=line.description,
                product_type=line.product_type,
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

    delivery_fields = InvoiceDeliveryRequestFields(
        recipient_name=request.recipient.name,
        recipient_email=request.recipient.email,
        recipient_phone=request.recipient.phone,
        requested_channels=request.delivery.requested_channels,
        idempotency_key=f"{request.idempotency_key}:delivery",
        external_reference=request.external_reference,
        invoice_number=invoice_number,
        source="API",
        notes=request.notes,
        attach_pdf_to_email=request.delivery.attach_pdf_to_email,
        include_download_link=request.delivery.include_secure_download_link,
        send_whatsapp_notification=request.delivery.send_whatsapp_notification,
    )
    delivery = create_delivery(db, document=invoice_document, fields=delivery_fields, correlation_id=correlation_id)
    delivery.created_by_user_id = created_by_user_id
    db.add(delivery)
    db.commit()

    generated_invoice.status = "DELIVERY_QUEUED"
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="DELIVERY_QUEUED", actor_type="SYSTEM", new_state="DELIVERY_QUEUED",
        safe_payload={"delivery_id": delivery.id},
    )

    return GeneratedInvoiceOutcome(
        generated_invoice=generated_invoice, invoice_document=invoice_document, delivery_id=delivery.id
    )
