from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import logging
import math
from typing import Any, Type

import numpy as np
import pandas as pd
from sqlalchemy import delete

from ..models import ForecastModelRun, GruForecast, LstmForecast
from ..services.series import fetch_price_series
from .model_registry import load_global_model

try:
    from darts import TimeSeries
except ImportError:  # pragma: no cover - optional dependency fallback
    TimeSeries = None

logger = logging.getLogger(__name__)


def _to_decimal(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _build_price_frame(rows: list[dict[str, Any]]):
    if TimeSeries is None:
        return None
    df = pd.DataFrame(rows)
    if df.empty:
        return None
    df["date"] = pd.to_datetime(df["date"])
    df["price"] = pd.to_numeric(df["price"])
    df = df.sort_values("date")
    df = df.set_index("date").asfreq("D")
    df["price"] = df["price"].ffill()
    df = df.reset_index()
    df["log_price"] = np.log(df["price"])
    df["log_return"] = df["log_price"].diff()
    return df


def _build_return_series(price_df: pd.DataFrame):
    if TimeSeries is None:
        return None
    returns_df = price_df.dropna(subset=["log_return"])
    if returns_df.empty:
        return None
    return TimeSeries.from_dataframe(
        returns_df, time_col="date", value_cols="log_return"
    )


def _build_covariates(rows: list[dict[str, Any]], horizon_days: int):
    if TimeSeries is None:
        return None
    df = pd.DataFrame(rows)
    if df.empty:
        return None
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    start = df["date"].iloc[0]
    end = df["date"].iloc[-1] + pd.Timedelta(days=horizon_days)
    full_dates = pd.date_range(start=start, end=end, freq="D")
    covariates = pd.DataFrame({"date": full_dates})
    covariates["dow"] = covariates["date"].dt.dayofweek
    covariates["doy"] = covariates["date"].dt.dayofyear
    covariates["dow_sin"] = np.sin(2 * np.pi * covariates["dow"] / 7.0)
    covariates["dow_cos"] = np.cos(2 * np.pi * covariates["dow"] / 7.0)
    covariates["doy_sin"] = np.sin(2 * np.pi * covariates["doy"] / 365.25)
    covariates["doy_cos"] = np.cos(2 * np.pi * covariates["doy"] / 365.25)
    return TimeSeries.from_dataframe(
        covariates,
        time_col="date",
        value_cols=["dow_sin", "dow_cos", "doy_sin", "doy_cos"],
    )


def _covariate_kwargs(model, covariates) -> dict[str, Any]:
    if covariates is None:
        return {}
    supports_future = bool(
        getattr(model, "supports_future_covariates", False)
    )
    supports_past = bool(getattr(model, "supports_past_covariates", False))
    if supports_future and not supports_past:
        return {"future_covariates": covariates}
    if supports_past and not supports_future:
        return {"past_covariates": covariates}
    if supports_future:
        return {"future_covariates": covariates}
    if supports_past:
        return {"past_covariates": covariates}
    return {}


def _extract_points(series) -> list[tuple[date, float]]:
    values = series.values().reshape(-1)
    dates = series.time_index
    return [
        (timestamp.date(), float(value)) for timestamp, value in zip(dates, values)
    ]


def _store_forecast_rows(
    session,
    table: Type[LstmForecast] | Type[GruForecast],
    crypto_id: int,
    rows: list[dict[str, Any]],
    horizon_days: int,
    cutoff_date: date,
    model_run_id: int | None,
) -> int:
    if horizon_days <= 0 or not rows:
        return 0
    session.execute(delete(table).where(table.crypto_id == crypto_id))

    records = []
    for row in rows:
        records.append(
            table(
                crypto_id=crypto_id,
                date=row["date"],
                yhat=_to_decimal(row.get("yhat")),
                yhat_lower=_to_decimal(row.get("yhat_lower")),
                yhat_upper=_to_decimal(row.get("yhat_upper")),
                cutoff_date=cutoff_date,
                horizon_days=horizon_days,
                model_run_id=model_run_id,
            )
        )
    session.add_all(records)
    session.commit()
    return len(records)


def _compute_forecast(
    model,
    run: ForecastModelRun,
    rows: list[dict[str, Any]],
    horizon_days: int,
) -> list[dict[str, Any]]:
    price_df = _build_price_frame(rows)
    if price_df is None or len(price_df) < 6:
        return []
    series = _build_return_series(price_df)
    if series is None or len(series) < 5:
        return []

    covariates = _build_covariates(rows, horizon_days)
    covariate_payload = _covariate_kwargs(model, covariates)

    input_chunk = int(getattr(model, "input_chunk_length", 1))
    output_chunk = int(getattr(model, "output_chunk_length", 1))
    forecast_horizon = 1 if run.model_family == "RNNModel" else max(1, output_chunk)

    historical = model.historical_forecasts(
        series=series,
        **covariate_payload,
        start=input_chunk,
        forecast_horizon=forecast_horizon,
        stride=1,
        retrain=False,
    )
    historical_points: list[tuple[date, float]] = []
    for forecast in historical:
        historical_points.extend(_extract_points(forecast))

    actual_returns = {
        row["date"].date(): float(row["log_return"])
        for _, row in price_df.dropna(subset=["log_return"]).iterrows()
    }
    residuals = [
        actual_returns[point_date] - prediction
        for point_date, prediction in historical_points
        if point_date in actual_returns
    ]
    sigma = float(np.std(residuals)) if residuals else 0.0
    ci_width = 1.96 * sigma

    future = model.predict(
        horizon_days,
        **covariate_payload,
        series=series,
    )
    future_points = _extract_points(future)

    price_by_date = {
        row["date"].date(): float(row["price"])
        for _, row in price_df.iterrows()
    }
    forecast_rows = []
    seen_dates = set()

    for point_date, prediction in historical_points:
        output_date = point_date - timedelta(days=1)
        if output_date in seen_dates:
            continue
        prev_date = point_date - timedelta(days=1)
        prev_price = price_by_date.get(prev_date)
        if prev_price is None:
            continue
        price_hat = prev_price * math.exp(prediction)
        lower = prev_price * math.exp(prediction - ci_width)
        upper = prev_price * math.exp(prediction + ci_width)
        forecast_rows.append(
            {
                "date": output_date,
                "yhat": price_hat,
                "yhat_lower": lower,
                "yhat_upper": upper,
            }
        )
        seen_dates.add(output_date)

    last_price_date = price_df["date"].iloc[-1].date()
    prev_price = price_by_date.get(last_price_date)
    for point_date, prediction in future_points:
        if prev_price is None:
            break
        output_date = point_date - timedelta(days=1)
        price_hat = prev_price * math.exp(prediction)
        lower = prev_price * math.exp(prediction - ci_width)
        upper = prev_price * math.exp(prediction + ci_width)
        forecast_rows.append(
            {
                "date": output_date,
                "yhat": price_hat,
                "yhat_lower": lower,
                "yhat_upper": upper,
            }
        )
        prev_price = price_hat

    return forecast_rows


def predict_with_global_model(
    session,
    model_run_id: int,
    crypto_id: int,
    horizon_days: int | None = None,
    allow_unseen: bool = True,
) -> list[dict[str, Any]]:
    run = session.get(ForecastModelRun, model_run_id)
    if run is None:
        raise ValueError("Model run not found.")
    if horizon_days is None:
        horizon_days = run.horizon_days
    if not allow_unseen and crypto_id not in (run.training_crypto_ids or []):
        raise ValueError("Crypto not part of the training set.")

    if TimeSeries is None:
        logger.warning("Darts no esta disponible; omitiendo forecast global.")
        return []

    rows = fetch_price_series(session, crypto_id, 0)
    if len(rows) < 5:
        return []

    model = load_global_model(run, prefer="best_checkpoint", map_location="cpu")
    forecast_rows = _compute_forecast(model, run, rows, horizon_days)
    if not forecast_rows:
        return []

    cutoff_date = rows[-1]["date"]
    if run.cell_type == "GRU":
        table = GruForecast
    else:
        table = LstmForecast
    _store_forecast_rows(
        session,
        table,
        crypto_id,
        forecast_rows,
        horizon_days,
        cutoff_date,
        run.id,
    )
    return forecast_rows
