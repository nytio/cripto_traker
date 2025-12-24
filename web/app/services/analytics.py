import logging
from functools import lru_cache
from typing import Any

import duckdb
import pandas as pd

try:
    from prophet import Prophet
except ImportError:  # pragma: no cover - optional dependency fallback
    Prophet = None

try:
    from cmdstanpy import cmdstan_path
except ImportError:  # pragma: no cover - optional dependency fallback
    cmdstan_path = None

logger = logging.getLogger(__name__)


def compute_indicators(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])

    con = duckdb.connect()
    con.register("prices", df)
    result = con.execute(
        """
        select
            date,
            price,
            avg(price) over (order by date rows between 6 preceding and current row) as sma_7,
            avg(price) over (order by date rows between 29 preceding and current row) as sma_30,
            avg(price) over (order by date rows between 19 preceding and current row) as sma_20,
            stddev_samp(price) over (order by date rows between 19 preceding and current row) as std_20
        from prices
        order by date
        """
    ).df()
    con.close()

    result["bb_upper"] = result["sma_20"] + (result["std_20"] * 2)
    result["bb_lower"] = result["sma_20"] - (result["std_20"] * 2)

    result["date"] = result["date"].dt.strftime("%Y-%m-%d")
    result = result.astype(object).where(pd.notnull(result), None)
    return result.to_dict(orient="records")


@lru_cache(maxsize=1)
def _prophet_ready() -> bool:
    if Prophet is None:
        logger.warning("Prophet no esta disponible; omitiendo pronostico.")
        return False
    if cmdstan_path is None:
        logger.warning("CmdStanPy no esta disponible; omitiendo pronostico.")
        return False
    try:
        cmdstan_path()
    except Exception as exc:
        logger.warning("CmdStan no instalado (%s); omitiendo pronostico.", exc)
        return False
    return True


def compute_prophet_forecast(
    rows: list[dict[str, Any]], horizon_days: int
) -> list[dict[str, Any]]:
    if horizon_days <= 0 or len(rows) < 2 or not _prophet_ready():
        return []

    df = pd.DataFrame(rows)
    if df.empty or "price" not in df:
        return []

    df = df.dropna(subset=["price"])
    if len(df) < 2:
        return []

    df["date"] = pd.to_datetime(df["date"])
    df = df.rename(columns={"date": "ds", "price": "y"}).sort_values("ds")

    try:
        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=True,
            stan_backend="CMDSTANPY",
        )
        model.fit(df)
    except Exception as exc:
        logger.warning(
            "Fallo el ajuste de Prophet (%s); omitiendo pronostico.", exc
        )
        return []

    future = model.make_future_dataframe(periods=horizon_days, freq="D")
    forecast = model.predict(future)
    forecast = forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]
    forecast["date"] = forecast["ds"].dt.strftime("%Y-%m-%d")
    forecast = forecast.drop(columns=["ds"])
    forecast = forecast.astype(object).where(pd.notnull(forecast), None)
    return forecast.to_dict(orient="records")


def merge_prophet_forecast(
    series: list[dict[str, Any]], forecast: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not forecast:
        return series

    base_row = {}
    if series:
        base_row = {key: None for key in series[0].keys() if key != "date"}

    series_map = {row["date"]: row for row in series}
    for row in forecast:
        date_key = row["date"]
        existing = series_map.get(date_key)
        if existing is not None:
            existing.update(row)
        else:
            merged = {"date": date_key, **base_row}
            merged.update(row)
            series_map[date_key] = merged

    return [series_map[date_key] for date_key in sorted(series_map)]
