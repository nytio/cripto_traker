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
    const prophetForecastRaw = JSON.parse(chartEl.dataset.prophet || "[]");
    const prophetForecast = Array.isArray(prophetForecastRaw)
      ? prophetForecastRaw
      : [];
    const toNumber = (value) =>
      value === null || value === undefined ? null : Number(value);
    const prophetRows = prophetForecast;
    const prophetDates = prophetRows.map((row) => row.date);
    const prophetYhat = prophetRows.map((row) => toNumber(row.yhat));
    const prophetLower = prophetRows.map((row) => toNumber(row.yhat_lower));
    const prophetUpper = prophetRows.map((row) => toNumber(row.yhat_upper));

    const baselinePrice = prices.find((value) => Number.isFinite(value));
    const priceTraces = [];
    const greenColor = "#2CA02C";
    const redColor = "#D62728";
    const bollingerBandColor = "rgba(148, 103, 189, 0.15)";
    const bollingerBandLine = "rgba(148, 103, 189, 0.3)";
    const bollingerLineColor = "rgba(148, 103, 189, 0.3)";
    const prophetBandColor = "rgba(23, 190, 207, 0.10)";
    const prophetLineColor = "#17BECF";
    const priceLineWidth = 2.5;
    const smaLineWidth = 1.2;
    const prophetLineWidth = 1.6;
    const priceMonoColor = "#1F77B4";

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
            line: { color: currentColor, width: priceLineWidth },
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
          line: { color: greenColor, width: priceLineWidth },
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
        line: { color: bollingerBandLine, width: 1 },
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
        line: { color: bollingerBandLine, width: 1 },
      },
    ];
    const prophetBandTraces = [
      {
        x: prophetDates,
        y: prophetLower,
        type: "scatter",
        mode: "lines",
        name: "Prophet band",
        showlegend: false,
        visible: "legendonly",
        line: { color: "rgba(23, 190, 207, 0)", width: 0 },
      },
      {
        x: prophetDates,
        y: prophetUpper,
        type: "scatter",
        mode: "lines",
        name: "Prophet band",
        showlegend: false,
        visible: "legendonly",
        fill: "tonexty",
        fillcolor: prophetBandColor,
        line: { color: "rgba(23, 190, 207, 0)", width: 0 },
      },
    ];
    const priceMonoTrace = {
      x: dates,
      y: prices,
      type: "scatter",
      mode: "lines",
      name: "Price mono",
      visible: "legendonly",
      line: { color: priceMonoColor, width: priceLineWidth },
    };
    const prophetLineTrace = {
      x: prophetDates,
      y: prophetYhat,
      type: "scatter",
      mode: "lines",
      name: "Prophet",
      visible: "legendonly",
      opacity: 1.0,
      line: { color: prophetLineColor, dash: "solid", width: prophetLineWidth },
    };

    const data = [
      ...bollingerBandTraces,
      ...prophetBandTraces,
      prophetLineTrace,
      ...priceTraces,
      priceMonoTrace,
      {
        x: dates,
        y: sma7,
        type: "scatter",
        mode: "lines",
        name: "SMA 7",
        visible: "legendonly",
        line: { color: "#FF7F0E", width: smaLineWidth },
      },
      {
        x: dates,
        y: sma30,
        type: "scatter",
        mode: "lines",
        name: "SMA 30",
        visible: "legendonly",
        line: { color: "#7F7F7F", dash: "dash", width: smaLineWidth },
      },
      {
        x: dates,
        y: bbUpper,
        type: "scatter",
        mode: "lines",
        name: "BB Upper",
        visible: "legendonly",
        line: { color: bollingerLineColor, width: 1 },
      },
      {
        x: dates,
        y: bbLower,
        type: "scatter",
        mode: "lines",
        name: "BB Lower",
        visible: "legendonly",
        line: { color: bollingerLineColor, width: 1 },
      },
    ];

    const layout = {
      margin: { t: 20, r: 20, l: 50, b: 40 },
      paper_bgcolor: "#FFFFFF",
      plot_bgcolor: "#FFFFFF",
      xaxis: {
        type: "date",
        rangeslider: { visible: false },
        showgrid: false,
      },
      yaxis: {
        title: `Price (${currency.toUpperCase()})`,
        showgrid: true,
        gridcolor: "#EAEAEA",
      },
      showlegend: false,
    };

    Plotly.newPlot("price-chart", data, layout, { responsive: true });

    const sma7Toggle = document.getElementById("toggle-sma-7");
    const sma30Toggle = document.getElementById("toggle-sma-30");
    const bollingerToggle = document.getElementById("toggle-bollinger");
    const prophetToggle = document.getElementById("toggle-prophet");
    const priceModeToggle = document.getElementById("toggle-price-mode");
    const prophetBandOffset = bollingerBandTraces.length;
    const prophetBandIndices = prophetBandTraces.map(
      (_, index) => prophetBandOffset + index
    );
    const prophetLineIndex = prophetBandOffset + prophetBandTraces.length;
    const priceTraceOffset = prophetLineIndex + 1;
    const priceTraceIndices = priceTraces.map((_, index) => priceTraceOffset + index);
    const priceMonoIndex = priceTraceOffset + priceTraces.length;
    const indicatorOffset = priceMonoIndex + 1;
    const bollingerBandIndices = bollingerBandTraces.map((_, index) => index);
    const bollingerLineIndices = [indicatorOffset + 2, indicatorOffset + 3];
    const bollingerTraceIndices = [...bollingerBandIndices, ...bollingerLineIndices];
    const prophetTraceIndices = [...prophetBandIndices, prophetLineIndex];

    const setVisibility = (traceIndices, visible) => {
      Plotly.restyle(
        "price-chart",
        { visible: visible ? true : "legendonly" },
        traceIndices
      );
    };
    const refreshAxes = () => {
      Plotly.relayout("price-chart", {
        "xaxis.autorange": true,
        "yaxis.autorange": true,
      });
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
    const prophetHasData = prophetYhat.some((value) => Number.isFinite(value));
    if (prophetToggle && !prophetHasData) {
      prophetToggle.disabled = true;
      prophetToggle.title = "Prophet sin datos";
    }
    if (prophetToggle) {
      prophetToggle.addEventListener("change", (event) => {
        setVisibility(prophetTraceIndices, event.target.checked);
        if (event.target.checked) {
          refreshAxes();
        }
      });
    }
    if (priceModeToggle) {
      priceModeToggle.addEventListener("change", (event) => {
        const useMono = event.target.checked;
        setVisibility(priceTraceIndices, !useMono);
        Plotly.restyle(
          "price-chart",
          { visible: useMono ? true : "legendonly" },
          [priceMonoIndex]
        );
      });
    }
  }
}
