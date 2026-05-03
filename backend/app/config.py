from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    DATABASE_URL: str
    SECRET_KEY: str
    tablesys_initial_user_password: str = Field(default="", alias="TABLESYS_INITIAL_USER_PASSWORD")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours for better UX

    # ── Super Admin (Platform Owner) Seed Credentials ────────────────────
    # Set these in .env — the account is auto-created on first startup if
    # no SUPERADMIN exists. Leave blank to skip auto-seeding.
    SUPERADMIN_USERNAME: str = ""
    SUPERADMIN_EMAIL: str = ""
    SUPERADMIN_PASSWORD: str = ""

    # ── University / Institution Identity ────────────────────────────────────
    # Set these per-deployment so the system works for any university.
    UNIVERSITY_NAME: str = "TABLESYS Platform"
    UNIVERSITY_SHORT_NAME: str = "TABLESYS"
    UNIVERSITY_EMAIL_DOMAIN: str = "tablesys.cloud"
    APP_TITLE: str = "TABLESYS — Timetable Management System"
    FRONTEND_URL: str = ""          # e.g. https://timetable.youruni.ac.zm

    # Rate Limiting Configuration
    RATE_LIMIT_MAX_ATTEMPTS: int = 5
    RATE_LIMIT_WINDOW_SECONDS: int = 300  # 5 minutes
    RATE_LIMIT_BLOCK_DURATION: int = 300  # 5 minutes

    # Redis / Celery Configuration
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_TASK_ALWAYS_EAGER: bool = False  # Set True in test env to run tasks synchronously

    # Email Configuration
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_ENABLED: bool = False  # Set to True when SMTP is configured

    # NOTE: SMTP_FROM_EMAIL / SMTP_FROM_NAME are @property (not pydantic fields)
    # because @cached_property is not compatible with BaseSettings.
    # They are derived automatically from UNIVERSITY_EMAIL_DOMAIN / UNIVERSITY_SHORT_NAME
    # but can still be overridden by the subclass or env vars if needed.
    @property
    def SMTP_FROM_EMAIL(self) -> str:
        return f"noreply@{self.UNIVERSITY_EMAIL_DOMAIN}"

    @property
    def SMTP_FROM_NAME(self) -> str:
        return f"{self.UNIVERSITY_SHORT_NAME} Timetable System"

    # ── SSO / OAuth2 ─────────────────────────────────────────────────────────
    # Set SSO_ENABLED=true and configure at least one provider to surface
    # SSO buttons on the Login page.  All fields are OPTIONAL — the system
    # gracefully falls back to password-only login if these are blank.
    SSO_ENABLED: bool = False

    # Google OAuth2
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Microsoft Entra ID (Azure AD)
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    # "common" allows any MS organisation; set to your tenant UUID to restrict
    MICROSOFT_TENANT_ID: str = "common"

    # Base URL of THIS backend (used to build the redirect_uri sent to providers)
    # e.g. https://api.youruni.tablesys.com  or  http://localhost:8000
    SSO_REDIRECT_BASE_URL: str = "http://localhost:8000"

    # Where to send the user after a successful SSO login (frontend URL + path)
    SSO_FRONTEND_CALLBACK: str = "http://localhost:5173/sso/callback"

    # Environment
    ENVIRONMENT: str = "development"  # "development" or "production"

    def validate_security(self):
        """Validate security settings"""
        normalized_secret = self.SECRET_KEY.strip().lower()
        placeholder_markers = ["change-me", "your-secret-key", "example", "placeholder"]

        if len(self.SECRET_KEY.strip()) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters for security")
        if any(marker in normalized_secret for marker in placeholder_markers):
            raise ValueError("SECRET_KEY appears to be a placeholder. Set a generated random key.")
        if self.ALGORITHM not in ["HS256", "HS384", "HS512"]:
            raise ValueError("Invalid ALGORITHM. Use HS256, HS384, or HS512")

settings = Settings()
settings.validate_security()
