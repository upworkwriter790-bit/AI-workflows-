"""Scope change: Invoice Delivery Agent. Drops the AR/GST/document-review
tables (no production data exists in any of them — this was never
deployed past local dev) and creates the delivery-agent schema.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_TABLES = [
    "invoice_line_items",
    "invoices",
    "orders",
    "invoice_sequences",
    "products",
    "decisions",
    "received_documents",
    "customers",
]


def upgrade() -> None:
    for table in _OLD_TABLES:
        op.drop_table(table)

    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.alter_column("actor_type", type_=sa.String(24))

    with op.batch_alter_table("idempotency_records") as batch_op:
        batch_op.add_column(sa.Column("delivery_id", sa.String(36)))
    op.create_index(
        "ix_idempotency_records_delivery_id", "idempotency_records", ["delivery_id"]
    )

    op.create_table(
        "invoice_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("sanitized_filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("byte_size", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False, unique=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("uploaded_by_user_id", sa.String(36)),
        sa.Column("external_reference", sa.String(128)),
        sa.Column("invoice_number", sa.String(64)),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_invoice_documents_sha256", "invoice_documents", ["sha256"])

    op.create_table(
        "invoice_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("invoice_documents.id"), nullable=False),
        sa.Column("recipient_name", sa.String(255), nullable=False),
        sa.Column("recipient_email", sa.String(255)),
        sa.Column("recipient_phone", sa.String(20)),
        sa.Column("requested_channels_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("external_reference", sa.String(128)),
        sa.Column("invoice_number", sa.String(64)),
        sa.Column("status", sa.String(32), server_default="RECEIVED"),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("idempotency_key", name="uq_invoice_delivery_idempotency_key"),
    )
    op.create_index("ix_invoice_deliveries_document_id", "invoice_deliveries", ["document_id"])
    op.create_index("ix_invoice_deliveries_idempotency_key", "invoice_deliveries", ["idempotency_key"])
    op.create_index("ix_invoice_deliveries_correlation_id", "invoice_deliveries", ["correlation_id"])

    op.create_table(
        "delivery_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("delivery_id", sa.String(36), sa.ForeignKey("invoice_deliveries.id"), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("attempt_number", sa.Integer, server_default="1"),
        sa.Column("is_resend", sa.Boolean, server_default=sa.false()),
        sa.Column("resend_reason", sa.String(500)),
        sa.Column("resend_requested_by_user_id", sa.String(36)),
        sa.Column("status", sa.String(16), server_default="QUEUED"),
        sa.Column("provider", sa.String(32)),
        sa.Column("provider_message_id", sa.String(255)),
        sa.Column("provider_response_safe_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_message_safe", sa.String(500)),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_delivery_attempts_delivery_id", "delivery_attempts", ["delivery_id"])

    op.create_table(
        "secure_download_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("invoice_documents.id"), nullable=False),
        sa.Column("delivery_id", sa.String(36), sa.ForeignKey("invoice_deliveries.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_downloads", sa.Integer, nullable=False),
        sa.Column("download_count", sa.Integer, server_default="0"),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_secure_download_links_document_id", "secure_download_links", ["document_id"])
    op.create_index("ix_secure_download_links_delivery_id", "secure_download_links", ["delivery_id"])

    op.create_table(
        "internal_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_internal_users_email", "internal_users", ["email"])


def downgrade() -> None:
    op.drop_table("internal_users")
    op.drop_table("secure_download_links")
    op.drop_table("delivery_attempts")
    op.drop_table("invoice_deliveries")
    op.drop_table("invoice_documents")
    op.drop_index("ix_idempotency_records_delivery_id", table_name="idempotency_records")
    with op.batch_alter_table("idempotency_records") as batch_op:
        batch_op.drop_column("delivery_id")
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.alter_column("actor_type", type_=sa.String(16))

    op.create_table(
        "customers",
        sa.Column("id", sa.String(36), primary_key=True),
    )
    op.create_table(
        "received_documents",
        sa.Column("id", sa.String(36), primary_key=True),
    )
    op.create_table(
        "decisions",
        sa.Column("id", sa.String(36), primary_key=True),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
    )
    op.create_table(
        "invoice_sequences",
        sa.Column("financial_year", sa.String(16), primary_key=True),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
    )
    op.create_table(
        "invoices",
        sa.Column("id", sa.String(36), primary_key=True),
    )
    op.create_table(
        "invoice_line_items",
        sa.Column("id", sa.String(36), primary_key=True),
    )
    # NOTE: this downgrade recreates only bare skeleton tables, not the
    # original full schema — it exists so `alembic downgrade` doesn't
    # error, not to actually restore the old system. To truly go back to
    # the AR/GST version, restore from the archived code
    # (archive/deprecated/) and re-run that version's own migrations
    # against a fresh database instead of relying on this downgrade.
