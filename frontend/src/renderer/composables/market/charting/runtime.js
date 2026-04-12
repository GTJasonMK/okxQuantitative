export function createMarketViewChartRuntime(ctx) {
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
    chartResizeObservers,
    chartResizeObserverSizes,
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
    removeChartResizeObserver,
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

  buildDeferredSetOptionKey = (symbol, slot = 'series') => (
    `${normalizeMonitorSymbol(symbol) || symbol}:${slot}`
  );

  isChartInMainProcess = (chart) => Boolean(chart?.__flagInMainProcess);

  clearDeferredChartSetOptions = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) {
      return;
    }

    const prefix = `${normalizedSymbol}:`;
    [...chartDeferredSetOptionFrames.entries()].forEach(([key, frameHandle]) => {
      if (!key.startsWith(prefix)) {
        return;
      }

      if (frameHandle?.type === 'raf') {
        window.cancelAnimationFrame(frameHandle.id);
      } else if (frameHandle?.id) {
        window.clearTimeout(frameHandle.id);
      }
      chartDeferredSetOptionFrames.delete(key);
    });

    [...chartDeferredSetOptionPayloads.keys()].forEach((key) => {
      if (key.startsWith(prefix)) {
        chartDeferredSetOptionPayloads.delete(key);
      }
    });
  };

  clearDeferredChartResizes = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) {
      return;
    }

    [...chartDeferredResizeFrames.entries()].forEach(([key, frameHandle]) => {
      if (key !== normalizedSymbol) {
        return;
      }

      if (frameHandle?.type === 'raf') {
        window.cancelAnimationFrame(frameHandle.id);
      } else if (frameHandle?.id) {
        window.clearTimeout(frameHandle.id);
      }
      chartDeferredResizeFrames.delete(key);
    });

    chartDeferredResizePayloads.delete(normalizedSymbol);
  };

  clearDeferredChartHideTip = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) {
      return;
    }

    const frameHandle = chartDeferredHideTipFrames.get(normalizedSymbol);
    if (!frameHandle) {
      return;
    }

    if (frameHandle.type === 'raf') {
      window.cancelAnimationFrame(frameHandle.id);
    } else {
      window.clearTimeout(frameHandle.id);
    }
    chartDeferredHideTipFrames.delete(normalizedSymbol);
  };

  scheduleDeferredChartSetOptionFlush = (symbol, slot = 'series') => {
    const key = buildDeferredSetOptionKey(symbol, slot);
    if (chartDeferredSetOptionFrames.has(key)) {
      return;
    }

    const flush = () => {
      chartDeferredSetOptionFrames.delete(key);
      const payload = chartDeferredSetOptionPayloads.get(key);
      if (!payload) {
        return;
      }

      const activeChart = chartInstances[payload.symbol] || payload.chart;
      if (!activeChart) {
        chartDeferredSetOptionPayloads.delete(key);
        return;
      }

      if (isChartInMainProcess(activeChart)) {
        scheduleDeferredChartSetOptionFlush(payload.symbol, payload.slot);
        return;
      }

      chartDeferredSetOptionPayloads.delete(key);
      activeChart.setOption(payload.option, payload.setOptionOptions);
    };

    if (typeof window.requestAnimationFrame === 'function') {
      chartDeferredSetOptionFrames.set(key, {
        type: 'raf',
        id: window.requestAnimationFrame(flush),
      });
      return;
    }

    chartDeferredSetOptionFrames.set(key, {
      type: 'timeout',
      id: window.setTimeout(flush, 16),
    });
  };

  applyChartSetOption = (
    symbol,
    chart,
    option,
    setOptionOptions,
    slot = 'series'
  ) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol || !chart) {
      return false;
    }

    // LWC 实例没有 setOption 方法，跳过 ECharts 专用的 option 推送
    if (typeof chart.setOption !== 'function') {
      return false;
    }

    if (!isChartInMainProcess(chart)) {
      chart.setOption(option, setOptionOptions);
      return true;
    }

    chartDeferredSetOptionPayloads.set(buildDeferredSetOptionKey(normalizedSymbol, slot), {
      symbol: normalizedSymbol,
      chart,
      option,
      setOptionOptions,
      slot,
    });
    scheduleDeferredChartSetOptionFlush(normalizedSymbol, slot);
    return false;
  };

  scheduleDeferredChartResizeFlush = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol || chartDeferredResizeFrames.has(normalizedSymbol)) {
      return;
    }

    const flush = () => {
      chartDeferredResizeFrames.delete(normalizedSymbol);
      const payload = chartDeferredResizePayloads.get(normalizedSymbol);
      if (!payload) {
        return;
      }

      const activeChart = chartInstances[normalizedSymbol] || payload.chart;
      if (!activeChart) {
        chartDeferredResizePayloads.delete(normalizedSymbol);
        return;
      }

      if (isChartInMainProcess(activeChart)) {
        scheduleDeferredChartResizeFlush(normalizedSymbol);
        return;
      }

      chartDeferredResizePayloads.delete(normalizedSymbol);
      const rawResize = chartRawResizeFns.get(activeChart) || activeChart.resize?.bind(activeChart);
      rawResize?.(payload.resizeOptions);
    };

    if (typeof window.requestAnimationFrame === 'function') {
      chartDeferredResizeFrames.set(normalizedSymbol, {
        type: 'raf',
        id: window.requestAnimationFrame(flush),
      });
      return;
    }

    chartDeferredResizeFrames.set(normalizedSymbol, {
      type: 'timeout',
      id: window.setTimeout(flush, 16),
    });
  };

  applyChartResize = (symbol, chart, resizeOptions) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol || !chart) {
      return false;
    }

    // LWC 实例通过全局 ResizeObserver 自动管理，无需手动 resize
    if (typeof chart.setOption !== 'function') {
      return false;
    }

    const rawResize = chartRawResizeFns.get(chart) || chart.resize?.bind(chart);
    if (!rawResize) {
      return false;
    }

    if (!isChartInMainProcess(chart)) {
      rawResize(resizeOptions);
      return true;
    }

    chartDeferredResizePayloads.set(normalizedSymbol, {
      chart,
      resizeOptions,
    });
    scheduleDeferredChartResizeFlush(normalizedSymbol);
    return false;
  };

  removeChartResizeObserver = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) {
      return;
    }

    const observer = chartResizeObservers.get(normalizedSymbol);
    if (observer) {
      observer.disconnect();
      chartResizeObservers.delete(normalizedSymbol);
    }
    chartResizeObserverSizes.delete(normalizedSymbol);
  };

  observeChartResize = (symbol, element) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol || !element || typeof ResizeObserver !== 'function') {
      return;
    }

    removeChartResizeObserver(normalizedSymbol);

    const updateObservedSize = (width, height) => {
      if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
        return false;
      }

      const nextSize = {
        width: Math.round(width),
        height: Math.round(height),
      };
      const previousSize = chartResizeObserverSizes.get(normalizedSymbol);
      if (
        previousSize
        && previousSize.width === nextSize.width
        && previousSize.height === nextSize.height
      ) {
        return false;
      }

      chartResizeObserverSizes.set(normalizedSymbol, nextSize);
      return true;
    };

    updateObservedSize(element.clientWidth, element.clientHeight);

    const observer = new ResizeObserver((entries) => {
      const entry = entries?.[0];
      const target = entry?.target || element;
      const width = Number(target?.clientWidth || entry?.contentRect?.width || 0);
      const height = Number(target?.clientHeight || entry?.contentRect?.height || 0);
      if (!updateObservedSize(width, height)) {
        return;
      }

      const chart = chartInstances[normalizedSymbol];
      if (!chart) {
        return;
      }

      applyChartResize(normalizedSymbol, chart, { width, height, silent: true });
      if (typeof ctx.scheduleChartViewportAxisRefresh === 'function') {
        ctx.scheduleChartViewportAxisRefresh(normalizedSymbol, { immediate: true });
      }
    });

    observer.observe(element);
    chartResizeObservers.set(normalizedSymbol, observer);
  };

  scheduleChartHideTip = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol || chartDeferredHideTipFrames.has(normalizedSymbol)) {
      return;
    }

    const flush = () => {
      chartDeferredHideTipFrames.delete(normalizedSymbol);
      const chart = chartInstances[normalizedSymbol];
      if (!chart) {
        return;
      }

      if (isChartInMainProcess(chart)) {
        scheduleChartHideTip(normalizedSymbol);
        return;
      }

      chart.dispatchAction({
        type: 'hideTip',
      });
    };

    if (typeof window.requestAnimationFrame === 'function') {
      chartDeferredHideTipFrames.set(normalizedSymbol, {
        type: 'raf',
        id: window.requestAnimationFrame(flush),
      });
      return;
    }

    chartDeferredHideTipFrames.set(normalizedSymbol, {
      type: 'timeout',
      id: window.setTimeout(flush, 16),
    });
  };

  clearChartViewportInteractionTimer = (symbol) => {
    const timerId = chartViewportInteractionTimers.get(symbol);
    if (timerId) {
      window.clearTimeout(timerId);
      chartViewportInteractionTimers.delete(symbol);
    }
  };

  getChartViewportInteractionRemainingMs = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) {
      return 0;
    }
    const interactionUntil = Number(chartViewportInteractionUntil.get(normalizedSymbol) || 0);
    if (!Number.isFinite(interactionUntil) || interactionUntil <= 0) {
      return 0;
    }
    return Math.max(interactionUntil - Date.now(), 0);
  };

  isChartViewportInteracting = (symbol) => (
    getChartViewportInteractionRemainingMs(symbol) > 0
  );

  clearChartViewportInteraction = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) {
      return;
    }
    clearChartViewportInteractionTimer(normalizedSymbol);
    chartViewportInteractionUntil.delete(normalizedSymbol);
    delete chartViewportInteractionFlags[normalizedSymbol];
    chartViewportInteractionLightweightSymbols.delete(normalizedSymbol);
  };

  buildCurrentPriceLineSeries = (cache, latestPrice, latestPriceColor, visibleRange = null) => {
    if (!Number.isFinite(latestPrice) || latestPrice <= 0) {
      return null;
    }

    const renderLength = Math.max(
      Number.isFinite(cache?.renderLength) ? cache.renderLength : 0,
      Array.isArray(cache?.dates) ? cache.dates.length : 0,
      Number.isFinite(cache?.length) ? cache.length : 0,
      1
    );
    const maxRenderIndex = Math.max(renderLength - 1, 0);
    const startRenderIndex = visibleRange && Number.isFinite(visibleRange.startRenderIndex)
      ? clamp(Math.floor(visibleRange.startRenderIndex), 0, maxRenderIndex)
      : 0;
    const endRenderIndex = visibleRange && Number.isFinite(visibleRange.endRenderIndex)
      ? clamp(Math.ceil(visibleRange.endRenderIndex), startRenderIndex, maxRenderIndex)
      : maxRenderIndex;

    return {
      id: 'current-price-line',
      name: '当前价线',
      type: 'line',
      xAxisIndex: 0,
      yAxisIndex: 0,
      coordinateSystem: 'cartesian2d',
      data: [
        [startRenderIndex, latestPrice],
        [endRenderIndex, latestPrice],
      ],
      showSymbol: false,
      symbol: 'none',
      silent: true,
      animation: false,
      clip: true,
      z: 12,
      tooltip: {
        show: false,
      },
      lineStyle: {
        color: latestPriceColor || '#F7931A',
        width: 1.2,
        type: 'dashed',
        opacity: 0.96,
      },
      endLabel: {
        show: true,
        distance: 8,
        color: '#ffffff',
        fontSize: 10,
        fontWeight: 700,
        padding: [4, 8],
        borderRadius: 8,
        backgroundColor: latestPriceColor || '#F7931A',
        formatter: () => formatPrice(latestPrice),
      },
      labelLayout: {
        hideOverlap: false,
      },
      emphasis: {
        disabled: true,
      },
    };
  };

  buildCurrentPriceLineGraphic = (
    symbol,
    chart,
    options = {}
  ) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol || !chart) {
      return [];
    }

    const cache = options.renderCache || chartRenderCaches[normalizedSymbol];
    const candles = Array.isArray(cache?.candles) ? cache.candles : candlesData[normalizedSymbol];
    if (!Array.isArray(candles) || candles.length === 0) {
      return [];
    }

    const latestCandle = candles[candles.length - 1];
    const resolveCurrentPriceLine = typeof ctx.resolveCurrentPriceLineValue === 'function'
      ? ctx.resolveCurrentPriceLineValue
      : () => Number.NaN;
    const latestPrice = toFiniteNumber(
      options.latestPrice,
      resolveCurrentPriceLine(normalizedSymbol, latestCandle)
    );
    if (!Number.isFinite(latestPrice) || latestPrice <= 0) {
      return [];
    }

    const latestPriceColor = options.latestPriceColor || (
      latestCandle && latestCandle.close >= latestCandle.open
        ? '#26a69a'
        : '#ef5350'
    );
    const gridRect = chart.getModel?.()?.getComponent?.('grid', 0)?.coordinateSystem?.getRect?.();
    const chartWidth = chart.getWidth?.() || 0;
    const chartHeight = chart.getHeight?.() || 0;
    const fallbackLeft = 54;
    const fallbackRight = Math.max(chartWidth - 14, fallbackLeft + 1);
    const fallbackTop = 12;
    const fallbackBottom = Math.max(chartHeight - 104, fallbackTop + 1);
    const lineLeft = Number.isFinite(gridRect?.x) ? gridRect.x : fallbackLeft;
    const lineRight = Number.isFinite(gridRect?.width)
      ? gridRect.x + gridRect.width
      : fallbackRight;

    const startPoint = chart.convertToPixel(
      { xAxisIndex: 0, yAxisIndex: 0 },
      [0, latestPrice]
    );
    const y = Array.isArray(startPoint) && Number.isFinite(startPoint[1])
      ? startPoint[1]
      : Number.NaN;
    if (!Number.isFinite(y)) {
      return [];
    }

    const minY = Number.isFinite(gridRect?.y) ? gridRect.y : fallbackTop;
    const maxY = Number.isFinite(gridRect?.height)
      ? gridRect.y + gridRect.height
      : fallbackBottom;
    const clampedY = clamp(y, minY, maxY);
    const labelY = clamp(clampedY, minY + 12, maxY - 12);
    const labelX = clamp(lineRight - 8, lineLeft + 48, Math.max(lineRight - 8, lineLeft + 48));

    return [{
      id: `current-price-graphic-${normalizedSymbol}`,
      type: 'group',
      silent: true,
      z: 120,
      children: [
        {
          type: 'line',
          shape: {
            x1: lineLeft,
            y1: clampedY,
            x2: lineRight,
            y2: clampedY,
          },
          style: {
            stroke: latestPriceColor || '#F7931A',
            lineWidth: 1.2,
            lineDash: [6, 4],
            opacity: 0.96,
          },
        },
        {
          type: 'text',
          style: {
            x: labelX,
            y: labelY,
            text: formatPrice(latestPrice),
            fill: '#ffffff',
            textAlign: 'right',
            textVerticalAlign: 'middle',
            font: '700 10px "Inter", "Segoe UI", sans-serif',
            backgroundColor: latestPriceColor || '#F7931A',
            padding: [4, 8],
            borderRadius: 8,
          },
        },
      ],
    }];
  };

  buildLightweightInteractionSeries = (cache) => {
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
      {
        id: 'volume',
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: cache.volumes,
        barMinHeight: 1,
        z: 1,
      },
    ];

    [
      { enabled: indicators.ma5, id: 'ma5', name: 'MA5', data: cache.ma5, color: '#f6c85d' },
      { enabled: indicators.ma10, id: 'ma10', name: 'MA10', data: cache.ma10, color: '#6be6c1' },
      { enabled: indicators.ma20, id: 'ma20', name: 'MA20', data: cache.ma20, color: '#3fb1e3' },
      { enabled: indicators.ma60, id: 'ma60', name: 'MA60', data: cache.ma60, color: '#a38bf8' },
      { enabled: indicators.ema12, id: 'ema12', name: 'EMA12', data: cache.ema12, color: '#ff6b6b' },
      { enabled: indicators.ema26, id: 'ema26', name: 'EMA26', data: cache.ema26, color: '#4ecdc4' },
      { enabled: indicators.boll, id: 'boll-upper', name: 'BOLL上轨', data: cache.boll?.upper || null, color: '#ff9800', type: 'dashed' },
      { enabled: indicators.boll, id: 'boll-middle', name: 'BOLL中轨', data: cache.boll?.middle || null, color: '#ff9800', type: 'solid' },
      { enabled: indicators.boll, id: 'boll-lower', name: 'BOLL下轨', data: cache.boll?.lower || null, color: '#ff9800', type: 'dashed' },
    ].forEach((item) => {
      if (!item.enabled || !item.data) {
        return;
      }
      series.push({
        id: item.id,
        name: item.name,
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: item.data,
        smooth: false,
        sampling: 'lttb',
        showSymbol: false,
        animation: false,
        lineStyle: { width: 1, color: item.color, type: item.type || 'solid' },
      });
    });

    return series;
  };

  applyChartViewportInteractionLightweightMode = (symbol) => {
    if (!ENABLE_CHART_VIEWPORT_LIGHTWEIGHT_MODE) {
      return;
    }

    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol || chartViewportInteractionLightweightSymbols.has(normalizedSymbol)) {
      return;
    }

    const chart = chartInstances[normalizedSymbol];
    const candles = candlesData[normalizedSymbol];
    if (!chart || !Array.isArray(candles) || candles.length === 0) {
      return;
    }

    const buildRenderCache = typeof ctx.buildChartRenderCache === 'function'
      ? ctx.buildChartRenderCache
      : null;
    const resolveCurrentPriceLine = typeof ctx.resolveCurrentPriceLineValue === 'function'
      ? ctx.resolveCurrentPriceLineValue
      : () => Number.NaN;
    const resolveVisibleRange = typeof ctx.getViewportVisibleIndexRange === 'function'
      ? ctx.getViewportVisibleIndexRange
      : null;
    const cache = chartRenderCaches[normalizedSymbol]
      || (typeof buildRenderCache === 'function'
        ? buildRenderCache(normalizedSymbol, candles)
        : null);
    const latestCandle = candles[candles.length - 1];
    const latestPrice = resolveCurrentPriceLine(normalizedSymbol, latestCandle);
    const latestPriceColor = latestCandle && latestCandle.close >= latestCandle.open
      ? '#26a69a'
      : '#ef5350';
    const viewportState = getChartViewportState(normalizedSymbol, candles.length);
    const visibleRange = typeof resolveVisibleRange === 'function'
      ? resolveVisibleRange(
          candles.length,
          viewportState,
          Math.max(
            Number.isFinite(cache?.renderLength) ? cache.renderLength : 0,
            Array.isArray(cache?.dates) ? cache.dates.length : 0,
            getChartRenderLength(candles.length),
            candles.length
          )
        )
      : null;

    chartViewportInteractionLightweightSymbols.add(normalizedSymbol);
    const graphic = buildChartGraphicOverlays(normalizedSymbol, chart, {
      renderCache: cache,
      latestPrice,
      latestPriceColor,
      visibleRange,
    });

    applyChartSetOption(normalizedSymbol, chart, {
      animation: false,
      animationDuration: 0,
      animationDurationUpdate: 0,
      stateAnimation: {
        duration: 0,
      },
      graphic,
      series: buildLightweightInteractionSeries(cache),
    }, {
      lazyUpdate: true,
      silent: true,
      replaceMerge: ['series', 'graphic'],
    }, 'graphic');
  };

  restoreChartViewportInteractionLightweightMode = (symbol) => {
    if (!ENABLE_CHART_VIEWPORT_LIGHTWEIGHT_MODE) {
      return;
    }

    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol || !chartViewportInteractionLightweightSymbols.has(normalizedSymbol)) {
      return;
    }

    chartViewportInteractionLightweightSymbols.delete(normalizedSymbol);
    updateChart(normalizedSymbol);
  };

  markChartViewportInteracting = (
    symbol,
    durationMs = CHART_VIEWPORT_INTERACTION_IDLE_MS
  ) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) {
      return 0;
    }

    const nextDuration = Math.max(
      Math.round(toFiniteNumber(durationMs, CHART_VIEWPORT_INTERACTION_IDLE_MS)),
      16
    );
    const wasInteracting = isChartViewportInteracting(normalizedSymbol);
    chartViewportInteractionFlags[normalizedSymbol] = true;
    scheduleChartHideTip(normalizedSymbol);
    const nextUntil = Date.now() + nextDuration;
    const currentUntil = Number(chartViewportInteractionUntil.get(normalizedSymbol) || 0);
    chartViewportInteractionUntil.set(normalizedSymbol, Math.max(currentUntil, nextUntil));
    clearChartViewportInteractionTimer(normalizedSymbol);
    if (!wasInteracting) {
      applyChartViewportInteractionLightweightMode(normalizedSymbol);
    }

    const releaseInteraction = () => {
      const remainingMs = getChartViewportInteractionRemainingMs(normalizedSymbol);
      if (remainingMs > 0) {
        chartViewportInteractionTimers.set(
          normalizedSymbol,
          window.setTimeout(releaseInteraction, remainingMs)
        );
        return;
      }

      chartViewportInteractionTimers.delete(normalizedSymbol);
      chartViewportInteractionUntil.delete(normalizedSymbol);
      restoreChartViewportInteractionLightweightMode(normalizedSymbol);
    };

    chartViewportInteractionTimers.set(
      normalizedSymbol,
      window.setTimeout(releaseInteraction, nextDuration)
    );

    return nextDuration;
  };

  scheduleChartViewportAction = (symbol, start, end) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol || !Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      return false;
    }

    markChartViewportInteracting(normalizedSymbol);
    chartPendingViewportActions.set(normalizedSymbol, { start, end });
    if (chartViewportActionFrames.has(normalizedSymbol)) {
      return true;
    }

    const flushPendingViewportAction = () => {
      chartViewportActionFrames.delete(normalizedSymbol);
      const chart = chartInstances[normalizedSymbol];
      const nextAction = chartPendingViewportActions.get(normalizedSymbol);
      chartPendingViewportActions.delete(normalizedSymbol);
      if (!chart || !nextAction) {
        return;
      }

      chart.dispatchAction({
        type: 'dataZoom',
        dataZoomId: 'inside',
        start: nextAction.start,
        end: nextAction.end,
      });
    };

    if (typeof window.requestAnimationFrame === 'function') {
      const frameId = window.requestAnimationFrame(flushPendingViewportAction);
      chartViewportActionFrames.set(normalizedSymbol, {
        type: 'raf',
        id: frameId,
      });
      return true;
    }

    const timerId = window.setTimeout(flushPendingViewportAction, CHART_VIEWPORT_ACTION_FRAME_MS);
    chartViewportActionFrames.set(normalizedSymbol, {
      type: 'timeout',
      id: timerId,
    });
    return true;
  };


  getChartDataZoomWindow = (chart) => {
    // LWC 实例没有 getOption/dataZoom，直接返回 null（LWC 原生管理视口）
    if (!chart || typeof chart.getOption !== 'function') {
      return null;
    }
    const option = chart.getOption();
    const dataZoomList = Array.isArray(option?.dataZoom) ? option.dataZoom : [];
    const insideZoom = dataZoomList.find(item => item?.id === 'inside') || dataZoomList[0];
    const sliderZoom = dataZoomList.find(item => item?.id === 'slider');

    const start = Number(insideZoom?.start ?? sliderZoom?.start ?? 0);
    const end = Number(insideZoom?.end ?? sliderZoom?.end ?? 100);
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
      return null;
    }

    return { start, end, span: end - start };
  };

  removeChartWheelInteraction = (symbol) => {
    const bound = chartWheelInteractionHandlers.get(symbol);
    if (!bound) return;

    bound.el.removeEventListener('wheel', bound.handler, true);
    chartWheelInteractionHandlers.delete(symbol);
  };

  removeChartDragInteraction = (symbol) => {
    const bound = chartDragInteractionHandlers.get(symbol);
    if (!bound) return;

    bound.cleanup();
    chartDragInteractionHandlers.delete(symbol);
  };

  removeChartAnnotationInteraction = (symbol) => {
    const bound = chartAnnotationInteractionHandlers.get(symbol);
    if (!bound) return;

    bound.cleanup();
    chartAnnotationInteractionHandlers.delete(symbol);
  };

  disposeChartInstance = (symbol) => {
    removeChartWheelInteraction(symbol);
    removeChartDragInteraction(symbol);
    removeChartAnnotationInteraction(symbol);
    removeChartResizeObserver(symbol);
    clearChartAnnotationFrame(symbol);
    clearChartAnnotationUpdateFrame(symbol);
    clearChartViewportAxisRefresh(symbol);
    clearChartViewportActionFrame(symbol);
    clearChartViewportInteraction(symbol);
    clearChartGraphicOverlays(symbol);
    clearDeferredChartSetOptions(symbol);
    clearDeferredChartResizes(symbol);
    clearDeferredChartHideTip(symbol);
    delete chartRenderCaches[symbol];

    // 优先通过 LWC 管理器销毁（内部会调用 chart.remove）
    const { lwcManagers } = ctx;
    const manager = lwcManagers?.get(symbol);
    if (manager) {
      manager.dispose();
      lwcManagers.delete(symbol);
      delete chartInstances[symbol];
      return;
    }

    // Fallback: 直接销毁 chartInstances 中的 ECharts 实例
    const instance = chartInstances[symbol];
    if (instance) {
      if (typeof instance.dispose === 'function') {
        try { instance.dispose(); } catch (_) {}
      }
      delete chartInstances[symbol];
    }
  };

  panChartViewportByWheel = (symbol, event) => {
    const chart = chartInstances[symbol];
    const dataLength = candlesData[symbol]?.length || 0;
    if (!chart || dataLength <= 1) return false;

    const zoomWindow = getChartDataZoomWindow(chart);
    if (!zoomWindow || zoomWindow.span >= 99.99) return false;

    const dominantDelta = Math.abs(event.deltaX) > Math.abs(event.deltaY)
      ? event.deltaX
      : event.deltaY;
    if (!Number.isFinite(dominantDelta) || Math.abs(dominantDelta) < 0.5) {
      return false;
    }

    const minShiftPercent = 100 / dataLength;
    const deltaScale = clamp(Math.abs(dominantDelta) / 120, 0.35, 2.4);
    const shiftPercent = Math.max(
      minShiftPercent,
      zoomWindow.span * CHART_TOUCHPAD_PAN_RATIO * deltaScale
    );
    const maxViewportStart = getChartMaxViewportStart(dataLength, zoomWindow.span, currentTimeframe.value);
    const nextStart = clamp(zoomWindow.start + Math.sign(dominantDelta) * shiftPercent, 0, maxViewportStart);
    const nextEnd = nextStart + zoomWindow.span;

    return scheduleChartViewportAction(symbol, nextStart, nextEnd);
  };

  zoomChartViewportByWheel = (symbol, event) => {
    const chart = chartInstances[symbol];
    const dataLength = candlesData[symbol]?.length || 0;
    if (!chart || dataLength <= 0) return false;

    const zoomWindow = getChartDataZoomWindow(chart);
    if (!zoomWindow) return false;

    const zoomDelta = Number.isFinite(event.deltaY) && Math.abs(event.deltaY) >= 0.5
      ? event.deltaY
      : event.deltaX;
    if (!Number.isFinite(zoomDelta) || Math.abs(zoomDelta) < 0.5) {
      return false;
    }

    const zoomScale = clamp(Math.abs(zoomDelta) / 240, 0.06, 0.32);
    const nextSpan = clamp(
      zoomWindow.span * (zoomDelta > 0 ? 1 + zoomScale : 1 - zoomScale),
      MIN_DATA_ZOOM_SPAN_PERCENT,
      100
    );
    if (Math.abs(nextSpan - zoomWindow.span) < 0.01) {
      return false;
    }

    const center = (zoomWindow.start + zoomWindow.end) / 2;
    const maxViewportStart = getChartMaxViewportStart(dataLength, nextSpan, currentTimeframe.value);
    const nextStart = clamp(center - nextSpan / 2, 0, maxViewportStart);
    const nextEnd = nextStart + nextSpan;

    return scheduleChartViewportAction(symbol, nextStart, nextEnd);
  };

  bindChartWheelInteraction = (symbol, chart) => {
    removeChartWheelInteraction(symbol);

    const el = chart?.getDom?.();
    if (!el) return;

    const handler = (event) => {
      const isHorizontalSwipe = Math.abs(event.deltaX) > Math.abs(event.deltaY) * 1.15;
      const handled = isHorizontalSwipe
        ? panChartViewportByWheel(symbol, event)
        : zoomChartViewportByWheel(symbol, event);

      if (handled) {
        scheduleChartHideTip(symbol);
        event.preventDefault();
        event.stopPropagation();
      }
    };

    el.addEventListener('wheel', handler, { passive: false, capture: true });
    chartWheelInteractionHandlers.set(symbol, { el, handler });
  };

  bindChartDragInteraction = (symbol, chart) => {
    removeChartDragInteraction(symbol);

    const el = chart?.getDom?.();
    if (!el) return;

    let dragState = null;

    const suppressHoverEvent = (event) => {
      if ((!dragState || !dragState.started) && !chartAnnotationEditSessions.has(symbol)) {
        return;
      }
      event.stopImmediatePropagation?.();
      event.stopPropagation();
      event.preventDefault();
    };

    const stopDragging = () => {
      dragState = null;
      el.classList.remove('chart-dragging');
    };

    const handleMouseMove = (event) => {
      const currentChart = chartInstances[symbol];
      if (!currentChart) {
        stopDragging();
        clearChartAnnotationEditSession(symbol);
        return;
      }

      if (chartAnnotationEditSessions.has(symbol)) {
        const handled = updateSelectedChartAnnotationEdit(symbol, currentChart, event);
        if (handled) {
          event.preventDefault();
        }
        return;
      }

      if (!dragState) return;

      const deltaX = event.clientX - dragState.startX;
      if (Math.abs(deltaX) < 2) return;

      if (!dragState.started) {
        dragState.started = true;
        scheduleChartHideTip(symbol);
        markChartViewportInteracting(symbol);
        el.classList.add('chart-dragging');
      }

      const shiftPercent = (deltaX / dragState.width) * dragState.span * CHART_DRAG_PAN_RATIO;
      const maxViewportStart = getChartMaxViewportStart(
        candlesData[symbol]?.length || 0,
        dragState.span,
        currentTimeframe.value
      );
      const nextStart = clamp(dragState.start - shiftPercent, 0, maxViewportStart);
      const nextEnd = nextStart + dragState.span;

      scheduleChartViewportAction(symbol, nextStart, nextEnd);

      event.preventDefault();
    };

    const handleMouseUp = () => {
      if (finishSelectedChartAnnotationEdit(symbol)) {
        return;
      }
      if (dragState?.started) {
        markChartViewportInteracting(symbol);
      }
      stopDragging();
    };

    const handleMouseDown = (event) => {
      if (event.button !== 0) return;
      if (activeAnalysisTool?.value && activeAnalysisTool.value !== 'none') return;

      const currentChart = chartInstances[symbol];
      if (!currentChart) return;

      if (beginSelectedChartAnnotationEdit(symbol, currentChart, event)) {
        scheduleChartHideTip(symbol);
        event.stopPropagation();
        event.preventDefault();
        return;
      }

      if (resolveChartAnnotationHit(symbol, currentChart, event)) {
        return;
      }

      const rect = el.getBoundingClientRect();
      const point = [event.clientX - rect.left, event.clientY - rect.top];
      if (!currentChart.containPixel({ gridIndex: 0 }, point)) {
        return;
      }

      const zoomWindow = getChartDataZoomWindow(currentChart);
      if (!zoomWindow || zoomWindow.span >= 99.99) {
        return;
      }

      dragState = {
        startX: event.clientX,
        start: zoomWindow.start,
        span: zoomWindow.span,
        width: Math.max(rect.width, 1),
        started: false,
      };
    };

    const cleanup = () => {
      stopDragging();
      clearChartAnnotationEditSession(symbol);
      el.removeEventListener('mousedown', handleMouseDown, true);
      el.removeEventListener('mousemove', suppressHoverEvent, true);
      el.removeEventListener('pointermove', suppressHoverEvent, true);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    el.addEventListener('mousedown', handleMouseDown, true);
    el.addEventListener('mousemove', suppressHoverEvent, true);
    el.addEventListener('pointermove', suppressHoverEvent, true);
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    chartDragInteractionHandlers.set(symbol, { cleanup });
  };


  return {
    buildDeferredSetOptionKey,
    isChartInMainProcess,
    clearDeferredChartSetOptions,
    clearDeferredChartResizes,
    clearDeferredChartHideTip,
    scheduleDeferredChartSetOptionFlush,
    applyChartSetOption,
    scheduleDeferredChartResizeFlush,
    applyChartResize,
    removeChartResizeObserver,
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
    getChartDataZoomWindow,
    removeChartWheelInteraction,
    removeChartDragInteraction,
    removeChartAnnotationInteraction,
    disposeChartInstance,
    panChartViewportByWheel,
    zoomChartViewportByWheel,
    bindChartWheelInteraction,
    bindChartDragInteraction,
  };
}
