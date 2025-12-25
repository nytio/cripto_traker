from datetime import date
from pathlib import Path

from app.db import get_session
from app.models import Cryptocurrency, Price


def test_crypto_detail_includes_today_data(client, app):
    with app.app_context():
        session = get_session()
        crypto = Cryptocurrency(coingecko_id="btc", name="Bitcoin", symbol="btc")
        session.add(crypto)
        session.commit()
        crypto_id = crypto.id
        session.add(Price(crypto_id=crypto.id, date=date.today(), price=1))
        session.commit()

    response = client.get(f"/cryptos/{crypto_id}")
    assert response.status_code == 200
    today = date.today().isoformat()
    assert f'data-today="{today}"' in response.get_data(as_text=True)


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
