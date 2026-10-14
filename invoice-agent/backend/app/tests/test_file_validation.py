from __future__ import annotations

import pytest

from app.services.file_validation import (
    FileValidationError,
    PhoneValidationError,
    sanitize_filename,
    validate_e164_phone,
    validate_pdf_upload,
)

PDF_BYTES = b"%PDF-1.4\n%%EOF"


def test_valid_pdf_passes():
    name = validate_pdf_upload(
        filename="invoice.pdf", content_type="application/pdf", data=PDF_BYTES, max_bytes=10 * 1024 * 1024
    )
    assert name == "invoice.pdf"


def test_non_pdf_extension_rejected():
    with pytest.raises(FileValidationError):
        validate_pdf_upload(
            filename="invoice.docx", content_type="application/pdf", data=PDF_BYTES, max_bytes=10 * 1024 * 1024
        )


def test_wrong_magic_bytes_rejected():
    with pytest.raises(FileValidationError):
        validate_pdf_upload(
            filename="invoice.pdf", content_type="application/pdf", data=b"not a pdf", max_bytes=10 * 1024 * 1024
        )


def test_oversized_file_rejected():
    with pytest.raises(FileValidationError):
        validate_pdf_upload(filename="invoice.pdf", content_type="application/pdf", data=PDF_BYTES, max_bytes=5)


def test_filename_sanitized():
    assert sanitize_filename("../../etc/passwd invoice!!.pdf") == "etc_passwd_invoice_.pdf"
    assert sanitize_filename("tiny") == "tiny.pdf"


def test_valid_e164_phone_accepted():
    assert validate_e164_phone("+919876543210") == "+919876543210"


def test_invalid_e164_phone_rejected():
    with pytest.raises(PhoneValidationError):
        validate_e164_phone("9876543210")  # missing country code / plus
