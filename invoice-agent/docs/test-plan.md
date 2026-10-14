# Test plan — Invoice Delivery Agent

49 tests, `backend/app/tests/`. Run: `cd invoice-agent/backend && python -m pytest -q`.

## Spec §16 required cases → implementing test

| # | Case | Test |
|---|---|---|
| 1 | Valid PDF upload queues a delivery | `test_invoice_delivery_intake.py::test_valid_pdf_upload_queues_delivery` |
| 2 | Non-PDF upload rejected | `test_invoice_delivery_intake.py::test_non_pdf_upload_rejected` |
| 3 | Oversized file rejected | `test_invoice_delivery_intake.py::test_oversized_file_rejected` |
| 4 | Missing email rejected when email requested | `test_invoice_delivery_intake.py::test_missing_email_rejected_when_email_requested` |
| 5 | Invalid E.164 phone rejected when WhatsApp requested | `test_invoice_delivery_intake.py::test_invalid_e164_phone_rejected_when_whatsapp_requested` |
| 6 | Same idempotency key does not create duplicate delivery | `test_invoice_delivery_intake.py::test_same_idempotency_key_does_not_create_duplicate_delivery` |
| 7 | Email delivery creates attempt with PDF attachment | `test_delivery_channels.py::test_email_delivery_creates_attempt_with_pdf_attachment` |
| 8 | WhatsApp delivery creates notification attempt | `test_delivery_channels.py::test_whatsapp_delivery_creates_notification_attempt` |
| 9 | Email provider success updates status correctly | `test_delivery_channels.py::test_email_provider_delivered_webhook_updates_status` |
| 10 | WhatsApp delivered/read callback updates status correctly | `test_delivery_channels.py::test_whatsapp_provider_delivered_then_read_callback_updates_status` |
| 11 | Email failure retries only for retryable errors | `test_delivery_channels.py::test_transient_email_failure_schedules_retry_then_eventually_fails` + `test_permanent_email_failure_does_not_retry` |
| 12 | WhatsApp failure does not prevent successful email | `test_delivery_channels.py::test_whatsapp_failure_does_not_prevent_successful_email` |
| 13 | Partial delivery correctly shown | `test_delivery_channels.py::test_partial_delivery_is_correctly_shown_in_detail_view` |
| 14 | Secure link expires after configured time | `test_secure_links.py::test_secure_link_expires_after_configured_time` |
| 15 | Revoked secure link cannot be accessed | `test_secure_links.py::test_revoked_secure_link_cannot_be_accessed` |
| 16 | Secure link respects maximum download count | `test_secure_links.py::test_secure_link_respects_max_download_count` |
| 17 | Manual resend requires proper role and a resend reason | `test_resend.py::test_resend_requires_manager_or_admin_role` + `test_resend_requires_a_reason` |
| 18 | Resend creates a new attempt but not a duplicate document | `test_resend.py::test_resend_creates_new_attempt_not_new_document` |
| 19 | Sensitive values masked in logs/dashboard list views | `test_invoice_delivery_intake.py::test_recipient_data_masked_in_list_view` + `test_logging_redaction.py` |
| 20 | Removed CRM/ERP/GST/LLM routes and jobs not reachable/imported | `test_invoice_delivery_intake.py::test_removed_crm_erp_gst_llm_routes_not_reachable` + `test_removed_modules_not_importable_from_live_tree` |

## Additional tests beyond the required 20

- `test_file_validation.py` — unit tests for PDF magic-byte/size/extension
  checks, filename sanitization, and E.164 phone validation in isolation
  from the HTTP layer.
- `test_invoice_delivery_intake.py::test_upload_requires_authorized_role` /
  `test_upload_without_token_rejected` — RBAC on the intake endpoint
  itself (403 for `DELIVERY_VIEWER`, 401 with no token).
- `test_resend.py::test_resend_audit_event_records_user_identity_and_reason`
  — audit-trail content check beyond just "a resend happened."
- `test_secure_links.py::test_download_route_streams_valid_pdf` /
  `test_download_route_rejects_unknown_token` — the public `GET /d/{token}`
  route end-to-end, not just the underlying service function.
- `test_models.py`, `test_health.py`, `test_security.py`,
  `test_logging_redaction.py` — carried over from the prior phase, updated
  for the new schema/scope.

## Test data policy

No real recipient data, phone numbers, or documents in any fixture.
Phone numbers use the `+91` country code with an obviously synthetic
subscriber number; emails use `@example.com`; the test PDF is the
smallest possible structurally-valid PDF (`%PDF-1.4\n%%EOF`), since this
system never reads what's inside a PDF anyway.

## User-acceptance checklist (once real providers are configured)

- [ ] A real PDF, uploaded through the real intake endpoint, is received
      correctly in a real inbox with the PDF attached and opens cleanly.
- [ ] A real WhatsApp utility template, approved by Meta/Twilio, renders
      correctly on a real device with the right variables substituted.
- [ ] A deliberately-bounced test email updates the delivery's status via
      the real provider's webhook within a reasonable time.
- [ ] A secure link generated against real cloud storage redirects to a
      working signed URL rather than streaming bytes directly.
- [ ] An `ADMIN` and a `DELIVERY_MANAGER` user can both complete a manual
      resend through whatever UI eventually calls this API; a
      `DELIVERY_VIEWER` cannot.
