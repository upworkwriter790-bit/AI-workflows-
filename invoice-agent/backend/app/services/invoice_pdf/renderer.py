"""Renders the locked, versioned HTML invoice template to PDF bytes via
WeasyPrint. The template is never LLM-generated — see spec §4/§11: "The
invoice must never be generated twice for the same order" and "use a
locked, versioned template, not an AI-generated layout."

TEMPLATE_VERSION travels with every Invoice row (`template_version`
column) so a future template change never silently reinterprets an old
invoice's rendering.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.services.gst.calculator import GSTCalculationResult
from app.services.invoice_pdf.amount_in_words import amount_in_words

TEMPLATE_VERSION = "1.0.0"
TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


@dataclass
class InvoiceRenderContext:
    company_legal_name: str
    company_registered_address: str
    seller_gstin: str
    support_email: str | None
    support_phone: str | None
    logo_path: str | None

    invoice_number: str
    invoice_date: date
    order_id: str | None
    payment_reference: str | None
    internal_invoice_id: str

    customer_name: str
    customer_gstin: str | None
    billing_address_lines: list[str]
    shipping_address_lines: list[str] | None
    customer_state_code: str

    currency: str
    tax_calc: GSTCalculationResult
    reverse_charge_applicable: bool = False


def render_invoice_html(ctx: InvoiceRenderContext) -> str:
    template = _env.get_template("invoice.html")
    tax = ctx.tax_calc
    return template.render(
        company_legal_name=ctx.company_legal_name,
        company_registered_address=ctx.company_registered_address,
        seller_gstin=ctx.seller_gstin,
        support_email=ctx.support_email,
        support_phone=ctx.support_phone,
        logo_path=ctx.logo_path,
        invoice_number=ctx.invoice_number,
        invoice_date=ctx.invoice_date.isoformat(),
        order_id=ctx.order_id,
        payment_reference=ctx.payment_reference,
        internal_invoice_id=ctx.internal_invoice_id,
        customer_name=ctx.customer_name,
        customer_gstin=ctx.customer_gstin,
        billing_address_lines=ctx.billing_address_lines,
        shipping_address_lines=ctx.shipping_address_lines,
        customer_state_code=ctx.customer_state_code,
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
        template_version=TEMPLATE_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def render_invoice_pdf(ctx: InvoiceRenderContext) -> bytes:
    from weasyprint import HTML

    html = render_invoice_html(ctx)
    return HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf()
