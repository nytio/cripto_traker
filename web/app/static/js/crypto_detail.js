const chartEl = document.getElementById("price-chart");

if (chartEl) {
  const series = JSON.parse(chartEl.dataset.series || "[]");
  const currency = chartEl.dataset.currency || "USD";
  if (series.length) {
    const dates = series.map((row) => row.date);
    const prices = series.map((row) => row.price);
    const sma7 = series.map((row) => row.sma_7);
    const sma30 = series.map((row) => row.sma_30);

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
  }
}
