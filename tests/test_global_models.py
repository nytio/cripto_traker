from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import select

from app.db import get_session
from app.models import Cryptocurrency, LstmForecast, Price
from app.services.global_inference import predict_with_global_model
from app.services.global_training import train_global_model
from app.services.model_registry import canonical_model_key


def _seed_crypto(session, name: str, symbol: str, coingecko_id: str):
    crypto = Cryptocurrency(
        name=name, symbol=symbol, coingecko_id=coingecko_id
    )
    session.add(crypto)
    session.commit()
    session.refresh(crypto)
    return crypto


def _seed_prices(session, crypto_id: int, start: date, days: int):
    for offset in range(days):
        session.add(
            Price(
                crypto_id=crypto_id,
                date=start + timedelta(days=offset),
                price=100 + offset,
            )
        )
    session.commit()


def test_canonical_model_key_deterministic(monkeypatch, tmp_path):
    monkeypatch.setenv("DARTS_WORK_DIR", str(tmp_path))
    hyperparams = {"input_chunk_length": 10, "n_epochs": 1}
    first = canonical_model_key(
        "global_shared",
        "RNNModel",
        "LSTM",
        30,
        "log_return",
        hyperparams,
    )
    second = canonical_model_key(
        "global_shared",
        "RNNModel",
        "LSTM",
        30,
        "log_return",
        hyperparams,
    )
    assert first == second
    assert first[1] == str(tmp_path)
    assert first[2].endswith(".pt")


def test_train_and_predict_global_model(app, monkeypatch, tmp_path):
    pytest.importorskip("darts")
    monkeypatch.setenv("DARTS_WORK_DIR", str(tmp_path))
    with app.app_context():
        session = get_session()
        btc = _seed_crypto(session, "Bitcoin", "BTC", "btc")
        eth = _seed_crypto(session, "Ethereum", "ETH", "eth")
        start = date.today() - timedelta(days=80)
        _seed_prices(session, btc.id, start, 60)
        _seed_prices(session, eth.id, start, 60)

        hyperparams = {
            "input_chunk_length": 6,
            "output_chunk_length": 3,
            "training_length": 8,
            "n_rnn_layers": 1,
            "hidden_dim": 4,
            "hidden_fc_sizes": [4],
            "n_epochs": 1,
            "batch_size": 4,
            "random_state": 1,
            "val_split": 0.2,
        }
        run = train_global_model(
            session,
            model_family="RNNModel",
            cell_type="LSTM",
            hyperparams=hyperparams,
            crypto_ids=[btc.id, eth.id],
            horizon_days=3,
            transform="log_return",
        )

        assert run.id is not None
        assert run.artifact_path_pt
        assert Path(run.artifact_path_pt).exists()
        assert Path(f"{run.artifact_path_pt}.ckpt").exists()

        rows = predict_with_global_model(
            session,
            run.id,
            btc.id,
            horizon_days=3,
            allow_unseen=True,
        )
        assert rows
        stored = session.execute(
            select(LstmForecast).where(LstmForecast.crypto_id == btc.id)
        ).scalars().all()
        assert stored
        assert all(row.model_run_id == run.id for row in stored)


def test_validation_kept_after_chunk_reduction(app, monkeypatch, tmp_path):
    from app.services import global_training as gt

    class FakeTimeSeries:
        def __init__(self, time_index, values):
            self.time_index = pd.DatetimeIndex(time_index)
            self._values = values

        @classmethod
        def from_dataframe(cls, df, time_col="date", value_cols=None):
            return cls(pd.to_datetime(df[time_col]), df[value_cols].to_numpy())

        def split_before(self, split_point):
            if isinstance(split_point, (float, int)):
                idx = int(len(self) * float(split_point))
            else:
                ts = pd.Timestamp(split_point)
                idx = int((self.time_index < ts).sum())
            return (
                FakeTimeSeries(self.time_index[:idx], self._values[:idx]),
                FakeTimeSeries(self.time_index[idx:], self._values[idx:]),
            )

        def __len__(self):
            return len(self.time_index)

        @property
        def width(self):
            if self._values.ndim == 1:
                return 1
            return self._values.shape[1]

    fit_calls: list[object] = []

    class FakeModel:
        supports_future_covariates = False
        supports_past_covariates = False

        def __init__(self, *args, **kwargs):
            return None

        def fit(self, train_series, val_series=None, **kwargs):
            fit_calls.append(val_series)

        def save(self, path):
            Path(path).write_text("")

        def load_weights(self, *args, **kwargs):
            return None

    def fake_resolve_val_split(*_args, **_kwargs):
        return 0.3

    def fake_resolve_chunk_lengths(
        series_len, input_chunk_length, output_chunk_length
    ):
        if series_len == 14:
            return 5, 1
        return 12, 4

    monkeypatch.setenv("DARTS_WORK_DIR", str(tmp_path))
    monkeypatch.setattr(gt, "TimeSeries", FakeTimeSeries)
    monkeypatch.setattr(gt, "RNNModel", FakeModel)
    monkeypatch.setattr(gt, "BlockRNNModel", FakeModel)
    monkeypatch.setattr(gt, "_resolve_val_split", fake_resolve_val_split)
    monkeypatch.setattr(gt, "_resolve_chunk_lengths", fake_resolve_chunk_lengths)
    monkeypatch.setattr(
        gt, "_build_covariates", lambda *_args, **_kwargs: None
    )

    with app.app_context():
        session = get_session()
        btc = _seed_crypto(session, "Bitcoin", "BTC", "btc-short")
        start = date.today() - timedelta(days=30)
        _seed_prices(session, btc.id, start, 21)

        hyperparams = {
            "input_chunk_length": 12,
            "output_chunk_length": 4,
            "training_length": 12,
            "n_rnn_layers": 1,
            "hidden_dim": 4,
            "hidden_fc_sizes": [4],
            "n_epochs": 1,
            "batch_size": 4,
            "random_state": 1,
            "val_split": 0.3,
        }
        gt.train_global_model(
            session,
            model_family="BlockRNNModel",
            cell_type="LSTM",
            hyperparams=hyperparams,
            crypto_ids=[btc.id],
            horizon_days=3,
            transform="log_return",
        )

    assert fit_calls
    assert fit_calls[0] is not None


def test_per_crypto_store_forecast_compatible(app, monkeypatch):
    from app.services import rnn

    def fake_forecast(*_args, **_kwargs):
        return [
            {
                "date": date.today(),
                "yhat": 1.0,
                "yhat_lower": 0.9,
                "yhat_upper": 1.1,
            }
        ]

    monkeypatch.setattr(rnn, "_compute_forecast", fake_forecast)

    with app.app_context():
        session = get_session()
        crypto = _seed_crypto(session, "Litecoin", "LTC", "ltc")
        rows = [
            {
                "date": date.today() - timedelta(days=offset),
                "price": 100.0 + offset,
            }
            for offset in range(5, 0, -1)
        ]
        stored = rnn.store_lstm_forecast(session, crypto.id, rows, 1)
        assert stored == 1


@pytest.mark.parametrize(
    "route_name, cell_type",
    [
        ("lstm", "LSTM"),
        ("gru", "GRU"),
    ],
)
def test_global_create_uses_multi_crypto_ids(
    app, auth_client, user, monkeypatch, route_name, cell_type
):
    from app.db import get_session
    from app.models import UserCrypto
    from app.routes import charts as charts_routes

    with app.app_context():
        session = get_session()
        primary = _seed_crypto(session, "Bitcoin", "BTC", "btc")
        extra_one = _seed_crypto(session, "Ethereum", "ETH", "eth")
        extra_two = _seed_crypto(session, "Litecoin", "LTC", "ltc")
        session.add(UserCrypto(user_id=user.id, crypto_id=primary.id))
        session.commit()
        primary_id = primary.id
        extra_one_id = extra_one.id
        extra_two_id = extra_two.id

    app.config["RNN_FUTURE_DAYS"] = 30
    captured: dict[str, object] = {}

    def fake_train_global_model(*_args, **kwargs):
        captured["crypto_ids"] = list(kwargs.get("crypto_ids") or [])
        captured["cell_type"] = kwargs.get("cell_type")

        class FakeRun:
            id = 123

        return FakeRun()

    def fake_predict_with_global_model(
        *_args, **_kwargs
    ):
        return [
            {
                "date": date.today(),
                "yhat": 1.0,
                "yhat_lower": 0.9,
                "yhat_upper": 1.1,
            }
        ]

    def fake_start_job(job_key, job_type, label, target):
        result = target()
        return {
            "job_key": job_key,
            "job_type": job_type,
            "label": label,
            "state": "done",
            "message": "done",
            "result": result,
        }

    monkeypatch.setattr(
        charts_routes, "train_global_model", fake_train_global_model
    )
    monkeypatch.setattr(
        charts_routes, "predict_with_global_model", fake_predict_with_global_model
    )
    monkeypatch.setattr(
        charts_routes, "_global_model_has_artifacts", lambda _run: True
    )
    monkeypatch.setattr(charts_routes, "start_job", fake_start_job)

    data = {
        f"{route_name}_days": "365",
        f"{route_name}_scope": "global_shared",
        f"{route_name}_model": "rnn",
        f"{route_name}_global_model_run_id": "",
        f"{route_name}_crypto_ids": [
            str(primary_id),
            str(extra_one_id),
            str(extra_two_id),
            "9999",
        ],
    }
    response = auth_client.post(
        f"/cryptos/{primary_id}/{route_name}",
        data=data,
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    assert set(captured["crypto_ids"]) == {
        primary_id,
        extra_one_id,
        extra_two_id,
    }
    assert captured["cell_type"] == cell_type


@pytest.mark.parametrize(
    "route_name, cell_type",
    [
        ("lstm", "LSTM"),
        ("gru", "GRU"),
    ],
)
def test_global_retrain_uses_run_crypto_ids(
    app, auth_client, user, monkeypatch, route_name, cell_type
):
    from app.db import get_session
    from app.models import UserCrypto
    from app.routes import charts as charts_routes
    from app.services.model_registry import create_model_run

    with app.app_context():
        session = get_session()
        primary = _seed_crypto(session, "Bitcoin", "BTC", "btc")
        extra_one = _seed_crypto(session, "Ethereum", "ETH", "eth")
        extra_two = _seed_crypto(session, "Litecoin", "LTC", "ltc")
        session.add(UserCrypto(user_id=user.id, crypto_id=primary.id))
        session.commit()
        run = create_model_run(
            session,
            scope="global_shared",
            model_family="RNNModel",
            cell_type=cell_type,
            horizon_days=30,
            transform="log_return",
            hyperparams_json={"input_chunk_length": 10},
            training_crypto_ids=[primary.id, extra_one.id],
            train_start_date=None,
            train_end_date=None,
            cutoff_date=None,
            artifact_path_pt="dummy.pt",
            work_dir="/tmp",
            model_name="dummy",
        )
        primary_id = primary.id
        extra_one_id = extra_one.id
        extra_two_id = extra_two.id
        run_id = run.id

    app.config["RNN_FUTURE_DAYS"] = 30
    captured: dict[str, object] = {}

    def fake_train_global_model(*_args, **kwargs):
        captured["crypto_ids"] = list(kwargs.get("crypto_ids") or [])
        captured["cell_type"] = kwargs.get("cell_type")

        class FakeRun:
            id = 123

        return FakeRun()

    def fake_predict_with_global_model(*_args, **_kwargs):
        return [
            {
                "date": date.today(),
                "yhat": 1.0,
                "yhat_lower": 0.9,
                "yhat_upper": 1.1,
            }
        ]

    def fake_start_job(job_key, job_type, label, target):
        result = target()
        return {
            "job_key": job_key,
            "job_type": job_type,
            "label": label,
            "state": "done",
            "message": "done",
            "result": result,
        }

    monkeypatch.setattr(
        charts_routes, "train_global_model", fake_train_global_model
    )
    monkeypatch.setattr(
        charts_routes,
        "predict_with_global_model",
        fake_predict_with_global_model,
    )
    monkeypatch.setattr(
        charts_routes, "_global_model_has_artifacts", lambda _run: True
    )
    monkeypatch.setattr(charts_routes, "start_job", fake_start_job)

    data = {
        f"{route_name}_days": "365",
        f"{route_name}_scope": "global_shared",
        f"{route_name}_model": "rnn",
        f"{route_name}_global_model_run_id": str(run_id),
        f"{route_name}_crypto_ids": [str(extra_two_id)],
        f"{route_name}_retrain": "1",
    }
    response = auth_client.post(
        f"/cryptos/{primary_id}/{route_name}",
        data=data,
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 200
    assert set(captured["crypto_ids"]) == {primary_id, extra_one_id}
    assert captured["cell_type"] == cell_type
