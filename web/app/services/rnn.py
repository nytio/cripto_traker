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
    from darts.models import BlockRNNModel, RNNModel
    import torch
    from pytorch_lightning.callbacks import EarlyStopping
except ImportError:  # pragma: no cover - optional dependency fallback
    TimeSeries = None
    RNNModel = None
    BlockRNNModel = None
    torch = None
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


def _val_covariate_kwargs(model, covariates) -> dict[str, Any]:
    base = _covariate_kwargs(model, covariates)
    if "future_covariates" in base:
        return {"val_future_covariates": base["future_covariates"]}
    if "past_covariates" in base:
        return {"val_past_covariates": base["past_covariates"]}
    return {}


def _min_required_length(
    model_kind: str,
    input_chunk_length: int,
    output_chunk_length: int,
    training_length: int,
) -> int:
    if model_kind == "rnn":
        base = max(input_chunk_length, training_length)
        return base + max(1, output_chunk_length)
    return input_chunk_length + max(1, output_chunk_length)


def _resolve_val_split(
    desired: float, series_len: int, min_required: int
) -> float:
    if desired <= 0 or series_len <= 0:
        return 0.0
    ratio = min(0.5, max(0.0, desired))
    if min_required <= 0:
        return ratio
    min_ratio = min_required / series_len
    max_ratio = (series_len - min_required) / series_len
    if min_ratio > max_ratio or max_ratio <= 0:
        return 0.0
    if ratio < min_ratio:
        ratio = min_ratio
    if ratio > max_ratio:
        ratio = max_ratio
    val_len = int(series_len * ratio)
    train_len = series_len - val_len
    if val_len < min_required or train_len < min_required:
        return 0.0
    return ratio


def _split_series(series, val_split: float):
    if val_split <= 0:
        return series, None
    ratio = min(0.5, max(0.0, val_split))
    if ratio <= 0:
        return series, None
    train, val = series.split_before(1 - ratio)
    return train, val if len(val) else None


def _extract_points(series) -> list[tuple[date, float]]:
    values = series.values().reshape(-1)
    dates = series.time_index
    return [
        (timestamp.date(), float(value)) for timestamp, value in zip(dates, values)
    ]


def _resolve_chunk_lengths(
    series_len: int, input_chunk_length: int, output_chunk_length: int
) -> tuple[int, int]:
    min_input = 5
    output_chunk = max(1, output_chunk_length)
    if series_len - output_chunk < min_input:
        output_chunk = max(1, series_len - min_input)
    input_chunk = min(input_chunk_length, series_len - output_chunk)
    input_chunk = max(min_input, input_chunk)
    if input_chunk + output_chunk > series_len:
        input_chunk = max(3, series_len - output_chunk)
    return input_chunk, output_chunk


def _resolve_training_length(
    series_len: int, input_chunk: int, training_length: int
) -> int:
    return max(input_chunk, min(training_length, series_len))


def _train_rnn(
    series,
    model_type: str,
    horizon_days: int,
    covariates=None,
    model_kind: str = "rnn",
    input_chunk_length: int = 180,
    training_length: int = 210,
    output_chunk_length: int = 30,
    hidden_dim: int = 64,
    n_rnn_layers: int = 2,
    hidden_fc_sizes: list[int] | None = None,
    val_split: float = 0.2,
):
    series_len = len(series)
    output_chunk = 1 if model_kind == "rnn" else max(1, output_chunk_length)
    input_chunk, output_chunk = _resolve_chunk_lengths(
        series_len, input_chunk_length, output_chunk
    )
    if model_kind == "rnn":
        training_length = _resolve_training_length(
            series_len, input_chunk, training_length
        )
        if training_length <= input_chunk:
            training_length = min(series_len, input_chunk + max(1, horizon_days))

    base_input_chunk = input_chunk
    base_output_chunk = output_chunk
    base_training_length = training_length

    min_required = _min_required_length(
        model_kind,
        input_chunk,
        output_chunk,
        training_length,
    )
    effective_val_split = _resolve_val_split(
        val_split, series_len, min_required
    )
    train_series, val_series = _split_series(series, effective_val_split)
    train_covariates = covariates
    val_covariates = None
    if covariates is not None and val_series is not None:
        split_point = val_series.time_index[0]
        train_covariates, val_covariates = covariates.split_before(
            split_point
        )
    if len(train_series) < 5:
        train_series = series
        val_series = None
        train_covariates = covariates
        val_covariates = None

    train_len = len(train_series)
    input_chunk, output_chunk = _resolve_chunk_lengths(
        train_len, input_chunk, output_chunk
    )
    if model_kind == "rnn":
        training_length = _resolve_training_length(
            train_len, input_chunk, training_length
        )

    min_required = _min_required_length(
        model_kind,
        input_chunk,
        output_chunk,
        training_length,
    )
    if val_series is not None and len(val_series) < min_required:
        train_series = series
        val_series = None
        train_covariates = covariates
        val_covariates = None
        input_chunk = base_input_chunk
        output_chunk = base_output_chunk
        training_length = base_training_length

    trainer_kwargs = {
        "accelerator": "cpu",
        "logger": False,
        "enable_progress_bar": False,
    }
    if EarlyStopping is not None:
        trainer_kwargs["callbacks"] = [
            EarlyStopping(monitor="train_loss", patience=10)
        ]

    dropout = 0.1 if n_rnn_layers > 1 else 0.0
    n_epochs = 200
    batch_size = 64
    model_kwargs = {
        "model": model_type,
        "input_chunk_length": input_chunk,
        "n_epochs": n_epochs,
        "batch_size": batch_size,
        "dropout": dropout,
        "n_rnn_layers": n_rnn_layers,
        "random_state": 42,
        "pl_trainer_kwargs": trainer_kwargs,
    }
    if torch is not None:
        model_kwargs["loss_fn"] = torch.nn.SmoothL1Loss()
        model_kwargs["optimizer_kwargs"] = {
            "lr": 1e-3,
            "weight_decay": 1e-6,
        }
        model_kwargs["lr_scheduler_cls"] = (
            torch.optim.lr_scheduler.ReduceLROnPlateau
        )
        model_kwargs["lr_scheduler_kwargs"] = {
            "factor": 0.5,
            "patience": 10,
            "min_lr": 1e-5,
            "monitor": "train_loss",
        }

    if model_kind == "block":
        if BlockRNNModel is None:
            logger.warning("BlockRNNModel no esta disponible; omitiendo.")
            return None, None, None
        model = BlockRNNModel(
            output_chunk_length=output_chunk,
            hidden_fc_sizes=hidden_fc_sizes,
            hidden_dim=hidden_dim,
            **model_kwargs,
        )
    else:
        model = RNNModel(
            training_length=training_length,
            hidden_dim=hidden_dim,
            **model_kwargs,
        )
    covariate_payload = _covariate_kwargs(model, train_covariates)
    val_covariate_payload = _val_covariate_kwargs(model, val_covariates)
    if val_series is not None:
        try:
            model.fit(
                train_series,
                val_series=val_series,
                **covariate_payload,
                **val_covariate_payload,
                verbose=False,
            )
        except ValueError as exc:
            message = str(exc).lower()
            if "validation time series dataset is too short" in message:
                logger.warning(
                    "Validation set rejected by Darts; retrying without val."
                )
                model.fit(
                    train_series,
                    **covariate_payload,
                    verbose=False,
                )
            else:
                raise
    else:
        model.fit(train_series, **covariate_payload, verbose=False)
    return model, input_chunk, output_chunk


def _compute_forecast(
    rows: list[dict[str, Any]],
    model_type: str,
    horizon_days: int,
    model_kind: str = "rnn",
    input_chunk_length: int = 180,
    training_length: int = 210,
    n_rnn_layers: int = 2,
    output_chunk_length: int = 30,
    hidden_dim: int = 64,
    hidden_fc_sizes: list[int] | None = None,
) -> list[dict[str, Any]]:
    if TimeSeries is None or (
        model_kind == "block" and BlockRNNModel is None
    ) or (model_kind == "rnn" and RNNModel is None):
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

    model, input_chunk, output_chunk = _train_rnn(
        scaled_series,
        model_type,
        horizon_days,
        covariates=covariates,
        model_kind=model_kind,
        input_chunk_length=input_chunk_length,
        training_length=training_length,
        n_rnn_layers=n_rnn_layers,
        output_chunk_length=output_chunk_length,
        hidden_dim=hidden_dim,
        hidden_fc_sizes=hidden_fc_sizes,
    )
    if model is None:
        return []
    forecast_horizon = 1 if model_kind == "rnn" else max(1, output_chunk)
    historical = model.historical_forecasts(
        scaled_series,
        **_covariate_kwargs(model, covariates),
        start=input_chunk,
        forecast_horizon=forecast_horizon,
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

    future = model.predict(
        horizon_days, **_covariate_kwargs(model, covariates)
    )
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
    model_run_id: int | None = None,
    model_kind: str = "rnn",
    input_chunk_length: int = 180,
    training_length: int = 210,
    n_rnn_layers: int = 2,
    output_chunk_length: int = 30,
    hidden_dim: int = 64,
    hidden_fc_sizes: list[int] | None = None,
) -> int:
    if horizon_days <= 0 or len(rows) < 5:
        return 0
    cutoff_date = rows[-1]["date"]
    forecast = _compute_forecast(
        rows,
        model_type,
        horizon_days,
        model_kind=model_kind,
        input_chunk_length=input_chunk_length,
        training_length=training_length,
        n_rnn_layers=n_rnn_layers,
        output_chunk_length=output_chunk_length,
        hidden_dim=hidden_dim,
        hidden_fc_sizes=hidden_fc_sizes,
    )
    if not forecast:
        return 0

    session.execute(delete(table).where(table.crypto_id == crypto_id))

    records = []
    for row in forecast:
        records.append(
            table(
                crypto_id=crypto_id,
                model_run_id=model_run_id,
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
    session,
    crypto_id: int,
    rows: list[dict[str, Any]],
    horizon_days: int,
    model_run_id: int | None = None,
    model_kind: str = "rnn",
    input_chunk_length: int = 180,
    training_length: int = 210,
    n_rnn_layers: int = 2,
    output_chunk_length: int = 30,
    hidden_dim: int = 64,
    hidden_fc_sizes: list[int] | None = None,
) -> int:
    return _store_forecast(
        session,
        LstmForecast,
        crypto_id,
        rows,
        horizon_days,
        "LSTM",
        model_run_id=model_run_id,
        model_kind=model_kind,
        input_chunk_length=input_chunk_length,
        training_length=training_length,
        n_rnn_layers=n_rnn_layers,
        output_chunk_length=output_chunk_length,
        hidden_dim=hidden_dim,
        hidden_fc_sizes=hidden_fc_sizes,
    )


def store_gru_forecast(
    session,
    crypto_id: int,
    rows: list[dict[str, Any]],
    horizon_days: int,
    model_run_id: int | None = None,
    model_kind: str = "rnn",
    input_chunk_length: int = 180,
    training_length: int = 210,
    n_rnn_layers: int = 2,
    output_chunk_length: int = 30,
    hidden_dim: int = 64,
    hidden_fc_sizes: list[int] | None = None,
) -> int:
    return _store_forecast(
        session,
        GruForecast,
        crypto_id,
        rows,
        horizon_days,
        "GRU",
        model_run_id=model_run_id,
        model_kind=model_kind,
        input_chunk_length=input_chunk_length,
        training_length=training_length,
        n_rnn_layers=n_rnn_layers,
        output_chunk_length=output_chunk_length,
        hidden_dim=hidden_dim,
        hidden_fc_sizes=hidden_fc_sizes,
    )


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
