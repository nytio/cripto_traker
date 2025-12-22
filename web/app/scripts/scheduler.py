import os
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from app import create_app
from app.services.coingecko import CoinGeckoClient
from app.services.price_updater import update_daily_prices


def run_update(app) -> None:
    with app.app_context():
        client = CoinGeckoClient(app.config["COINGECKO_BASE_URL"])
        vs_currency = app.config["COINGECKO_VS_CURRENCY"]
        result = update_daily_prices(client, vs_currency=vs_currency)
        updated = result.get("updated", 0)
        errors = result.get("errors", [])
        timestamp = datetime.utcnow().isoformat()
        print(f"[{timestamp}] Updated {updated} cryptos; errors: {len(errors)}", flush=True)


def main() -> None:
    app = create_app()
    tz_name = os.environ.get("SCHEDULER_TIMEZONE", "UTC")
    hour_raw = os.environ.get("SCHEDULE_HOUR", "0")
    minute_raw = os.environ.get("SCHEDULE_MINUTE", "0")
    run_on_start = os.environ.get("SCHEDULE_RUN_ON_START", "0")

    hour = int(hour_raw) if hour_raw.isdigit() else 0
    minute = int(minute_raw) if minute_raw.isdigit() else 0

    scheduler = BlockingScheduler(timezone=ZoneInfo(tz_name))
    scheduler.add_job(
        lambda: run_update(app),
        "cron",
        hour=hour,
        minute=minute,
        id="daily_price_update",
        replace_existing=True,
    )

    if run_on_start == "1":
        run_update(app)

    print(
        f"Scheduler started (daily at {hour:02d}:{minute:02d} {tz_name})",
        flush=True,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
