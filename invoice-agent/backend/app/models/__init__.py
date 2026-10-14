"""Import every model so `Base.metadata` is complete for Alembic autogenerate
and for the test-suite's `Base.metadata.create_all`.
"""

from app.models.audit_event import AuditEvent
from app.models.delivery_attempt import DeliveryAttempt
from app.models.idempotency import IdempotencyRecord
from app.models.internal_user import InternalUser
from app.models.invoice_delivery import InvoiceDelivery
from app.models.invoice_document import InvoiceDocument
from app.models.secure_download_link import SecureDownloadLink

__all__ = [
    "AuditEvent",
    "DeliveryAttempt",
    "IdempotencyRecord",
    "InternalUser",
    "InvoiceDelivery",
    "InvoiceDocument",
    "SecureDownloadLink",
]
