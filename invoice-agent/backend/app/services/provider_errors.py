"""Shared error taxonomy for email/WhatsApp provider adapters (spec §12).

Retryable (`TransientProviderError`): network errors, timeouts, HTTP 429,
provider 5xx.

Not retryable (`PermanentProviderError`): invalid recipient data, an
explicit provider rejection, a bounced email, a template configuration
error, or unauthorized API credentials. A permanent error goes straight
to FAILED — no automatic retry, because retrying it cannot succeed and
would just risk a duplicate send once provider state is involved.
"""

from __future__ import annotations


class TransientProviderError(Exception):
    def __init__(self, message: str, *, error_code: str = "transient_error") -> None:
        self.error_code = error_code
        super().__init__(message)


class PermanentProviderError(Exception):
    def __init__(self, message: str, *, error_code: str = "permanent_error") -> None:
        self.error_code = error_code
        super().__init__(message)
