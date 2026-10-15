"""Renders the locked, versioned HTML invoice template to PDF bytes.
Never LLM-generated — the layout and every value come from
`GeneratedInvoice`/the GST calculator (spec §9: "Do not have AI generate
the invoice layout or its values").

Only `PDF_RENDERER=weasyprint` is implemented. `playwright` is accepted
as a config value but not yet built — see app/core/config.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import Settings
from app.services.invoicing.amount_in_words import amount_in_words
from app.services.invoicing.calculator import GSTCalculationResult

TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


@dataclass
class InvoiceRenderContext:
    seller_legal_name: str
    seller_registered_address: str
    seller_gstin: str
    support_email: str | None
    support_phone: str | None
    logo_url: str | None

    invoice_number: str
    invoice_date: date
    payment_reference: str
    external_reference: str | None

    recipient_name: str
    recipient_gstin: str | None
    billing_address_lines: list[str]
    shipping_address_lines: list[str] | None

    currency: str
    tax_calc: GSTCalculationResult
    template_version: str
    reverse_charge_applicable: bool = False
    # Shown as a diagonal overlay when set (rendered for every draft
    # version until approval); None on the final, approved PDF.
    watermark_text: str | None = None


def render_invoice_html(ctx: InvoiceRenderContext) -> str:
    template = _env.get_template("generated_invoice.html")
    tax = ctx.tax_calc
    return template.render(
        seller_legal_name=ctx.seller_legal_name,
        seller_registered_address=ctx.seller_registered_address,
        seller_gstin=ctx.seller_gstin,
        support_email=ctx.support_email,
        support_phone=ctx.support_phone,
        logo_url=ctx.logo_url,
        invoice_number=ctx.invoice_number,
        invoice_date=ctx.invoice_date.isoformat(),
        payment_reference=ctx.payment_reference,
        external_reference=ctx.external_reference,
        recipient_name=ctx.recipient_name,
        recipient_gstin=ctx.recipient_gstin,
        billing_address_lines=ctx.billing_address_lines,
        shipping_address_lines=ctx.shipping_address_lines,
        place_of_supply=tax.place_of_supply_state,
        is_inter_state=tax.is_inter_state,
        currency=ctx.currency,
        line_items=tax.line_items,
        subtotal=tax.subtotal,
        discount_total=tax.discount_total,
        taxable_total=tax.taxable_total,
        cgst_total=tax.cgst_total,
        sgst_total=tax.sgst_total,
        igst_total=tax.igst_total,
        cess_total=tax.cess_total,
        grand_total=tax.grand_total,
        amount_in_words=amount_in_words(Decimal(tax.grand_total)),
        reverse_charge_applicable=ctx.reverse_charge_applicable,
        template_version=ctx.template_version,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        watermark_text=ctx.watermark_text,
    )


def render_invoice_pdf(ctx: InvoiceRenderContext, settings: Settings) -> bytes:
    if settings.pdf_renderer != "weasyprint":
        raise NotImplementedError(
            f"PDF_RENDERER={settings.pdf_renderer!r} is not implemented yet — "
            "only 'weasyprint' is built. See app/services/invoicing/pdf_renderer.py."
        )

    from weasyprint import HTML

    html = render_invoice_html(ctx)
    return HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf()
