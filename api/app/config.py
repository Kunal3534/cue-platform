from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://cue:cue@db:5432/cue"
    secret_key: str = "dev-change-me"
    frontend_origin: str = "http://localhost:3000"
    dev_auto_login_email: str | None = None
    resend_api_key: str | None = None
    mail_from: str | None = None

    # v1 additions
    redis_url: str = "redis://redis:6379/0"
    s3_endpoint: str = "http://storage:9000"
    s3_bucket: str = "cue-v1"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"
    magic_link_ttl_seconds: int = 900
    env: str = "development"
    # Public base URL the browser reaches the API on (e.g. https://gq.cueit.io/api
    # when the web app proxies). Used to build magic links; falls back to the
    # request's own base URL when unset.
    public_api_url: str | None = None
    # Comma-separated emails allowed to sign in. Empty = anyone (dev default).
    allowed_emails: str = ""
    # Google OAuth ("Sign in with Google" + Calendar sync). Create a Web
    # OAuth client in Google Cloud Console; authorised redirect URI is
    # {PUBLIC_API_URL or API base}/auth/google/callback.
    google_client_id: str | None = None
    google_client_secret: str | None = None

    class Config:
        env_file = ".env"


settings = Settings()
