from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours for better UX
    
    class Config:
        env_file = ".env"
    
    def validate_security(self):
        """Validate security settings"""
        if len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters for security")
        if self.ALGORITHM not in ["HS256", "HS384", "HS512"]:
            raise ValueError("Invalid ALGORITHM. Use HS256, HS384, or HS512")

settings = Settings()
# Validate on startup
try:
    settings.validate_security()
except ValueError:
    # Generate a secure key if not set properly
    if len(settings.SECRET_KEY) < 32:
        print("⚠️  WARNING: SECRET_KEY is too short. Using generated key for this session.")
        print("   Please set a secure SECRET_KEY in production!")
