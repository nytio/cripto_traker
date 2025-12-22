const chartEl = document.getElementById("price-chart");

if (chartEl) {
  const series = JSON.parse(chartEl.dataset.series || "[]");
  const currency = chartEl.dataset.currency || "USD";
  if (series.length) {
    const dates = series.map((row) => row.date);
    const prices = series.map((row) => row.price);
    const sma7 = series.map((row) => row.sma_7);
    const sma30 = series.map((row) => row.sma_30);
    const bbUpper = series.map((row) => row.bb_upper);
    const bbLower = series.map((row) => row.bb_lower);

    const data = [
      {
        x: dates,
        y: prices,
        type: "scatter",
        mode: "lines",
        name: "Price",
      },
      {
        x: dates,
        y: sma7,
        type: "scatter",
        mode: "lines",
        name: "SMA 7",
      },
      {
        x: dates,
        y: sma30,
        type: "scatter",
        mode: "lines",
        name: "SMA 30",
      },
      {
        x: dates,
        y: bbUpper,
        type: "scatter",
        mode: "lines",
        name: "BB Upper",
        visible: "legendonly",
      },
      {
        x: dates,
        y: bbLower,
        type: "scatter",
        mode: "lines",
        name: "BB Lower",
        visible: "legendonly",
      },
    ];

    const layout = {
      margin: { t: 20, r: 20, l: 50, b: 40 },
      xaxis: {
        type: "date",
        rangeslider: { visible: true },
        rangeselector: {
          buttons: [
            { count: 7, label: "7d", step: "day", stepmode: "backward" },
            { count: 1, label: "1m", step: "month", stepmode: "backward" },
            { count: 3, label: "3m", step: "month", stepmode: "backward" },
            { step: "all", label: "All" },
          ],
        },
      },
      yaxis: { title: `Price (${currency.toUpperCase()})` },
      legend: { orientation: "h" },
    };

    Plotly.newPlot("price-chart", data, layout, { responsive: true });

    const sma7Toggle = document.getElementById("toggle-sma-7");
    const sma30Toggle = document.getElementById("toggle-sma-30");
    const bollingerToggle = document.getElementById("toggle-bollinger");

    const setVisibility = (traceIndices, visible) => {
      Plotly.restyle(
        "price-chart",
        { visible: visible ? true : "legendonly" },
        traceIndices
      );
    };

    if (sma7Toggle) {
      sma7Toggle.addEventListener("change", (event) => {
        setVisibility([1], event.target.checked);
      });
    }
    if (sma30Toggle) {
      sma30Toggle.addEventListener("change", (event) => {
        setVisibility([2], event.target.checked);
      });
    }
    if (bollingerToggle) {
      bollingerToggle.addEventListener("change", (event) => {
        setVisibility([3, 4], event.target.checked);
      });
    }
  }
}
