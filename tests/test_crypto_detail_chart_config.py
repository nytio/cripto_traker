from datetime import date
from pathlib import Path

from app.db import get_session
from app.models import Cryptocurrency, Price, ProphetForecast


def test_crypto_detail_includes_prophet_line_data(client, app):
    with app.app_context():
        session = get_session()
        crypto = Cryptocurrency(coingecko_id="btc", name="Bitcoin", symbol="btc")
        session.add(crypto)
        session.commit()
        crypto_id = crypto.id
        cutoff_date = date(2024, 1, 10)
        session.add(Price(crypto_id=crypto.id, date=cutoff_date, price=1))
        session.add(
            ProphetForecast(
                crypto_id=crypto.id,
                date=cutoff_date,
                yhat=1,
                yhat_lower=1,
                yhat_upper=1,
                cutoff_date=cutoff_date,
                horizon_days=30,
            )
        )
        session.commit()

    response = client.get(f"/cryptos/{crypto_id}")
    assert response.status_code == 200
    expected_line = cutoff_date.isoformat()
    payload = response.get_data(as_text=True)
    assert f'data-prophet-cutoff="{cutoff_date.isoformat()}"' in payload
    assert f'data-prophet-line="{expected_line}"' in payload


def test_crypto_detail_defaults_to_one_year_range(client, app):
    with app.app_context():
        session = get_session()
        crypto = Cryptocurrency(
            coingecko_id="eth", name="Ethereum", symbol="eth"
        )
        session.add(crypto)
        session.commit()
        crypto_id = crypto.id

    response = client.get(f"/cryptos/{crypto_id}")
    assert response.status_code == 200
    payload = response.get_data(as_text=True)
    expected_days = min(365, app.config["MAX_HISTORY_DAYS"])
    assert f'value="{expected_days}" selected' in payload


def test_prophet_chart_styles_present():
    content = Path("web/app/static/js/crypto_detail.js").read_text()
    build_start = content.index("const buildForecastTraces")
    build_end = content.index("const buildMarkerShape")
    build_block = content[build_start:build_end]

    assert "dash" not in build_block
    assert 'prophetFill: "rgba(23, 190, 207, 0.10)"' in content
    assert 'fill: "tonexty"' in content
    assert 'line: { color: "rgba(0, 0, 0, 0)", width: 0 }' in content
    assert "showlegend: false" in content
