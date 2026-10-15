"""Import every model so `Base.metadata` is complete for Alembic autogenerate
and for the test-suite's `Base.metadata.create_all`.
"""

from app.models.audit_event import AuditEvent
from app.models.customer import Customer
from app.models.delivery_attempt import DeliveryAttempt
from app.models.generated_invoice import GeneratedInvoice
from app.models.generated_invoice_line_item import GeneratedInvoiceLineItem
from app.models.idempotency import IdempotencyRecord
from app.models.internal_user import InternalUser
from app.models.invoice_delivery import InvoiceDelivery
from app.models.invoice_document import InvoiceDocument
from app.models.invoice_draft_version import InvoiceDraftVersion
from app.models.invoice_edit_proposal import InvoiceEditProposal
from app.models.invoice_number_sequence import InvoiceNumberSequence
from app.models.product_catalog_item import ProductCatalogItem
from app.models.secure_download_link import SecureDownloadLink
from app.models.tax_config_version import TaxConfigVersion

__all__ = [
    "AuditEvent",
    "Customer",
    "DeliveryAttempt",
    "GeneratedInvoice",
    "GeneratedInvoiceLineItem",
    "IdempotencyRecord",
    "InternalUser",
    "InvoiceDelivery",
    "InvoiceDocument",
    "InvoiceDraftVersion",
    "InvoiceEditProposal",
    "InvoiceNumberSequence",
    "ProductCatalogItem",
    "SecureDownloadLink",
    "TaxConfigVersion",
]
