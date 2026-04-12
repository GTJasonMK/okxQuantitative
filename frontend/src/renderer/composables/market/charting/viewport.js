export function createMarketViewChartViewport(ctx) {
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

  getDisplayRangeDays = () => {
    const numeric = Number(displayRangeDays?.value ?? displayRangeDays ?? 7);
    if (!Number.isFinite(numeric) || numeric <= 0) {
      return 7;
    }
    return Math.max(1, Math.round(numeric));
  };

  getMaxTrackedCandles = () => {
    const numeric = Number(maxTrackedCandles?.value ?? maxTrackedCandles ?? 300);
    if (!Number.isFinite(numeric) || numeric <= 0) {
      return 300;
    }
    return Math.max(RANGE_FETCH_MIN_CANDLES, Math.round(numeric));
  };

  estimateVisibleRangeCandles = (timeframe = currentTimeframe.value) => {
    const timeframeMs = TIMEFRAME_MS[timeframe] || DAY_MS;
    return Math.max(1, Math.ceil((getDisplayRangeDays() * DAY_MS) / timeframeMs));
  };

  getChartVisibleCandleHint = (dataLength = 0, timeframe = currentTimeframe.value) => {
    const normalizedDataLength = Number.isFinite(dataLength) && dataLength > 0
      ? Math.max(1, Math.floor(dataLength))
      : 0;
    const visibleHint = Math.min(
      estimateVisibleRangeCandles(timeframe),
      Math.max(getMaxTrackedCandles() - RANGE_FETCH_WARMUP_CANDLES, 1)
    );

    if (normalizedDataLength <= 0) {
      return Math.max(1, visibleHint);
    }

    return Math.max(1, Math.min(normalizedDataLength, visibleHint));
  };

  getChartLatestAnchorPaddingCount = (dataLength = 0) => {
    const normalizedDataLength = Number.isFinite(dataLength) && dataLength > 0
      ? Math.max(1, Math.floor(dataLength))
      : 0;
    if (normalizedDataLength <= 1) {
      return 0;
    }

    return Math.max(
      0,
      Math.ceil(
        ((normalizedDataLength - 1) / CHART_LATEST_CANDLE_VIEW_RATIO)
        - normalizedDataLength
        + 1
      )
    );
  };

  getChartRightPaddingCount = (dataLength = 0, timeframe = currentTimeframe.value) => {
    const normalizedDataLength = Number.isFinite(dataLength) && dataLength > 0
      ? Math.max(1, Math.floor(dataLength))
      : 0;
    if (normalizedDataLength <= 0) {
      return 0;
    }

    return Math.max(
      getChartLatestAnchorPaddingCount(normalizedDataLength),
      Math.max(0, Math.round(
        getChartVisibleCandleHint(normalizedDataLength, timeframe)
        * (1 - CHART_LATEST_CANDLE_VIEW_RATIO)
      ))
    );
  };

  getChartRenderLength = (dataLength = 0, timeframe = currentTimeframe.value) => {
    const normalizedDataLength = Number.isFinite(dataLength) && dataLength > 0
      ? Math.max(1, Math.floor(dataLength))
      : 0;
    if (normalizedDataLength <= 0) {
      return 0;
    }

    return normalizedDataLength + getChartRightPaddingCount(normalizedDataLength, timeframe);
  };

  getChartLatestRenderPercent = (dataLength = 0, timeframe = currentTimeframe.value) => {
    const normalizedDataLength = Number.isFinite(dataLength) && dataLength > 0
      ? Math.max(1, Math.floor(dataLength))
      : 0;
    if (normalizedDataLength <= 1) {
      return 50;
    }

    const renderLastIndex = Math.max(getChartRenderLength(normalizedDataLength, timeframe) - 1, 1);
    return clamp(((normalizedDataLength - 1) / renderLastIndex) * 100, 0, 100);
  };

  buildLatestAnchoredViewportState = (
    dataLength = 0,
    spanPercent = 100,
    timeframe = currentTimeframe.value,
    source = 'default'
  ) => {
    if (!Number.isFinite(dataLength) || dataLength <= 0) {
      return { start: 0, end: 100, source: 'empty', keepLatestCentered: true };
    }

    const normalizedSpan = clamp(spanPercent, MIN_DATA_ZOOM_SPAN_PERCENT, 100);
    const latestRenderPercent = getChartLatestRenderPercent(dataLength, timeframe);
    const anchoredStart = clamp(
      latestRenderPercent - normalizedSpan * CHART_LATEST_CANDLE_VIEW_RATIO,
      0,
      100 - normalizedSpan
    );

    return {
      start: anchoredStart,
      end: anchoredStart + normalizedSpan,
      source,
      keepLatestCentered: true,
    };
  };

  getChartMaxViewportStart = (
    dataLength = 0,
    spanPercent = 100,
    timeframe = currentTimeframe.value
  ) => {
    if (!Number.isFinite(dataLength) || dataLength <= 0) {
      return 0;
    }

    const normalizedSpan = clamp(spanPercent, MIN_DATA_ZOOM_SPAN_PERCENT, 100);
    const latestRenderPercent = getChartLatestRenderPercent(dataLength, timeframe);
    return clamp(
      latestRenderPercent - normalizedSpan * CHART_LATEST_CANDLE_VIEW_RATIO,
      0,
      100 - normalizedSpan
    );
  };

  getChartViewportStateKey = (symbol) => (
    `${normalizeMonitorSymbol(symbol)}:${marketInstType.value}:${currentTimeframe.value}`
  );

  buildDefaultChartViewportState = (dataLength = 0, timeframe = currentTimeframe.value) => {
    if (!Number.isFinite(dataLength) || dataLength <= 0) {
      return { start: 0, end: 100, source: 'empty' };
    }

    const visibleCandleHint = getChartVisibleCandleHint(dataLength, timeframe);
    if (dataLength <= visibleCandleHint) {
      return buildLatestAnchoredViewportState(dataLength, 100, timeframe, 'default');
    }

    const renderLength = getChartRenderLength(dataLength, timeframe);
    const visibleRenderCount = Math.min(
      renderLength,
      Math.ceil(visibleCandleHint / CHART_LATEST_CANDLE_VIEW_RATIO)
    );
    const span = clamp(
      (visibleRenderCount / renderLength) * 100,
      MIN_DATA_ZOOM_SPAN_PERCENT,
      100
    );

    return buildLatestAnchoredViewportState(dataLength, span, timeframe, 'default');
  };

  getChartViewportState = (symbol, dataLength = 0) => {
    const key = getChartViewportStateKey(symbol);
    const current = chartViewportStates[key];

    if (
      current
      && Number.isFinite(current.start)
      && Number.isFinite(current.end)
      && current.end > current.start
    ) {
      if (current.source === 'empty' && dataLength > 0) {
        const next = buildDefaultChartViewportState(dataLength);
        chartViewportStates[key] = next;
        return next;
      }
      return current;
    }

    const next = buildDefaultChartViewportState(dataLength);
    chartViewportStates[key] = next;
    return next;
  };

  setChartViewportState = (symbol, start, end, source = 'user', options = {}) => {
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      return;
    }

    const normalizedStart = clamp(start, 0, 100);
    const normalizedEnd = clamp(end, normalizedStart + 0.01, 100);
    chartViewportStates[getChartViewportStateKey(symbol)] = {
      start: normalizedStart,
      end: normalizedEnd,
      source,
      keepLatestCentered: options.keepLatestCentered === true,
    };
  };

  clearChartViewportState = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) return;

    const prefix = `${normalizedSymbol}:`;
    Object.keys(chartViewportStates)
      .filter(key => key.startsWith(prefix))
      .forEach(key => delete chartViewportStates[key]);
    clearChartViewportInteraction(normalizedSymbol);
    clearDeferredChartSetOptions(normalizedSymbol);
  };

  buildDisplayRangeWindow = (timeframe = currentTimeframe.value) => {
    const timeframeMs = TIMEFRAME_MS[timeframe] || DAY_MS;
    const maxCandles = getMaxTrackedCandles();
    const visibleCandles = Math.min(
      estimateVisibleRangeCandles(timeframe),
      Math.max(maxCandles - RANGE_FETCH_WARMUP_CANDLES, 1)
    );
    const warmupCandles = Math.max(Math.min(maxCandles - visibleCandles, RANGE_FETCH_WARMUP_CANDLES), 0);
    const endMs = Date.now();
    const visibleStartMs = endMs - visibleCandles * timeframeMs;
    const requestStartMs = Math.max(0, visibleStartMs - warmupCandles * timeframeMs);

    return {
      timeframeMs,
      endMs,
      visibleStartMs,
      requestStartMs,
      visibleCandles,
      warmupCandles,
      maxCandles,
    };
  };

  mergeCandlesByTimestamp = (batches) => {
    const merged = [];
    const seen = new Set();

    (batches || []).forEach((batch) => {
      (batch || []).forEach((candle) => {
        const timestamp = getCandleTimestamp(candle);
        if (!timestamp || seen.has(timestamp)) {
          return;
        }
        seen.add(timestamp);
        merged.push(candle);
      });
    });

    return merged.sort((left, right) => getCandleTimestamp(left) - getCandleTimestamp(right));
  };

  applyDisplayRangeViewport = (symbol, candles, timeframe = currentTimeframe.value) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol || !Array.isArray(candles) || candles.length === 0) {
      return;
    }

    const { visibleStartMs } = buildDisplayRangeWindow(timeframe);
    const lastIndex = candles.length - 1;
    if (lastIndex <= 0) {
      const nextViewport = buildLatestAnchoredViewportState(candles.length, 100, timeframe, 'range');
      setChartViewportState(
        normalizedSymbol,
        nextViewport.start,
        nextViewport.end,
        nextViewport.source,
        { keepLatestCentered: true }
      );
      return;
    }

    const startIndex = candles.findIndex(candle => getCandleTimestamp(candle) >= visibleStartMs);
    if (startIndex <= 0) {
      const nextViewport = buildLatestAnchoredViewportState(candles.length, 100, timeframe, 'range');
      setChartViewportState(
        normalizedSymbol,
        nextViewport.start,
        nextViewport.end,
        nextViewport.source,
        { keepLatestCentered: true }
      );
      return;
    }

    const visibleCandleCount = Math.max(lastIndex - startIndex + 1, 1);
    const renderLength = getChartRenderLength(candles.length, timeframe);
    const span = clamp(
      (Math.min(renderLength, Math.ceil(visibleCandleCount / CHART_LATEST_CANDLE_VIEW_RATIO)) / renderLength) * 100,
      MIN_DATA_ZOOM_SPAN_PERCENT,
      100
    );
    const nextViewport = buildLatestAnchoredViewportState(candles.length, span, timeframe, 'range');
    setChartViewportState(
      normalizedSymbol,
      nextViewport.start,
      nextViewport.end,
      nextViewport.source,
      { keepLatestCentered: true }
    );
  };

  const loadCandlesForSelectedRange = async (instId, instType, timeframe) => {
    const window = buildDisplayRangeWindow(timeframe);
    const estimatedRequestCount = Math.max(
      RANGE_FETCH_MIN_CANDLES,
      window.visibleCandles + window.warmupCandles + 8
    );
    const loopCount = Math.max(1, Math.ceil(estimatedRequestCount / RANGE_FETCH_BATCH_LIMIT) + 1);
    const batches = [];
    let cursorEndMs = window.endMs;

    for (let index = 0; index < loopCount; index += 1) {
      const response = await api.getCandles(instId, {
        timeframe,
        limit: RANGE_FETCH_BATCH_LIMIT,
        instType,
        endTime: new Date(cursorEndMs).toISOString(),
      });

      const batch = response?.code === 0 && Array.isArray(response.data)
        ? response.data
        : [];
      if (batch.length === 0) {
        break;
      }

      batches.unshift(batch.filter((candle) => {
        const timestamp = getCandleTimestamp(candle);
        return timestamp > 0 && timestamp <= window.endMs && timestamp >= window.requestStartMs;
      }));

      const oldestTimestamp = getCandleTimestamp(batch[0]);
      if (!oldestTimestamp || oldestTimestamp <= window.requestStartMs || batch.length < RANGE_FETCH_BATCH_LIMIT) {
        break;
      }

      cursorEndMs = oldestTimestamp - 1;
    }

    const localCandles = mergeCandlesByTimestamp(batches);
    const localOldestTimestamp = localCandles.length > 0 ? getCandleTimestamp(localCandles[0]) : 0;
    const localNewestTimestamp = localCandles.length > 0 ? getCandleTimestamp(localCandles[localCandles.length - 1]) : 0;
    const localVisibleCoverageEnough = (
      localCandles.length >= Math.max(window.visibleCandles - 2, 1)
      && localOldestTimestamp > 0
      && localOldestTimestamp <= window.visibleStartMs
      && localNewestTimestamp > 0
      && localNewestTimestamp >= window.endMs - window.timeframeMs * 3
    );

    if (localVisibleCoverageEnough) {
      return localCandles.slice(-window.maxCandles);
    }

    const fallbackLimit = Math.max(
      window.visibleCandles + window.warmupCandles + 8,
      RANGE_FETCH_MIN_CANDLES
    );
    const fallbackResponse = await api.getCandles(instId, {
      timeframe,
      limit: fallbackLimit,
      instType,
      startTime: new Date(window.requestStartMs).toISOString(),
      endTime: new Date(window.endMs).toISOString(),
    });
    const fallbackCandles = fallbackResponse?.code === 0 && Array.isArray(fallbackResponse.data)
      ? fallbackResponse.data
      : [];
    const mergedCandles = mergeCandlesByTimestamp([localCandles, fallbackCandles]);
    return mergedCandles.slice(-window.maxCandles);
  };


  return {
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
  };
}
