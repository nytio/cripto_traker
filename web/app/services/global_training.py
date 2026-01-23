from __future__ import annotations

from datetime import date
import logging
import os
from typing import Any

import numpy as np
import pandas as pd

from ..services.series import fetch_price_series
from ..models import ForecastModelRun
from .model_registry import canonical_model_key, create_model_run

try:
    from darts import TimeSeries
    from darts.models import BlockRNNModel, RNNModel
    import torch
    from pytorch_lightning.callbacks import EarlyStopping, ModelCheckpoint
except ImportError:  # pragma: no cover - optional dependency fallback
    TimeSeries = None
    BlockRNNModel = None
    RNNModel = None
    torch = None
    EarlyStopping = None
    ModelCheckpoint = None

logger = logging.getLogger(__name__)


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


def _series_width(series) -> int | None:
    if series is None:
        return None
    width = getattr(series, "width", None)
    if width is not None:
        return width
    return getattr(series, "n_components", None)


def _min_required_length(
    model_family: str,
    input_chunk_length: int,
    output_chunk_length: int,
    training_length: int,
) -> int:
    if model_family == "RNNModel":
        base = max(input_chunk_length, training_length)
        return base + max(1, output_chunk_length)
    return input_chunk_length + max(1, output_chunk_length)


def _resolve_val_split(
    desired: float, min_series_len: int, min_required: int
) -> float:
    if desired <= 0 or min_series_len <= 0:
        return 0.0
    ratio = min(0.5, max(0.0, desired))
    if min_required <= 0:
        return ratio
    min_ratio = min_required / min_series_len
    max_ratio = (min_series_len - min_required) / min_series_len
    if min_ratio > max_ratio or max_ratio <= 0:
        return 0.0
    if ratio < min_ratio:
        ratio = min_ratio
    if ratio > max_ratio:
        ratio = max_ratio
    val_len = int(min_series_len * ratio)
    train_len = min_series_len - val_len
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


def train_global_model(
    session,
    model_family: str,
    cell_type: str,
    hyperparams: dict[str, Any],
    crypto_ids: list[int],
    horizon_days: int = 30,
    transform: str = "log_return",
    warm_start_run: ForecastModelRun | None = None,
    warm_start_mode: str | None = None,
    training_days: int = 0,
    update_run: ForecastModelRun | None = None,
) -> ForecastModelRun:
    if TimeSeries is None or RNNModel is None or BlockRNNModel is None:
        raise RuntimeError("Darts no esta disponible; omitiendo entrenamiento.")
    if not crypto_ids:
        raise ValueError("No crypto ids provided for training.")

    hyperparams = dict(hyperparams or {})
    requested_val_split = float(hyperparams.get("val_split", 0.2))

    series_payloads = []
    for crypto_id in crypto_ids:
        rows = fetch_price_series(session, crypto_id, training_days)
        price_df = _build_price_frame(rows)
        if price_df is None or len(price_df) < 6:
            continue
        series = _build_return_series(price_df)
        if series is None or len(series) < 6:
            continue
        covariates = _build_covariates(rows, horizon_days)
        series_payloads.append(
            {
                "crypto_id": crypto_id,
                "series": series,
                "covariates": covariates,
                "cutoff_date": price_df["date"].iloc[-1].date(),
            }
        )

    if not series_payloads:
        raise ValueError("Not enough data to train a global model.")

    base_input_chunk_length = int(hyperparams.get("input_chunk_length", 180))
    base_output_chunk_length = int(
        hyperparams.get("output_chunk_length", horizon_days)
    )
    base_training_length = int(
        hyperparams.get(
            "training_length", base_input_chunk_length + horizon_days
        )
    )
    n_rnn_layers = int(hyperparams.get("n_rnn_layers", 2))
    hidden_dim = int(hyperparams.get("hidden_dim", 64))
    hidden_fc_sizes = hyperparams.get("hidden_fc_sizes", [64, 32])
    n_epochs = int(hyperparams.get("n_epochs", 200))
    batch_size = int(hyperparams.get("batch_size", 64))
    random_state = int(hyperparams.get("random_state", 42))

    output_for_chunks = base_output_chunk_length
    if model_family == "RNNModel":
        output_for_chunks = 1

    def _resolve_sizing(
        min_len: int,
    ) -> tuple[int, int, int, int, float]:
        input_chunk_length = base_input_chunk_length
        output_chunk_length = base_output_chunk_length
        training_length = base_training_length

        input_chunk, output_chunk = _resolve_chunk_lengths(
            min_len, input_chunk_length, output_for_chunks
        )
        input_chunk_length = input_chunk
        output_chunk_length = output_chunk
        if model_family == "RNNModel":
            training_length = _resolve_training_length(
                min_len, input_chunk_length, training_length
            )

        min_required = _min_required_length(
            model_family,
            input_chunk_length,
            output_chunk_length,
            training_length,
        )
        val_split = _resolve_val_split(
            requested_val_split, min_len, min_required
        )
        min_train_len = (
            int(min_len * (1 - val_split)) if val_split > 0 else min_len
        )
        if min_train_len < min_len:
            input_chunk, output_chunk = _resolve_chunk_lengths(
                min_train_len, input_chunk_length, output_for_chunks
            )
            input_chunk_length = input_chunk
            output_chunk_length = output_chunk
            if model_family == "RNNModel":
                training_length = _resolve_training_length(
                    min_train_len, input_chunk_length, training_length
                )
        min_required = _min_required_length(
            model_family,
            input_chunk_length,
            output_chunk_length,
            training_length,
        )
        return (
            input_chunk_length,
            output_chunk_length,
            training_length,
            min_required,
            val_split,
        )

    filtered_payloads = series_payloads
    while True:
        min_series_len = min(
            len(payload["series"]) for payload in filtered_payloads
        )
        (
            input_chunk_length,
            output_chunk_length,
            training_length,
            min_required,
            val_split,
        ) = _resolve_sizing(min_series_len)
        kept_payloads = []
        for payload in filtered_payloads:
            train_series, _ = _split_series(payload["series"], val_split)
            if len(train_series) < 5:
                continue
            kept_payloads.append(payload)
        if not kept_payloads:
            raise ValueError("Not enough data to train a global model.")
        if len(kept_payloads) == len(filtered_payloads):
            series_payloads = kept_payloads
            break
        filtered_payloads = kept_payloads

    train_series_list = []
    val_series_list = []
    train_covariates_list = []
    val_covariates_list = []
    used_crypto_ids: list[int] = []
    train_start_date: date | None = None
    train_end_date: date | None = None
    cutoff_date: date | None = None

    for payload in series_payloads:
        series = payload["series"]
        train_series, val_series = _split_series(series, val_split)
        covariates = payload["covariates"]
        if covariates is not None and val_series is not None:
            split_point = val_series.time_index[0]
            train_covariates, val_covariates = covariates.split_before(
                split_point
            )
        else:
            train_covariates = covariates
            val_covariates = None
        train_series_list.append(train_series)
        val_series_list.append(val_series)
        train_covariates_list.append(train_covariates)
        val_covariates_list.append(val_covariates)
        used_crypto_ids.append(payload["crypto_id"])

        start_date = train_series.time_index[0].date()
        end_date = train_series.time_index[-1].date()
        series_cutoff = payload["cutoff_date"]
        train_start_date = (
            start_date
            if train_start_date is None
            else min(train_start_date, start_date)
        )
        train_end_date = (
            end_date if train_end_date is None else max(train_end_date, end_date)
        )
        cutoff_date = (
            series_cutoff
            if cutoff_date is None
            else max(cutoff_date, series_cutoff)
        )

    if not train_series_list:
        raise ValueError("Not enough data to train a global model.")

    effective_hyperparams = {
        "input_chunk_length": input_chunk_length,
        "output_chunk_length": output_chunk_length,
        "training_length": training_length,
        "n_rnn_layers": n_rnn_layers,
        "hidden_dim": hidden_dim,
        "hidden_fc_sizes": hidden_fc_sizes,
        "n_epochs": n_epochs,
        "batch_size": batch_size,
        "random_state": random_state,
        "val_split": val_split,
        "save_checkpoints": True,
    }

    model_name, work_dir, artifact_path_pt = canonical_model_key(
        "global_shared",
        model_family,
        cell_type,
        horizon_days,
        transform,
        effective_hyperparams,
    )
    if update_run is not None:
        if update_run.model_name:
            model_name = update_run.model_name
        if update_run.work_dir:
            work_dir = update_run.work_dir
        if update_run.artifact_path_pt:
            artifact_path_pt = update_run.artifact_path_pt
    model_dir = os.path.join(work_dir, model_name)
    checkpoints_dir = os.path.join(model_dir, "checkpoints")
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(model_dir, exist_ok=True)
    os.makedirs(os.path.dirname(artifact_path_pt), exist_ok=True)
    os.makedirs(checkpoints_dir, exist_ok=True)

    trainer_kwargs = {
        "accelerator": "cpu",
        "logger": False,
        "enable_progress_bar": False,
        "enable_checkpointing": False,
    }
    callbacks = []
    if EarlyStopping is not None:
        callbacks.append(EarlyStopping(monitor="train_loss", patience=10))
    if callbacks:
        trainer_kwargs["callbacks"] = callbacks

    dropout = 0.1 if n_rnn_layers > 1 else 0.0
    model_kwargs = {
        "model": cell_type,
        "input_chunk_length": input_chunk_length,
        "n_epochs": n_epochs,
        "batch_size": batch_size,
        "dropout": dropout,
        "n_rnn_layers": n_rnn_layers,
        "random_state": random_state,
        "pl_trainer_kwargs": trainer_kwargs,
        "save_checkpoints": False,
        "model_name": model_name,
        "work_dir": work_dir,
        "force_reset": True,
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

    if model_family == "BlockRNNModel":
        model = BlockRNNModel(
            output_chunk_length=output_chunk_length,
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

    if warm_start_run and warm_start_mode == "weights":
        artifact_path = warm_start_run.artifact_path_pt
        if artifact_path:
            try:
                model.load_weights(artifact_path, map_location="cpu")
            except (FileNotFoundError, ValueError):
                logger.warning(
                    "Warm start weights not found for %s; training from scratch.",
                    warm_start_run.model_name,
                )
        else:
            logger.warning(
                "Warm start artifact missing for %s; training from scratch.",
                warm_start_run.model_name,
            )

    covariate_payload = _covariate_kwargs(
        model,
        train_covariates_list if all(train_covariates_list) else None,
    )
    val_covariate_payload = _val_covariate_kwargs(
        model,
        val_covariates_list if all(val_covariates_list) else None,
    )
    use_val = all(series is not None for series in val_series_list)
    if use_val and any(len(series) < min_required for series in val_series_list):
        logger.warning("Validation split too short; skipping val.")
        use_val = False
    if use_val and all(train_covariates_list) and not all(val_covariates_list):
        logger.warning("Validation covariates incomplete; skipping val.")
        use_val = False
    if use_val:
        same_dims = all(
            _series_width(val) == _series_width(train)
            for train, val in zip(train_series_list, val_series_list)
        )
        if not same_dims:
            logger.warning(
                "Validation series dimensions do not match training; skipping val."
            )
            use_val = False
    if use_val:
        actual_use_val = True
        try:
            model.fit(
                train_series_list,
                val_series=val_series_list,
                **covariate_payload,
                **val_covariate_payload,
                verbose=False,
            )
        except ValueError as exc:
            message = str(exc)
            retry_messages = (
                "dimensions of the series in the training set",
                "validation time series dataset is too short",
            )
            if any(fragment in message.lower() for fragment in retry_messages):
                logger.warning(
                    "Validation set rejected by Darts; retrying without val."
                )
                model.fit(
                    train_series_list,
                    **covariate_payload,
                    verbose=False,
                )
                actual_use_val = False
            else:
                raise
    else:
        actual_use_val = False
        model.fit(
            train_series_list,
            **covariate_payload,
            verbose=False,
        )

    if not actual_use_val and effective_hyperparams["val_split"] != 0.0:
        effective_hyperparams["val_split"] = 0.0

    model.save(artifact_path_pt)
    if update_run is not None:
        update_run.scope = "global_shared"
        update_run.model_family = model_family
        update_run.cell_type = cell_type
        update_run.horizon_days = horizon_days
        update_run.transform = transform
        update_run.hyperparams_json = effective_hyperparams
        update_run.training_crypto_ids = used_crypto_ids
        update_run.train_start_date = train_start_date
        update_run.train_end_date = train_end_date
        update_run.cutoff_date = cutoff_date
        update_run.artifact_path_pt = artifact_path_pt
        update_run.work_dir = work_dir
        update_run.model_name = model_name
        session.commit()
        session.refresh(update_run)
        return update_run
    return create_model_run(
        session,
        scope="global_shared",
        model_family=model_family,
        cell_type=cell_type,
        horizon_days=horizon_days,
        transform=transform,
        hyperparams_json=effective_hyperparams,
        training_crypto_ids=used_crypto_ids,
        train_start_date=train_start_date,
        train_end_date=train_end_date,
        cutoff_date=cutoff_date,
        artifact_path_pt=artifact_path_pt,
        work_dir=work_dir,
        model_name=model_name,
    )
