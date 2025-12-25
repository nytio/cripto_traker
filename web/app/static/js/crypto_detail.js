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
    const chartColors = {
      price: "#1F77B4",
      priceUp: "#2CA02C",
      priceDown: "#D62728",
      prophet: "#17BECF",
      prophetFill: "rgba(23, 190, 207, 0.10)",
      markerLine: "rgba(160, 160, 160, 0.8)",
      bollingerBand: "rgba(148, 103, 189, 0.15)",
      bollingerLine: "rgba(148, 103, 189, 0.3)",
    };
    const lineWidths = {
      price: 2.5,
      sma: 1.2,
      prophet: 1.8,
      prophetHistory: 1.4,
    };
    const prophetCutoff = chartEl.dataset.prophetCutoff || null;
    const prophetLineDate = chartEl.dataset.prophetLine || null;
    // Split Prophet into in-sample vs forecast using the stored cutoff date.
    const lastObservedDate = series.reduce(
      (acc, row) => (Number.isFinite(row.price) ? row.date : acc),
      null
    );
    const cutoffDate = prophetCutoff || lastObservedDate;
    const prophetHistoryRows = cutoffDate
      ? prophetForecast.filter((row) => row.date <= cutoffDate)
      : prophetForecast;
    const prophetFutureRows = cutoffDate
      ? prophetForecast.filter((row) => row.date >= cutoffDate)
      : [];
    const prophetAllDates = prophetForecast.map((row) => row.date);
    const prophetAllLower = prophetForecast.map((row) =>
      toNumber(row.yhat_lower)
    );
    const prophetAllUpper = prophetForecast.map((row) =>
      toNumber(row.yhat_upper)
    );
    const prophetHistoryDates = prophetHistoryRows.map((row) => row.date);
    const prophetHistoryYhat = prophetHistoryRows.map((row) =>
      toNumber(row.yhat)
    );
    const prophetFutureDates = prophetFutureRows.map((row) => row.date);
    const prophetFutureYhat = prophetFutureRows.map((row) =>
      toNumber(row.yhat)
    );

    const baselinePrice = prices.find((value) => Number.isFinite(value));
    const priceTraces = [];
    const greenColor = chartColors.priceUp;
    const redColor = chartColors.priceDown;
    const bollingerBandColor = chartColors.bollingerBand;
    const bollingerBandLine = chartColors.bollingerLine;
    const bollingerLineColor = chartColors.bollingerLine;
    const prophetLineColor = chartColors.prophet;
    const priceLineWidth = lineWidths.price;
    const smaLineWidth = lineWidths.sma;
    const priceMonoColor = chartColors.price;

    if (!Number.isFinite(baselinePrice)) {
      priceTraces.push({
        x: dates,
        y: prices,
        type: "scatter",
        mode: "lines",
        name: "Price",
        opacity: 1.0,
        line: { color: greenColor, width: priceLineWidth },
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
            opacity: 1.0,
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
          opacity: 1.0,
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
    const prophetHasHistory = prophetHistoryYhat.some((value) =>
      Number.isFinite(value)
    );
    const prophetHasFuture = prophetFutureYhat.some((value) =>
      Number.isFinite(value)
    );
    const prophetCiTraces = [
      {
        x: prophetAllDates,
        y: prophetAllLower,
        type: "scatter",
        mode: "lines",
        name: "Forecast CI",
        legendgroup: "prophet",
        showlegend: false,
        visible: "legendonly",
        line: { color: "rgba(0, 0, 0, 0)", width: 0 },
      },
      {
        x: prophetAllDates,
        y: prophetAllUpper,
        type: "scatter",
        mode: "lines",
        name: "Forecast CI",
        legendgroup: "prophet",
        showlegend: prophetHasFuture,
        visible: "legendonly",
        fill: "tonexty",
        fillcolor: chartColors.prophetFill,
        line: { color: "rgba(0, 0, 0, 0)", width: 0 },
      },
    ];
    const prophetHistoryTrace = {
      x: prophetHistoryDates,
      y: prophetHistoryYhat,
      type: "scatter",
      mode: "lines",
      name: "Forecast (Prophet)",
      legendgroup: "prophet",
      showlegend: false,
      visible: "legendonly",
      opacity: 0.55,
      line: { color: prophetLineColor, width: lineWidths.prophetHistory },
    };
    const prophetFutureTrace = {
      x: prophetFutureDates,
      y: prophetFutureYhat,
      type: "scatter",
      mode: "lines",
      name: "Forecast (Prophet)",
      legendgroup: "prophet",
      showlegend: prophetHasFuture,
      visible: "legendonly",
      opacity: 1.0,
      line: {
        color: prophetLineColor,
        width: lineWidths.prophet,
      },
    };
    const prophetTraces = [
      ...prophetCiTraces,
      prophetHistoryTrace,
      prophetFutureTrace,
    ];
    const priceMonoTrace = {
      x: dates,
      y: prices,
      type: "scatter",
      mode: "lines",
      name: "Price mono",
      showlegend: false,
      visible: "legendonly",
      line: { color: priceMonoColor, width: priceLineWidth },
    };
    const data = [
      ...bollingerBandTraces,
      ...prophetTraces,
      ...priceTraces,
      priceMonoTrace,
      {
        x: dates,
        y: sma7,
        type: "scatter",
        mode: "lines",
        name: "SMA 7",
        showlegend: false,
        visible: "legendonly",
        line: { color: "#FF7F0E", width: smaLineWidth },
      },
      {
        x: dates,
        y: sma30,
        type: "scatter",
        mode: "lines",
        name: "SMA 30",
        showlegend: false,
        visible: "legendonly",
        line: { color: "#7F7F7F", dash: "dash", width: smaLineWidth },
      },
      {
        x: dates,
        y: bbUpper,
        type: "scatter",
        mode: "lines",
        name: "BB Upper",
        showlegend: false,
        visible: "legendonly",
        line: { color: bollingerLineColor, width: 1 },
      },
      {
        x: dates,
        y: bbLower,
        type: "scatter",
        mode: "lines",
        name: "BB Lower",
        showlegend: false,
        visible: "legendonly",
        line: { color: bollingerLineColor, width: 1 },
      },
    ];

    const lineDate = prophetLineDate || prophetCutoff || null;
    const markerShape = lineDate
      ? {
          type: "line",
          xref: "x",
          yref: "paper",
          x0: lineDate,
          x1: lineDate,
          y0: 0,
          y1: 1,
          line: { color: chartColors.markerLine, width: 1, dash: "dot" },
        }
      : null;

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
      shapes: [],
      showlegend: false,
    };

    Plotly.newPlot("price-chart", data, layout, { responsive: true });

    const sma7Toggle = document.getElementById("toggle-sma-7");
    const sma30Toggle = document.getElementById("toggle-sma-30");
    const bollingerToggle = document.getElementById("toggle-bollinger");
    const prophetToggle = document.getElementById("toggle-prophet");
    const priceModeToggle = document.getElementById("toggle-price-mode");
    const prophetTraceOffset = bollingerBandTraces.length;
    const prophetTraceIndices = prophetTraces.map(
      (_, index) => prophetTraceOffset + index
    );
    const priceTraceOffset = prophetTraceOffset + prophetTraces.length;
    const priceTraceIndices = priceTraces.map((_, index) => priceTraceOffset + index);
    const priceMonoIndex = priceTraceOffset + priceTraces.length;
    const indicatorOffset = priceMonoIndex + 1;
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
    const prophetHasData = prophetHasHistory || prophetHasFuture;
    if (prophetToggle && !prophetHasData) {
      prophetToggle.disabled = true;
      prophetToggle.title = "Prophet sin datos";
    }
    if (prophetToggle) {
      prophetToggle.addEventListener("change", (event) => {
        setVisibility(prophetTraceIndices, event.target.checked);
        if (markerShape) {
          Plotly.relayout("price-chart", {
            shapes: event.target.checked ? [markerShape] : [],
          });
        }
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
