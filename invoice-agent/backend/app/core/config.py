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

    # Used only in email body text / dashboard branding — never interpreted,
    # never written onto the invoice itself (the PDF already exists).
    company_legal_name: str | None = Field(default=None, alias="COMPANY_LEGAL_NAME")
    support_email: str | None = Field(default=None, alias="SUPPORT_EMAIL")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def retry_schedule_seconds(self) -> list[int]:
        return [int(m.strip()) * 60 for m in self.retry_schedule_minutes.split(",") if m.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
