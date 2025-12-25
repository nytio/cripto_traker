from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import logging
import math
from typing import Any, Type

import numpy as np
import pandas as pd
from sqlalchemy import delete, select

from ..models import GruForecast, LstmForecast

try:
    from darts import TimeSeries
    from darts.dataprocessing.transformers import Scaler
    from darts.models import RNNModel
    from pytorch_lightning.callbacks import EarlyStopping
except ImportError:  # pragma: no cover - optional dependency fallback
    TimeSeries = None
    RNNModel = None
    Scaler = None
    EarlyStopping = None

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


def _extract_points(series) -> list[tuple[date, float]]:
    values = series.values().reshape(-1)
    dates = series.time_index
    return [
        (timestamp.date(), float(value)) for timestamp, value in zip(dates, values)
    ]


def _train_rnn(series, model_type: str, horizon_days: int, future_covariates=None):
    series_len = len(series)
    output_chunk = 1
    input_chunk = max(5, min(30, series_len // 4))
    if input_chunk + output_chunk > series_len:
        input_chunk = max(3, series_len - output_chunk)

    trainer_kwargs = {
        "accelerator": "cpu",
        "logger": False,
        "enable_progress_bar": False,
    }
    if EarlyStopping is not None:
        trainer_kwargs["callbacks"] = [
            EarlyStopping(monitor="train_loss", patience=10)
        ]

    model = RNNModel(
        model=model_type,
        input_chunk_length=input_chunk,
        output_chunk_length=output_chunk,
        n_epochs=100,
        batch_size=32,
        dropout=0.1,
        random_state=42,
        pl_trainer_kwargs=trainer_kwargs,
    )
    model.fit(series, future_covariates=future_covariates, verbose=False)
    return model, input_chunk


def _compute_forecast(
    rows: list[dict[str, Any]], model_type: str, horizon_days: int
) -> list[dict[str, Any]]:
    if TimeSeries is None or RNNModel is None:
        logger.warning("Darts no esta disponible; omitiendo forecast %s.", model_type)
        return []
    if horizon_days <= 0 or len(rows) < 5:
        return []

    price_df = _build_price_frame(rows)
    if price_df is None or len(price_df) < 6:
        return []
    series = _build_return_series(price_df)
    if series is None or len(series) < 5:
        return []
    scaler = Scaler() if Scaler is not None else None
    scaled_series = scaler.fit_transform(series) if scaler else series
    covariates = _build_covariates(rows, horizon_days)

    model, input_chunk = _train_rnn(
        scaled_series, model_type, horizon_days, future_covariates=covariates
    )
    historical = model.historical_forecasts(
        scaled_series,
        future_covariates=covariates,
        start=input_chunk,
        forecast_horizon=1,
        stride=1,
        retrain=False,
    )
    historical_points: list[tuple[date, float]] = []
    for forecast in historical:
        adjusted = scaler.inverse_transform(forecast) if scaler else forecast
        historical_points.extend(_extract_points(adjusted))

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

    future = model.predict(horizon_days, future_covariates=covariates)
    adjusted_future = scaler.inverse_transform(future) if scaler else future
    future_points = _extract_points(adjusted_future)

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


def _store_forecast(
    session,
    table: Type[LstmForecast] | Type[GruForecast],
    crypto_id: int,
    rows: list[dict[str, Any]],
    horizon_days: int,
    model_type: str,
) -> int:
    if horizon_days <= 0 or len(rows) < 5:
        return 0
    cutoff_date = rows[-1]["date"]
    forecast = _compute_forecast(rows, model_type, horizon_days)
    if not forecast:
        return 0

    session.execute(delete(table).where(table.crypto_id == crypto_id))

    records = []
    for row in forecast:
        records.append(
            table(
                crypto_id=crypto_id,
                date=row["date"],
                yhat=_to_decimal(row.get("yhat")),
                yhat_lower=_to_decimal(row.get("yhat_lower")),
                yhat_upper=_to_decimal(row.get("yhat_upper")),
                cutoff_date=cutoff_date,
                horizon_days=horizon_days,
            )
        )

    session.add_all(records)
    session.commit()
    return len(records)


def store_lstm_forecast(
    session, crypto_id: int, rows: list[dict[str, Any]], horizon_days: int
) -> int:
    return _store_forecast(session, LstmForecast, crypto_id, rows, horizon_days, "LSTM")


def store_gru_forecast(
    session, crypto_id: int, rows: list[dict[str, Any]], horizon_days: int
) -> int:
    return _store_forecast(session, GruForecast, crypto_id, rows, horizon_days, "GRU")


def _fetch_forecast(
    session,
    table: Type[LstmForecast] | Type[GruForecast],
    crypto_id: int,
    start_date: date | None,
) -> list[dict[str, Any]]:
    stmt = select(table).where(table.crypto_id == crypto_id)
    if start_date is not None:
        stmt = stmt.where(table.date >= start_date)
    stmt = stmt.order_by(table.date.asc())
    rows = session.execute(stmt).scalars().all()
    return [
        {
            "date": row.date.isoformat(),
            "yhat": float(row.yhat) if row.yhat is not None else None,
            "yhat_lower": float(row.yhat_lower) if row.yhat_lower is not None else None,
            "yhat_upper": float(row.yhat_upper) if row.yhat_upper is not None else None,
        }
        for row in rows
    ]


def _fetch_meta(
    session, table: Type[LstmForecast] | Type[GruForecast], crypto_id: int
) -> tuple[date | None, int | None]:
    row = session.execute(
        select(table.cutoff_date, table.horizon_days)
        .where(table.crypto_id == crypto_id)
        .order_by(table.created_at.desc())
        .limit(1)
    ).first()
    if not row:
        return None, None
    return row[0], row[1]


def fetch_lstm_forecast(
    session, crypto_id: int, start_date: date | None
) -> list[dict[str, Any]]:
    return _fetch_forecast(session, LstmForecast, crypto_id, start_date)


def fetch_gru_forecast(
    session, crypto_id: int, start_date: date | None
) -> list[dict[str, Any]]:
    return _fetch_forecast(session, GruForecast, crypto_id, start_date)


def fetch_lstm_meta(
    session, crypto_id: int
) -> tuple[date | None, int | None]:
    return _fetch_meta(session, LstmForecast, crypto_id)


def fetch_gru_meta(
    session, crypto_id: int
) -> tuple[date | None, int | None]:
    return _fetch_meta(session, GruForecast, crypto_id)
