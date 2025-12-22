from typing import Any

import duckdb
import pandas as pd


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
