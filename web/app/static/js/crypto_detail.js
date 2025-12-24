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

    const baselinePrice = prices.find((value) => Number.isFinite(value));
    const priceTraces = [];
    const greenColor = "#198754";
    const redColor = "#dc3545";
    const bollingerBandColor = "rgba(140, 108, 214, 0.4)";
    const bollingerBandLine = "rgba(140, 108, 214, 0)";
    const bollingerLineColor = "rgba(170, 150, 230, 0.75)";

    if (!Number.isFinite(baselinePrice)) {
      priceTraces.push({
        x: dates,
        y: prices,
        type: "scatter",
        mode: "lines",
        name: "Price",
        line: { color: greenColor },
      });
    } else {
      let currentColor = null;
      let segmentX = [];
      let segmentY = [];
      let lastDate = null;
      let lastPrice = null;
      let hasLegend = false;

      const flushSegment = () => {
        if (segmentX.length > 1 && currentColor) {
          priceTraces.push({
            x: segmentX,
            y: segmentY,
            type: "scatter",
            mode: "lines",
            name: "Price",
            showlegend: !hasLegend,
            line: { color: currentColor },
          });
          hasLegend = true;
        }
      };

      for (let i = 0; i < prices.length; i += 1) {
        const price = prices[i];
        const date = dates[i];

        if (!Number.isFinite(price)) {
          flushSegment();
          segmentX = [];
          segmentY = [];
          currentColor = null;
          lastDate = null;
          lastPrice = null;
          continue;
        }

        if (lastDate === null) {
          segmentX = [date];
          segmentY = [price];
          lastDate = date;
          lastPrice = price;
          continue;
        }

        const segmentColor = price >= baselinePrice ? greenColor : redColor;
        if (currentColor === null) {
          currentColor = segmentColor;
        } else if (segmentColor !== currentColor) {
          flushSegment();
          segmentX = [lastDate];
          segmentY = [lastPrice];
          currentColor = segmentColor;
        }

        segmentX.push(date);
        segmentY.push(price);
        lastDate = date;
        lastPrice = price;
      }

      flushSegment();

      if (!priceTraces.length) {
        priceTraces.push({
          x: dates,
          y: prices,
          type: "scatter",
          mode: "lines",
          name: "Price",
          line: { color: greenColor },
        });
      }
    }

    const bollingerBandTraces = [
      {
        x: dates,
        y: bbLower,
        type: "scatter",
        mode: "lines",
        name: "BB Band",
        showlegend: false,
        visible: "legendonly",
        line: { color: bollingerBandLine },
      },
      {
        x: dates,
        y: bbUpper,
        type: "scatter",
        mode: "lines",
        name: "BB Band",
        showlegend: false,
        visible: "legendonly",
        fill: "tonexty",
        fillcolor: bollingerBandColor,
        line: { color: bollingerBandLine },
      },
    ];

    const data = [
      ...bollingerBandTraces,
      ...priceTraces,
      {
        x: dates,
        y: sma7,
        type: "scatter",
        mode: "lines",
        name: "SMA 7",
        visible: "legendonly",
        line: { dash: "dash" },
      },
      {
        x: dates,
        y: sma30,
        type: "scatter",
        mode: "lines",
        name: "SMA 30",
        visible: "legendonly",
        line: { dash: "dash" },
      },
      {
        x: dates,
        y: bbUpper,
        type: "scatter",
        mode: "lines",
        name: "BB Upper",
        visible: "legendonly",
        line: { color: bollingerLineColor },
      },
      {
        x: dates,
        y: bbLower,
        type: "scatter",
        mode: "lines",
        name: "BB Lower",
        visible: "legendonly",
        line: { color: bollingerLineColor },
      },
    ];

    const layout = {
      margin: { t: 20, r: 20, l: 50, b: 40 },
      xaxis: {
        type: "date",
        rangeslider: { visible: false },
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
    const indicatorOffset = bollingerBandTraces.length + priceTraces.length;
    const bollingerBandIndices = bollingerBandTraces.map((_, index) => index);
    const bollingerLineIndices = [indicatorOffset + 2, indicatorOffset + 3];
    const bollingerTraceIndices = [...bollingerBandIndices, ...bollingerLineIndices];

    const setVisibility = (traceIndices, visible) => {
      Plotly.restyle(
        "price-chart",
        { visible: visible ? true : "legendonly" },
        traceIndices
      );
    };

    if (sma7Toggle) {
      sma7Toggle.addEventListener("change", (event) => {
        setVisibility([indicatorOffset], event.target.checked);
      });
    }
    if (sma30Toggle) {
      sma30Toggle.addEventListener("change", (event) => {
        setVisibility([indicatorOffset + 1], event.target.checked);
      });
    }
    if (bollingerToggle) {
      bollingerToggle.addEventListener("change", (event) => {
        setVisibility(bollingerTraceIndices, event.target.checked);
      });
    }
  }
}
