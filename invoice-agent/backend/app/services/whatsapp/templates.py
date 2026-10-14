"""Exact template copy from spec §10. The three variables map to a
provider-approved utility/template message's {{1}}, {{2}}, {{3}}
placeholders — never sent as free-form text.
"""

from __future__ import annotations


def build_template_variables(
    *,
    recipient_name: str,
    invoice_number_or_reference: str | None,
    secure_link: str | None,
    support_email: str,
) -> dict[str, str]:
    return {
        "1": recipient_name,
        "2": invoice_number_or_reference or "",
        "3": secure_link or "",
    }


def render_preview_text(
    *,
    recipient_name: str,
    invoice_number_or_reference: str | None,
    secure_link: str | None,
    support_email: str,
) -> str:
    """Human-readable preview of the approved template, for logs/dashboard
    display only — never what's actually sent (the provider renders the
    real template from its own stored copy + the variables above).
    """
    invoice_part = invoice_number_or_reference or "(reference not provided)"
    link_part = secure_link or "(no link)"
    return (
        f"Hello {recipient_name}, your invoice {invoice_part} is ready.\n"
        f"You can securely access it here: {link_part}.\n"
        f"For support, contact {support_email}."
    )
