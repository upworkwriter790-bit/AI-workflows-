"""Import every model so `Base.metadata` is complete for Alembic autogenerate
and for the test-suite's `Base.metadata.create_all`.
"""

from app.models.audit_event import AuditEvent
from app.models.customer import Customer
from app.models.decision import Decision
from app.models.idempotency import IdempotencyRecord
from app.models.invoice import Invoice
from app.models.invoice_line_item import InvoiceLineItem
from app.models.order import Order
from app.models.product import Product
from app.models.received_document import ReceivedDocument

__all__ = [
    "AuditEvent",
    "Customer",
    "Decision",
    "IdempotencyRecord",
    "Invoice",
    "InvoiceLineItem",
    "Order",
    "Product",
    "ReceivedDocument",
]
