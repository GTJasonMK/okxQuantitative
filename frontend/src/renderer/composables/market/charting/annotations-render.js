export function createMarketViewChartAnnotationRender(ctx) {
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

  const resolveAnnotationRenderOptions = (annotation, options = {}) => {
    if (!annotation || typeof annotation !== 'object') {
      return options;
    }

    const source = String(annotation?.meta?.source || '').trim().toLowerCase();
    if (!['assistant', 'assistant_patrol'].includes(source)) {
      return options;
    }

    if (annotation.type === 'horizontal') {
      const role = String(annotation?.meta?.role || '').trim().toLowerCase();
      if (role === 'support') {
        return { ...options, color: '#57e3a0', linePattern: 'dashed', opacity: 0.92 };
      }
      if (role === 'resistance') {
        return { ...options, color: '#ff8e8e', linePattern: 'dashed', opacity: 0.92 };
      }
      if (role === 'entry') {
        return { ...options, color: '#F7931A', linePattern: 'solid', opacity: 0.95 };
      }
      if (role === 'stop') {
        return { ...options, color: '#ff6b6b', linePattern: 'dashed', opacity: 0.95 };
      }
      if (role === 'target') {
        return { ...options, color: '#ffd166', linePattern: 'solid', opacity: 0.95 };
      }
      if (role.includes('invalidation')) {
        return { ...options, color: '#ff9f43', linePattern: 'dashed', opacity: 0.92 };
      }
      return { ...options, color: '#ffd166', linePattern: 'dashed', opacity: 0.9 };
    }

    if (annotation.type === 'trendline') {
      const scenario = String(annotation?.meta?.scenario || '').trim().toLowerCase();
      if (scenario === 'bullish') {
        return { ...options, color: '#57e3a0', linePattern: 'dashed', opacity: 0.94 };
      }
      if (scenario === 'bearish') {
        return { ...options, color: '#ff8e8e', linePattern: 'dashed', opacity: 0.94 };
      }
      return { ...options, color: '#F7931A', linePattern: 'dashed', opacity: 0.94 };
    }

    return options;
  };

  buildTrendlineAnnotationSeries = (annotation, candles, options = {}) => {
    const resolvedOptions = resolveAnnotationRenderOptions(annotation, options);
    const startIndex = findClosestCandleIndexByTimestamp(candles, annotation.startTs);
    const endIndex = findClosestCandleIndexByTimestamp(candles, annotation.endTs);
    if (startIndex < 0 || endIndex < 0) {
      return null;
    }

    return {
      id: `annotation-trendline-${annotation.id || annotation.startTs || annotation.endTs || 'unknown'}${options.draft ? '-draft' : ''}`,
      name: options.draft ? '趋势线草稿' : '趋势线',
      type: 'line',
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: [
        [startIndex, annotation.startPrice],
        [endIndex, annotation.endPrice],
      ],
      showSymbol: false,
      silent: true,
      animation: false,
      z: 8,
      lineStyle: {
        color: resolvedOptions.color || '#F7931A',
        width: resolvedOptions.draft ? 1.5 : 2,
        type: resolvedOptions.draft ? 'dashed' : (resolvedOptions.linePattern || 'solid'),
        opacity: resolvedOptions.draft ? 0.78 : (resolvedOptions.opacity || 0.94),
      },
    };
  };

  formatRulerSignedPrice = (value) => {
    const numeric = toFiniteNumber(value, Number.NaN);
    if (!Number.isFinite(numeric)) {
      return '--';
    }

    const prefix = numeric > 0 ? '+' : '';
    return `${prefix}${formatPrice(numeric)}`;
  };

  formatRulerSignedPercent = (value) => {
    const numeric = toFiniteNumber(value, Number.NaN);
    if (!Number.isFinite(numeric)) {
      return '--';
    }

    const prefix = numeric > 0 ? '+' : '';
    return `${prefix}${numeric.toFixed(2)}%`;
  };

  formatRulerDuration = (milliseconds) => {
    const duration = Math.max(0, Math.round(toFiniteNumber(milliseconds, 0)));
    if (duration <= 0) {
      return '0m';
    }

    const totalMinutes = Math.max(1, Math.round(duration / (60 * 1000)));
    const days = Math.floor(totalMinutes / (24 * 60));
    const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
    const minutes = totalMinutes % 60;
    const parts = [];

    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0 && parts.length < 2) parts.push(`${minutes}m`);

    if (parts.length === 0) {
      parts.push(`${totalMinutes}m`);
    }

    return parts.slice(0, 2).join(' ');
  };

  buildRulerAnnotationSeries = (annotation, candles, options = {}) => {
    const resolvedOptions = resolveAnnotationRenderOptions(annotation, options);
    const startIndex = findClosestCandleIndexByTimestamp(candles, annotation.startTs);
    const endIndex = findClosestCandleIndexByTimestamp(candles, annotation.endTs);
    if (startIndex < 0 || endIndex < 0) {
      return null;
    }

    const priceDelta = toFiniteNumber(annotation.endPrice, 0) - toFiniteNumber(annotation.startPrice, 0);
    const percentDelta = Math.abs(annotation.startPrice) > Number.EPSILON
      ? (priceDelta / annotation.startPrice) * 100
      : Number.NaN;
    const candleCount = Math.abs(endIndex - startIndex) + 1;
    const timeSpan = Math.abs(
      toFiniteNumber(annotation.endTs, 0) - toFiniteNumber(annotation.startTs, 0)
    );
    const measurementTone = Math.abs(priceDelta) <= Number.EPSILON
      ? 'neutral'
      : priceDelta > 0
        ? 'bullish'
        : 'bearish';

    return {
      id: `annotation-ruler-${annotation.id || annotation.startTs || annotation.endTs || 'unknown'}${options.draft ? '-draft' : ''}`,
      name: options.draft ? '测距尺草稿' : '测距尺',
      type: 'custom',
      coordinateSystem: 'cartesian2d',
      xAxisIndex: 0,
      yAxisIndex: 0,
      silent: true,
      animation: false,
      z: 8,
      data: [[
        startIndex,
        annotation.startPrice,
        endIndex,
        annotation.endPrice,
        candleCount,
        timeSpan,
        priceDelta,
        percentDelta,
      ]],
      renderItem: (params, api) => {
        const start = api.coord([api.value(0), api.value(1)]);
        const end = api.coord([api.value(2), api.value(3)]);
        const x = Math.min(start[0], end[0]);
        const y = Math.min(start[1], end[1]);
        const width = Math.max(Math.abs(end[0] - start[0]), 1);
        const height = Math.max(Math.abs(end[1] - start[1]), 1);
        const palette = measurementTone === 'bullish'
          ? {
              stroke: '#57e3a0',
              fill: 'rgba(87, 227, 160, 0.08)',
              labelFill: '#7ce8bc',
              labelBg: 'rgba(11, 34, 24, 0.88)',
            }
          : measurementTone === 'bearish'
            ? {
                stroke: '#ff8e8e',
                fill: 'rgba(255, 110, 110, 0.08)',
                labelFill: '#ffb0b0',
                labelBg: 'rgba(43, 18, 20, 0.9)',
              }
            : {
                stroke: '#F7931A',
                fill: 'rgba(247, 147, 26, 0.08)',
                labelFill: '#fde8cd',
                labelBg: 'rgba(14, 27, 39, 0.9)',
              };
        const line1 = `${formatRulerSignedPrice(api.value(6))} / ${formatRulerSignedPercent(api.value(7))}`;
        const line2 = `${Math.max(1, Math.round(api.value(4)))}根 / ${formatRulerDuration(api.value(5))}`;
        const labelX = x + 8;
        const labelY = y <= 34 ? y + 6 : y - 36;

        return {
          type: 'group',
          children: [
            {
              type: 'rect',
              shape: { x, y, width, height },
              style: {
                fill: resolvedOptions.fill || palette.fill,
                stroke: resolvedOptions.color || palette.stroke,
                lineWidth: resolvedOptions.draft ? 1.5 : 2,
                lineDash: resolvedOptions.draft || resolvedOptions.linePattern === 'dashed' ? [6, 4] : [],
              },
            },
            {
              type: 'line',
              shape: {
                x1: start[0],
                y1: start[1],
                x2: end[0],
                y2: end[1],
              },
              style: {
                stroke: resolvedOptions.color || palette.stroke,
                lineWidth: resolvedOptions.draft ? 1.25 : 1.5,
                lineDash: resolvedOptions.draft || resolvedOptions.linePattern === 'dashed' ? [6, 4] : [4, 3],
                opacity: resolvedOptions.draft ? 0.85 : (resolvedOptions.opacity || 0.92),
              },
            },
            {
              type: 'circle',
              shape: { cx: start[0], cy: start[1], r: 3 },
              style: {
                fill: resolvedOptions.color || palette.stroke,
                stroke: '#06111b',
                lineWidth: 1,
              },
            },
            {
              type: 'circle',
              shape: { cx: end[0], cy: end[1], r: 3 },
              style: {
                fill: resolvedOptions.color || palette.stroke,
                stroke: '#06111b',
                lineWidth: 1,
              },
            },
            {
              type: 'text',
              style: {
                x: labelX,
                y: labelY,
                text: `${line1}\n${line2}`,
                fill: palette.labelFill,
                font: '11px "IBM Plex Sans", "Segoe UI", sans-serif',
                lineHeight: 16,
                backgroundColor: palette.labelBg,
                borderColor: resolvedOptions.color || palette.stroke,
                borderWidth: 1,
                borderRadius: 8,
                padding: [6, 8],
              },
            },
          ],
        };
      },
    };
  };

  buildHorizontalAnnotationSeries = (annotation, candles, options = {}) => {
    const resolvedOptions = resolveAnnotationRenderOptions(annotation, options);
    if (!Array.isArray(candles) || candles.length === 0) {
      return null;
    }

    const renderLength = Math.max(getChartRenderLength(candles.length), candles.length);

    return {
      id: `annotation-horizontal-${annotation.id || annotation.price || 'unknown'}${options.draft ? '-draft' : ''}`,
      name: options.draft ? '水平位草稿' : '水平位',
      type: 'line',
      xAxisIndex: 0,
      yAxisIndex: 0,
      data: [
        [0, annotation.price],
        [renderLength - 1, annotation.price],
      ],
      showSymbol: false,
      silent: true,
      animation: false,
      z: 8,
      lineStyle: {
        color: resolvedOptions.color || '#ffd166',
        width: resolvedOptions.draft ? 1.5 : 2,
        type: resolvedOptions.draft ? 'dashed' : (resolvedOptions.linePattern || 'solid'),
        opacity: resolvedOptions.draft ? 0.76 : (resolvedOptions.opacity || 0.92),
      },
    };
  };

  buildRectangleAnnotationSeries = (annotation, candles, options = {}) => {
    const resolvedOptions = resolveAnnotationRenderOptions(annotation, options);
    const startIndex = findClosestCandleIndexByTimestamp(candles, annotation.startTs);
    const endIndex = findClosestCandleIndexByTimestamp(candles, annotation.endTs);
    if (startIndex < 0 || endIndex < 0) {
      return null;
    }

    return {
      id: `annotation-rectangle-${annotation.id || annotation.startTs || annotation.endTs || 'unknown'}${options.draft ? '-draft' : ''}`,
      name: options.draft ? '区间框草稿' : '区间框',
      type: 'custom',
      coordinateSystem: 'cartesian2d',
      xAxisIndex: 0,
      yAxisIndex: 0,
      silent: true,
      animation: false,
      z: 7,
      data: [[
        startIndex,
        annotation.startPrice,
        endIndex,
        annotation.endPrice,
      ]],
      renderItem: (params, api) => {
        const start = api.coord([api.value(0), api.value(1)]);
        const end = api.coord([api.value(2), api.value(3)]);
        const x = Math.min(start[0], end[0]);
        const y = Math.min(start[1], end[1]);
        const width = Math.max(Math.abs(end[0] - start[0]), 1);
        const height = Math.max(Math.abs(end[1] - start[1]), 1);

        return {
          type: 'rect',
          shape: { x, y, width, height },
          style: {
            fill: resolvedOptions.fill || 'rgba(247, 147, 26, 0.08)',
            stroke: resolvedOptions.color || '#F7931A',
            lineWidth: resolvedOptions.draft ? 1.5 : 2,
            lineDash: resolvedOptions.draft || resolvedOptions.linePattern === 'dashed' ? [6, 4] : [],
          },
        };
      },
    };
  };

  buildDraftPreviewSignature = (draft) => (
    draft
      ? [
          draft.type || '',
          draft.startTs || '',
          draft.endTs || '',
          draft.startPrice || '',
          draft.endPrice || '',
        ].join(':')
      : 'none'
  );

  buildDraftPreviewPoint = (chart, candleIndex, price) => {
    const pixel = chart.convertToPixel({ xAxisIndex: 0, yAxisIndex: 0 }, [candleIndex, price]);
    if (!Array.isArray(pixel) || pixel.length < 2) {
      return null;
    }

    const [x, y] = pixel;
    return Number.isFinite(x) && Number.isFinite(y) ? [x, y] : null;
  };

  buildDraftPreviewLabelY = (topY) => (
    topY <= 34 ? topY + 6 : topY - 36
  );

  buildSelectedAnnotationGraphic = (symbol, chart) => {
    const selectedAnnotation = getSelectedChartAnnotation(symbol);
    if (!selectedAnnotation) {
      return [];
    }

    const geometry = buildAnnotationPixelGeometry(symbol, chart, selectedAnnotation);
    if (!geometry) {
      return [];
    }

    const children = [];

    if (geometry.type === 'horizontal' && geometry.line) {
      children.push({
        type: 'line',
        shape: {
          x1: geometry.line.x1,
          y1: geometry.line.y1,
          x2: geometry.line.x2,
          y2: geometry.line.y2,
        },
        style: {
          stroke: ANNOTATION_SELECTED_STROKE,
          lineWidth: 1,
          lineDash: [4, 4],
          opacity: 0.36,
        },
      });
    }

    if (geometry.type === 'trendline' && geometry.line) {
      children.push({
        type: 'line',
        shape: {
          x1: geometry.line.x1,
          y1: geometry.line.y1,
          x2: geometry.line.x2,
          y2: geometry.line.y2,
        },
        style: {
          stroke: ANNOTATION_SELECTED_STROKE,
          lineWidth: 4,
          opacity: 0.12,
        },
      });
    }

    if ((geometry.type === 'rectangle' || geometry.type === 'ruler') && geometry.rect) {
      children.push({
        type: 'rect',
        shape: geometry.rect,
        style: {
          fill: ANNOTATION_SELECTED_FILL,
          stroke: ANNOTATION_SELECTED_STROKE,
          lineWidth: 1,
          lineDash: [4, 4],
          opacity: 0.28,
        },
      });
    }

    geometry.handles.forEach((handle) => {
      children.push({
        type: 'circle',
        shape: { cx: handle.x, cy: handle.y, r: 5 },
        style: {
          fill: '#06111b',
          stroke: ANNOTATION_SELECTED_STROKE,
          lineWidth: 2,
          shadowBlur: 6,
          shadowColor: 'rgba(242, 246, 251, 0.28)',
        },
      });
    });

    return children.length > 0
      ? [{
          id: `selected-annotation-${symbol}`,
          type: 'group',
          silent: true,
          z: 140,
          children,
        }]
      : [];
  };

  buildChartGraphicOverlays = (symbol, chart, options = {}) => {
    const priceGraphic = buildCurrentPriceLineGraphic(symbol, chart, options);
    const draftGraphic = buildChartDraftPreviewGraphic(symbol, chart);
    const selectedGraphic = buildSelectedAnnotationGraphic(symbol, chart);
    return [...priceGraphic, ...draftGraphic, ...selectedGraphic];
  };

  buildChartDraftPreviewGraphic = (symbol, chart) => {
    const candles = candlesData[symbol];
    const draft = getChartAnnotationDraft(symbol);
    if (!chart || !Array.isArray(candles) || candles.length === 0 || !draft) {
      return [];
    }

    const startIndex = findClosestCandleIndexByTimestamp(candles, draft.startTs);
    const endIndex = findClosestCandleIndexByTimestamp(candles, draft.endTs);
    if (startIndex < 0 || endIndex < 0) {
      return [];
    }

    const start = buildDraftPreviewPoint(chart, startIndex, draft.startPrice);
    const end = buildDraftPreviewPoint(chart, endIndex, draft.endPrice);
    if (!start || !end) {
      return [];
    }

    if (draft.type === 'trendline') {
      return [{
        id: `draft-trendline-${symbol}`,
        type: 'group',
        silent: true,
        children: [
          {
            type: 'line',
            shape: {
              x1: start[0],
              y1: start[1],
              x2: end[0],
              y2: end[1],
            },
            style: {
              stroke: '#F7931A',
              lineWidth: 1.5,
              lineDash: [6, 4],
              opacity: 0.9,
            },
          },
          {
            type: 'circle',
            shape: { cx: start[0], cy: start[1], r: 3 },
            style: {
              fill: '#F7931A',
              stroke: '#06111b',
              lineWidth: 1,
            },
          },
          {
            type: 'circle',
            shape: { cx: end[0], cy: end[1], r: 3 },
            style: {
              fill: '#F7931A',
              stroke: '#06111b',
              lineWidth: 1,
            },
          },
        ],
      }];
    }

    if (draft.type === 'rectangle') {
      const x = Math.min(start[0], end[0]);
      const y = Math.min(start[1], end[1]);
      const width = Math.max(Math.abs(end[0] - start[0]), 1);
      const height = Math.max(Math.abs(end[1] - start[1]), 1);

      return [{
        id: `draft-rectangle-${symbol}`,
        type: 'rect',
        silent: true,
        shape: { x, y, width, height },
        style: {
          fill: 'rgba(87, 227, 160, 0.05)',
          stroke: '#57e3a0',
          lineWidth: 1.5,
          lineDash: [6, 4],
        },
      }];
    }

    if (draft.type === 'ruler') {
      const priceDelta = toFiniteNumber(draft.endPrice, 0) - toFiniteNumber(draft.startPrice, 0);
      const percentDelta = Math.abs(draft.startPrice) > Number.EPSILON
        ? (priceDelta / draft.startPrice) * 100
        : Number.NaN;
      const candleCount = Math.abs(endIndex - startIndex) + 1;
      const timeSpan = Math.abs(
        toFiniteNumber(draft.endTs, 0) - toFiniteNumber(draft.startTs, 0)
      );
      const measurementTone = Math.abs(priceDelta) <= Number.EPSILON
        ? 'neutral'
        : priceDelta > 0
          ? 'bullish'
          : 'bearish';
      const palette = measurementTone === 'bullish'
        ? {
            stroke: '#57e3a0',
            fill: 'rgba(87, 227, 160, 0.08)',
            labelFill: '#7ce8bc',
            labelBg: 'rgba(11, 34, 24, 0.88)',
          }
        : measurementTone === 'bearish'
          ? {
              stroke: '#ff8e8e',
              fill: 'rgba(255, 110, 110, 0.08)',
              labelFill: '#ffb0b0',
              labelBg: 'rgba(43, 18, 20, 0.9)',
            }
          : {
              stroke: '#F7931A',
              fill: 'rgba(247, 147, 26, 0.08)',
              labelFill: '#fde8cd',
              labelBg: 'rgba(14, 27, 39, 0.9)',
            };
      const x = Math.min(start[0], end[0]);
      const y = Math.min(start[1], end[1]);
      const width = Math.max(Math.abs(end[0] - start[0]), 1);
      const height = Math.max(Math.abs(end[1] - start[1]), 1);
      const labelX = x + 8;
      const labelY = buildDraftPreviewLabelY(y);
      const line1 = `${formatRulerSignedPrice(priceDelta)} / ${formatRulerSignedPercent(percentDelta)}`;
      const line2 = `${Math.max(1, Math.round(candleCount))}根 / ${formatRulerDuration(timeSpan)}`;

      return [{
        id: `draft-ruler-${symbol}`,
        type: 'group',
        silent: true,
        children: [
          {
            type: 'rect',
            shape: { x, y, width, height },
            style: {
              fill: palette.fill,
              stroke: palette.stroke,
              lineWidth: 1.5,
              lineDash: [6, 4],
            },
          },
          {
            type: 'line',
            shape: {
              x1: start[0],
              y1: start[1],
              x2: end[0],
              y2: end[1],
            },
            style: {
              stroke: palette.stroke,
              lineWidth: 1.25,
              lineDash: [6, 4],
              opacity: 0.88,
            },
          },
          {
            type: 'circle',
            shape: { cx: start[0], cy: start[1], r: 3 },
            style: {
              fill: palette.stroke,
              stroke: '#06111b',
              lineWidth: 1,
            },
          },
          {
            type: 'circle',
            shape: { cx: end[0], cy: end[1], r: 3 },
            style: {
              fill: palette.stroke,
              stroke: '#06111b',
              lineWidth: 1,
            },
          },
          {
            type: 'text',
            style: {
              x: labelX,
              y: labelY,
              text: `${line1}\n${line2}`,
              fill: palette.labelFill,
              font: '11px "IBM Plex Sans", "Segoe UI", sans-serif',
              lineHeight: 16,
              backgroundColor: palette.labelBg,
              borderColor: palette.stroke,
              borderWidth: 1,
              borderRadius: 8,
              padding: [6, 8],
            },
          },
        ],
      }];
    }

    return [];
  };

  renderChartDraftPreview = (symbol) => {
    const chart = chartInstances[symbol];
    if (!chart) {
      return;
    }

    const draft = getChartAnnotationDraft(symbol);
    const signature = draft
      ? [
          buildDraftPreviewSignature(draft),
          chart.getWidth?.() || 0,
          chart.getHeight?.() || 0,
        ].join('|')
      : 'none';
    if (chartDraftPreviewSignatures.get(symbol) === signature) {
      return;
    }

    chartDraftPreviewSignatures.set(symbol, signature);
    const graphic = buildChartGraphicOverlays(symbol, chart);

    applyChartSetOption(symbol, chart, {
      graphic,
    }, {
      lazyUpdate: false,
      silent: true,
      replaceMerge: ['graphic'],
    }, 'graphic');
  };

  buildAnnotationSeries = (symbol, candles) => {
    const annotations = getChartAnnotations(symbol);
    if (!Array.isArray(annotations) || annotations.length === 0 || !Array.isArray(candles) || candles.length === 0) {
      return [];
    }

    return annotations
      .map((annotation) => {
        if (!annotation || typeof annotation !== 'object') {
          return null;
        }

        switch (annotation.type) {
          case 'trendline':
            return buildTrendlineAnnotationSeries(annotation, candles);
          case 'horizontal':
            return buildHorizontalAnnotationSeries(annotation, candles);
          case 'rectangle':
            return buildRectangleAnnotationSeries(annotation, candles);
          case 'ruler':
            return buildRulerAnnotationSeries(annotation, candles);
          default:
            return null;
        }
      })
      .filter(Boolean);
  };

  return {
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
  };
}
