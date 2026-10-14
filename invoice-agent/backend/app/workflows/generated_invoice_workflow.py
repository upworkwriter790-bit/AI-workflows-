"""Method B workflow — spec §6 plus the human draft/approve gate added
on top of it: a generated invoice is calculated and held as an editable
DRAFT; nothing is numbered, rendered, stored, or queued for delivery
until an authorized user calls `approve_and_finalize()`.

Idempotency design: `GeneratedInvoice.idempotency_key` is a DB-unique
column. The workflow inserts a row for a brand-new key and relies on the
unique-constraint violation (not a separate idempotency-service lookup)
to detect a repeat — simpler than double-bookkeeping through the generic
`IdempotencyRecord` table for this one endpoint. A repeat call with the
same key always returns the ORIGINAL outcome, success or failure — if the
original request failed validation, fix the data and submit again under
a NEW idempotency_key.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime
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
from app.services.invoicing.amount_in_words import amount_in_words
from app.services.invoicing.calculator import (
    LineItemInput,
    amounts_match_within_tolerance,
    calculate_invoice_tax,
)
from app.services.invoicing.numbering import reserve_invoice_number
from app.services.invoicing.pdf_renderer import InvoiceRenderContext, render_invoice_pdf
from app.services.storage.factory import get_storage_adapter
from app.workflows.delivery_workflow import approve_delivery, create_delivery


class GeneratedInvoiceValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class TotalMismatchError(Exception):
    def __init__(self, mismatches: list[str]) -> None:
        self.mismatches = mismatches
        super().__init__("; ".join(mismatches))


class GeneratedInvoiceNotDraftError(Exception):
    def __init__(self, invoice_id: str, current_status: str) -> None:
        self.invoice_id = invoice_id
        self.current_status = current_status
        super().__init__(f"generated invoice {invoice_id} is not a DRAFT (status: {current_status})")


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


def _validate_request(db: Session, settings: Settings, request: GeneratedInvoiceDeliveryRequest) -> list[str]:
    errors = request.require_channel_contact_info()
    errors += _validate_against_catalog(db, request)
    missing_seller_fields = settings.missing_seller_identity_fields()
    if missing_seller_fields:
        errors.append(f"server is not configured with seller identity: {missing_seller_fields}")
    return errors


def _calculate(settings: Settings, request: GeneratedInvoiceDeliveryRequest):
    line_inputs = [
        LineItemInput(
            description=item.description, product_type=item.product_type,
            hsn_or_sac_code=item.hsn_or_sac_code, quantity=item.quantity, unit=item.unit,
            unit_price=item.unit_price, discount_amount=item.discount_amount, gst_rate=item.gst_rate,
            item_reference=item.item_reference,
        )
        for item in request.items
    ]
    return calculate_invoice_tax(
        line_items=line_inputs,
        seller_state_code=settings.seller_state_code or "",
        recipient_state_code=request.recipient.billing_address.state_code,
        place_of_supply_state_name=request.recipient.billing_address.state,
        tax_inclusive=request.payment_or_order_details.tax_inclusive,
        rounding_mode=settings.rounding_mode,
    )


def _check_totals(settings: Settings, request: GeneratedInvoiceDeliveryRequest, tax_result) -> list[str]:
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
    return mismatches


def _apply_request_to_invoice(generated_invoice: GeneratedInvoice, request: GeneratedInvoiceDeliveryRequest) -> None:
    generated_invoice.external_reference = request.external_reference
    generated_invoice.payment_reference = request.payment_or_order_details.payment_reference
    generated_invoice.payment_date = request.payment_or_order_details.payment_date
    generated_invoice.payment_status = request.payment_or_order_details.payment_status
    generated_invoice.currency = request.payment_or_order_details.currency
    generated_invoice.tax_inclusive = request.payment_or_order_details.tax_inclusive
    generated_invoice.recipient_name = request.recipient.name
    generated_invoice.recipient_email = request.recipient.email
    generated_invoice.recipient_phone = request.recipient.phone
    generated_invoice.recipient_gstin = request.recipient.gstin
    generated_invoice.billing_address_json = request.recipient.billing_address.model_dump(mode="json")
    generated_invoice.shipping_address_json = (
        request.recipient.shipping_address.model_dump(mode="json") if request.recipient.shipping_address else None
    )
    generated_invoice.requested_channels_json = request.delivery.requested_channels
    generated_invoice.attach_pdf_to_email = request.delivery.attach_pdf_to_email
    generated_invoice.include_download_link = request.delivery.include_secure_download_link
    generated_invoice.send_whatsapp_notification = request.delivery.send_whatsapp_notification
    generated_invoice.notes = request.notes


def _replace_line_items(db: Session, generated_invoice: GeneratedInvoice, tax_result) -> None:
    db.query(GeneratedInvoiceLineItem).filter_by(generated_invoice_id=generated_invoice.id).delete()
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


def create_draft_generated_invoice(
    db: Session, settings: Settings, request: GeneratedInvoiceDeliveryRequest, created_by_user_id: str
) -> GeneratedInvoiceOutcome:
    """Validates and calculates, then stops — the result is a DRAFT the
    caller can review, edit (`edit_draft_generated_invoice`), and
    eventually approve (`approve_and_finalize`). Nothing is numbered,
    rendered, stored, or sent at this point.
    """
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
        requested_channels_json=request.delivery.requested_channels,
        attach_pdf_to_email=request.delivery.attach_pdf_to_email,
        include_download_link=request.delivery.include_secure_download_link,
        send_whatsapp_notification=request.delivery.send_whatsapp_notification,
        notes=request.notes,
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

    validation_errors = _validate_request(db, settings, request)
    if validation_errors:
        return _fail("INVALID_REQUEST", validation_errors)

    generated_invoice.status = "REQUEST_VALIDATED"
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="REQUEST_VALIDATED", actor_type="SYSTEM", new_state="REQUEST_VALIDATED",
    )

    tax_result = _calculate(settings, request)
    generated_invoice.status = "AMOUNTS_CALCULATED"
    generated_invoice.calculation_snapshot_json = tax_result.snapshot()
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="AMOUNTS_CALCULATED", actor_type="SYSTEM", new_state="AMOUNTS_CALCULATED",
    )

    mismatches = _check_totals(settings, request, tax_result)
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
    generated_invoice.amount_in_words = amount_in_words(tax_result.grand_total)
    generated_invoice.status = "DRAFT"
    db.add(generated_invoice)
    db.commit()
    _replace_line_items(db, generated_invoice, tax_result)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="DRAFT_READY_FOR_REVIEW", actor_type="SYSTEM", new_state="DRAFT",
        safe_payload={"grand_total": str(tax_result.grand_total)},
    )

    return GeneratedInvoiceOutcome(generated_invoice=generated_invoice, invoice_document=None, delivery_id=None)


def edit_draft_generated_invoice(
    db: Session,
    settings: Settings,
    generated_invoice: GeneratedInvoice,
    request: GeneratedInvoiceDeliveryRequest,
    edited_by_user_id: str,
) -> GeneratedInvoice:
    """Replaces the draft's content with `request` and recalculates.
    Raises GeneratedInvoiceNotDraftError if the invoice has already been
    approved/finalized, GeneratedInvoiceValidationError /
    TotalMismatchError on the same conditions `create_draft_...` checks.
    """
    if generated_invoice.status != "DRAFT":
        raise GeneratedInvoiceNotDraftError(generated_invoice.id, generated_invoice.status)

    validation_errors = _validate_request(db, settings, request)
    if validation_errors:
        raise GeneratedInvoiceValidationError(validation_errors)

    tax_result = _calculate(settings, request)
    mismatches = _check_totals(settings, request, tax_result)
    if mismatches:
        raise TotalMismatchError(mismatches)

    _apply_request_to_invoice(generated_invoice, request)
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
    generated_invoice.amount_in_words = amount_in_words(tax_result.grand_total)
    generated_invoice.calculation_snapshot_json = tax_result.snapshot()
    db.add(generated_invoice)
    db.commit()
    _replace_line_items(db, generated_invoice, tax_result)
    db.commit()
    record_event(
        db, correlation_id=generated_invoice.correlation_id, entity_type="GeneratedInvoice",
        entity_id=generated_invoice.id, event_name="DRAFT_EDITED", actor_type="USER",
        actor_id=edited_by_user_id, safe_payload={"grand_total": str(tax_result.grand_total)},
    )
    return generated_invoice


def approve_and_finalize(
    db: Session, settings: Settings, generated_invoice: GeneratedInvoice, approved_by_user_id: str
) -> GeneratedInvoiceOutcome:
    """The human-approval step. Reserves the invoice number, renders and
    stores the final PDF, creates the InvoiceDocument + InvoiceDelivery,
    and immediately approves the delivery too — one human action both
    finalizes the invoice's content and authorizes it to be sent.
    From this point on the invoice is immutable.
    """
    if generated_invoice.status != "DRAFT":
        raise GeneratedInvoiceNotDraftError(generated_invoice.id, generated_invoice.status)

    correlation_id = generated_invoice.correlation_id

    invoice_date = date.today()
    invoice_number = reserve_invoice_number(db, settings, invoice_date)
    generated_invoice.invoice_number = invoice_number
    generated_invoice.invoice_date = invoice_date
    generated_invoice.status = "INVOICE_NUMBER_RESERVED"
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="INVOICE_NUMBER_RESERVED", actor_type="USER", actor_id=approved_by_user_id,
        new_state="INVOICE_NUMBER_RESERVED", safe_payload={"invoice_number": invoice_number},
    )

    line_items = (
        db.query(GeneratedInvoiceLineItem)
        .filter_by(generated_invoice_id=generated_invoice.id)
        .order_by(GeneratedInvoiceLineItem.line_number)
        .all()
    )
    billing = generated_invoice.billing_address_json
    shipping = generated_invoice.shipping_address_json
    shipping_lines = None
    if shipping and not shipping.get("same_as_billing") and shipping.get("line1"):
        shipping_lines = _address_lines(shipping)

    from app.services.invoicing.calculator import GSTCalculationResult, LineItemResult

    tax_calc_for_render = GSTCalculationResult(
        is_inter_state=settings.seller_state_code != billing.get("state_code"),
        place_of_supply_state=generated_invoice.place_of_supply,
        subtotal=Decimal(str(generated_invoice.subtotal)),
        discount_total=Decimal(str(generated_invoice.discount_total)),
        taxable_total=Decimal(str(generated_invoice.taxable_total)),
        cgst_total=Decimal(str(generated_invoice.cgst_total)),
        sgst_total=Decimal(str(generated_invoice.sgst_total)),
        igst_total=Decimal(str(generated_invoice.igst_total)),
        cess_total=Decimal(str(generated_invoice.cess_total)),
        tax_total=Decimal(str(generated_invoice.tax_total)),
        grand_total=Decimal(str(generated_invoice.grand_total)),
        line_items=[
            LineItemResult(
                description=li.description, product_type=li.product_type, hsn_or_sac_code=li.hsn_or_sac_code,
                quantity=Decimal(str(li.quantity)), unit=li.unit, unit_price=Decimal(str(li.unit_price)),
                discount_amount=Decimal(str(li.discount_amount)), taxable_value=Decimal(str(li.taxable_value)),
                gst_rate=Decimal(str(li.gst_rate)), cgst_amount=Decimal(str(li.cgst_amount)),
                sgst_amount=Decimal(str(li.sgst_amount)), igst_amount=Decimal(str(li.igst_amount)),
                cess_amount=Decimal(str(li.cess_amount)), line_total=Decimal(str(li.line_total)),
                item_reference=li.item_reference,
            )
            for li in line_items
        ],
    )

    render_ctx = InvoiceRenderContext(
        seller_legal_name=settings.company_legal_name,
        seller_registered_address=settings.company_registered_address,
        seller_gstin=settings.seller_gstin,
        support_email=settings.support_email,
        support_phone=settings.support_phone,
        logo_url=settings.company_logo_url,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        payment_reference=generated_invoice.payment_reference,
        external_reference=generated_invoice.external_reference,
        recipient_name=generated_invoice.recipient_name,
        recipient_gstin=generated_invoice.recipient_gstin,
        billing_address_lines=_address_lines(billing),
        shipping_address_lines=shipping_lines,
        currency=generated_invoice.currency,
        tax_calc=tax_calc_for_render,
        template_version=settings.invoice_template_version,
        reverse_charge_applicable=settings.reverse_charge_applicable,
    )

    try:
        pdf_bytes = render_invoice_pdf(render_ctx, settings)
    except Exception as exc:
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
    sanitized_filename = f"{invoice_number.replace('/', '_')}.pdf"
    storage_key = f"invoice-documents/{generated_invoice.id}/{sanitized_filename}"
    try:
        storage = get_storage_adapter(settings)
        storage.save(storage_key, pdf_bytes, content_type="application/pdf")
    except Exception as exc:
        generated_invoice.status = "STORAGE_FAILED"
        db.add(generated_invoice)
        db.commit()
        record_event(
            db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
            event_name="STORAGE_FAILED", actor_type="SYSTEM", new_state="STORAGE_FAILED",
            safe_payload={"error": str(exc)[:200]},
        )
        raise

    invoice_document = InvoiceDocument(
        original_filename=sanitized_filename, sanitized_filename=sanitized_filename,
        mime_type="application/pdf", byte_size=len(pdf_bytes), sha256=pdf_sha256,
        storage_key=storage_key, uploaded_by_user_id=approved_by_user_id,
        external_reference=generated_invoice.external_reference, invoice_number=invoice_number, source="API",
    )
    db.add(invoice_document)
    db.commit()

    generated_invoice.invoice_document_id = invoice_document.id
    generated_invoice.seller_legal_name = settings.company_legal_name
    generated_invoice.seller_registered_address = settings.company_registered_address
    generated_invoice.seller_gstin = settings.seller_gstin
    generated_invoice.seller_state_name = settings.seller_state_name
    generated_invoice.seller_state_code = settings.seller_state_code
    generated_invoice.template_version = settings.invoice_template_version
    generated_invoice.pdf_sha256 = pdf_sha256
    generated_invoice.status = "INVOICE_DOCUMENT_CREATED"
    generated_invoice.generated_at = datetime.now(UTC)
    generated_invoice.approved_by_user_id = approved_by_user_id
    generated_invoice.approved_at = datetime.now(UTC)
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="INVOICE_DOCUMENT_CREATED", actor_type="USER", actor_id=approved_by_user_id,
        new_state="INVOICE_DOCUMENT_CREATED", safe_payload={"invoice_document_id": invoice_document.id},
    )

    delivery_fields = InvoiceDeliveryRequestFields(
        recipient_name=generated_invoice.recipient_name,
        recipient_email=generated_invoice.recipient_email,
        recipient_phone=generated_invoice.recipient_phone,
        requested_channels=generated_invoice.requested_channels_json,
        idempotency_key=f"{generated_invoice.idempotency_key}:delivery",
        external_reference=generated_invoice.external_reference,
        invoice_number=invoice_number,
        source="API",
        notes=generated_invoice.notes,
        attach_pdf_to_email=generated_invoice.attach_pdf_to_email,
        include_download_link=generated_invoice.include_download_link,
        send_whatsapp_notification=generated_invoice.send_whatsapp_notification,
    )
    delivery = create_delivery(db, document=invoice_document, fields=delivery_fields, correlation_id=correlation_id)
    delivery.created_by_user_id = approved_by_user_id
    db.add(delivery)
    db.commit()

    approve_delivery(db, delivery, approved_by_user_id=approved_by_user_id)

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
