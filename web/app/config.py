import os


class Config:
    def __init__(self) -> None:
        self.SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
        self.DATABASE_URL = os.environ.get("DATABASE_URL", "")
        self.COINGECKO_BASE_URL = os.environ.get(
            "COINGECKO_BASE_URL", "https://api.coingecko.com/api/v3"
        )
        vs_currency = os.environ.get("COINGECKO_VS_CURRENCY", "").strip()
        self.COINGECKO_VS_CURRENCY = (vs_currency or "usd").lower()
        max_days_raw = os.environ.get("MAX_HISTORY_DAYS", "")
        self.MAX_HISTORY_DAYS = int(max_days_raw) if max_days_raw.isdigit() else 365
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
        self.WTF_CSRF_TIME_LIMIT = 3600
        self.SESSION_COOKIE_HTTPONLY = True
        self.SESSION_COOKIE_SAMESITE = "Lax"
