import os


class Config:
    def __init__(self) -> None:
        self.SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
        self.DATABASE_URL = os.environ.get("DATABASE_URL", "")
        base_url_raw = os.environ.get("COINGECKO_BASE_URL", "").strip()
        if not base_url_raw:
            base_url_raw = "https://api.coingecko.com/api/v3"
        base_url = base_url_raw.split("?", 1)[0].split("#", 1)[0].rstrip("/")
        self.COINGECKO_BASE_URL = base_url or "https://api.coingecko.com/api/v3"
        api_key = os.environ.get("COINGECKO_API_KEY", "").strip()
        self.COINGECKO_API_KEY = api_key
        api_key_header_raw = os.environ.get("COINGECKO_API_KEY_HEADER", "").strip()
        api_key_header = api_key_header_raw.lower().replace("_", "-")
        if api_key_header:
            self.COINGECKO_API_KEY_HEADER = api_key_header
        elif "pro-api.coingecko.com" in self.COINGECKO_BASE_URL:
            self.COINGECKO_API_KEY_HEADER = "x-cg-pro-api-key"
        else:
            self.COINGECKO_API_KEY_HEADER = "x-cg-demo-api-key"
        vs_currency = os.environ.get("COINGECKO_VS_CURRENCY", "").strip()
        self.COINGECKO_VS_CURRENCY = (vs_currency or "usd").lower()
        max_days_raw = os.environ.get("MAX_HISTORY_DAYS", "")
        self.MAX_HISTORY_DAYS = (
            int(max_days_raw) if max_days_raw.isdigit() else 3650
        )
        delay_raw = os.environ.get("COINGECKO_REQUEST_DELAY", "1.1").strip()
        try:
            self.COINGECKO_REQUEST_DELAY = float(delay_raw)
        except ValueError:
            self.COINGECKO_REQUEST_DELAY = 1.1
        retry_count_raw = os.environ.get("COINGECKO_RETRY_COUNT", "2").strip()
        self.COINGECKO_RETRY_COUNT = (
            int(retry_count_raw) if retry_count_raw.isdigit() else 2
        )
        retry_delay_raw = os.environ.get("COINGECKO_RETRY_DELAY", "1.0").strip()
        try:
            self.COINGECKO_RETRY_DELAY = float(retry_delay_raw)
        except ValueError:
            self.COINGECKO_RETRY_DELAY = 1.0
        coincap_base_url_raw = os.environ.get("COINCAP_BASE_URL", "").strip()
        if not coincap_base_url_raw:
            coincap_base_url_raw = "https://api.coincap.io/v2"
        coincap_base_url = (
            coincap_base_url_raw.split("?", 1)[0]
            .split("#", 1)[0]
            .rstrip("/")
        )
        self.COINCAP_BASE_URL = coincap_base_url or "https://api.coincap.io/v2"
        self.COINCAP_API_KEY = os.environ.get("COINCAP_API_KEY", "").strip()
        coincap_delay_raw = os.environ.get("COINCAP_REQUEST_DELAY", "1.1").strip()
        try:
            self.COINCAP_REQUEST_DELAY = float(coincap_delay_raw)
        except ValueError:
            self.COINCAP_REQUEST_DELAY = 1.1
        coincap_retry_raw = os.environ.get("COINCAP_RETRY_COUNT", "2").strip()
        self.COINCAP_RETRY_COUNT = (
            int(coincap_retry_raw) if coincap_retry_raw.isdigit() else 2
        )
        coincap_retry_delay_raw = os.environ.get("COINCAP_RETRY_DELAY", "1.0").strip()
        try:
            self.COINCAP_RETRY_DELAY = float(coincap_retry_delay_raw)
        except ValueError:
            self.COINCAP_RETRY_DELAY = 1.0
        prophet_days_raw = os.environ.get("PROPHET_FUTURE_DAYS", "30").strip()
        self.PROPHET_FUTURE_DAYS = (
            int(prophet_days_raw) if prophet_days_raw.isdigit() else 30
        )
        rnn_days_raw = os.environ.get("RNN_FUTURE_DAYS", "30").strip()
        self.RNN_FUTURE_DAYS = int(rnn_days_raw) if rnn_days_raw.isdigit() else 30
        self.LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
        self.WTF_CSRF_TIME_LIMIT = 3600
        self.SESSION_COOKIE_HTTPONLY = True
        self.SESSION_COOKIE_SAMESITE = "Lax"
