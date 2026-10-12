"""initial schema: customers, products, orders, invoices, invoice_line_items,
received_documents, decisions, audit_events, idempotency_records

Revision ID: 0001
Revises:
Create Date: 2026-10-13
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("crm_customer_id", sa.String(128), unique=True),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(32)),
        sa.Column("gstin", sa.String(15)),
        sa.Column("billing_address_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("shipping_address_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("state_name", sa.String(64)),
        sa.Column("state_code", sa.String(4)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_customers_email", "customers", ["email"])
    op.create_index("ix_customers_crm_customer_id", "customers", ["crm_customer_id"])

    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("crm_product_id", sa.String(128), unique=True),
        sa.Column("sku", sa.String(128)),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000)),
        sa.Column("hsn_or_sac_code", sa.String(16)),
        sa.Column("product_type", sa.String(16), nullable=False),
        sa.Column("unit", sa.String(16)),
        sa.Column("default_gst_rate", sa.Numeric(5, 2), server_default="0"),
        sa.Column("active", sa.Boolean, server_default=sa.true()),
    )
    op.create_index("ix_products_sku", "products", ["sku"])
    op.create_index("ix_products_crm_product_id", "products", ["crm_product_id"])

    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("crm_order_id", sa.String(128), nullable=False, unique=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("payment_status", sa.String(32), nullable=False),
        sa.Column("payment_reference", sa.String(128)),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("currency", sa.String(8), server_default="INR"),
        sa.Column("subtotal", sa.Numeric(14, 2), server_default="0"),
        sa.Column("discount_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("tax_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("grand_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("order_snapshot_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_orders_crm_order_id", "orders", ["crm_order_id"])
    op.create_index("ix_orders_idempotency_key", "orders", ["idempotency_key"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("invoice_number", sa.String(64), unique=True),
        sa.Column("invoice_type", sa.String(32), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id")),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id")),
        sa.Column("issuer_name", sa.String(255)),
        sa.Column("issuer_gstin", sa.String(15)),
        sa.Column("recipient_name", sa.String(255)),
        sa.Column("recipient_gstin", sa.String(15)),
        sa.Column("invoice_date", sa.Date),
        sa.Column("currency", sa.String(8), server_default="INR"),
        sa.Column("subtotal", sa.Numeric(14, 2), server_default="0"),
        sa.Column("discount_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("taxable_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("cgst_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("sgst_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("igst_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("cess_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("grand_total", sa.Numeric(14, 2), server_default="0"),
        sa.Column("place_of_supply", sa.String(64)),
        sa.Column("reverse_charge_applicable", sa.Boolean, server_default=sa.false()),
        sa.Column("invoice_status", sa.String(48), server_default="PAID_ORDER_RECEIVED"),
        sa.Column("template_version", sa.String(16)),
        sa.Column("pdf_storage_key", sa.String(512)),
        sa.Column("pdf_sha256", sa.String(64)),
        sa.Column("erp_invoice_id", sa.String(128)),
        sa.Column("crm_invoice_reference", sa.String(128)),
        sa.Column("email_status", sa.String(32)),
        sa.Column("email_message_id", sa.String(255)),
        sa.Column("operations_notification_status", sa.String(32)),
        sa.Column("product_access_status", sa.String(32)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"])
    op.create_index("ix_invoices_erp_invoice_id", "invoices", ["erp_invoice_id"])

    op.create_table(
        "invoice_line_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id")),
        sa.Column("external_product_reference", sa.String(128)),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("hsn_or_sac_code", sa.String(16)),
        sa.Column("quantity", sa.Numeric(14, 3), server_default="1"),
        sa.Column("unit", sa.String(16)),
        sa.Column("unit_price", sa.Numeric(14, 2), server_default="0"),
        sa.Column("discount_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("taxable_value", sa.Numeric(14, 2), server_default="0"),
        sa.Column("gst_rate", sa.Numeric(5, 2), server_default="0"),
        sa.Column("cgst_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("sgst_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("igst_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("cess_amount", sa.Numeric(14, 2), server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), server_default="0"),
    )
    op.create_index("ix_invoice_line_items_invoice_id", "invoice_line_items", ["invoice_id"])

    op.create_table(
        "received_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_reference", sa.String(255)),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128)),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("issuer_email", sa.String(255)),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("extraction_status", sa.String(32), server_default="DOCUMENT_RECEIVED"),
        sa.Column("extraction_json", sa.JSON),
        sa.Column("extracted_confidence_json", sa.JSON),
        sa.Column("matched_invoice_id", sa.String(36)),
        sa.Column("decision_status", sa.String(32)),
        sa.Column("decision_reason_json", sa.JSON),
    )
    op.create_index("ix_received_documents_sha256", "received_documents", ["sha256"])

    op.create_table(
        "decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("llm_recommendation", sa.String(32)),
        sa.Column("final_decision", sa.String(32)),
        sa.Column("deterministic_rules_result_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("confidence_summary_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("reasons_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("decided_by", sa.String(64), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_decisions_entity_id", "decisions", ["entity_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("event_name", sa.String(128), nullable=False),
        sa.Column("previous_state", sa.String(64)),
        sa.Column("new_state", sa.String(64)),
        sa.Column("actor_type", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(128)),
        sa.Column("safe_payload_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_correlation_id", "audit_events", ["correlation_id"])
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("operation_name", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_reference", sa.String(255)),
        sa.Column("status", sa.String(32), server_default="PROCESSING"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("operation_name", "idempotency_key", name="uq_idempotency_op_key"),
    )
    op.create_index("ix_idempotency_records_operation_name", "idempotency_records", ["operation_name"])
    op.create_index("ix_idempotency_records_idempotency_key", "idempotency_records", ["idempotency_key"])


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_table("audit_events")
    op.drop_table("decisions")
    op.drop_table("received_documents")
    op.drop_table("invoice_line_items")
    op.drop_table("invoices")
    op.drop_table("orders")
    op.drop_table("products")
    op.drop_table("customers")
