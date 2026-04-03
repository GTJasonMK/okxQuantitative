export function createMarketViewChartRenderingSupport(ctx) {
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
    echarts,
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
    observeChartResize,
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

  const chartInitRetryTimers = new Map();
  const MAX_CHART_INIT_RETRY_COUNT = 12;

  const clearChartInitRetry = (symbol) => {
    const timerId = chartInitRetryTimers.get(symbol);
    if (timerId) {
      window.clearTimeout(timerId);
      chartInitRetryTimers.delete(symbol);
    }
  };

  const scheduleChartInitRetry = (symbol, retryAttempt) => {
    clearChartInitRetry(symbol);
    const timerId = window.setTimeout(() => {
      chartInitRetryTimers.delete(symbol);
      initChart(symbol, { retryAttempt });
    }, 80);
    chartInitRetryTimers.set(symbol, timerId);
  };

  initChart = (symbol, options = {}) => {
    const el = chartRefs[symbol];
    if (!el) return;
    const retryAttempt = Number(options.retryAttempt) || 0;
    const width = Number(el.clientWidth) || 0;
    const height = Number(el.clientHeight) || 0;

    // 容器尚未参与布局时先延后，避免 ECharts 在 0x0 尺寸上初始化报错。
    if (width <= 0 || height <= 0) {
      if (retryAttempt < MAX_CHART_INIT_RETRY_COUNT) {
        scheduleChartInitRetry(symbol, retryAttempt + 1);
      }
      return;
    }

    clearChartInitRetry(symbol);
    disposeChartInstance(symbol);
    const initialViewport = getChartViewportState(symbol, candlesData[symbol]?.length || 0);
    const chartDevicePixelRatio = 1;

    const chart = echarts.init(el, 'dark', {
      renderer: 'canvas',
      // dataZoom + 自定义 graphic/annotation 场景下，脏矩形重绘会留下轴标签残影。
      useDirtyRect: false,
      devicePixelRatio: chartDevicePixelRatio,
    });
    chartRawResizeFns.set(chart, chart.resize.bind(chart));
    chart.resize = (resizeOptions) => applyChartResize(symbol, chart, resizeOptions);
    chartInstances[symbol] = chart;
    observeChartResize(symbol, el);

    // 设置初始空配置，避免未设置数据时报错
    applyChartSetOption(symbol, chart, {
      backgroundColor: 'transparent',
      grid: [
        { left: 50, right: 10, top: 10, bottom: 100 },
        { left: 50, right: 10, height: 35, bottom: 55 },
      ],
      xAxis: [
        { type: 'category', data: [] },
        { type: 'category', gridIndex: 1, data: [] },
      ],
      yAxis: [
        { type: 'value' },
        { type: 'value', gridIndex: 1 },
      ],
      dataZoom: [
        {
          id: 'inside',
          type: 'inside',
          xAxisIndex: [0, 1],
          filterMode: 'filter',
          start: initialViewport.start,
          end: initialViewport.end,
          minSpan: MIN_DATA_ZOOM_SPAN_PERCENT,
          throttle: 24,
          // 主图平移统一走自定义拖拽逻辑，避免与内置 inside dataZoom 重复响应。
          moveOnMouseMove: false,
          moveOnMouseWheel: false,
          zoomOnMouseWheel: false,
          preventDefaultMouseMove: true,
        },
        {
          id: 'slider',
          type: 'slider',
          xAxisIndex: [0, 1],
          filterMode: 'filter',
          start: initialViewport.start,
          end: initialViewport.end,
          minSpan: MIN_DATA_ZOOM_SPAN_PERCENT,
          throttle: 24,
          height: 24,
          bottom: 5,
          handleSize: 18,
          moveHandleSize: 10,
          showDetail: false,
          brushSelect: false,
          borderColor: '#30363d',
          backgroundColor: 'rgba(47, 69, 84, 0.3)',
          fillerColor: 'rgba(247, 147, 26, 0.2)',
          handleStyle: { color: '#F7931A', borderColor: '#F7931A' },
          textStyle: { color: '#8b949e', fontSize: 10 },
          dataBackground: {
            lineStyle: { color: '#30363d' },
            areaStyle: { color: 'rgba(47, 69, 84, 0.3)' },
          },
        },
      ],
      series: [
        { type: 'candlestick', data: [] },
        { type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: [] },
      ],
    }, { lazyUpdate: true, silent: true }, 'init');
    chart.on('datazoom', () => {
      const zoomWindow = getChartDataZoomWindow(chart);
      if (!zoomWindow) return;
      markChartViewportInteracting(symbol);
      const dataLength = candlesData[symbol]?.length || 0;
      if (dataLength > 0) {
        const maxViewportStart = getChartMaxViewportStart(
          dataLength,
          zoomWindow.span,
          currentTimeframe.value
        );
        const clampedStart = clamp(zoomWindow.start, 0, maxViewportStart);
        const clampedEnd = clampedStart + zoomWindow.span;

        setChartViewportState(symbol, clampedStart, clampedEnd, 'user', {
          keepLatestCentered: Math.abs(clampedStart - maxViewportStart) <= 0.05,
        });

        if (
          Math.abs(clampedStart - zoomWindow.start) > 0.05
          || Math.abs(clampedEnd - zoomWindow.end) > 0.05
        ) {
          scheduleChartViewportAction(symbol, clampedStart, clampedEnd);
        }
      } else {
        setChartViewportState(symbol, zoomWindow.start, zoomWindow.end, 'user');
      }

      if (typeof ctx.scheduleChartViewportAxisRefresh === 'function') {
        ctx.scheduleChartViewportAxisRefresh(symbol);
      }
    });
    bindChartWheelInteraction(symbol, chart);
    bindChartDragInteraction(symbol, chart);
    bindChartAnnotationInteraction(symbol, chart);

    // 确保图表获取正确尺寸
    setTimeout(() => {
      chart.resize();
    }, 100);
  };

  // 计算移动平均线

  getChartRenderContextKey = (symbol) => (
    `${normalizeMonitorSymbol(symbol)}:${marketInstType.value}:${currentTimeframe.value}:${getDisplayRangeDays()}:${getMaxTrackedCandles()}`
  );

  getIndicatorsSignature = () => (
    Object.keys(indicators)
      .filter(key => indicators[key])
      .sort()
      .join('|')
  );

  getFillsSignature = (symbol) => {
    if (!showTradeMarkers.value) {
      return 'fills:off';
    }

    const fills = Array.isArray(fillsData[symbol]) ? fillsData[symbol] : [];
    const latestFill = fills[fills.length - 1] || null;
    return [
      'fills:on',
      fills.length,
      latestFill?.ts || latestFill?.timestamp || '',
      latestFill?.fill_px || latestFill?.price || '',
      latestFill?.side || '',
    ].join(':');
  };

  serializeAnnotationSignature = (annotation) => ([
    annotation?.type || '',
    annotation?.startTs || '',
    annotation?.endTs || '',
    annotation?.price || '',
    annotation?.startPrice || '',
    annotation?.endPrice || '',
  ].join(':'));

  getAnnotationSignature = (symbol) => {
    const annotations = getChartAnnotations(symbol);
    return [
      annotations.length,
      ...annotations.map(serializeAnnotationSignature),
    ].join('|');
  };

  buildChartCoreMetaSignature = (symbol) => ([
    getChartRenderContextKey(symbol),
    getIndicatorsSignature(),
    getFillsSignature(symbol),
  ].join('::'));

  buildChartMetaSignature = (symbol) => ([
    buildChartCoreMetaSignature(symbol),
    getAnnotationSignature(symbol),
  ].join('::'));

  buildChartAxisLabels = (candles, options = {}) => {
    const tf = currentTimeframe.value;
    const labels = candles.map(candle => {
      const dt = candle.datetime
        ? new Date(candle.datetime)
        : new Date(candle.timestamp);
      const MM = String(dt.getMonth() + 1).padStart(2, '0');
      const DD = String(dt.getDate()).padStart(2, '0');
      const hh = String(dt.getHours()).padStart(2, '0');
      const mm = String(dt.getMinutes()).padStart(2, '0');
      if (tf === '1D' || tf === '1W' || tf === '1M') {
        return `${MM}-${DD}`;
      }
      if (tf === '1H' || tf === '4H') {
        return `${MM}-${DD} ${hh}:${mm}`;
      }
      return `${hh}:${mm}`;
    });

    const rightPaddingCount = Number.isFinite(options.rightPaddingCount)
      ? Math.max(0, Math.floor(options.rightPaddingCount))
      : 0;
    if (rightPaddingCount <= 0) {
      return labels;
    }

    return labels.concat(Array.from({ length: rightPaddingCount }, () => ''));
  };

  buildOhlcSeriesData = (candles) => (
    candles.map(candle => [candle.open, candle.close, candle.low, candle.high])
  );

  buildVolumeSeriesData = (candles) => (
    candles.map(candle => ({
      value: candle.volume || 0,
      itemStyle: {
        color: candle.close >= candle.open ? '#26a69a' : '#ef5350',
      },
    }))
  );

  return {
    initChart,
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
  };
}
