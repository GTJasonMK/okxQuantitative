import { createLatestOnly } from '@/utils/async';

export function createMarketViewChartRendering(ctx) {
  // 图表数据加载的"最新请求胜出"控制器：
  // 快速切换 symbol/timeframe 时，旧的 loadChartData 会被自动丢弃。
  const chartDataLoader = createLatestOnly();

  let {
    api,
    loading,
    activeSymbol,
    activeAnalysisTool,
    selectedSymbols,
    marketInstType,
    currentTimeframe,
    displayRangeDays,
    maxTrackedCandles,
    chartRefs,
    chartInstances,
    chartLoading,
    chartErrors,
    candlesData,
    tickers,
    indicators,
    showTradeMarkers,
    fillsData,
    TIMEFRAME_MS,
    DEFAULT_VISIBLE_CANDLES,
    MIN_DATA_ZOOM_SPAN_PERCENT,
    CHART_TOUCHPAD_PAN_RATIO,
    CHART_DRAG_PAN_RATIO,
    normalizeMonitorSymbol,
    resolveMarketInstId,
    toFiniteNumber,
    binarySearchCandleIndex,
    getCandleTimestamp,
    formatPrice,
    formatTradeSize,
    loadFillsForSymbol,
    loadExecutionPanelData,
    normalizeTickerData,
    applyIncomingTicker,
    clamp,
    nextTick,
    chartViewportStates,
    chartWheelInteractionHandlers,
    chartDragInteractionHandlers,
    chartAnnotationInteractionHandlers,
    chartAnnotationRefreshTimers,
    chartViewportAxisRefreshTimers,
    chartViewportActionFrames,
    chartPendingViewportActions,
    chartViewportInteractionTimers,
    chartViewportInteractionUntil,
    chartViewportInteractionFlags,
    chartViewportInteractionLightweightSymbols,
    chartDeferredSetOptionFrames,
    chartDeferredSetOptionPayloads,
    chartDeferredResizeFrames,
    chartDeferredResizePayloads,
    chartDeferredHideTipFrames,
    chartRawResizeFns,
    chartDraftPreviewSignatures,
    chartAnnotations,
    chartSelectedAnnotationIds,
    chartAnnotationDrafts,
    chartAnnotationUpdateFrames,
    chartAnnotationEditSessions,
    chartAnnotationSuppressClickUntil,
    chartRenderCaches,
    CHART_ANNOTATION_REFRESH_DELAY,
    CHART_ANNOTATION_UPDATE_FRAME_MS,
    CHART_REALTIME_ANIMATION_DURATION,
    CHART_REALTIME_AXIS_ANIMATION_DURATION,
    CHART_REALTIME_ANIMATION_EASING,
    CHART_VIEWPORT_ACTION_FRAME_MS,
    CHART_VIEWPORT_AXIS_REFRESH_DELAY,
    CHART_VIEWPORT_AXIS_INTERACTION_REFRESH_DELAY,
    CHART_VIEWPORT_INTERACTION_IDLE_MS,
    CHART_LATEST_CANDLE_VIEW_RATIO,
    ENABLE_CHART_VIEWPORT_LIGHTWEIGHT_MODE,
    DAY_MS,
    RANGE_FETCH_BATCH_LIMIT,
    RANGE_FETCH_WARMUP_CANDLES,
    RANGE_FETCH_MIN_CANDLES,
    getDisplayRangeDays,
    getMaxTrackedCandles,
    estimateVisibleRangeCandles,
    getChartVisibleCandleHint,
    getChartLatestAnchorPaddingCount,
    getChartRightPaddingCount,
    getChartRenderLength,
    getChartLatestRenderPercent,
    buildLatestAnchoredViewportState,
    getChartMaxViewportStart,
    getChartViewportStateKey,
    buildDefaultChartViewportState,
    getChartViewportState,
    setChartViewportState,
    clearChartViewportState,
    buildDisplayRangeWindow,
    mergeCandlesByTimestamp,
    applyDisplayRangeViewport,
    loadCandlesForSelectedRange,
    getChartAnnotationStateKey,
    getChartAnnotations,
    getSelectedChartAnnotationId,
    getSelectedChartAnnotation,
    getChartAnnotationDraft,
    getChartAnnotationCount,
    setChartAnnotations,
    setSelectedChartAnnotationId,
    clearSelectedChartAnnotation,
    setChartAnnotationDraft,
    updateChartAnnotation,
    scheduleAnnotationOnlyChartUpdate,
    exportChartAnnotationsForPersistence,
    hydrateChartAnnotationsFromPersistence,
    scheduleChartAnnotationRefresh,
    clearChartAnnotationFrame,
    clearChartAnnotationUpdateFrame,
    clearChartViewportAxisRefresh,
    clearChartViewportActionFrame,
    buildDeferredSetOptionKey,
    isChartInMainProcess,
    clearDeferredChartSetOptions,
    clearDeferredChartResizes,
    clearDeferredChartHideTip,
    scheduleDeferredChartSetOptionFlush,
    applyChartSetOption,
    scheduleDeferredChartResizeFlush,
    applyChartResize,
    scheduleChartHideTip,
    clearChartViewportInteractionTimer,
    getChartViewportInteractionRemainingMs,
    isChartViewportInteracting,
    clearChartViewportInteraction,
    buildCurrentPriceLineSeries,
    buildCurrentPriceLineGraphic,
    buildLightweightInteractionSeries,
    applyChartViewportInteractionLightweightMode,
    restoreChartViewportInteractionLightweightMode,
    markChartViewportInteracting,
    scheduleChartViewportAction,
    clearChartDraftPreview,
    clearChartGraphicOverlays,
    clearChartAnnotations,
    removeLastChartAnnotation,
    removeSelectedChartAnnotation,
    cancelChartAnnotationDraft,
    getChartDataZoomWindow,
    removeChartWheelInteraction,
    removeChartDragInteraction,
    removeChartAnnotationInteraction,
    disposeChartInstance,
    panChartViewportByWheel,
    zoomChartViewportByWheel,
    bindChartWheelInteraction,
    bindChartDragInteraction,
    createChartAnnotationId,
    findClosestCandleIndexByTimestamp,
    getChartPrimaryGridRect,
    convertChartCoordToPixel,
    getChartRenderLengthForSymbol,
    getDistanceToSegment,
    isPointInsideRect,
    buildAnnotationPixelGeometry,
    resolveChartAnnotationHit,
    updateChartAnnotationFromPoint,
    clearChartAnnotationEditSession,
    beginSelectedChartAnnotationEdit,
    updateSelectedChartAnnotationEdit,
    finishSelectedChartAnnotationEdit,
    getChartValueFromPointerEvent,
    appendChartAnnotation,
    bindChartAnnotationInteraction,
    initChart,
    calculateMA,
    calculateEMA,
    calculateBOLL,
    calculateSAR,
    updateMALastPoint,
    updateEMALastPoint,
    updateBollLastPoint,
    buildTrendlineAnnotationSeries,
    formatRulerSignedPrice,
    formatRulerSignedPercent,
    formatRulerDuration,
    buildRulerAnnotationSeries,
    buildHorizontalAnnotationSeries,
    buildRectangleAnnotationSeries,
    buildDraftPreviewSignature,
    buildDraftPreviewPoint,
    buildDraftPreviewLabelY,
    buildSelectedAnnotationGraphic,
    buildChartGraphicOverlays,
    buildChartDraftPreviewGraphic,
    renderChartDraftPreview,
    buildAnnotationSeries,
    getChartRenderContextKey,
    getIndicatorsSignature,
    getFillsSignature,
    serializeAnnotationSignature,
    getAnnotationSignature,
    buildChartCoreMetaSignature,
    buildChartMetaSignature,
    buildChartAxisLabels,
    buildOhlcSeriesData,
    buildVolumeSeriesData,
    buildTradeMarkerSeries,
    syncRealtimeChartRenderCache,
    syncChartAnnotationRenderCache,
    buildChartRenderCache,
    canReuseChartRenderCacheBase,
    canUseRealtimeChartCache,
    buildChartSeries,
    buildRealtimeChartSeriesPatch,
    getViewportVisibleIndexRange,
    createFiniteRangeTracker,
    pushRangeValue,
    pushPositiveRangeValue,
    hasFiniteRange,
    pushSeriesSliceRangeValues,
    resolveVisiblePriceAxisRange,
    resolveVisibleVolumeAxisRange,
    buildExpandedRange,
    resolveAxisExtentRange,
    buildChartYAxisPatch,
    buildChartXAxisLabelFormatter,
    buildChartXAxisPatch,
    scheduleChartViewportAxisRefresh,
    resolveCurrentPriceLineValue,
    extractTooltipSeriesValue,
    buildTooltipIndicatorRow,
    buildChartTooltipFormatter,
    updateChart,
    loadChartData,
    updateAllCharts,
    refreshChart,
    refreshActiveChart,
    refreshAllCharts,
    refreshAllTickers,
    ANNOTATION_HANDLE_HIT_RADIUS,
    ANNOTATION_BODY_HIT_RADIUS,
    ANNOTATION_SELECTED_STROKE,
    ANNOTATION_SELECTED_FILL,
  } = ctx;

  buildTradeMarkerSeries = (symbol, candles) => {
    if (!showTradeMarkers.value || !Array.isArray(fillsData[symbol]) || fillsData[symbol].length === 0) {
      return [];
    }

    const fills = fillsData[symbol];
    const buyMarkers = [];
    const sellMarkers = [];
    const duration = TIMEFRAME_MS[currentTimeframe.value] || 60 * 60 * 1000;

    fills.forEach(fill => {
      const fillTime = parseInt(fill.ts);
      const idx = binarySearchCandleIndex(candles, fillTime, duration);
      if (idx < 0) {
        return;
      }

      const price = parseFloat(fill.fill_px);
      if (fill.side === 'buy') {
        buyMarkers.push([idx, price]);
      } else {
        sellMarkers.push([idx, price]);
      }
    });

    const series = [];
    if (buyMarkers.length > 0) {
      series.push({
        id: 'trade-marker-buy',
        name: '买入',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: buyMarkers,
        symbolSize: 14,
        symbol: 'triangle',
        symbolRotate: 0,
        itemStyle: { color: '#26a69a' },
        label: {
          show: true,
          position: 'bottom',
          formatter: 'B',
          fontSize: 10,
          fontWeight: 'bold',
          color: '#26a69a',
        },
        z: 10,
      });
    }

    if (sellMarkers.length > 0) {
      series.push({
        id: 'trade-marker-sell',
        name: '卖出',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: sellMarkers,
        symbolSize: 14,
        symbol: 'triangle',
        symbolRotate: 180,
        itemStyle: { color: '#ef5350' },
        label: {
          show: true,
          position: 'top',
          formatter: 'S',
          fontSize: 10,
          fontWeight: 'bold',
          color: '#ef5350',
        },
        z: 10,
      });
    }

    return series;
  };

  syncRealtimeChartRenderCache = (symbol, candles) => {
    const cache = chartRenderCaches[symbol];
    if (!cache) {
      return null;
    }

    const lastCandle = candles[candles.length - 1];
    const lastIndex = candles.length - 1;
    cache.candles = candles;
    cache.length = candles.length;
    cache.lastTimestamp = getCandleTimestamp(lastCandle);
    cache.ohlc[lastIndex] = [lastCandle.open, lastCandle.close, lastCandle.low, lastCandle.high];
    cache.closeData[lastIndex] = lastCandle.close;
    cache.volumeData[lastIndex] = lastCandle.volume || 0;
    cache.volumes[lastIndex] = {
      value: lastCandle.volume || 0,
      itemStyle: {
        color: lastCandle.close >= lastCandle.open ? '#26a69a' : '#ef5350',
      },
    };

    cache.ma5 = indicators.ma5 ? updateMALastPoint(cache.ma5 || calculateMA(cache.closeData, 5), cache.closeData, 5) : null;
    cache.ma10 = indicators.ma10 ? updateMALastPoint(cache.ma10 || calculateMA(cache.closeData, 10), cache.closeData, 10) : null;
    cache.ma20 = indicators.ma20 ? updateMALastPoint(cache.ma20 || calculateMA(cache.closeData, 20), cache.closeData, 20) : null;
    cache.ma60 = indicators.ma60 ? updateMALastPoint(cache.ma60 || calculateMA(cache.closeData, 60), cache.closeData, 60) : null;
    cache.ema12 = indicators.ema12 ? updateEMALastPoint(cache.ema12 || calculateEMA(cache.closeData, 12), cache.closeData, 12) : null;
    cache.ema26 = indicators.ema26 ? updateEMALastPoint(cache.ema26 || calculateEMA(cache.closeData, 26), cache.closeData, 26) : null;
    cache.boll = indicators.boll ? updateBollLastPoint(cache.boll || calculateBOLL(cache.closeData), cache.closeData) : null;
    cache.vma5 = indicators.vma5 ? updateMALastPoint(cache.vma5 || calculateMA(cache.volumeData, 5), cache.volumeData, 5) : null;
    cache.vma10 = indicators.vma10 ? updateMALastPoint(cache.vma10 || calculateMA(cache.volumeData, 10), cache.volumeData, 10) : null;
    cache.vma20 = indicators.vma20 ? updateMALastPoint(cache.vma20 || calculateMA(cache.volumeData, 20), cache.volumeData, 20) : null;
    cache.coreMetaSignature = buildChartCoreMetaSignature(symbol);
    cache.annotationSignature = getAnnotationSignature(symbol);
    cache.metaSignature = buildChartMetaSignature(symbol);
    return cache;
  };

  syncChartAnnotationRenderCache = (symbol, candles) => {
    const cache = chartRenderCaches[symbol];
    if (!cache) {
      return null;
    }

    cache.candles = candles;
    cache.length = candles.length;
    cache.lastTimestamp = getCandleTimestamp(candles[candles.length - 1]);
    cache.annotationSeries = buildAnnotationSeries(symbol, candles);
    cache.annotationSignature = getAnnotationSignature(symbol);
    cache.metaSignature = buildChartMetaSignature(symbol);
    return cache;
  };

  buildChartRenderCache = (symbol, candles) => {
    const closeData = candles.map(candle => candle.close);
    const volumeData = candles.map(candle => toFiniteNumber(candle.volume, 0));
    const rightPaddingCount = getChartRightPaddingCount(candles.length, currentTimeframe.value);
    const cache = {
      symbol,
      contextKey: getChartRenderContextKey(symbol),
      coreMetaSignature: buildChartCoreMetaSignature(symbol),
      annotationSignature: getAnnotationSignature(symbol),
      metaSignature: buildChartMetaSignature(symbol),
      candles,
      dates: buildChartAxisLabels(candles, { rightPaddingCount }),
      ohlc: buildOhlcSeriesData(candles),
      closeData,
      volumeData,
      volumes: buildVolumeSeriesData(candles),
      length: candles.length,
      renderLength: candles.length + rightPaddingCount,
      rightPaddingCount,
      lastTimestamp: getCandleTimestamp(candles[candles.length - 1]),
      annotationSeries: buildAnnotationSeries(symbol, candles),
      tradeMarkerSeries: buildTradeMarkerSeries(symbol, candles),
      ma5: indicators.ma5 ? calculateMA(closeData, 5) : null,
      ma10: indicators.ma10 ? calculateMA(closeData, 10) : null,
      ma20: indicators.ma20 ? calculateMA(closeData, 20) : null,
      ma60: indicators.ma60 ? calculateMA(closeData, 60) : null,
      ema12: indicators.ema12 ? calculateEMA(closeData, 12) : null,
      ema26: indicators.ema26 ? calculateEMA(closeData, 26) : null,
      boll: indicators.boll ? calculateBOLL(closeData) : null,
      vma5: indicators.vma5 ? calculateMA(volumeData, 5) : null,
      vma10: indicators.vma10 ? calculateMA(volumeData, 10) : null,
      vma20: indicators.vma20 ? calculateMA(volumeData, 20) : null,
      sarData: indicators.sar ? calculateSAR(candles) : null,
    };
    chartRenderCaches[symbol] = cache;
    return cache;
  };

  canReuseChartRenderCacheBase = (symbol, candles) => {
    const cache = chartRenderCaches[symbol];
    if (!cache || !Array.isArray(candles) || candles.length === 0) {
      return false;
    }

    const lastTimestamp = getCandleTimestamp(candles[candles.length - 1]);
    return (
      cache.contextKey === getChartRenderContextKey(symbol)
      && cache.coreMetaSignature === buildChartCoreMetaSignature(symbol)
      && cache.length === candles.length
      && cache.lastTimestamp === lastTimestamp
    );
  };

  canUseRealtimeChartCache = (symbol, candles) => {
    if (!canReuseChartRenderCacheBase(symbol, candles)) {
      return false;
    }

    const cache = chartRenderCaches[symbol];
    return cache.annotationSignature === getAnnotationSignature(symbol);
  };

  buildChartSeries = (cache, latestPrice, latestPriceColor, visibleRange = null) => {
    const series = [
      {
        id: 'kline',
        name: 'K线',
        type: 'candlestick',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: cache.ohlc,
        itemStyle: {
          color: '#26a69a',
          color0: '#ef5350',
          borderColor: '#26a69a',
          borderColor0: '#ef5350',
        },
      },
    ];

    [
      { data: cache.ma5, name: 'MA5', color: '#f6c85d' },
      { data: cache.ma10, name: 'MA10', color: '#6be6c1' },
      { data: cache.ma20, name: 'MA20', color: '#3fb1e3' },
      { data: cache.ma60, name: 'MA60', color: '#a38bf8' },
    ].forEach(cfg => {
      if (cfg.data) {
        series.push({
          id: cfg.name.toLowerCase(),
          name: cfg.name,
          type: 'line',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: cfg.data,
          smooth: false,
          sampling: 'lttb',
          showSymbol: false,
          lineStyle: { width: 1, color: cfg.color },
        });
      }
    });

    [
      { data: cache.ema12, name: 'EMA12', color: '#ff6b6b' },
      { data: cache.ema26, name: 'EMA26', color: '#4ecdc4' },
    ].forEach(cfg => {
      if (cfg.data) {
        series.push({
          id: cfg.name.toLowerCase(),
          name: cfg.name,
          type: 'line',
          xAxisIndex: 0,
          yAxisIndex: 0,
          data: cfg.data,
          smooth: false,
          sampling: 'lttb',
          showSymbol: false,
          lineStyle: { width: 1, color: cfg.color },
        });
      }
    });

    if (cache.boll) {
      series.push({
        id: 'boll-upper',
        name: 'BOLL上轨',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: cache.boll.upper,
        smooth: false,
        sampling: 'lttb',
        showSymbol: false,
        lineStyle: { width: 1, color: '#ff9800', type: 'dashed' },
      });
      series.push({
        id: 'boll-middle',
        name: 'BOLL中轨',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: cache.boll.middle,
        smooth: false,
        sampling: 'lttb',
        showSymbol: false,
        lineStyle: { width: 1, color: '#ff9800' },
      });
      series.push({
        id: 'boll-lower',
        name: 'BOLL下轨',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: cache.boll.lower,
        smooth: false,
        sampling: 'lttb',
        showSymbol: false,
        lineStyle: { width: 1, color: '#ff9800', type: 'dashed' },
      });
    }

    if (cache.sarData) {
      series.push({
        id: 'sar',
        name: 'SAR',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: cache.sarData,
        symbolSize: 4,
        itemStyle: { color: '#e91e63' },
      });
    }

    if (cache.tradeMarkerSeries.length > 0) {
      series.push(...cache.tradeMarkerSeries);
    }

    if (cache.annotationSeries.length > 0) {
      series.push(...cache.annotationSeries);
    }

    series.push({
      id: 'volume',
      name: '成交量',
      type: 'bar',
      xAxisIndex: 1,
      yAxisIndex: 1,
      data: cache.volumes,
      barMinHeight: 1,
      z: 1,
    });

    [
      { data: cache.vma5, name: 'VMA5', color: '#ffb347' },
      { data: cache.vma10, name: 'VMA10', color: '#7bdff2' },
      { data: cache.vma20, name: 'VMA20', color: '#c792ea' },
    ].forEach(cfg => {
      if (cfg.data) {
        series.push({
          id: cfg.name.toLowerCase(),
          name: cfg.name,
          type: 'line',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: cfg.data,
          smooth: false,
          sampling: 'lttb',
          showSymbol: false,
          connectNulls: false,
          z: 3,
          lineStyle: { width: 1.2, color: cfg.color, opacity: 0.94 },
        });
      }
    });

    return series;
  };

  buildRealtimeChartSeriesPatch = (cache, latestPrice, latestPriceColor, visibleRange = null) => {
    const series = [
      {
        id: 'kline',
        data: cache.ohlc,
        animation: false,
      },
      {
        id: 'volume',
        data: cache.volumes,
        animation: false,
      },
    ];

    [
      { enabled: indicators.ma5, id: 'ma5', data: cache.ma5 },
      { enabled: indicators.ma10, id: 'ma10', data: cache.ma10 },
      { enabled: indicators.ma20, id: 'ma20', data: cache.ma20 },
      { enabled: indicators.ma60, id: 'ma60', data: cache.ma60 },
      { enabled: indicators.ema12, id: 'ema12', data: cache.ema12 },
      { enabled: indicators.ema26, id: 'ema26', data: cache.ema26 },
      { enabled: indicators.boll, id: 'boll-upper', data: cache.boll?.upper || null },
      { enabled: indicators.boll, id: 'boll-middle', data: cache.boll?.middle || null },
      { enabled: indicators.boll, id: 'boll-lower', data: cache.boll?.lower || null },
      { enabled: indicators.vma5, id: 'vma5', data: cache.vma5 },
      { enabled: indicators.vma10, id: 'vma10', data: cache.vma10 },
      { enabled: indicators.vma20, id: 'vma20', data: cache.vma20 },
    ].forEach((item) => {
      if (!item.enabled || !item.data) {
        return;
      }
      series.push({
        id: item.id,
        data: item.data,
        smooth: false,
        sampling: 'lttb',
        animation: false,
      });
    });

    if (cache.sarData) {
      series.push({
        id: 'sar',
        name: 'SAR',
        type: 'scatter',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: cache.sarData,
        symbolSize: 4,
        itemStyle: { color: '#e91e63' },
        animation: false,
      });
    }

    if (Array.isArray(cache.tradeMarkerSeries) && cache.tradeMarkerSeries.length > 0) {
      series.push(...cache.tradeMarkerSeries);
    }

    if (Array.isArray(cache.annotationSeries) && cache.annotationSeries.length > 0) {
      series.push(...cache.annotationSeries);
    }

    return series;
  };

  getViewportVisibleIndexRange = (length, viewportState, renderLength = length) => {
    if (!Number.isFinite(length) || length <= 0) {
      return {
        startIndex: 0,
        endIndex: -1,
        startRenderIndex: 0,
        endRenderIndex: -1,
      };
    }

    const normalizedRenderLength = Math.max(
      Number.isFinite(renderLength) ? Math.floor(renderLength) : length,
      length,
      1
    );
    const renderLastIndex = Math.max(normalizedRenderLength - 1, 0);

    if (!viewportState || !Number.isFinite(viewportState.start) || !Number.isFinite(viewportState.end)) {
      return {
        startIndex: 0,
        endIndex: length - 1,
        startRenderIndex: 0,
        endRenderIndex: renderLastIndex,
      };
    }

    const lastIndex = Math.max(length - 1, 0);
    const startRenderIndex = clamp(
      Math.floor((viewportState.start / 100) * renderLastIndex),
      0,
      renderLastIndex
    );
    const endRenderIndex = clamp(
      Math.ceil((viewportState.end / 100) * renderLastIndex),
      startRenderIndex,
      renderLastIndex
    );
    const startIndex = clamp(startRenderIndex, 0, lastIndex);
    const endIndex = clamp(Math.min(endRenderIndex, lastIndex), startIndex, lastIndex);
    return { startIndex, endIndex, startRenderIndex, endRenderIndex };
  };

  createFiniteRangeTracker = () => ({
    min: Number.POSITIVE_INFINITY,
    max: Number.NEGATIVE_INFINITY,
  });

  pushRangeValue = (range, value) => {
    const numeric = toFiniteNumber(value, Number.NaN);
    if (!Number.isFinite(numeric)) {
      return;
    }
    range.min = Math.min(range.min, numeric);
    range.max = Math.max(range.max, numeric);
  };

  pushPositiveRangeValue = (range, value) => {
    const numeric = toFiniteNumber(value, Number.NaN);
    if (!Number.isFinite(numeric) || numeric <= 0) {
      return;
    }
    range.min = Math.min(range.min, numeric);
    range.max = Math.max(range.max, numeric);
  };

  hasFiniteRange = (range) => (
    Number.isFinite(range?.min)
    && Number.isFinite(range?.max)
    && range.max >= range.min
  );

  pushSeriesSliceRangeValues = (range, series, startIndex, endIndex, options = {}) => {
    if (!Array.isArray(series) || series.length === 0) {
      return;
    }

    const safeStartIndex = clamp(
      Math.floor(toFiniteNumber(startIndex, 0)),
      0,
      Math.max(series.length - 1, 0)
    );
    const safeEndIndex = clamp(
      Math.ceil(toFiniteNumber(endIndex, safeStartIndex)),
      safeStartIndex,
      Math.max(series.length - 1, 0)
    );

    const pushValue = options.positiveOnly ? pushPositiveRangeValue : pushRangeValue;

    for (let index = safeStartIndex; index <= safeEndIndex; index += 1) {
      const point = series[index];

      if (point === null || point === undefined) {
        continue;
      }

      if (Array.isArray(point)) {
        pushValue(range, point[1] ?? point[point.length - 1]);
        continue;
      }

      if (typeof point === 'object') {
        if (Array.isArray(point.value)) {
          pushValue(range, point.value[1] ?? point.value[point.value.length - 1]);
          continue;
        }

        if (point.value !== undefined) {
          pushValue(range, point.value);
          continue;
        }
      }

      pushValue(range, point);
    }
  };

  resolveVisiblePriceAxisRange = (symbol, options = {}) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    const cache = normalizedSymbol ? chartRenderCaches[normalizedSymbol] : null;
    const candles = Array.isArray(cache?.candles) ? cache.candles : candlesData[normalizedSymbol];
    if (!Array.isArray(candles) || candles.length === 0) {
      return null;
    }

    const viewportState = getChartViewportState(normalizedSymbol, candles.length);
    const renderLength = Math.max(
      Number.isFinite(cache?.renderLength) ? cache.renderLength : 0,
      Array.isArray(cache?.dates) ? cache.dates.length : 0,
      getChartRenderLength(candles.length),
      candles.length
    );
    const visibleRange = getViewportVisibleIndexRange(candles.length, viewportState, renderLength);
    const range = createFiniteRangeTracker();

    for (let index = visibleRange.startIndex; index <= visibleRange.endIndex; index += 1) {
      const candle = candles[index];
      pushPositiveRangeValue(range, candle?.low);
      pushPositiveRangeValue(range, candle?.high);
    }

    [
      indicators.ma5 ? cache?.ma5 : null,
      indicators.ma10 ? cache?.ma10 : null,
      indicators.ma20 ? cache?.ma20 : null,
      indicators.ma60 ? cache?.ma60 : null,
      indicators.ema12 ? cache?.ema12 : null,
      indicators.ema26 ? cache?.ema26 : null,
      indicators.boll ? cache?.boll?.upper : null,
      indicators.boll ? cache?.boll?.middle : null,
      indicators.boll ? cache?.boll?.lower : null,
      indicators.sar ? cache?.sarData : null,
    ].forEach(series => {
      pushSeriesSliceRangeValues(range, series, visibleRange.startIndex, visibleRange.endIndex, {
        positiveOnly: true,
      });
    });

    const referenceCandle = candles[visibleRange.endIndex] || candles[candles.length - 1];
    const referencePrice = toFiniteNumber(referenceCandle?.close, Number.NaN);
    const latestPrice = toFiniteNumber(options.latestPrice, Number.NaN);

    if (options.includeLatestPrice === true && Number.isFinite(latestPrice) && latestPrice > 0) {
      pushPositiveRangeValue(range, latestPrice);
    }

    return buildExpandedRange(range, {
      paddingRatio: 0.08,
      flatPaddingRatio: 0.008,
      fallbackCenter: Number.isFinite(referencePrice) ? referencePrice : latestPrice,
    });
  };

  resolveVisibleVolumeAxisRange = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    const cache = normalizedSymbol ? chartRenderCaches[normalizedSymbol] : null;
    const candles = Array.isArray(cache?.candles) ? cache.candles : candlesData[normalizedSymbol];
    if (!Array.isArray(candles) || candles.length === 0) {
      return null;
    }

    const viewportState = getChartViewportState(normalizedSymbol, candles.length);
    const renderLength = Math.max(
      Number.isFinite(cache?.renderLength) ? cache.renderLength : 0,
      Array.isArray(cache?.dates) ? cache.dates.length : 0,
      getChartRenderLength(candles.length),
      candles.length
    );
    const visibleRange = getViewportVisibleIndexRange(candles.length, viewportState, renderLength);
    const range = createFiniteRangeTracker();

    pushSeriesSliceRangeValues(range, cache?.volumeData, visibleRange.startIndex, visibleRange.endIndex, {
      positiveOnly: true,
    });

    [
      indicators.vma5 ? cache?.vma5 : null,
      indicators.vma10 ? cache?.vma10 : null,
      indicators.vma20 ? cache?.vma20 : null,
    ].forEach(series => {
      pushSeriesSliceRangeValues(range, series, visibleRange.startIndex, visibleRange.endIndex, {
        positiveOnly: true,
      });
    });

    return buildExpandedRange(range, {
      paddingRatio: 0.16,
      flatPaddingRatio: 0.24,
      fallbackCenter: range.max,
    });
  };

  buildExpandedRange = (range, options = {}) => {
    const fallbackCenter = Math.abs(toFiniteNumber(options.fallbackCenter, 1)) || 1;
    if (!hasFiniteRange(range)) {
      const padding = Math.max(fallbackCenter * 0.08, 1e-6);
      return {
        min: -padding,
        max: padding,
      };
    }

    const span = range.max - range.min;
    const padding = span > 0
      ? span * (options.paddingRatio ?? 0.08)
      : Math.max(Math.abs(range.max || range.min || fallbackCenter) * (options.flatPaddingRatio ?? 0.01), 1e-6);

    return {
      min: range.min - padding,
      max: range.max + padding,
    };
  };

  resolveAxisExtentRange = (
    extent,
    options = {}
  ) => {
    const range = createFiniteRangeTracker();
    pushRangeValue(range, extent?.min);
    pushRangeValue(range, extent?.max);

    const latestPrice = toFiniteNumber(options.latestPrice, Number.NaN);
    if (options.includeLatestPrice === true && Number.isFinite(latestPrice) && latestPrice > 0) {
      pushPositiveRangeValue(range, latestPrice);
    }

    return buildExpandedRange(range, {
      paddingRatio: options.paddingRatio,
      flatPaddingRatio: options.flatPaddingRatio,
      fallbackCenter: options.fallbackCenter ?? latestPrice,
    });
  };

  buildChartYAxisPatch = (symbol, options = {}) => ([
    {
      id: 'price-y-axis',
      type: 'value',
      scale: true,
      min: (extent) => (
        (
          resolveVisiblePriceAxisRange(symbol, {
            latestPrice: options.latestPrice,
            includeLatestPrice: options.includeLatestPrice,
          })
          || resolveAxisExtentRange(extent, {
            paddingRatio: 0.08,
            flatPaddingRatio: 0.008,
            latestPrice: options.latestPrice,
            includeLatestPrice: options.includeLatestPrice,
            fallbackCenter: options.latestPrice,
          })
        ).min
      ),
      max: (extent) => (
        (
          resolveVisiblePriceAxisRange(symbol, {
            latestPrice: options.latestPrice,
            includeLatestPrice: options.includeLatestPrice,
          })
          || resolveAxisExtentRange(extent, {
            paddingRatio: 0.08,
            flatPaddingRatio: 0.008,
            latestPrice: options.latestPrice,
            includeLatestPrice: options.includeLatestPrice,
            fallbackCenter: options.latestPrice,
          })
        ).max
      ),
      axisLine: { lineStyle: { color: '#30363d' } },
      axisLabel: { color: '#8b949e', fontSize: 9 },
      splitLine: { lineStyle: { color: '#21262d' } },
    },
    {
      id: 'volume-y-axis',
      type: 'value',
      scale: true,
      gridIndex: 1,
      min: 0,
      max: (extent) => {
        const nextRange = resolveVisibleVolumeAxisRange(symbol)
          || resolveAxisExtentRange(extent, {
            paddingRatio: 0.16,
            flatPaddingRatio: 0.24,
            fallbackCenter: extent?.max,
          });
        return Math.max(nextRange.max, 1);
      },
      axisLine: { lineStyle: { color: '#30363d' } },
      axisLabel: { show: false },
      splitLine: { show: false },
    },
  ]);

  buildChartXAxisLabelFormatter = () => {
    const timeframe = currentTimeframe.value;
    return (value) => {
      if (typeof value !== 'string' || !value) {
        return value ?? '';
      }

      if ((timeframe === '1H' || timeframe === '4H') && value.includes(' ')) {
        const [dateText, timeText] = value.split(' ');
        return `${dateText}\n${timeText}`;
      }

      return value;
    };
  };

  buildChartXAxisPatch = (cache) => {
    const formatter = buildChartXAxisLabelFormatter();
    const multiline = currentTimeframe.value === '1H' || currentTimeframe.value === '4H';

    return [
      {
        id: 'price-x-axis',
        type: 'category',
        data: cache?.dates || [],
        axisLine: { lineStyle: { color: '#30363d' } },
        axisLabel: {
          color: '#8b949e',
          fontSize: 9,
          hideOverlap: true,
          showMinLabel: true,
          showMaxLabel: true,
          interval: 'auto',
          margin: multiline ? 10 : 8,
          formatter,
        },
        axisPointer: {
          show: true,
          label: { show: true },
        },
        splitLine: { show: false },
      },
      {
        id: 'volume-x-axis',
        type: 'category',
        gridIndex: 1,
        data: cache?.dates || [],
        axisLine: { lineStyle: { color: '#30363d' } },
        axisLabel: { show: false },
        splitLine: { show: false },
      },
    ];
  };

  scheduleChartViewportAxisRefresh = (symbol, options = {}) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) {
      return;
    }

    clearChartViewportAxisRefresh(normalizedSymbol);

    const immediate = options.immediate === true;
    const interactionDelay = isChartViewportInteracting(normalizedSymbol)
      ? Math.max(
          getChartViewportInteractionRemainingMs(normalizedSymbol),
          CHART_VIEWPORT_AXIS_INTERACTION_REFRESH_DELAY
        )
      : CHART_VIEWPORT_AXIS_REFRESH_DELAY;
    const waitMs = immediate ? 0 : interactionDelay;

    const timerId = window.setTimeout(() => {
      chartViewportAxisRefreshTimers.delete(normalizedSymbol);
      const chart = chartInstances[normalizedSymbol];
      if (!chart) {
        return;
      }

      // LWC 原生管理 Y 轴自适应，无需手动刷新
      if (typeof chart.setOption !== 'function') {
        return;
      }

      const candles = candlesData[normalizedSymbol];
      const latestCandle = Array.isArray(candles) && candles.length > 0
        ? candles[candles.length - 1]
        : null;
      const latestPrice = resolveCurrentPriceLineValue(normalizedSymbol, latestCandle);
      const viewportState = getChartViewportState(normalizedSymbol, candles?.length || 0);
      const cache = chartRenderCaches[normalizedSymbol];
      const renderLength = Math.max(
        Number.isFinite(cache?.renderLength) ? cache.renderLength : 0,
        Array.isArray(cache?.dates) ? cache.dates.length : 0,
        getChartRenderLength(candles?.length || 0),
        candles?.length || 0
      );
      const visibleRange = getViewportVisibleIndexRange(
        candles?.length || 0,
        viewportState,
        renderLength
      );
      const includeLatestPriceInAxis = Array.isArray(candles)
        && visibleRange.endIndex >= candles.length - 1;
      const graphic = buildChartGraphicOverlays(normalizedSymbol, chart, {
        renderCache: cache,
        latestPrice,
        visibleRange,
      });

      // 重算 Y 轴范围，确保价格轴和成交量轴跟随可见区域自适应
      applyChartSetOption(normalizedSymbol, chart, {
        yAxis: buildChartYAxisPatch(normalizedSymbol, {
          latestPrice,
          includeLatestPrice: includeLatestPriceInAxis,
        }),
        graphic,
      }, {
        lazyUpdate: false,
        silent: true,
        replaceMerge: ['yAxis', 'graphic'],
      }, 'graphic');
    }, waitMs);

    chartViewportAxisRefreshTimers.set(normalizedSymbol, timerId);
  };

  resolveCurrentPriceLineValue = (symbol, latestCandle) => {
    const candleClose = toFiniteNumber(latestCandle?.close, Number.NaN);
    if (Number.isFinite(candleClose) && candleClose > 0) {
      return candleClose;
    }

    const tickerLast = toFiniteNumber(tickers[symbol]?.last, Number.NaN);
    if (Number.isFinite(tickerLast) && tickerLast > 0) {
      return tickerLast;
    }

    return Number.NaN;
  };

  extractTooltipSeriesValue = (param) => {
    if (!param) {
      return Number.NaN;
    }

    if (Array.isArray(param.value)) {
      return toFiniteNumber(param.value[param.value.length - 1], Number.NaN);
    }

    if (param.data && typeof param.data === 'object' && !Array.isArray(param.data)) {
      if (Array.isArray(param.data.value)) {
        return toFiniteNumber(param.data.value[param.data.value.length - 1], Number.NaN);
      }
      if (param.data.value !== undefined) {
        return toFiniteNumber(param.data.value, Number.NaN);
      }
    }

    return toFiniteNumber(param.value, Number.NaN);
  };

  buildTooltipIndicatorRow = (axisParams, seriesNames, formatter, rowLabel = '') => {
    const values = seriesNames
      .map((name) => {
        const param = axisParams.find(item => item?.seriesName === name);
        const value = extractTooltipSeriesValue(param);
        if (!Number.isFinite(value)) {
          return null;
        }
        return `${name} ${formatter(value)}`;
      })
      .filter(Boolean);

    if (values.length === 0) {
      return '';
    }

    if (!rowLabel) {
      return values.join(' / ');
    }

    return `${rowLabel} ${values.join(' / ')}`;
  };

  buildChartTooltipFormatter = (symbol) => (params) => {
    const renderCache = chartRenderCaches[symbol];
    const candles = renderCache?.candles || [];
    const dates = renderCache?.dates || [];
    const axisParams = Array.isArray(params) ? params : [params];
    const candleParam = axisParams.find(item => item?.seriesName === 'K线');
    if (!candleParam) return '';

    const candle = candles[candleParam.dataIndex];
    if (!candle) return '';

    const isRealtimeCandle = candleParam.dataIndex === candles.length - 1;
    const rows = [
      `<div style="font-weight:600;margin-bottom:6px;">${dates[candleParam.dataIndex] || ''}${isRealtimeCandle ? ' · 实时中' : ''}</div>`,
      `开 ${formatPrice(candle.open)}`,
      `高 ${formatPrice(candle.high)}`,
      `低 ${formatPrice(candle.low)}`,
      `收 ${formatPrice(candle.close)}`,
      `量 ${formatTradeSize(toFiniteNumber(candle.volume, 0))}`,
    ];

    const indicatorRows = [
      buildTooltipIndicatorRow(axisParams, ['MA5', 'MA10', 'MA20', 'MA60'], formatPrice, '主图'),
      buildTooltipIndicatorRow(axisParams, ['EMA12', 'EMA26'], formatPrice, 'EMA'),
      buildTooltipIndicatorRow(axisParams, ['BOLL上轨', 'BOLL中轨', 'BOLL下轨'], formatPrice, 'BOLL'),
      buildTooltipIndicatorRow(axisParams, ['SAR'], formatPrice, ''),
      buildTooltipIndicatorRow(axisParams, ['VMA5', 'VMA10', 'VMA20'], formatTradeSize, '量均'),
    ].filter(Boolean);

    if (indicatorRows.length > 0) {
      rows.push(...indicatorRows);
    }
    return rows.join('<br/>');
  };

  // 更新单个图表
  updateChart = (symbol, options = {}) => {
    const candles = candlesData[symbol];
    if (!candles || !Array.isArray(candles) || candles.length === 0) {
      return;
    }

    const firstCandle = candles[0];
    if (!firstCandle || typeof firstCandle.open !== 'number') {
      return;
    }

    const { lwcManagers } = ctx;
    const manager = lwcManagers?.get(symbol);
    if (manager) {
      const realtime = options.realtime === true;
      if (realtime) {
        // 实时增量：更新/追加最后一根 K 线
        // LWC 的 series.update() 在 time 比已有数据新时自动追加
        manager.updateLastBar(candles[candles.length - 1]);
        // 如果 candlesData 被裁剪过（shift），需要定期全量同步
        // 通过比较管理器内部记录的长度判断是否偏差过大
        if (manager._syncCounter === undefined) manager._syncCounter = 0;
        manager._syncCounter++;
        if (manager._syncCounter >= 100) {
          // 每 100 次增量更新后做一次全量同步，修正 LWC 和 candlesData 的偏差
          manager._syncCounter = 0;
          manager.setData(candles, { symbol, indicators, fitContent: false });
        }
      } else {
        manager.setData(candles, {
          symbol,
          indicators: indicators,
          fitContent: !realtime,
        });
      }
      return;
    }
  };
  // 加载单个币种数据（自动取消旧请求，快速切换时只保留最新调用的结果）
  loadChartData = async (symbol) => {
    const instId = resolveMarketInstId(symbol);
    const instType = marketInstType.value;

    if (!instId) {
      chartErrors[symbol] = '无效交易对';
      return;
    }

    chartLoading[symbol] = true;
    chartErrors[symbol] = null;

    const result = await chartDataLoader.run(async () => {
      // 并行获取数据
      const tasks = [];

      // 获取 ticker
      tasks.push(
        api.getTicker(instId, { instType })
          .then(res => {
            if (res.code === 0) {
              const normalized = normalizeTickerData(res.data);
              if (normalized) {
                applyIncomingTicker(symbol, normalized);
              }
            }
          })
          .catch(e => console.warn(`获取 ${symbol} ticker 失败:`, e.message))
      );

      // 获取成交记录（用于买卖标记）
      if (showTradeMarkers.value) {
        tasks.push(loadFillsForSymbol(symbol));
      }

      // 获取 K线数据
      const candlesTask = (async () => {
        const candles = await loadCandlesForSelectedRange(instId, instType, currentTimeframe.value);

        if (Array.isArray(candles) && candles.length > 0) {
          candlesData[symbol] = candles;
          applyDisplayRangeViewport(symbol, candles, currentTimeframe.value);
        } else {
          chartErrors[symbol] = '暂无K线数据，请先同步数据';
        }
      })();
      tasks.push(candlesTask);

      // 等待所有任务完成
      await Promise.all(tasks);
      return true;
    });

    // result 为 undefined 说明被后续调用取代，不更新状态
    if (result === undefined) {
      return;
    }

    try {
      // 更新图表
      if (candlesData[symbol] && candlesData[symbol].length > 0) {
        await nextTick();
        updateChart(symbol);
      }
    } catch (error) {
      console.error(`加载 ${symbol} 数据失败:`, error);
      chartErrors[symbol] = '数据加载失败';
    } finally {
      chartLoading[symbol] = false;
    }
  };

  // 更新所有图表（仅重绘，不重新加载数据）
  updateAllCharts = () => {
    selectedSymbols.value.forEach(symbol => {
      if (candlesData[symbol]) {
        updateChart(symbol);
      }
    });
  };

  // 刷新单个图表（重新加载数据）
  refreshChart = (symbol) => {
    loadChartData(symbol);
    if (symbol === activeSymbol.value) {
      loadExecutionPanelData(symbol);
    }
  };

  refreshActiveChart = async () => {
    const symbol = activeSymbol.value;
    if (!symbol) {
      return;
    }

    loading.value = true;
    try {
      await loadChartData(symbol);
      await loadExecutionPanelData(symbol);
    } finally {
      loading.value = false;
    }
  };

  // 刷新所有图表
  refreshAllCharts = async () => {
    loading.value = true;
    try {
      await Promise.all(selectedSymbols.value.map(symbol => loadChartData(symbol)));
      if (activeSymbol.value) {
        await loadExecutionPanelData(activeSymbol.value);
      }
    } finally {
      loading.value = false;
    }
  };

  // 只刷新ticker数据（轻量级）
  refreshAllTickers = async () => {
    await Promise.all(
      selectedSymbols.value.map(async (symbol) => {
        try {
          const res = await api.getTicker(
            resolveMarketInstId(symbol),
            { instType: marketInstType.value }
          );
          if (res.code === 0) {
            const normalized = normalizeTickerData(res.data);
            if (normalized) {
              applyIncomingTicker(symbol, normalized);
            }
          }
        } catch (e) {
          // 静默处理：某些币种可能不存在交易对
        }
      })
    );
  };



  return {
    buildTradeMarkerSeries,
    syncRealtimeChartRenderCache,
    syncChartAnnotationRenderCache,
    buildChartRenderCache,
    canReuseChartRenderCacheBase,
    canUseRealtimeChartCache,
    buildChartSeries,
    buildRealtimeChartSeriesPatch,
    getViewportVisibleIndexRange,
    createFiniteRangeTracker,
    pushRangeValue,
    pushPositiveRangeValue,
    hasFiniteRange,
    pushSeriesSliceRangeValues,
    resolveVisiblePriceAxisRange,
    resolveVisibleVolumeAxisRange,
    buildExpandedRange,
    resolveAxisExtentRange,
    buildChartYAxisPatch,
    buildChartXAxisLabelFormatter,
    buildChartXAxisPatch,
    scheduleChartViewportAxisRefresh,
    resolveCurrentPriceLineValue,
    extractTooltipSeriesValue,
    buildTooltipIndicatorRow,
    buildChartTooltipFormatter,
    updateChart,
    loadChartData,
    updateAllCharts,
    refreshChart,
    refreshActiveChart,
    refreshAllCharts,
    refreshAllTickers,
  };
}
