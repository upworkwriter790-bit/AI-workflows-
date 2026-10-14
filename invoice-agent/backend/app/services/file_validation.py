"""Upload validation for the Invoice Delivery Agent intake endpoint.

Deliberately does nothing beyond validating shape/size/type — per the
approved scope, this system must never inspect, interpret, extract,
authenticate, or edit invoice content. A file that is a structurally valid
PDF is accepted; what's drawn on its pages is never read.
"""

from __future__ import annotations

import re
import unicodedata

import phonenumbers

PDF_MAGIC_BYTES = b"%PDF-"
ALLOWED_MIME_TYPES = {"application/pdf"}


class FileValidationError(ValueError):
    pass


class PhoneValidationError(ValueError):
    pass


def sanitize_filename(original_filename: str) -> str:
    name = unicodedata.normalize("NFKD", original_filename)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    if not name:
        name = "invoice.pdf"
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return name[:255]


def validate_pdf_upload(
    *,
    filename: str,
    content_type: str | None,
    data: bytes,
    max_bytes: int,
) -> str:
    """Returns the sanitized filename, or raises FileValidationError."""
    if not filename.lower().endswith(".pdf"):
        raise FileValidationError("only .pdf files are accepted in version 1")

    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise FileValidationError(f"unsupported content type: {content_type}")

    if len(data) == 0:
        raise FileValidationError("uploaded file is empty")

    if len(data) > max_bytes:
        raise FileValidationError(
            f"file exceeds maximum size of {max_bytes // (1024 * 1024)} MB"
        )

    if not data.startswith(PDF_MAGIC_BYTES):
        raise FileValidationError("file does not have valid PDF magic bytes")

    return sanitize_filename(filename)


def validate_e164_phone(phone: str) -> str:
    """Returns the normalized E.164 string, or raises PhoneValidationError."""
    try:
        parsed = phonenumbers.parse(phone, None)
    except phonenumbers.NumberParseException as exc:
        raise PhoneValidationError(f"phone number is not valid E.164: {exc}") from exc

    if not phonenumbers.is_valid_number(parsed) or not phone.startswith("+"):
        raise PhoneValidationError("phone number must be valid E.164, e.g. +919876543210")

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
