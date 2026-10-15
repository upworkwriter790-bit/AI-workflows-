"""Method B workflow: payment/order details in, a versioned, human-
reviewed DRAFT out. Nothing is numbered-and-shown-as-final, rendered as
a final PDF, or queued for delivery until an authorized INVOICE_APPROVER
or ADMIN explicitly approves it (never the AI, never automatically).

State machine (trimmed from the full reference spec — this app folds a
few of its micro-states into fewer persisted ones, with the
InvoiceDraftVersion/AuditEvent trail carrying the detail instead of a
longer status enum):

    REQUEST_RECEIVED -> REQUEST_VALIDATED -> AMOUNTS_CALCULATED
      -> PENDING_HUMAN_REVIEW
      -> (manual edit | AI proposal applied) -> PENDING_HUMAN_REVIEW  [loops]
      -> REJECTED | CANCELLED                                        [terminal, no delivery]
      -> DELIVERY_QUEUED (on approval; InvoiceDelivery owns delivery-outcome
         truth from there, same as Method A)

Failure states: INVALID_REQUEST, CALCULATION_FAILED, TOTAL_MISMATCH,
INVOICE_NUMBER_RESERVATION_FAILED, PDF_RENDER_FAILED, STORAGE_FAILED.

Idempotency: `GeneratedInvoice.idempotency_key` is DB-unique; a repeat
call with the same key always returns the ORIGINAL outcome (whatever
state it is currently in), never generates a second draft.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.generated_invoice import GeneratedInvoice
from app.models.generated_invoice_line_item import GeneratedInvoiceLineItem
from app.models.invoice_document import InvoiceDocument
from app.models.invoice_draft_version import InvoiceDraftVersion
from app.models.invoice_edit_proposal import InvoiceEditProposal
from app.models.product_catalog_item import ProductCatalogItem
from app.schemas.ai_edit_proposal import AIEditProposalOutput
from app.schemas.delivery_request import InvoiceDeliveryRequestFields
from app.schemas.generated_invoice_request import GeneratedInvoiceDeliveryRequest
from app.services.ai.factory import get_ai_provider
from app.services.audit.service import record_event
from app.services.invoicing.amount_in_words import amount_in_words
from app.services.invoicing.calculator import (
    GSTCalculationResult,
    LineItemInput,
    amounts_match_within_tolerance,
    calculate_invoice_tax,
)
from app.services.invoicing.numbering import reserve_invoice_number
from app.services.invoicing.pdf_renderer import InvoiceRenderContext, render_invoice_pdf
from app.services.storage.factory import get_storage_adapter
from app.workflows.delivery_workflow import approve_delivery, create_delivery

PENDING_REVIEW = "PENDING_HUMAN_REVIEW"
TERMINAL_STATUSES = {"REJECTED", "CANCELLED"}


class GeneratedInvoiceValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class TotalMismatchError(Exception):
    def __init__(self, mismatches: list[str]) -> None:
        self.mismatches = mismatches
        super().__init__("; ".join(mismatches))


class InvalidInvoiceStateError(Exception):
    """Raised whenever an action requires the invoice to be in
    PENDING_HUMAN_REVIEW (edit, AI-proposal apply, approve, reject,
    cancel) and it isn't — including, deliberately, after it has been
    approved: there is no path in this module that mutates a locked
    invoice. A correction is always a new draft (rule §2.11).
    """

    def __init__(self, invoice_id: str, current_status: str) -> None:
        self.invoice_id = invoice_id
        self.current_status = current_status
        super().__init__(f"generated invoice {invoice_id} is not editable (status: {current_status})")


class AIEditUnavailableError(Exception):
    def __init__(self) -> None:
        super().__init__("AI edit assistant is disabled or not configured (no AI_API_KEY)")


class StaleProposalError(Exception):
    def __init__(self, proposal_id: str) -> None:
        self.proposal_id = proposal_id
        super().__init__(
            f"proposal {proposal_id} was generated against an earlier draft version "
            "— re-fetch the current draft and request a new proposal"
        )


class ProposalNotApplicableError(Exception):
    def __init__(self, proposal_id: str, status: str) -> None:
        super().__init__(f"proposal {proposal_id} is {status}, not GENERATED")


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


def _calculate(settings: Settings, request: GeneratedInvoiceDeliveryRequest) -> GSTCalculationResult:
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


def _check_totals(
    settings: Settings, request: GeneratedInvoiceDeliveryRequest, tax_result: GSTCalculationResult
) -> list[str]:
    tolerance = _dec(settings.tax_tolerance_amount)
    stated = request.payment_or_order_details
    mismatches = []
    if not amounts_match_within_tolerance(tax_result.subtotal, stated.subtotal, tolerance):
        mismatches.append(f"subtotal: computed {tax_result.subtotal} vs submitted {stated.subtotal}")
    if not amounts_match_within_tolerance(tax_result.discount_total, stated.discount_total, tolerance):
        mismatches.append(
            f"discount_total: computed {tax_result.discount_total} vs submitted {stated.discount_total}"
        )
    if not amounts_match_within_tolerance(tax_result.tax_total, stated.tax_total, tolerance):
        mismatches.append(f"tax_total: computed {tax_result.tax_total} vs submitted {stated.tax_total}")
    if not amounts_match_within_tolerance(tax_result.grand_total, stated.grand_total, tolerance):
        mismatches.append(f"grand_total: computed {tax_result.grand_total} vs submitted {stated.grand_total}")
    return mismatches


def _apply_request_fields(generated_invoice: GeneratedInvoice, request: GeneratedInvoiceDeliveryRequest) -> None:
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


def _apply_tax_result(generated_invoice: GeneratedInvoice, tax_result: GSTCalculationResult) -> None:
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


def _replace_line_items(db: Session, generated_invoice: GeneratedInvoice, tax_result: GSTCalculationResult) -> None:
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


def _render_draft_pdf(
    settings: Settings, generated_invoice: GeneratedInvoice, tax_result: GSTCalculationResult
) -> tuple[str | None, str | None]:
    """Renders the draft PDF (with the configured DRAFT watermark) and
    stores it. Returns (storage_key, sha256), or (None, None) if the
    seller identity / renderer isn't configured yet, or rendering/
    storage fails — a draft can still exist and be edited without a
    preview in that case, it just has no PDF to show until that's fixed.
    """
    if settings.missing_seller_identity_fields():
        return None, None
    try:
        render_ctx = InvoiceRenderContext(
            seller_legal_name=settings.company_legal_name,
            seller_registered_address=settings.company_registered_address,
            seller_gstin=settings.seller_gstin,
            support_email=settings.support_email,
            support_phone=settings.support_phone,
            logo_url=settings.company_logo_url,
            invoice_number=generated_invoice.invoice_number or "DRAFT",
            invoice_date=generated_invoice.invoice_date or date.today(),
            payment_reference=generated_invoice.payment_reference,
            external_reference=generated_invoice.external_reference,
            recipient_name=generated_invoice.recipient_name,
            recipient_gstin=generated_invoice.recipient_gstin,
            billing_address_lines=_address_lines(generated_invoice.billing_address_json),
            shipping_address_lines=(
                _address_lines(generated_invoice.shipping_address_json)
                if generated_invoice.shipping_address_json
                and not generated_invoice.shipping_address_json.get("same_as_billing")
                and generated_invoice.shipping_address_json.get("line1")
                else None
            ),
            currency=generated_invoice.currency,
            tax_calc=tax_result,
            template_version=settings.invoice_template_version,
            reverse_charge_applicable=settings.reverse_charge_applicable,
            watermark_text=settings.draft_watermark_text,
        )
        pdf_bytes = render_invoice_pdf(render_ctx, settings)
    except Exception:  # noqa: BLE001
        return None, None

    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    storage_key = f"invoice-drafts/{generated_invoice.id}/v{generated_invoice.current_version_number}.pdf"
    try:
        storage = get_storage_adapter(settings)
        storage.save(storage_key, pdf_bytes, content_type="application/pdf")
    except Exception:  # noqa: BLE001
        return None, None
    return storage_key, sha256


def _create_draft_version(
    db: Session,
    generated_invoice: GeneratedInvoice,
    request: GeneratedInvoiceDeliveryRequest,
    tax_result: GSTCalculationResult,
    *,
    created_by_type: str,
    created_by_user_id: str | None,
    creation_reason: str,
    change_summary: str | None,
    draft_pdf_storage_key: str | None,
    draft_pdf_sha256: str | None,
) -> InvoiceDraftVersion:
    version = InvoiceDraftVersion(
        generated_invoice_id=generated_invoice.id,
        version_number=generated_invoice.current_version_number,
        parent_version_number=(
            generated_invoice.current_version_number - 1 if generated_invoice.current_version_number > 1 else None
        ),
        created_by_type=created_by_type,
        created_by_user_id=created_by_user_id,
        creation_reason=creation_reason,
        invoice_data_snapshot_json=request.model_dump(mode="json"),
        line_items_snapshot_json=[
            {
                "description": li.description, "hsn_or_sac_code": li.hsn_or_sac_code,
                "quantity": str(li.quantity), "unit_price": str(li.unit_price), "gst_rate": str(li.gst_rate),
            }
            for li in tax_result.line_items
        ],
        calculation_snapshot_json=tax_result.snapshot(),
        template_version="v1",
        draft_pdf_storage_key=draft_pdf_storage_key,
        draft_pdf_sha256=draft_pdf_sha256,
        change_summary=change_summary,
        is_current=True,
    )
    db.query(InvoiceDraftVersion).filter_by(generated_invoice_id=generated_invoice.id, is_current=True).update(
        {"is_current": False}
    )
    db.add(version)
    db.commit()
    return version


def create_draft_generated_invoice(
    db: Session, settings: Settings, request: GeneratedInvoiceDeliveryRequest, created_by_user_id: str
) -> GeneratedInvoiceOutcome:
    existing = db.query(GeneratedInvoice).filter_by(idempotency_key=request.idempotency_key).one_or_none()
    if existing is not None:
        document = (
            db.query(InvoiceDocument).filter_by(id=existing.final_document_id).one_or_none()
            if existing.final_document_id
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
        current_version_number=1,
        invoice_number_assignment_stage=settings.invoice_number_assignment_stage,
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
                (
                    f"external_reference {request.external_reference!r} + payment_reference "
                    f"{request.payment_or_order_details.payment_reference!r} already has an active "
                    "generated invoice — use the original idempotency_key to retrieve it, or submit a "
                    "documented correction/credit-note instead"
                )
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

    _apply_tax_result(generated_invoice, tax_result)

    if generated_invoice.invoice_number_assignment_stage == "DRAFT":
        try:
            generated_invoice.invoice_number = reserve_invoice_number(db, settings, date.today())
            generated_invoice.invoice_date = date.today()
        except Exception as exc:
            generated_invoice.status = "INVOICE_NUMBER_RESERVATION_FAILED"
            db.add(generated_invoice)
            db.commit()
            record_event(
                db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
                event_name="INVOICE_NUMBER_RESERVATION_FAILED", actor_type="SYSTEM",
                new_state="INVOICE_NUMBER_RESERVATION_FAILED", safe_payload={"error": str(exc)[:200]},
            )
            raise

    generated_invoice.status = PENDING_REVIEW
    db.add(generated_invoice)
    db.commit()
    _replace_line_items(db, generated_invoice, tax_result)
    db.commit()

    storage_key, sha256 = _render_draft_pdf(settings, generated_invoice, tax_result)
    _create_draft_version(
        db, generated_invoice, request, tax_result,
        created_by_type="SYSTEM", created_by_user_id=created_by_user_id, creation_reason="INITIAL_GENERATION",
        change_summary="Initial draft generated from payment/order details.",
        draft_pdf_storage_key=storage_key, draft_pdf_sha256=sha256,
    )

    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="PENDING_HUMAN_REVIEW", actor_type="SYSTEM", new_state=PENDING_REVIEW,
        safe_payload={"grand_total": str(tax_result.grand_total), "version": 1},
    )

    return GeneratedInvoiceOutcome(generated_invoice=generated_invoice, invoice_document=None, delivery_id=None)


def edit_draft_generated_invoice(
    db: Session,
    settings: Settings,
    generated_invoice: GeneratedInvoice,
    request: GeneratedInvoiceDeliveryRequest,
    edited_by_user_id: str,
) -> GeneratedInvoice:
    """A human's full-replace manual edit (spec §5.C / §9). Raises
    InvalidInvoiceStateError if the invoice isn't PENDING_HUMAN_REVIEW,
    GeneratedInvoiceValidationError / TotalMismatchError on the same
    conditions create_draft_generated_invoice checks.
    """
    if generated_invoice.status != PENDING_REVIEW:
        raise InvalidInvoiceStateError(generated_invoice.id, generated_invoice.status)

    validation_errors = _validate_request(db, settings, request)
    if validation_errors:
        raise GeneratedInvoiceValidationError(validation_errors)

    tax_result = _calculate(settings, request)
    mismatches = _check_totals(settings, request, tax_result)
    if mismatches:
        raise TotalMismatchError(mismatches)

    before_total = generated_invoice.grand_total
    _apply_request_fields(generated_invoice, request)
    _apply_tax_result(generated_invoice, tax_result)
    generated_invoice.current_version_number += 1
    db.add(generated_invoice)
    db.commit()
    _replace_line_items(db, generated_invoice, tax_result)
    db.commit()

    storage_key, sha256 = _render_draft_pdf(settings, generated_invoice, tax_result)
    _create_draft_version(
        db, generated_invoice, request, tax_result,
        created_by_type="USER", created_by_user_id=edited_by_user_id, creation_reason="MANUAL_EDIT",
        change_summary=f"Manual edit: grand total {before_total} -> {tax_result.grand_total}.",
        draft_pdf_storage_key=storage_key, draft_pdf_sha256=sha256,
    )
    record_event(
        db, correlation_id=generated_invoice.correlation_id, entity_type="GeneratedInvoice",
        entity_id=generated_invoice.id, event_name="DRAFT_EDITED", actor_type="USER",
        actor_id=edited_by_user_id,
        safe_payload={"before_grand_total": str(before_total), "after_grand_total": str(tax_result.grand_total)},
    )
    return generated_invoice


# ---------------------------------------------------------------------------
# AI edit proposals — generate / apply / reject. The AI never writes to the
# database directly: generate_ai_edit_proposal only ever inserts a PENDING/
# GENERATED/INVALID proposal row; apply_ai_edit_proposal is a separate call
# that a human (INVOICE_EDITOR/ADMIN) must explicitly make.
# ---------------------------------------------------------------------------

_PATH_SEGMENT = re.compile(r"([^\[\].]+)(\[(\d+)\])?")


def _apply_json_path(data: dict, path: str, value) -> bool:
    """Applies `value` at a dotted/bracketed path like
    "recipient.billing_address.city" or "items[0].quantity" onto `data`
    in place. Returns False (no-op) if the path doesn't resolve —
    callers must have already validated the path against the allowed
    set before calling this.
    """
    segments = [
        (m.group(1), int(m.group(3)) if m.group(3) is not None else None) for m in _PATH_SEGMENT.finditer(path)
    ]
    node = data
    for key, index in segments[:-1]:
        if key not in node:
            return False
        node = node[key]
        if index is not None:
            if not isinstance(node, list) or index >= len(node):
                return False
            node = node[index]
    last_key, last_index = segments[-1]
    if last_index is not None:
        if last_key not in node or not isinstance(node[last_key], list) or last_index >= len(node[last_key]):
            return False
        node[last_key][last_index] = value
    else:
        node[last_key] = value
    return True


def _current_version(db: Session, generated_invoice_id: str) -> InvoiceDraftVersion:
    return (
        db.query(InvoiceDraftVersion)
        .filter_by(generated_invoice_id=generated_invoice_id, is_current=True)
        .one()
    )


def _open_prompt_file(name: str):
    from pathlib import Path

    prompts_dir = Path(__file__).resolve().parents[1] / "prompts"
    return open(prompts_dir / name, encoding="utf-8")


def generate_ai_edit_proposal(
    db: Session,
    settings: Settings,
    generated_invoice: GeneratedInvoice,
    instruction: str,
    requested_by_user_id: str,
) -> InvoiceEditProposal:
    if generated_invoice.status != PENDING_REVIEW:
        raise InvalidInvoiceStateError(generated_invoice.id, generated_invoice.status)

    provider = get_ai_provider(settings)
    if provider is None:
        raise AIEditUnavailableError()

    from app.schemas.ai_edit_proposal import ALLOWED_EDITABLE_PATHS

    current = _current_version(db, generated_invoice.id)
    with _open_prompt_file("invoice_draft_edit_system.txt") as f:
        system_prompt = f.read()

    context = {
        "instruction": instruction,
        "base_draft_version_number": generated_invoice.current_version_number,
        "current_draft": current.invoice_data_snapshot_json,
        "allowed_editable_paths": sorted(ALLOWED_EDITABLE_PATHS),
    }
    raw = provider.generate_edit_proposal(system_prompt=system_prompt, context=context)

    proposal = InvoiceEditProposal(
        generated_invoice_id=generated_invoice.id,
        base_draft_version_number=generated_invoice.current_version_number,
        requested_by_user_id=requested_by_user_id,
        natural_language_instruction=instruction,
        ai_model=settings.ai_model,
        prompt_version=settings.ai_edit_prompt_version,
    )
    try:
        parsed = AIEditProposalOutput.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        proposal.status = "FAILED"
        proposal.validation_result_json = {"error": str(exc)[:500]}
        db.add(proposal)
        db.commit()
        record_event(
            db, correlation_id=generated_invoice.correlation_id, entity_type="InvoiceEditProposal",
            entity_id=proposal.id, event_name="AI_EDIT_PROPOSAL_FAILED", actor_type="SYSTEM",
            actor_id=requested_by_user_id, safe_payload={"error": str(exc)[:200]},
        )
        return proposal

    problems = parsed.validate_against_allowed_paths()
    proposal.structured_change_proposal_json = parsed.model_dump(mode="json")
    proposal.proposed_change_summary = parsed.reviewer_summary
    if problems:
        proposal.status = "INVALID"
        proposal.validation_result_json = {"problems": problems}
    else:
        proposal.status = "GENERATED"
        proposal.validation_result_json = {"problems": []}
    db.add(proposal)
    db.commit()
    record_event(
        db, correlation_id=generated_invoice.correlation_id, entity_type="InvoiceEditProposal",
        entity_id=proposal.id, event_name="AI_EDIT_PROPOSAL_GENERATED", actor_type="USER",
        actor_id=requested_by_user_id,
        safe_payload={"instruction": instruction[:200], "status": proposal.status},
    )
    return proposal


def reject_ai_edit_proposal(
    db: Session,
    generated_invoice: GeneratedInvoice,
    proposal: InvoiceEditProposal,
    *,
    rejected_by_user_id: str,
    reason: str | None,
) -> InvoiceEditProposal:
    proposal.status = "REJECTED_BY_USER"
    proposal.rejected_by_user_id = rejected_by_user_id
    proposal.rejected_at = datetime.now(UTC)
    proposal.rejection_reason = reason
    db.add(proposal)
    db.commit()
    record_event(
        db, correlation_id=generated_invoice.correlation_id, entity_type="InvoiceEditProposal",
        entity_id=proposal.id, event_name="AI_EDIT_PROPOSAL_REJECTED", actor_type="USER",
        actor_id=rejected_by_user_id, safe_payload={"reason": reason},
    )
    return proposal


def apply_ai_edit_proposal(
    db: Session,
    settings: Settings,
    generated_invoice: GeneratedInvoice,
    proposal: InvoiceEditProposal,
    *,
    applied_by_user_id: str,
) -> GeneratedInvoice:
    if generated_invoice.status != PENDING_REVIEW:
        raise InvalidInvoiceStateError(generated_invoice.id, generated_invoice.status)
    if proposal.status != "GENERATED":
        raise ProposalNotApplicableError(proposal.id, proposal.status)
    if proposal.base_draft_version_number != generated_invoice.current_version_number:
        proposal.status = "FAILED"
        db.add(proposal)
        db.commit()
        raise StaleProposalError(proposal.id)

    current = _current_version(db, generated_invoice.id)
    working_data = dict(current.invoice_data_snapshot_json)
    parsed = AIEditProposalOutput.model_validate(proposal.structured_change_proposal_json)
    for change in parsed.proposed_changes:
        _apply_json_path(working_data, change.path, change.proposed_value)

    request = GeneratedInvoiceDeliveryRequest.model_validate(working_data)

    validation_errors = _validate_request(db, settings, request)
    if validation_errors:
        raise GeneratedInvoiceValidationError(validation_errors)
    tax_result = _calculate(settings, request)
    # An AI-applied edit has no independently-claimed payment total to
    # cross-check against — the freshly recalculated figures become the
    # new truth, same as a manual edit's recalculation.

    _apply_request_fields(generated_invoice, request)
    _apply_tax_result(generated_invoice, tax_result)
    generated_invoice.current_version_number += 1
    db.add(generated_invoice)
    db.commit()
    _replace_line_items(db, generated_invoice, tax_result)
    db.commit()

    storage_key, sha256 = _render_draft_pdf(settings, generated_invoice, tax_result)
    _create_draft_version(
        db, generated_invoice, request, tax_result,
        created_by_type="AI_PROPOSAL_APPLIED", created_by_user_id=applied_by_user_id,
        creation_reason="AI_PROPOSAL_APPLIED", change_summary=parsed.reviewer_summary,
        draft_pdf_storage_key=storage_key, draft_pdf_sha256=sha256,
    )

    proposal.status = "APPLIED"
    proposal.applied_by_user_id = applied_by_user_id
    proposal.applied_at = datetime.now(UTC)
    db.add(proposal)
    db.commit()
    record_event(
        db, correlation_id=generated_invoice.correlation_id, entity_type="InvoiceEditProposal",
        entity_id=proposal.id, event_name="AI_EDIT_PROPOSAL_APPLIED", actor_type="USER",
        actor_id=applied_by_user_id, safe_payload={"grand_total": str(tax_result.grand_total)},
    )
    return generated_invoice


# ---------------------------------------------------------------------------
# Approve / reject / cancel
# ---------------------------------------------------------------------------


def reject_generated_invoice(
    db: Session, generated_invoice: GeneratedInvoice, *, rejected_by_user_id: str, reason: str
) -> GeneratedInvoice:
    if generated_invoice.status != PENDING_REVIEW:
        raise InvalidInvoiceStateError(generated_invoice.id, generated_invoice.status)
    generated_invoice.status = "REJECTED"
    generated_invoice.rejected_by_user_id = rejected_by_user_id
    generated_invoice.rejected_at = datetime.now(UTC)
    generated_invoice.rejection_reason = reason
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=generated_invoice.correlation_id, entity_type="GeneratedInvoice",
        entity_id=generated_invoice.id, event_name="REJECTED", actor_type="USER",
        actor_id=rejected_by_user_id, previous_state=PENDING_REVIEW, new_state="REJECTED",
        safe_payload={"reason": reason},
    )
    return generated_invoice


def cancel_generated_invoice(
    db: Session, generated_invoice: GeneratedInvoice, *, cancelled_by_user_id: str, reason: str | None
) -> GeneratedInvoice:
    if generated_invoice.status != PENDING_REVIEW:
        raise InvalidInvoiceStateError(generated_invoice.id, generated_invoice.status)
    generated_invoice.status = "CANCELLED"
    generated_invoice.rejected_by_user_id = cancelled_by_user_id
    generated_invoice.rejected_at = datetime.now(UTC)
    generated_invoice.rejection_reason = reason
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=generated_invoice.correlation_id, entity_type="GeneratedInvoice",
        entity_id=generated_invoice.id, event_name="CANCELLED", actor_type="USER",
        actor_id=cancelled_by_user_id, previous_state=PENDING_REVIEW, new_state="CANCELLED",
        safe_payload={"reason": reason},
    )
    return generated_invoice


def approve_and_finalize(
    db: Session, settings: Settings, generated_invoice: GeneratedInvoice, approved_by_user_id: str
) -> GeneratedInvoiceOutcome:
    """The ONLY path that can ever queue delivery for a generated
    invoice. Never callable by AI output — this always takes an
    authenticated human `approved_by_user_id`, enforced one layer up by
    require_role("ADMIN", "INVOICE_APPROVER") at the API boundary.
    Re-validates the latest draft, locks it, renders the final
    (unwatermarked) PDF, and queues delivery — all in one action.
    """
    if generated_invoice.status != PENDING_REVIEW:
        raise InvalidInvoiceStateError(generated_invoice.id, generated_invoice.status)

    current = _current_version(db, generated_invoice.id)
    request = GeneratedInvoiceDeliveryRequest.model_validate(current.invoice_data_snapshot_json)
    validation_errors = _validate_request(db, settings, request)
    if validation_errors:
        raise GeneratedInvoiceValidationError(validation_errors)
    tax_result = _calculate(settings, request)

    correlation_id = generated_invoice.correlation_id
    invoice_date = generated_invoice.invoice_date or date.today()

    if generated_invoice.invoice_number is None:
        try:
            generated_invoice.invoice_number = reserve_invoice_number(db, settings, invoice_date)
            generated_invoice.invoice_date = invoice_date
            db.add(generated_invoice)
            db.commit()
        except Exception as exc:
            generated_invoice.status = "INVOICE_NUMBER_RESERVATION_FAILED"
            db.add(generated_invoice)
            db.commit()
            record_event(
                db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
                event_name="INVOICE_NUMBER_RESERVATION_FAILED", actor_type="SYSTEM",
                new_state="INVOICE_NUMBER_RESERVATION_FAILED", safe_payload={"error": str(exc)[:200]},
            )
            raise

    billing = generated_invoice.billing_address_json
    shipping = generated_invoice.shipping_address_json
    shipping_lines = None
    if shipping and not shipping.get("same_as_billing") and shipping.get("line1"):
        shipping_lines = _address_lines(shipping)

    render_ctx = InvoiceRenderContext(
        seller_legal_name=settings.company_legal_name,
        seller_registered_address=settings.company_registered_address,
        seller_gstin=settings.seller_gstin,
        support_email=settings.support_email,
        support_phone=settings.support_phone,
        logo_url=settings.company_logo_url,
        invoice_number=generated_invoice.invoice_number,
        invoice_date=invoice_date,
        payment_reference=generated_invoice.payment_reference,
        external_reference=generated_invoice.external_reference,
        recipient_name=generated_invoice.recipient_name,
        recipient_gstin=generated_invoice.recipient_gstin,
        billing_address_lines=_address_lines(billing),
        shipping_address_lines=shipping_lines,
        currency=generated_invoice.currency,
        tax_calc=tax_result,
        template_version=settings.invoice_template_version,
        reverse_charge_applicable=settings.reverse_charge_applicable,
        watermark_text=None,  # final PDF never carries the draft watermark
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
    sanitized_filename = f"{generated_invoice.invoice_number.replace('/', '_')}.pdf"
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
        external_reference=generated_invoice.external_reference, invoice_number=generated_invoice.invoice_number,
        source="API",
    )
    db.add(invoice_document)
    db.commit()

    now = datetime.now(UTC)
    generated_invoice.seller_legal_name = settings.company_legal_name
    generated_invoice.seller_registered_address = settings.company_registered_address
    generated_invoice.seller_gstin = settings.seller_gstin
    generated_invoice.seller_state_name = settings.seller_state_name
    generated_invoice.seller_state_code = settings.seller_state_code
    generated_invoice.template_version = settings.invoice_template_version
    generated_invoice.final_document_id = invoice_document.id
    generated_invoice.final_pdf_sha256 = pdf_sha256
    generated_invoice.finalization_timestamp = now
    generated_invoice.approved_by_user_id = approved_by_user_id
    generated_invoice.approved_at = now
    generated_invoice.approved_version_number = generated_invoice.current_version_number
    generated_invoice.locked_at = now
    generated_invoice.generated_at = now
    generated_invoice.status = "DELIVERY_QUEUED"
    db.add(generated_invoice)
    db.commit()
    record_event(
        db, correlation_id=correlation_id, entity_type="GeneratedInvoice", entity_id=generated_invoice.id,
        event_name="APPROVED_FOR_DELIVERY", actor_type="USER", actor_id=approved_by_user_id,
        previous_state=PENDING_REVIEW, new_state="DELIVERY_QUEUED",
        safe_payload={
            "invoice_document_id": invoice_document.id,
            "approved_version": generated_invoice.current_version_number,
        },
    )

    delivery_fields = InvoiceDeliveryRequestFields(
        recipient_name=generated_invoice.recipient_name,
        recipient_email=generated_invoice.recipient_email,
        recipient_phone=generated_invoice.recipient_phone,
        requested_channels=generated_invoice.requested_channels_json,
        idempotency_key=f"{generated_invoice.idempotency_key}:delivery",
        external_reference=generated_invoice.external_reference,
        invoice_number=generated_invoice.invoice_number,
        source="API",
        notes=generated_invoice.notes,
        attach_pdf_to_email=generated_invoice.attach_pdf_to_email,
        include_download_link=generated_invoice.include_download_link,
        send_whatsapp_notification=generated_invoice.send_whatsapp_notification,
    )
    delivery = create_delivery(
        db, document=invoice_document, fields=delivery_fields, correlation_id=correlation_id,
        require_human_approval=True,
    )
    delivery.created_by_user_id = approved_by_user_id
    db.add(delivery)
    db.commit()

    approve_delivery(db, delivery, approved_by_user_id=approved_by_user_id)

    return GeneratedInvoiceOutcome(
        generated_invoice=generated_invoice, invoice_document=invoice_document, delivery_id=delivery.id
    )
