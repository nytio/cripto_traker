import os


class Config:
    def __init__(self) -> None:
        self.SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
        self.DATABASE_URL = os.environ.get("DATABASE_URL", "")
        self.COINGECKO_BASE_URL = os.environ.get(
            "COINGECKO_BASE_URL", "https://api.coingecko.com/api/v3"
        )
        self.COINGECKO_VS_CURRENCY = os.environ.get("COINGECKO_VS_CURRENCY", "usd")
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
        self.WTF_CSRF_TIME_LIMIT = 3600
        self.SESSION_COOKIE_HTTPONLY = True
        self.SESSION_COOKIE_SAMESITE = "Lax"
