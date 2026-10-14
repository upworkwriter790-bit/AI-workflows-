"""Exact subject/body copy from spec §9. Kept separate from the provider
adapters so the copy can be reviewed/changed without touching provider
wiring.
"""

from __future__ import annotations


def build_subject(invoice_number_or_reference: str | None) -> str:
    if invoice_number_or_reference:
        return f"Invoice {invoice_number_or_reference}"
    return "Your invoice document"


def build_body(
    *,
    recipient_name: str,
    support_email: str,
    company_legal_name: str,
    secure_link: str | None,
) -> str:
    link_line = (
        f"\nYou can also securely download it here: {secure_link}\n" if secure_link else ""
    )
    return (
        f"Hello {recipient_name},\n\n"
        f"Please find your invoice attached.\n"
        f"{link_line}"
        f"For help, contact {support_email}.\n\n"
        f"Regards,\n"
        f"{company_legal_name}"
    )
