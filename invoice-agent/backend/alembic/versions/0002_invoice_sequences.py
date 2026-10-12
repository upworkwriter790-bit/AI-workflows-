"""invoice_sequences table for concurrency-safe invoice numbering

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invoice_sequences",
        sa.Column("financial_year", sa.String(16), primary_key=True),
        sa.Column("last_sequence", sa.Integer, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("invoice_sequences")
