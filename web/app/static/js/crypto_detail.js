const rangeSelect = document.getElementById("days");
const chartEl = document.getElementById("price-chart");
const storage =
  (() => {
    try {
      return window.sessionStorage;
    } catch (error) {
      return null;
    }
  })();
const cryptoId =
  (rangeSelect && rangeSelect.dataset.cryptoId) ||
  (chartEl && chartEl.dataset.cryptoId) ||
  null;
const storageKey = cryptoId ? `crypto-detail-toggles:${cryptoId}` : null;
const readToggleState = () => {
  if (!storage || !storageKey) {
    return {};
  }
  const raw = storage.getItem(storageKey);
  if (!raw) {
    return {};
  }
  try {
    return JSON.parse(raw);
  } catch (error) {
    return {};
  }
};
const writeToggleState = (state) => {
  if (!storage || !storageKey) {
    return;
  }
  try {
    storage.setItem(storageKey, JSON.stringify(state));
  } catch (error) {
    // Ignore storage failures (private mode, quota, etc.).
  }
};
const persistToggleState = (key, value) => {
  if (!storage || !storageKey) {
    return;
  }
  const state = readToggleState();
  state[key] = value;
  writeToggleState(state);
};

if (rangeSelect && rangeSelect.form) {
  const url = new URL(window.location.href);
  const savedDays = readToggleState().rangeDays;
  if (!url.searchParams.has("days") && savedDays) {
    url.searchParams.set("days", savedDays);
    window.location.replace(url.toString());
  } else {
    persistToggleState("rangeDays", rangeSelect.value);
    rangeSelect.addEventListener("change", () => {
      persistToggleState("rangeDays", rangeSelect.value);
      rangeSelect.form.submit();
    });
  }
}

if (chartEl) {
  const series = JSON.parse(chartEl.dataset.series || "[]");
  const currency = chartEl.dataset.currency || "USD";
  if (series.length) {
    const dates = series.map((row) => row.date);
    const prices = series.map((row) => row.price);
    const sma50 = series.map((row) => row.sma_50);
    const sma20 = series.map((row) => row.sma_20);
    const seriesPadding = JSON.parse(chartEl.dataset.seriesPadding || "[]");
    const paddingPrices = seriesPadding.map((row) => row.price);
    const buildEmaWithPadding = (period) => {
      const paddingNeeded = Math.max(period - 1, 0);
      const paddingTail =
        paddingNeeded > 0 ? paddingPrices.slice(-paddingNeeded) : [];
      const extraCount = paddingTail.length;
      const paddedValues =
        extraCount > 0 ? [...paddingTail, ...prices] : prices;
      const alpha = 2 / (period + 1);
      const result = new Array(paddedValues.length).fill(null);
      let ema = null;
      for (let i = 0; i < paddedValues.length; i += 1) {
        const value = paddedValues[i];
        if (!Number.isFinite(value)) {
          ema = null;
          result[i] = null;
          continue;
        }
        const isPadding = i < extraCount;
        if (ema === null) {
          const windowStart = i - (period - 1);
          if (windowStart < 0) {
            result[i] = null;
            continue;
          }
          const window = paddedValues.slice(windowStart, i + 1);
          if (!window.every((item) => Number.isFinite(item))) {
            result[i] = null;
            continue;
          }
          ema = window.reduce((acc, current) => acc + current, 0) / period;
          result[i] = isPadding ? null : ema;
          continue;
        }
        ema = alpha * value + (1 - alpha) * ema;
        result[i] = isPadding ? null : ema;
      }
      return result.slice(extraCount);
    };
    const ema20 = buildEmaWithPadding(20);
    const ema50 = buildEmaWithPadding(50);
    const bbUpper = series.map((row) => row.bb_upper);
    const bbLower = series.map((row) => row.bb_lower);
    const prophetForecastRaw = JSON.parse(chartEl.dataset.prophet || "[]");
    const prophetForecast = Array.isArray(prophetForecastRaw)
      ? prophetForecastRaw
      : [];
    const lstmForecastRaw = JSON.parse(chartEl.dataset.lstm || "[]");
    const lstmForecast = Array.isArray(lstmForecastRaw) ? lstmForecastRaw : [];
    const gruForecastRaw = JSON.parse(chartEl.dataset.gru || "[]");
    const gruForecast = Array.isArray(gruForecastRaw) ? gruForecastRaw : [];
    const toNumber = (value) =>
      value === null || value === undefined ? null : Number(value);
    const chartColors = {
      price: "#1F77B4",
      priceUp: "#2CA02C",
      priceDown: "#D62728",
      prophet: "#17BECF",
      prophetFill: "rgba(23, 190, 207, 0.10)",
      lstm: "#2CA02C",
      lstmFill: "rgba(44, 160, 44, 0.10)",
      gru: "#E377C2",
      gruFill: "rgba(227, 119, 194, 0.10)",
      markerLine: "rgba(160, 160, 160, 0.8)",
      bollingerBand: "rgba(148, 103, 189, 0.15)",
      bollingerLine: "rgba(148, 103, 189, 0.3)",
      sma50: "#1f77b4",
      sma20: "#ff7f0e",
    };
    const rulerColors = {
      line: "#F39C12",
      fill: "rgba(243, 156, 18, 0.12)",
      annotationBg: "rgba(255, 255, 255, 0.92)",
      annotationBorder: "rgba(243, 156, 18, 0.55)",
    };
    const lineWidths = {
      price: 2.5,
      sma: 1.2,
      prophet: 1.6,
      prophetHistory: 1.4,
      rnn: 1.6,
      rnnHistory: 1.2,
    };
    const prophetCutoff = chartEl.dataset.prophetCutoff || null;
    const prophetLineDate = chartEl.dataset.prophetLine || null;
    const lstmCutoff = chartEl.dataset.lstmCutoff || null;
    const lstmLineDate = chartEl.dataset.lstmLine || null;
    const gruCutoff = chartEl.dataset.gruCutoff || null;
    const gruLineDate = chartEl.dataset.gruLine || null;
    const buildForecastTraces = ({
      rows,
      cutoffDate,
      color,
      fillColor,
      historyWidth,
      futureWidth,
      historyOpacity,
      futureOpacity,
      name,
    }) => {
      const safeRows = Array.isArray(rows) ? rows : [];
      const historyRows = cutoffDate
        ? safeRows.filter((row) => row.date <= cutoffDate)
        : safeRows;
      const futureRows = cutoffDate
        ? safeRows.filter((row) => row.date >= cutoffDate)
        : [];
      const allDates = safeRows.map((row) => row.date);
      const allLower = safeRows.map((row) => toNumber(row.yhat_lower));
      const allUpper = safeRows.map((row) => toNumber(row.yhat_upper));
      const historyDates = historyRows.map((row) => row.date);
      const historyYhat = historyRows.map((row) => toNumber(row.yhat));
      const futureDates = futureRows.map((row) => row.date);
      const futureYhat = futureRows.map((row) => toNumber(row.yhat));
      const hasHistory = historyYhat.some((value) => Number.isFinite(value));
      const hasFuture = futureYhat.some((value) => Number.isFinite(value));

      const ciTraces = [
        {
          x: allDates,
          y: allLower,
          type: "scatter",
          mode: "lines",
          name: `${name} CI`,
          showlegend: false,
          visible: "legendonly",
          line: { color: "rgba(0, 0, 0, 0)", width: 0 },
        },
        {
          x: allDates,
          y: allUpper,
          type: "scatter",
          mode: "lines",
          name: `${name} CI`,
          showlegend: false,
          visible: "legendonly",
          fill: "tonexty",
          fillcolor: fillColor,
          line: { color: "rgba(0, 0, 0, 0)", width: 0 },
        },
      ];
      const historyTrace = {
        x: historyDates,
        y: historyYhat,
        type: "scatter",
        mode: "lines",
        name,
        showlegend: false,
        visible: "legendonly",
        opacity: historyOpacity,
        line: { color, width: historyWidth },
      };
      const futureTrace = {
        x: futureDates,
        y: futureYhat,
        type: "scatter",
        mode: "lines",
        name,
        showlegend: false,
        visible: "legendonly",
        opacity: futureOpacity,
        line: { color, width: futureWidth },
      };
      return {
        traces: [...ciTraces, historyTrace, futureTrace],
        hasData: hasHistory || hasFuture,
      };
    };
    const buildMarkerShape = (lineDate) =>
      lineDate
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
    // Split forecasts into in-sample vs future using stored cutoff dates.
    const lastObservedDate = series.reduce(
      (acc, row) => (Number.isFinite(row.price) ? row.date : acc),
      null
    );
    const prophetCutoffDate = prophetCutoff || lastObservedDate;
    const lstmCutoffDate = lstmCutoff || lastObservedDate;
    const gruCutoffDate = gruCutoff || lastObservedDate;

    const baselinePrice = prices.find((value) => Number.isFinite(value));
    const priceTraces = [];
    const greenColor = chartColors.priceUp;
    const redColor = chartColors.priceDown;
    const bollingerBandColor = chartColors.bollingerBand;
    const bollingerBandLine = chartColors.bollingerLine;
    const bollingerLineColor = chartColors.bollingerLine;
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
    const prophetBundle = buildForecastTraces({
      rows: prophetForecast,
      cutoffDate: prophetCutoffDate,
      color: chartColors.prophet,
      fillColor: chartColors.prophetFill,
      historyWidth: lineWidths.prophetHistory,
      futureWidth: lineWidths.prophet,
      historyOpacity: 0.55,
      futureOpacity: 1.0,
      name: "Prophet",
    });
    const lstmBundle = buildForecastTraces({
      rows: lstmForecast,
      cutoffDate: lstmCutoffDate,
      color: chartColors.lstm,
      fillColor: chartColors.lstmFill,
      historyWidth: lineWidths.rnnHistory,
      futureWidth: lineWidths.rnn,
      historyOpacity: 0.55,
      futureOpacity: 1.0,
      name: "LSTM",
    });
    const gruBundle = buildForecastTraces({
      rows: gruForecast,
      cutoffDate: gruCutoffDate,
      color: chartColors.gru,
      fillColor: chartColors.gruFill,
      historyWidth: lineWidths.rnnHistory,
      futureWidth: lineWidths.rnn,
      historyOpacity: 0.55,
      futureOpacity: 1.0,
      name: "GRU",
    });
    const prophetTraces = prophetBundle.traces;
    const lstmTraces = lstmBundle.traces;
    const gruTraces = gruBundle.traces;
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
      ...lstmTraces,
      ...gruTraces,
      ...priceTraces,
      priceMonoTrace,
      {
        x: dates,
        y: ema50,
        type: "scatter",
        mode: "lines",
        name: "EMA 50",
        showlegend: false,
        visible: "legendonly",
        line: { color: "#1f77b4", width: smaLineWidth },
      },
      {
        x: dates,
        y: ema20,
        type: "scatter",
        mode: "lines",
        name: "EMA 20",
        showlegend: false,
        visible: "legendonly",
        line: { color: "#ff7f0e", width: smaLineWidth },
      },
      {
        x: dates,
        y: sma50,
        type: "scatter",
        mode: "lines",
        name: "SMA 50",
        showlegend: false,
        visible: "legendonly",
        line: { color: chartColors.sma50, dash: "dash", width: smaLineWidth },
      },
      {
        x: dates,
        y: sma20,
        type: "scatter",
        mode: "lines",
        name: "SMA 20",
        showlegend: false,
        visible: "legendonly",
        line: { color: chartColors.sma20, dash: "dash", width: smaLineWidth },
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

    const prophetMarker = buildMarkerShape(prophetLineDate || prophetCutoffDate);
    const lstmMarker = buildMarkerShape(lstmLineDate || lstmCutoffDate);
    const gruMarker = buildMarkerShape(gruLineDate || gruCutoffDate);

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

    const pickPlotlyIcon = (candidates) => {
      if (!Plotly || !Plotly.Icons) {
        return null;
      }
      for (const key of candidates) {
        if (Plotly.Icons[key]) {
          return Plotly.Icons[key];
        }
      }
      return null;
    };
    const plotConfig = { responsive: true };
    const rulerModebarIcon = pickPlotlyIcon([
      "drawrect",
      "square",
      "rect",
      "shape",
      "selectbox",
      "pencil",
    ]);
    const clearModebarIcon = pickPlotlyIcon([
      "eraseshape",
      "eraser",
      "trash",
      "close",
    ]);
    if (rulerModebarIcon) {
      plotConfig.modeBarButtonsToAdd = [
        {
          name: "Regla",
          title: "Regla (rectángulo)",
          icon: rulerModebarIcon,
          click: () => {
            const nextActive = !rulerState.active;
            if (rulerToggle) {
              rulerToggle.checked = nextActive;
            }
            setRulerActive(nextActive);
            persistToggleState("ruler", nextActive);
          },
        },
      ];
      if (clearModebarIcon) {
        plotConfig.modeBarButtonsToAdd.push({
          name: "Limpiar regla",
          title: "Limpiar regla",
          icon: clearModebarIcon,
          click: () => {
            clearRuler();
          },
        });
      }
    } else {
      plotConfig.modeBarButtonsToAdd = ["drawrect", "eraseshape"];
    }

    Plotly.newPlot("price-chart", data, layout, plotConfig);

    const ema50Toggle = document.getElementById("toggle-ema-50");
    const ema20Toggle = document.getElementById("toggle-ema-20");
    const sma50Toggle = document.getElementById("toggle-sma-50");
    const sma20Toggle = document.getElementById("toggle-sma-20");
    const bollingerToggle = document.getElementById("toggle-bollinger");
    const prophetToggle = document.getElementById("toggle-prophet");
    const lstmToggle = document.getElementById("toggle-lstm");
    const gruToggle = document.getElementById("toggle-gru");
    const priceModeToggle = document.getElementById("toggle-price-mode");
    const rulerToggle = document.getElementById("toggle-ruler");
    const rulerClear = document.getElementById("clear-ruler");
    const prophetTraceOffset = bollingerBandTraces.length;
    const prophetTraceIndices = prophetTraces.map(
      (_, index) => prophetTraceOffset + index
    );
    const lstmTraceOffset = prophetTraceOffset + prophetTraces.length;
    const lstmTraceIndices = lstmTraces.map(
      (_, index) => lstmTraceOffset + index
    );
    const gruTraceOffset = lstmTraceOffset + lstmTraces.length;
    const gruTraceIndices = gruTraces.map((_, index) => gruTraceOffset + index);
    const priceTraceOffset = gruTraceOffset + gruTraces.length;
    const priceTraceIndices = priceTraces.map((_, index) => priceTraceOffset + index);
    const priceMonoIndex = priceTraceOffset + priceTraces.length;
    const indicatorOffset = priceMonoIndex + 1;
    const bollingerBandIndices = bollingerBandTraces.map((_, index) => index);
    const bollingerLineIndices = [indicatorOffset + 4, indicatorOffset + 5];
    const bollingerTraceIndices = [...bollingerBandIndices, ...bollingerLineIndices];

    const setVisibility = (traceIndices, visible) => {
      Plotly.restyle(
        "price-chart",
        { visible: visible ? true : "legendonly" },
        traceIndices
      );
    };
    let suppressRelayout = false;
    const relayoutSafe = (updates) => {
      suppressRelayout = true;
      const relayoutPromise = Plotly.relayout("price-chart", updates);
      if (relayoutPromise && typeof relayoutPromise.finally === "function") {
        relayoutPromise.finally(() => {
          suppressRelayout = false;
        });
      } else {
        suppressRelayout = false;
      }
      return relayoutPromise;
    };
    const refreshAxes = () => {
      relayoutSafe({
        "xaxis.autorange": true,
        "yaxis.autorange": true,
      });
    };
    const activeMarkers = {
      prophet: null,
      lstm: null,
      gru: null,
    };
    const rulerState = {
      active: false,
      rect: null,
      line: null,
      annotation: null,
      lastDragMode: null,
      isUpdating: false,
    };
    const formatElapsed = (ms) => {
      const absMs = Math.abs(ms);
      const minutes = absMs / 60000;
      if (minutes < 60) {
        return `${Math.round(minutes)} min`;
      }
      const hours = absMs / 3600000;
      if (hours < 24) {
        return `${hours.toFixed(1)} h`;
      }
      const days = absMs / 86400000;
      const decimals = days < 10 ? 2 : 1;
      return `${days.toFixed(decimals)} días`;
    };
    const parseDateValue = (value) => {
      if (value instanceof Date) {
        return value;
      }
      const parsed = new Date(value);
      if (Number.isNaN(parsed.getTime())) {
        return null;
      }
      return parsed;
    };
    const formatPercent = (value) => {
      if (!Number.isFinite(value)) {
        return "--";
      }
      const sign = value >= 0 ? "+" : "";
      return `${sign}${value.toFixed(2)}%`;
    };
    const buildRulerOverlay = (rect) => {
      if (!rect) {
        return null;
      }
      const x0 = rect.x0;
      const x1 = rect.x1;
      const y0 = Number(rect.y0);
      const y1 = Number(rect.y1);
      if (!Number.isFinite(y0) || !Number.isFinite(y1)) {
        return null;
      }
      const startDate = parseDateValue(x0);
      const endDate = parseDateValue(x1);
      const deltaTimeMs =
        startDate && endDate ? endDate.getTime() - startDate.getTime() : 0;
      const deltaPct = y0 !== 0 ? ((y1 - y0) / y0) * 100 : null;
      const midX =
        startDate && endDate
          ? new Date(
              (startDate.getTime() + endDate.getTime()) / 2
            ).toISOString()
          : x0;
      const midY = (y0 + y1) / 2;
      return {
        rect: {
          type: "rect",
          xref: "x",
          yref: "y",
          x0,
          x1,
          y0,
          y1,
          line: { color: rulerColors.line, width: 1.2, dash: "dot" },
          fillcolor: rulerColors.fill,
          opacity: 0.25,
          layer: "above",
        },
        line: {
          type: "line",
          xref: "x",
          yref: "y",
          x0,
          x1,
          y0,
          y1,
          line: { color: rulerColors.line, width: 2 },
          layer: "above",
        },
        annotation: {
          x: midX,
          y: midY,
          xref: "x",
          yref: "y",
          text: `${formatPercent(deltaPct)}<br>${formatElapsed(deltaTimeMs)}`,
          showarrow: false,
          bgcolor: rulerColors.annotationBg,
          bordercolor: rulerColors.annotationBorder,
          borderwidth: 1,
          font: { size: 11, color: "#2f2f2f" },
          align: "center",
        },
      };
    };
    const updateOverlays = () => {
      const markerShapes = Object.values(activeMarkers).filter(Boolean);
      const rulerShapes = [];
      if (rulerState.rect) {
        rulerShapes.push(rulerState.rect);
      }
      if (rulerState.line) {
        rulerShapes.push(rulerState.line);
      }
      const annotations = rulerState.annotation ? [rulerState.annotation] : [];
      rulerState.isUpdating = true;
      const overlayPromise = relayoutSafe({
        shapes: [...markerShapes, ...rulerShapes],
        annotations,
      });
      if (overlayPromise && typeof overlayPromise.finally === "function") {
        overlayPromise.finally(() => {
          rulerState.isUpdating = false;
        });
      } else {
        setTimeout(() => {
          rulerState.isUpdating = false;
        }, 0);
      }
    };
    const updateMarkers = () => {
      updateOverlays();
    };

    if (ema50Toggle) {
      ema50Toggle.addEventListener("change", (event) => {
        setVisibility([indicatorOffset], event.target.checked);
        persistToggleState("ema50", event.target.checked);
      });
    }
    if (ema20Toggle) {
      ema20Toggle.addEventListener("change", (event) => {
        setVisibility([indicatorOffset + 1], event.target.checked);
        persistToggleState("ema20", event.target.checked);
      });
    }
    if (sma50Toggle) {
      sma50Toggle.addEventListener("change", (event) => {
        setVisibility([indicatorOffset + 2], event.target.checked);
        persistToggleState("sma50", event.target.checked);
      });
    }
    if (sma20Toggle) {
      sma20Toggle.addEventListener("change", (event) => {
        setVisibility([indicatorOffset + 3], event.target.checked);
        persistToggleState("sma20", event.target.checked);
      });
    }
    if (bollingerToggle) {
      bollingerToggle.addEventListener("change", (event) => {
        setVisibility(bollingerTraceIndices, event.target.checked);
        persistToggleState("bollinger", event.target.checked);
      });
    }
    const prophetHasData = prophetBundle.hasData;
    const lstmHasData = lstmBundle.hasData;
    const gruHasData = gruBundle.hasData;
    if (prophetToggle && !prophetHasData) {
      prophetToggle.disabled = true;
      prophetToggle.title = "Prophet sin datos";
    }
    if (prophetToggle) {
      prophetToggle.addEventListener("change", (event) => {
        setVisibility(prophetTraceIndices, event.target.checked);
        if (prophetMarker) {
          activeMarkers.prophet = event.target.checked ? prophetMarker : null;
          updateMarkers();
        }
        if (event.target.checked) {
          refreshAxes();
        }
        persistToggleState("prophet", event.target.checked);
      });
    }
    if (lstmToggle && !lstmHasData) {
      lstmToggle.disabled = true;
      lstmToggle.title = "LSTM sin datos";
    }
    if (lstmToggle) {
      lstmToggle.addEventListener("change", (event) => {
        setVisibility(lstmTraceIndices, event.target.checked);
        if (lstmMarker) {
          activeMarkers.lstm = event.target.checked ? lstmMarker : null;
          updateMarkers();
        }
        if (event.target.checked) {
          refreshAxes();
        }
        persistToggleState("lstm", event.target.checked);
      });
    }
    if (gruToggle && !gruHasData) {
      gruToggle.disabled = true;
      gruToggle.title = "GRU sin datos";
    }
    if (gruToggle) {
      gruToggle.addEventListener("change", (event) => {
        setVisibility(gruTraceIndices, event.target.checked);
        if (gruMarker) {
          activeMarkers.gru = event.target.checked ? gruMarker : null;
          updateMarkers();
        }
        if (event.target.checked) {
          refreshAxes();
        }
        persistToggleState("gru", event.target.checked);
      });
    }
    const clearRuler = (deactivate = true) => {
      rulerState.rect = null;
      rulerState.line = null;
      rulerState.annotation = null;
      updateOverlays();
      if (deactivate) {
        if (rulerToggle) {
          rulerToggle.checked = false;
        }
        setRulerActive(false);
        persistToggleState("ruler", false);
      }
    };
    const setRulerActive = (active) => {
      rulerState.active = active;
      if (active) {
        rulerState.lastDragMode =
          (chartEl._fullLayout && chartEl._fullLayout.dragmode) || "zoom";
        relayoutSafe({
          dragmode: "drawrect",
          newshape: {
            line: { color: rulerColors.line, width: 1.2 },
            fillcolor: rulerColors.fill,
            opacity: 0.25,
          },
        });
      } else {
        relayoutSafe({
          dragmode: rulerState.lastDragMode || "zoom",
          newshape: {},
        });
      }
    };
    const extractRectFromRelayout = (eventData) => {
      if (!eventData) {
        return null;
      }
      if (Array.isArray(eventData.shapes) && eventData.shapes.length) {
        for (let i = eventData.shapes.length - 1; i >= 0; i -= 1) {
          const shape = eventData.shapes[i];
          if (shape && shape.type === "rect") {
            return shape;
          }
        }
      }
      const keys = Object.keys(eventData).filter((key) =>
        key.startsWith("shapes[")
      );
      if (!keys.length) {
        return null;
      }
      const match = keys[0].match(/^shapes\[(\d+)\]/);
      if (!match) {
        return null;
      }
      const index = Number(match[1]);
      const shapes =
        (chartEl.layout && chartEl.layout.shapes) ||
        (chartEl._fullLayout && chartEl._fullLayout.shapes) ||
        [];
      const shape = shapes[index];
      return shape && shape.type === "rect" ? shape : null;
    };
    chartEl.on("plotly_relayout", (eventData) => {
      if (suppressRelayout || rulerState.isUpdating) {
        return;
      }
      if (!eventData) {
        return;
      }
      const relayoutKeys = Object.keys(eventData);
      const shapesProvided = Array.isArray(eventData.shapes);
      if (shapesProvided && eventData.shapes.length === 0) {
        clearRuler();
        return;
      }
      const hasShapeArray = shapesProvided && eventData.shapes.length > 0;
      const hasShapeCorners = relayoutKeys.some((key) =>
        /^shapes\[\d+\]\.(x0|x1|y0|y1)$/.test(key)
      );
      if (!hasShapeArray && !hasShapeCorners) {
        return;
      }
      const rect = extractRectFromRelayout(eventData);
      if (!rect) {
        clearRuler();
        return;
      }
      if (!rulerState.active) {
        rulerState.active = true;
        if (rulerToggle) {
          rulerToggle.checked = true;
        }
      }
      const overlay = buildRulerOverlay(rect);
      if (!overlay) {
        return;
      }
      rulerState.rect = overlay.rect;
      rulerState.line = overlay.line;
      rulerState.annotation = overlay.annotation;
      updateOverlays();
    });
    if (rulerToggle) {
      rulerToggle.addEventListener("change", (event) => {
        setRulerActive(event.target.checked);
        persistToggleState("ruler", event.target.checked);
      });
    }
    if (rulerClear) {
      rulerClear.addEventListener("click", () => {
        clearRuler();
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
        persistToggleState("priceMode", useMono);
      });
    }

    const savedToggles = readToggleState();
    const applyToggleState = (toggle, key) => {
      if (!toggle || toggle.disabled) {
        return;
      }
      const savedValue = savedToggles[key];
      if (typeof savedValue !== "boolean") {
        return;
      }
      toggle.checked = savedValue;
      toggle.dispatchEvent(new Event("change", { bubbles: true }));
    };

    applyToggleState(ema50Toggle, "ema50");
    applyToggleState(ema20Toggle, "ema20");
    applyToggleState(sma50Toggle, "sma50");
    applyToggleState(sma20Toggle, "sma20");
    applyToggleState(bollingerToggle, "bollinger");
    applyToggleState(prophetToggle, "prophet");
    applyToggleState(lstmToggle, "lstm");
    applyToggleState(gruToggle, "gru");
    applyToggleState(priceModeToggle, "priceMode");
    applyToggleState(rulerToggle, "ruler");
  }
}
