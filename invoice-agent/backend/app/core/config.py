"""Central settings object. Everything business/tax/integration-specific comes
from the environment — never hardcoded, never guessed.

`Settings.require_live_invoicing_config()` is the gate that stops the sales
invoice workflow from running against invented company/tax data: it is called
once at the start of the Use Case 1 workflow (Phase 2+), not here.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development", alias="ENVIRONMENT")
    app_secret_key: str = Field(default="change-me-dev-only", alias="APP_SECRET_KEY")

    # Company / tax identity — intentionally no defaults.
    company_legal_name: str | None = Field(default=None, alias="COMPANY_LEGAL_NAME")
    company_registered_address: str | None = Field(
        default=None, alias="COMPANY_REGISTERED_ADDRESS"
    )
    seller_gstin: str | None = Field(default=None, alias="SELLER_GSTIN")
    seller_state_name: str | None = Field(default=None, alias="SELLER_STATE_NAME")
    seller_state_code: str | None = Field(default=None, alias="SELLER_STATE_CODE")
    invoice_prefix: str = Field(default="INV", alias="INVOICE_PREFIX")
    invoice_number_format: str = Field(
        default="INV/FY{fy_start}-{fy_end}/{seq:06d}", alias="INVOICE_NUMBER_FORMAT"
    )
    support_email: str | None = Field(default=None, alias="SUPPORT_EMAIL")
    support_phone: str | None = Field(default=None, alias="SUPPORT_PHONE")
    invoice_logo_path: str | None = Field(default=None, alias="INVOICE_LOGO_PATH")

    # Database / queue
    database_url: str = Field(
        default="sqlite:///./invoice_agent.db", alias="DATABASE_URL"
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # CRM
    crm_provider: str = Field(default="mock", alias="CRM_PROVIDER")
    crm_name: str | None = Field(default=None, alias="CRM_NAME")
    crm_api_base_url: str | None = Field(default=None, alias="CRM_API_BASE_URL")
    crm_api_key: str | None = Field(default=None, alias="CRM_API_KEY")
    crm_webhook_hmac_secret: str = Field(
        default="change-me-dev-only", alias="CRM_WEBHOOK_HMAC_SECRET"
    )

    # ERP
    erp_provider: str = Field(default="mock", alias="ERP_PROVIDER")
    erp_name: str | None = Field(default=None, alias="ERP_NAME")
    erp_api_base_url: str | None = Field(default=None, alias="ERP_API_BASE_URL")
    erp_api_key: str | None = Field(default=None, alias="ERP_API_KEY")

    # Product access
    product_access_provider: str = Field(default="mock", alias="PRODUCT_ACCESS_PROVIDER")
    product_access_system_name: str | None = Field(
        default=None, alias="PRODUCT_ACCESS_SYSTEM_NAME"
    )
    product_access_api_base_url: str | None = Field(
        default=None, alias="PRODUCT_ACCESS_API_BASE_URL"
    )
    product_access_api_key: str | None = Field(default=None, alias="PRODUCT_ACCESS_API_KEY")

    # Email
    email_provider: str = Field(default="mock", alias="EMAIL_PROVIDER")
    email_api_key: str | None = Field(default=None, alias="EMAIL_API_KEY")
    email_from_address: str | None = Field(default=None, alias="EMAIL_FROM_ADDRESS")

    # Operations notification
    operations_notification_provider: str = Field(
        default="mock", alias="OPERATIONS_NOTIFICATION_PROVIDER"
    )
    operations_webhook_url: str | None = Field(default=None, alias="OPERATIONS_WEBHOOK_URL")

    # Storage
    storage_provider: str = Field(default="local", alias="STORAGE_PROVIDER")
    storage_bucket: str | None = Field(default=None, alias="STORAGE_BUCKET")
    storage_endpoint_url: str | None = Field(default=None, alias="STORAGE_ENDPOINT_URL")
    storage_access_key_id: str | None = Field(default=None, alias="STORAGE_ACCESS_KEY_ID")
    storage_secret_access_key: str | None = Field(
        default=None, alias="STORAGE_SECRET_ACCESS_KEY"
    )
    storage_local_dir: str = Field(default="./storage_dev", alias="STORAGE_LOCAL_DIR")

    # LLM
    llm_provider: str = Field(default="anthropic", alias="LLM_PROVIDER")
    llm_model: str | None = Field(default=None, alias="LLM_MODEL")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    sarvam_api_key: str | None = Field(default=None, alias="SARVAM_API_KEY")

    # Decision thresholds
    auto_accept_max_amount: float = Field(default=0.0, alias="AUTO_ACCEPT_MAX_AMOUNT")
    critical_field_confidence_threshold: float = Field(
        default=0.95, alias="CRITICAL_FIELD_CONFIDENCE_THRESHOLD"
    )
    tax_mismatch_tolerance: float = Field(default=0.01, alias="TAX_MISMATCH_TOLERANCE")

    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def missing_live_invoicing_fields(self) -> list[str]:
        """Fields that must be real (not None) before Use Case 1 can post a
        real, legally-usable invoice. Returns an empty list when all are set.
        """
        required = {
            "company_legal_name": self.company_legal_name,
            "company_registered_address": self.company_registered_address,
            "seller_gstin": self.seller_gstin,
            "seller_state_name": self.seller_state_name,
            "seller_state_code": self.seller_state_code,
            "support_email": self.support_email,
        }
        return [name for name, value in required.items() if not value]


@lru_cache
def get_settings() -> Settings:
    return Settings()
