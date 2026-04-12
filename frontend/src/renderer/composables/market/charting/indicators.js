export function createMarketViewChartIndicators(ctx) {
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

  // 滑动窗口 MA — O(n) 替代朴素 O(n*period)
  calculateMA = (data, period) => {
    const result = [];
    let windowSum = 0;
    for (let i = 0; i < data.length; i++) {
      windowSum += data[i];
      if (i < period - 1) {
        result.push(null);
      } else {
        if (i >= period) {
          windowSum -= data[i - period];
        }
        result.push(windowSum / period);
      }
    }
    return result;
  };

  // 计算指数移动平均线
  calculateEMA = (data, period) => {
    const result = [];
    const multiplier = 2 / (period + 1);
    let ema = null;
    for (let i = 0; i < data.length; i++) {
      if (i < period - 1) {
        result.push(null);
      } else if (i === period - 1) {
        // 首个EMA用SMA初始化
        let sum = 0;
        for (let j = 0; j < period; j++) {
          sum += data[i - j];
        }
        ema = sum / period;
        result.push(ema);
      } else {
        ema = (data[i] - ema) * multiplier + ema;
        result.push(ema);
      }
    }
    return result;
  };

  // Welford 在线算法 BOLL — 滑动窗口 O(n) 替代朴素 O(n*period*2)
  calculateBOLL = (data, period = 20, mult = 2) => {
    const upper = [];
    const middle = [];
    const lower = [];
    let windowSum = 0;
    let windowSqSum = 0;

    for (let i = 0; i < data.length; i++) {
      windowSum += data[i];
      windowSqSum += data[i] * data[i];

      if (i < period - 1) {
        upper.push(null);
        middle.push(null);
        lower.push(null);
      } else {
        if (i >= period) {
          const dropped = data[i - period];
          windowSum -= dropped;
          windowSqSum -= dropped * dropped;
        }
        const ma = windowSum / period;
        // variance = E[X²] - (E[X])²
        const variance = Math.max(windowSqSum / period - ma * ma, 0);
        const std = Math.sqrt(variance);
        middle.push(ma);
        upper.push(ma + mult * std);
        lower.push(ma - mult * std);
      }
    }
    return { upper, middle, lower };
  };

  // 计算抛物线SAR
  calculateSAR = (candles, af0 = 0.02, afMax = 0.2, afStep = 0.02) => {
    const result = [];
    if (candles.length < 2) return result;

    let isUpTrend = candles[1].close > candles[0].close;
    let ep = isUpTrend ? candles[0].high : candles[0].low;
    let sar = isUpTrend ? candles[0].low : candles[0].high;
    let af = af0;

    result.push(null); // 第一根无法计算

    for (let i = 1; i < candles.length; i++) {
      const high = candles[i].high;
      const low = candles[i].low;

      // 计算当前SAR
      sar = sar + af * (ep - sar);

      if (isUpTrend) {
        // 确保SAR不高于前两根K线的最低价
        if (i >= 2) {
          sar = Math.min(sar, candles[i - 1].low, candles[i - 2].low);
        } else {
          sar = Math.min(sar, candles[i - 1].low);
        }

        if (low < sar) {
          // 转为下降趋势
          isUpTrend = false;
          sar = ep;
          ep = low;
          af = af0;
        } else {
          if (high > ep) {
            ep = high;
            af = Math.min(af + afStep, afMax);
          }
        }
      } else {
        // 确保SAR不低于前两根K线的最高价
        if (i >= 2) {
          sar = Math.max(sar, candles[i - 1].high, candles[i - 2].high);
        } else {
          sar = Math.max(sar, candles[i - 1].high);
        }

        if (high > sar) {
          // 转为上升趋势
          isUpTrend = true;
          sar = ep;
          ep = high;
          af = af0;
        } else {
          if (low < ep) {
            ep = low;
            af = Math.min(af + afStep, afMax);
          }
        }
      }

      result.push(sar);
    }
    return result;
  };

  updateMALastPoint = (series, closeData, period) => {
    if (!Array.isArray(series)) {
      return null;
    }

    const lastIndex = closeData.length - 1;
    if (lastIndex < 0) {
      return series;
    }

    if (lastIndex < period - 1) {
      series[lastIndex] = null;
      return series;
    }

    let sum = 0;
    for (let index = lastIndex; index > lastIndex - period; index -= 1) {
      sum += closeData[index];
    }
    series[lastIndex] = sum / period;
    return series;
  };

  updateEMALastPoint = (series, closeData, period) => {
    if (!Array.isArray(series)) {
      return null;
    }

    const lastIndex = closeData.length - 1;
    if (lastIndex < 0) {
      return series;
    }

    if (lastIndex < period - 1) {
      series[lastIndex] = null;
      return series;
    }

    if (lastIndex === period - 1) {
      let sum = 0;
      for (let index = lastIndex; index > lastIndex - period; index -= 1) {
        sum += closeData[index];
      }
      series[lastIndex] = sum / period;
      return series;
    }

    const previous = Number(series[lastIndex - 1]);
    if (!Number.isFinite(previous)) {
      return calculateEMA(closeData, period);
    }

    const multiplier = 2 / (period + 1);
    series[lastIndex] = (closeData[lastIndex] - previous) * multiplier + previous;
    return series;
  };

  updateBollLastPoint = (boll, closeData, period = 20, mult = 2) => {
    if (
      !boll
      || !Array.isArray(boll.upper)
      || !Array.isArray(boll.middle)
      || !Array.isArray(boll.lower)
    ) {
      return calculateBOLL(closeData, period, mult);
    }

    const lastIndex = closeData.length - 1;
    if (lastIndex < 0) {
      return boll;
    }

    if (lastIndex < period - 1) {
      boll.upper[lastIndex] = null;
      boll.middle[lastIndex] = null;
      boll.lower[lastIndex] = null;
      return boll;
    }

    let sum = 0;
    for (let index = lastIndex; index > lastIndex - period; index -= 1) {
      sum += closeData[index];
    }
    const mean = sum / period;

    let variance = 0;
    for (let index = lastIndex; index > lastIndex - period; index -= 1) {
      variance += (closeData[index] - mean) ** 2;
    }
    const stdDev = Math.sqrt(variance / period);

    boll.middle[lastIndex] = mean;
    boll.upper[lastIndex] = mean + mult * stdDev;
    boll.lower[lastIndex] = mean - mult * stdDev;
    return boll;
  };

  return {
    calculateMA,
    calculateEMA,
    calculateBOLL,
    calculateSAR,
    updateMALastPoint,
    updateEMALastPoint,
    updateBollLastPoint,
  };
}
