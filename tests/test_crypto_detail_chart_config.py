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


def test_prophet_chart_styles_present():
    content = Path("web/app/static/js/crypto_detail.js").read_text()
    history_start = content.index("const prophetHistoryTrace")
    future_start = content.index("const prophetFutureTrace")
    trace_end = content.index("const prophetTraces")
    history_block = content[history_start:future_start]
    future_block = content[future_start:trace_end]

    assert "dash:" not in history_block
    assert "dash:" not in future_block
    assert 'name: "Forecast (Prophet)"' in content
    assert 'name: "Forecast CI"' in content
    assert 'prophetFill: "rgba(23, 190, 207, 0.10)"' in content
    assert 'line: { color: "rgba(0, 0, 0, 0)", width: 0 }' in content
    assert "markerLine" in content
    assert "showlegend: false" in content
