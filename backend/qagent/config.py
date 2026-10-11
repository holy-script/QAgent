from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres / Neon
    database_url: str = Field(
        default="sqlite+aiosqlite:///qagent.db",
        alias="DATABASE_URL",
    )
    database_url_direct: Optional[str] = Field(
        default=None,
        alias="DATABASE_URL_DIRECT",
    )

    # Neon Object Storage (S3-compatible)
    neon_s3_endpoint: Optional[str] = Field(default=None, alias="NEON_S3_ENDPOINT")
    neon_s3_access_key_id: Optional[str] = Field(default=None, alias="NEON_S3_ACCESS_KEY_ID")
    neon_s3_secret_access_key: Optional[str] = Field(default=None, alias="NEON_S3_SECRET_ACCESS_KEY")
    neon_s3_region: str = Field(default="ap-southeast-1", alias="NEON_S3_REGION")
    neon_s3_bucket: str = Field(default="qagent-artifacts", alias="NEON_S3_BUCKET")

    local_artifact_dir: str = Field(default=".artifacts", alias="LOCAL_ARTIFACT_DIR")

    # Jev (TypeSafe AI)
    typesafe_api_key: Optional[str] = Field(default=None, alias="TYPESAFE_API_KEY")
    jev_api_token: Optional[str] = Field(default=None, alias="JEV_API_TOKEN")
    typesafe_base_url: str = Field(default="https://api.typesafe.ai", alias="TYPESAFE_BASE_URL")
    jev_model: str = Field(default="jev-1.13.0", alias="JEV_MODEL")
    jev_max_concurrency: int = Field(default=4, alias="JEV_MAX_CONCURRENCY")

    # Claude on Bedrock
    bedrock_region: str = Field(default="us-east-1", alias="BEDROCK_REGION")
    bedrock_api_key: Optional[str] = Field(default=None, alias="BEDROCK_API_KEY")
    bedrock_reasoning_model_id: str = Field(
        default="us.anthropic.claude-sonnet-4-20250514-v1:0",
        alias="BEDROCK_REASONING_MODEL_ID",
    )

    # Gating
    gate_auto_min: float = Field(default=0.75, alias="GATE_AUTO_MIN")
    gate_escalate_min: float = Field(default=0.45, alias="GATE_ESCALATE_MIN")

    # Runtime budgets and rules
    qagent_allowed_hosts: str = Field(
        default="localhost,127.0.0.1",
        alias="QAGENT_ALLOWED_HOSTS",
    )
    qagent_inject_traceparent: bool = Field(default=True, alias="QAGENT_INJECT_TRACEPARENT")
    flow_step_budget: int = Field(default=25, alias="FLOW_STEP_BUDGET")
    flow_time_budget_s: int = Field(default=90, alias="FLOW_TIME_BUDGET_S")
    flow_max_parallel: int = Field(default=3, alias="FLOW_MAX_PARALLEL")
    network_body_cap_kb: int = Field(default=256, alias="NETWORK_BODY_CAP_KB")
    step_sla_ms: float = Field(default=2000.0, alias="STEP_SLA_MS")
    settle_timeout_ms: int = Field(default=3000, alias="SETTLE_TIMEOUT_MS")

    # Browser: leave channel unset to use bundled Chromium; the sandbox falls back
    # to installed Google Chrome when the bundled build is missing.
    browser_channel: Optional[str] = Field(default=None, alias="QAGENT_BROWSER_CHANNEL")
    browser_path: Optional[str] = Field(default=None, alias="QAGENT_BROWSER_PATH")
    browser_headless: bool = Field(default=True, alias="QAGENT_HEADLESS")

    # Team login. One shared account, kept in config on purpose (simple auth for now). Override with env vars.
    auth_email: str = Field(default="admin@chryselys.com", alias="AUTH_EMAIL")
    auth_password: str = Field(default="Admin@QAgent!2026", alias="AUTH_PASSWORD")
    auth_secret: str = Field(default="qagent-dev-secret-change-me", alias="AUTH_SECRET")
    auth_ttl_hours: int = Field(default=12, alias="AUTH_TTL_HOURS")
    auth_cookie_secure: bool = Field(default=False, alias="AUTH_COOKIE_SECURE")
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000", alias="CORS_ORIGINS")

    # Demo & Local Dev
    demo_shop_url: str = Field(default="http://localhost:8001", alias="DEMO_SHOP_URL")
    api_url: str = Field(default="http://localhost:8000", alias="API_URL")

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_hosts_list(self) -> List[str]:
        return [h.strip() for h in self.qagent_allowed_hosts.split(",") if h.strip()]

    @property
    def active_jev_token(self) -> Optional[str]:
        return self.typesafe_api_key or self.jev_api_token


settings = Settings()
