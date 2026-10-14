"""Method B addition: payment-details-to-invoice generation. Purely
additive — no existing table is altered or dropped.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-14
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_catalog_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("internal_reference", sa.String(64), nullable=False, unique=True),
        sa.Column("display_description", sa.String(500), nullable=False),
        sa.Column("product_type", sa.String(16), nullable=False),
        sa.Column("hsn_or_sac_code", sa.String(16), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("gst_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("tax_category", sa.String(128)),
        sa.Column("active", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_product_catalog_items_internal_reference", "product_catalog_items", ["internal_reference"]
    )

    op.create_table(
        "invoice_number_sequences",
        sa.Column("financial_year", sa.String(16), primary_key=True),
        sa.Column("last_sequence", sa.Integer, server_default="0"),
    )

    op.create_table(
        "tax_config_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version", sa.Integer, nullable=False, unique=True),
        sa.Column("config_json", sa.JSON, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("created_by_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tax_config_versions_version", "tax_config_versions", ["version"])

    op.create_table(
        "generated_invoices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("invoice_document_id", sa.String(36), sa.ForeignKey("invoice_documents.id"), unique=True),
        sa.Column("external_reference", sa.String(128), nullable=False),
        sa.Column("payment_reference", sa.String(128), nullable=False),
        sa.Column("payment_date", sa.Date, nullable=False),
        sa.Column("payment_status", sa.String(32), nullable=False),
        sa.Column("invoice_number", sa.String(64), unique=True),
        sa.Column("invoice_date", sa.Date),
        sa.Column("currency", sa.String(8), server_default="INR"),
        sa.Column("tax_inclusive", sa.Boolean, nullable=False),
        sa.Column("seller_legal_name", sa.String(255), nullable=False),
        sa.Column("seller_registered_address", sa.String(1000), nullable=False),
        sa.Column("seller_gstin", sa.String(15), nullable=False),
        sa.Column("seller_state_name", sa.String(64), nullable=False),
        sa.Column("seller_state_code", sa.String(4), nullable=False),
        sa.Column("recipient_name", sa.String(255), nullable=False),
        sa.Column("recipient_email", sa.String(255)),
        sa.Column("recipient_phone", sa.String(20)),
        sa.Column("recipient_gstin", sa.String(15)),
        sa.Column("billing_address_json", sa.JSON, nullable=False),
        sa.Column("shipping_address_json", sa.JSON),
        sa.Column("place_of_supply", sa.String(64), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("taxable_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("cgst_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("sgst_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("igst_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("cess_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("tax_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("grand_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_in_words", sa.String(500), nullable=False),
        sa.Column("template_version", sa.String(16)),
        sa.Column("calculation_snapshot_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("pdf_sha256", sa.String(64)),
        sa.Column("status", sa.String(48), server_default="REQUEST_RECEIVED"),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.String(36)),
        sa.Column("generated_at", sa.DateTime(timezone=True)),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("external_reference", "payment_reference", name="uq_generated_invoice_refs"),
    )
    op.create_index("ix_generated_invoices_external_reference", "generated_invoices", ["external_reference"])
    op.create_index("ix_generated_invoices_payment_reference", "generated_invoices", ["payment_reference"])
    op.create_index("ix_generated_invoices_invoice_number", "generated_invoices", ["invoice_number"])
    op.create_index("ix_generated_invoices_idempotency_key", "generated_invoices", ["idempotency_key"])
    op.create_index("ix_generated_invoices_correlation_id", "generated_invoices", ["correlation_id"])

    op.create_table(
        "generated_invoice_line_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("generated_invoice_id", sa.String(36), sa.ForeignKey("generated_invoices.id"), nullable=False),
        sa.Column("line_number", sa.Integer, nullable=False),
        sa.Column("item_reference", sa.String(64)),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("product_type", sa.String(16), nullable=False),
        sa.Column("hsn_or_sac_code", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("taxable_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("gst_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("cgst_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("sgst_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("igst_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("cess_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index(
        "ix_generated_invoice_line_items_generated_invoice_id",
        "generated_invoice_line_items", ["generated_invoice_id"],
    )


def downgrade() -> None:
    op.drop_table("generated_invoice_line_items")
    op.drop_table("generated_invoices")
    op.drop_table("tax_config_versions")
    op.drop_table("invoice_number_sequences")
    op.drop_table("product_catalog_items")
