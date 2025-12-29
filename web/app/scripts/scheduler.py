import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from app import create_app
from app.services.coingecko import CoinGeckoClient
from app.services.price_updater import update_daily_prices


def run_update(app, as_of_date) -> None:
    with app.app_context():
        client = CoinGeckoClient(
            app.config["COINGECKO_BASE_URL"],
            retry_count=app.config["COINGECKO_RETRY_COUNT"],
            retry_delay=app.config["COINGECKO_RETRY_DELAY"],
            api_key=app.config["COINGECKO_API_KEY"],
            api_key_header=app.config["COINGECKO_API_KEY_HEADER"],
        )
        vs_currency = app.config["COINGECKO_VS_CURRENCY"]
        request_delay = app.config["COINGECKO_REQUEST_DELAY"]
        result = update_daily_prices(
            client, vs_currency=vs_currency, as_of=as_of_date, request_delay=request_delay
        )
        updated = result.get("updated", 0)
        inserted = result.get("inserted", 0)
        errors = result.get("errors", [])
        timestamp = datetime.utcnow().isoformat()
        print(
            (
                f"[{timestamp}] Updated {updated} cryptos through {as_of_date}; "
                f"prices inserted: {inserted}; errors: {len(errors)}"
            ),
            flush=True,
        )


def main() -> None:
    app = create_app()
    tz_name = os.environ.get("SCHEDULER_TIMEZONE", "UTC")
    hour_raw = os.environ.get("SCHEDULE_HOUR", "0")
    minute_raw = os.environ.get("SCHEDULE_MINUTE", "0")
    run_on_start = os.environ.get("SCHEDULE_RUN_ON_START", "0")
    offset_raw = os.environ.get("SCHEDULE_OFFSET_DAYS", "1")

    hour = int(hour_raw) if hour_raw.isdigit() else 0
    minute = int(minute_raw) if minute_raw.isdigit() else 0
    offset_days = int(offset_raw) if offset_raw.isdigit() else 1
    if offset_days < 0:
        offset_days = 0

    tz = ZoneInfo(tz_name)
    scheduler = BlockingScheduler(timezone=tz)
    scheduler.add_job(
        lambda: run_update(app, (datetime.now(tz).date() - timedelta(days=offset_days))),
        "cron",
        hour=hour,
        minute=minute,
        id="daily_price_update",
        replace_existing=True,
    )

    if run_on_start == "1":
        run_update(app, (datetime.now(tz).date() - timedelta(days=offset_days)))

    print(
        f"Scheduler started (daily at {hour:02d}:{minute:02d} {tz_name}, "
        f"offset {offset_days} day(s))",
        flush=True,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
