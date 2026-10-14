"""Draft/approval gate: no delivery (Method A or B) is dispatched until
an authorized human approves it. Purely additive columns; no existing
data is altered or dropped.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("invoice_deliveries") as batch_op:
        batch_op.add_column(sa.Column("attach_pdf_to_email", sa.Boolean, server_default=sa.true()))
        batch_op.add_column(sa.Column("include_download_link", sa.Boolean, server_default=sa.true()))
        batch_op.add_column(sa.Column("send_whatsapp_notification", sa.Boolean, server_default=sa.true()))

    with op.batch_alter_table("generated_invoices") as batch_op:
        batch_op.add_column(sa.Column("requested_channels_json", sa.JSON, server_default="[]"))
        batch_op.add_column(sa.Column("attach_pdf_to_email", sa.Boolean, server_default=sa.true()))
        batch_op.add_column(sa.Column("include_download_link", sa.Boolean, server_default=sa.true()))
        batch_op.add_column(sa.Column("send_whatsapp_notification", sa.Boolean, server_default=sa.true()))
        batch_op.add_column(sa.Column("notes", sa.String(2000)))
        batch_op.add_column(sa.Column("approved_by_user_id", sa.String(36)))
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(timezone=True)))

    # The unique constraints on invoice_number / invoice_document_id
    # already allow NULL (a draft has neither yet) — no change needed
    # there; SQLite and Postgres both treat multiple NULLs as distinct
    # under a unique constraint.


def downgrade() -> None:
    with op.batch_alter_table("generated_invoices") as batch_op:
        batch_op.drop_column("approved_at")
        batch_op.drop_column("approved_by_user_id")
        batch_op.drop_column("notes")
        batch_op.drop_column("send_whatsapp_notification")
        batch_op.drop_column("include_download_link")
        batch_op.drop_column("attach_pdf_to_email")
        batch_op.drop_column("requested_channels_json")

    with op.batch_alter_table("invoice_deliveries") as batch_op:
        batch_op.drop_column("send_whatsapp_notification")
        batch_op.drop_column("include_download_link")
        batch_op.drop_column("attach_pdf_to_email")
