"""Central settings object for the Invoice Delivery Agent. Only the
variable groups listed in the approved scope (§15): app/db/queue, storage,
upload limits, email provider, WhatsApp provider, retry policy, and the
two company-identity fields the email template needs. No CRM/ERP/GST/LLM/
payment/Operations/product-access field exists here — if one creeps back
in, that's scope drift to catch in review, not something this file should
silently support.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_base_url: str = Field(default="http://localhost:8000", alias="APP_BASE_URL")
    database_url: str = Field(default="sqlite:///./invoice_agent.db", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    jwt_secret: str = Field(default="change-me-dev-only", alias="JWT_SECRET")

    # Storage
    storage_provider: str = Field(default="local", alias="STORAGE_PROVIDER")
    storage_bucket: str | None = Field(default=None, alias="STORAGE_BUCKET")
    storage_region: str | None = Field(default=None, alias="STORAGE_REGION")
    storage_endpoint_url: str | None = Field(default=None, alias="STORAGE_ENDPOINT_URL")
    storage_access_key_id: str | None = Field(default=None, alias="STORAGE_ACCESS_KEY_ID")
    storage_secret_access_key: str | None = Field(default=None, alias="STORAGE_SECRET_ACCESS_KEY")
    storage_local_dir: str = Field(default="./storage_dev", alias="STORAGE_LOCAL_DIR")

    # Upload / secure-link limits
    max_file_size_mb: int = Field(default=10, alias="MAX_FILE_SIZE_MB")
    secure_link_expiry_days: int = Field(default=7, alias="SECURE_LINK_EXPIRY_DAYS")
    secure_link_max_downloads: int = Field(default=3, alias="SECURE_LINK_MAX_DOWNLOADS")

    # Email provider
    email_provider: str = Field(default="mock", alias="EMAIL_PROVIDER")
    email_from_name: str | None = Field(default=None, alias="EMAIL_FROM_NAME")
    email_from_address: str | None = Field(default=None, alias="EMAIL_FROM_ADDRESS")
    email_reply_to_address: str | None = Field(default=None, alias="EMAIL_REPLY_TO_ADDRESS")
    email_api_key: str | None = Field(default=None, alias="EMAIL_API_KEY")
    email_webhook_signing_secret: str | None = Field(
        default=None, alias="EMAIL_WEBHOOK_SIGNING_SECRET"
    )

    # WhatsApp provider (Twilio-shaped by default; interface is provider-agnostic)
    whatsapp_provider: str = Field(default="mock", alias="WHATSAPP_PROVIDER")
    whatsapp_account_sid: str | None = Field(default=None, alias="WHATSAPP_ACCOUNT_SID")
    whatsapp_auth_token: str | None = Field(default=None, alias="WHATSAPP_AUTH_TOKEN")
    whatsapp_from_number: str | None = Field(default=None, alias="WHATSAPP_FROM_NUMBER")
    whatsapp_template_id: str | None = Field(default=None, alias="WHATSAPP_TEMPLATE_ID")
    whatsapp_webhook_signing_secret: str | None = Field(
        default=None, alias="WHATSAPP_WEBHOOK_SIGNING_SECRET"
    )

    # Retry policy
    retry_max_attempts: int = Field(default=4, alias="RETRY_MAX_ATTEMPTS")
    retry_schedule_minutes: str = Field(default="1,5,30,120", alias="RETRY_SCHEDULE_MINUTES")

    # Company identity. For Method A (existing-PDF delivery) these are used
    # only in email/WhatsApp copy, never written onto the invoice itself.
    # For Method B (generated invoices) these are the ONLY source of
    # seller details on the rendered PDF — never taken from the request
    # body, never invented (spec §7 rule 2).
    company_legal_name: str | None = Field(default=None, alias="COMPANY_LEGAL_NAME")
    company_registered_address: str | None = Field(default=None, alias="COMPANY_REGISTERED_ADDRESS")
    seller_gstin: str | None = Field(default=None, alias="SELLER_GSTIN")
    seller_state_name: str | None = Field(default=None, alias="SELLER_STATE_NAME")
    seller_state_code: str | None = Field(default=None, alias="SELLER_STATE_CODE")
    support_email: str | None = Field(default=None, alias="SUPPORT_EMAIL")
    support_phone: str | None = Field(default=None, alias="SUPPORT_PHONE")
    company_logo_url: str | None = Field(default=None, alias="COMPANY_LOGO_URL")

    # Invoice numbering (Method B only — Method A never reserves a number)
    invoice_prefix: str = Field(default="INV", alias="INVOICE_PREFIX")
    invoice_number_format: str = Field(
        default="{prefix}/FY{fy_start_short}-{fy_end_short}/{sequence}",
        alias="INVOICE_NUMBER_FORMAT",
    )
    invoice_sequence_padding: int = Field(default=6, alias="INVOICE_SEQUENCE_PADDING")
    financial_year_start_month: int = Field(default=4, alias="FINANCIAL_YEAR_START_MONTH")

    # Invoice PDF (Method B only)
    invoice_template_version: str = Field(default="v1", alias="INVOICE_TEMPLATE_VERSION")
    # Only "weasyprint" is implemented today (see app/services/invoicing/
    # pdf_renderer.py) — proven to work in this environment without a
    # browser process. "playwright" is accepted as a config value (the
    # spec's suggested default) but raises NotImplementedError until a
    # Playwright-based renderer is actually built.
    pdf_renderer: str = Field(default="weasyprint", alias="PDF_RENDERER")
    pdf_timezone: str = Field(default="Asia/Kolkata", alias="PDF_TIMEZONE")

    # Tax rules (Method B only)
    tax_tolerance_amount: str = Field(default="0.01", alias="TAX_TOLERANCE_AMOUNT")
    currency: str = Field(default="INR", alias="CURRENCY")
    rounding_mode: str = Field(default="HALF_UP", alias="ROUNDING_MODE")
    reverse_charge_applicable: bool = Field(default=False, alias="REVERSE_CHARGE_APPLICABLE")

    # Retention
    document_retention_days: int = Field(default=90, alias="DOCUMENT_RETENTION_DAYS")

    # First-run convenience: if the internal_users table is empty at
    # startup, an ADMIN account is seeded with these credentials so the
    # UI has something to log in with immediately. Change the password
    # (via the Users screen) before any real deployment.
    default_admin_email: str = Field(default="admin@example.com", alias="DEFAULT_ADMIN_EMAIL")
    default_admin_password: str = Field(default="ChangeMe123!", alias="DEFAULT_ADMIN_PASSWORD")

    # Human-approval gate
    require_human_approval_for_generated_invoices: bool = Field(
        default=True, alias="REQUIRE_HUMAN_APPROVAL_FOR_GENERATED_INVOICES"
    )
    default_require_human_approval_for_uploaded_invoices: bool = Field(
        default=False, alias="DEFAULT_REQUIRE_HUMAN_APPROVAL_FOR_UPLOADED_INVOICES"
    )
    # "DRAFT" reserves the invoice number when the draft is first saved
    # (shown with a DRAFT watermark until approval); "APPROVAL" waits
    # until approval to reserve it. Either way the number is reserved
    # exactly once and never reused.
    invoice_number_assignment_stage: str = Field(default="DRAFT", alias="INVOICE_NUMBER_ASSIGNMENT_STAGE")
    draft_watermark_text: str = Field(default="DRAFT - NOT FOR DELIVERY", alias="DRAFT_WATERMARK_TEXT")

    # AI draft-prefill / AI edit-proposal assistant. Disabled gracefully
    # (not an error) when no API key is configured — see
    # app/services/ai/factory.py.
    ai_edit_enabled: bool = Field(default=True, alias="AI_EDIT_ENABLED")
    ai_provider: str = Field(default="anthropic", alias="AI_PROVIDER")
    ai_model: str = Field(default="claude-sonnet-4-5", alias="AI_MODEL")
    ai_api_key: str | None = Field(default=None, alias="AI_API_KEY")
    ai_edit_prompt_version: str = Field(default="v1", alias="AI_EDIT_PROMPT_VERSION")
    ai_edit_max_proposals_per_hour_per_user: int = Field(
        default=20, alias="AI_EDIT_MAX_PROPOSALS_PER_HOUR_PER_USER"
    )

    @property
    def ai_edit_available(self) -> bool:
        return self.ai_edit_enabled and bool(self.ai_api_key)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def missing_seller_identity_fields(self) -> list[str]:
        """Fields that must be real (not None) before Method B can generate
        a real invoice. An empty list means generation is safe to proceed;
        a non-empty one means the request must fail closed, never fall
        back to an invented or blank seller identity.
        """
        required = {
            "company_legal_name": self.company_legal_name,
            "company_registered_address": self.company_registered_address,
            "seller_gstin": self.seller_gstin,
            "seller_state_name": self.seller_state_name,
            "seller_state_code": self.seller_state_code,
        }
        return [name for name, value in required.items() if not value]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def retry_schedule_seconds(self) -> list[int]:
        return [int(m.strip()) * 60 for m in self.retry_schedule_minutes.split(",") if m.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
