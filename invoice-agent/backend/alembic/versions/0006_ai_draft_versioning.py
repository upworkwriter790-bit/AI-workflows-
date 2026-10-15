"""AI-assisted draft-versioning workflow for Method B, a lightweight
customer directory, product-catalog aliases, multi-role users, and an
optional human-approval flag for Method A. Additive only — no existing
table is dropped and no existing row is rewritten.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-14
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("legal_name", sa.String(255)),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(20)),
        sa.Column("gstin", sa.String(15)),
        sa.Column("billing_address_json", sa.JSON),
        sa.Column("shipping_address_json", sa.JSON),
        sa.Column("state_name", sa.String(64)),
        sa.Column("state_code", sa.String(4)),
        sa.Column("preferred_delivery_channels_json", sa.JSON, server_default="[]"),
        sa.Column("source", sa.String(32), server_default="MANUAL"),
        sa.Column("verification_status", sa.String(16), server_default="UNVERIFIED"),
        sa.Column("created_by_user_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_customers_email", "customers", ["email"])
    op.create_index("ix_customers_phone", "customers", ["phone"])

    op.create_table(
        "invoice_draft_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("generated_invoice_id", sa.String(36), sa.ForeignKey("generated_invoices.id"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("parent_version_number", sa.Integer),
        sa.Column("created_by_type", sa.String(24), nullable=False),
        sa.Column("created_by_user_id", sa.String(36)),
        sa.Column("creation_reason", sa.String(32), nullable=False),
        sa.Column("invoice_data_snapshot_json", sa.JSON, nullable=False),
        sa.Column("line_items_snapshot_json", sa.JSON, nullable=False),
        sa.Column("calculation_snapshot_json", sa.JSON, nullable=False),
        sa.Column("validation_result_json", sa.JSON, server_default="{}"),
        sa.Column("template_version", sa.String(16)),
        sa.Column("draft_pdf_storage_key", sa.String(500)),
        sa.Column("draft_pdf_sha256", sa.String(64)),
        sa.Column("change_summary", sa.String(1000)),
        sa.Column("is_current", sa.Boolean, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("generated_invoice_id", "version_number", name="uq_draft_version_number"),
    )
    op.create_index("ix_invoice_draft_versions_generated_invoice_id", "invoice_draft_versions", ["generated_invoice_id"])

    op.create_table(
        "invoice_edit_proposals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("generated_invoice_id", sa.String(36), sa.ForeignKey("generated_invoices.id"), nullable=False),
        sa.Column("base_draft_version_number", sa.Integer, nullable=False),
        sa.Column("requested_by_user_id", sa.String(36), nullable=False),
        sa.Column("natural_language_instruction", sa.String(2000), nullable=False),
        sa.Column("structured_change_proposal_json", sa.JSON, server_default="{}"),
        sa.Column("ai_model", sa.String(64)),
        sa.Column("prompt_version", sa.String(16)),
        sa.Column("status", sa.String(24), server_default="PENDING"),
        sa.Column("proposed_change_summary", sa.String(1000)),
        sa.Column("validation_result_json", sa.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("applied_by_user_id", sa.String(36)),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("rejected_by_user_id", sa.String(36)),
        sa.Column("rejected_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.String(500)),
    )
    op.create_index("ix_invoice_edit_proposals_generated_invoice_id", "invoice_edit_proposals", ["generated_invoice_id"])

    with op.batch_alter_table("generated_invoices") as batch_op:
        # No inline ForeignKey() here — SQLite's batch-recreate mode
        # requires named constraints for that, and the relationship is
        # already enforced at the application layer like the table's
        # other id-reference columns.
        batch_op.add_column(sa.Column("customer_id", sa.String(36)))
        batch_op.add_column(sa.Column("current_version_number", sa.Integer, server_default="1"))
        batch_op.add_column(sa.Column("approved_version_number", sa.Integer))
        batch_op.add_column(sa.Column("invoice_number_assignment_stage", sa.String(16), server_default="DRAFT"))
        batch_op.add_column(sa.Column("rejected_by_user_id", sa.String(36)))
        batch_op.add_column(sa.Column("rejected_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("rejection_reason", sa.String(500)))
        batch_op.add_column(sa.Column("final_document_id", sa.String(36)))
        batch_op.add_column(sa.Column("final_pdf_sha256", sa.String(64)))
        batch_op.add_column(sa.Column("finalization_timestamp", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("locked_at", sa.DateTime(timezone=True)))

    with op.batch_alter_table("invoice_deliveries") as batch_op:
        batch_op.add_column(sa.Column("require_human_approval", sa.Boolean, server_default=sa.false()))

    with op.batch_alter_table("product_catalog_items") as batch_op:
        batch_op.add_column(sa.Column("aliases_json", sa.JSON, server_default="[]"))

    # internal_users.role grows to hold a comma-separated multi-role
    # string (e.g. "INVOICE_EDITOR,INVOICE_APPROVER").
    with op.batch_alter_table("internal_users") as batch_op:
        batch_op.alter_column("role", type_=sa.String(128), existing_type=sa.String(32))


def downgrade() -> None:
    with op.batch_alter_table("internal_users") as batch_op:
        batch_op.alter_column("role", type_=sa.String(32), existing_type=sa.String(128))

    with op.batch_alter_table("product_catalog_items") as batch_op:
        batch_op.drop_column("aliases_json")

    with op.batch_alter_table("invoice_deliveries") as batch_op:
        batch_op.drop_column("require_human_approval")

    with op.batch_alter_table("generated_invoices") as batch_op:
        batch_op.drop_column("locked_at")
        batch_op.drop_column("finalization_timestamp")
        batch_op.drop_column("final_pdf_sha256")
        batch_op.drop_column("final_document_id")
        batch_op.drop_column("rejection_reason")
        batch_op.drop_column("rejected_at")
        batch_op.drop_column("rejected_by_user_id")
        batch_op.drop_column("invoice_number_assignment_stage")
        batch_op.drop_column("approved_version_number")
        batch_op.drop_column("current_version_number")
        batch_op.drop_column("customer_id")

    op.drop_index("ix_invoice_edit_proposals_generated_invoice_id", table_name="invoice_edit_proposals")
    op.drop_table("invoice_edit_proposals")
    op.drop_index("ix_invoice_draft_versions_generated_invoice_id", table_name="invoice_draft_versions")
    op.drop_table("invoice_draft_versions")
    op.drop_index("ix_customers_phone", table_name="customers")
    op.drop_index("ix_customers_email", table_name="customers")
    op.drop_table("customers")
