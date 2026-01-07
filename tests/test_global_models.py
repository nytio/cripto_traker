from datetime import date, timedelta
from pathlib import Path

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
