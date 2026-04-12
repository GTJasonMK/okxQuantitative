export function createMarketViewChartAnnotationState(ctx) {
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
    clearChartAnnotationsBySource,
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

  getChartAnnotationStateKey = (symbol) => getChartViewportStateKey(symbol);

  getChartAnnotations = (symbol) => (
    chartAnnotations[getChartAnnotationStateKey(symbol)] || []
  );

  getSelectedChartAnnotationId = (symbol) => (
    chartSelectedAnnotationIds[getChartAnnotationStateKey(symbol)] || ''
  );

  getSelectedChartAnnotation = (symbol) => {
    const selectedId = getSelectedChartAnnotationId(symbol);
    if (!selectedId) {
      return null;
    }
    return getChartAnnotations(symbol).find(annotation => annotation?.id === selectedId) || null;
  };

  getChartAnnotationDraft = (symbol) => (
    chartAnnotationDrafts[getChartAnnotationStateKey(symbol)] || null
  );

  getChartAnnotationCount = (symbol) => getChartAnnotations(symbol).length;

  const matchesAnnotationSource = (annotation, source) => {
    if (!annotation || typeof annotation !== 'object') {
      return false;
    }
    const annotationSource = String(annotation?.meta?.source || '').trim().toLowerCase();
    if (!annotationSource) {
      return false;
    }
    if (Array.isArray(source)) {
      return source.some(item => annotationSource === String(item || '').trim().toLowerCase());
    }
    return annotationSource === String(source || '').trim().toLowerCase();
  };

  const AI_ANNOTATION_SOURCES = ['assistant', 'assistant_patrol'];

  const getChartAnnotationCountBySource = (symbol, source) => (
    getChartAnnotations(symbol).filter(annotation => matchesAnnotationSource(annotation, source)).length
  );

  setChartAnnotations = (symbol, nextAnnotations) => {
    const key = getChartAnnotationStateKey(symbol);
    chartAnnotations[key] = nextAnnotations;
    const selectedId = chartSelectedAnnotationIds[key];
    if (selectedId && !nextAnnotations.some(annotation => annotation?.id === selectedId)) {
      delete chartSelectedAnnotationIds[key];
    }
  };

  setSelectedChartAnnotationId = (symbol, nextAnnotationId) => {
    const key = getChartAnnotationStateKey(symbol);
    if (typeof nextAnnotationId === 'string' && nextAnnotationId.trim()) {
      chartSelectedAnnotationIds[key] = nextAnnotationId.trim();
      return;
    }
    delete chartSelectedAnnotationIds[key];
  };

  clearSelectedChartAnnotation = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) {
      return false;
    }
    const currentSelectedId = getSelectedChartAnnotationId(normalizedSymbol);
    if (!currentSelectedId) {
      return false;
    }
    setSelectedChartAnnotationId(normalizedSymbol, '');
    ctx.scheduleChartViewportAxisRefresh(normalizedSymbol, { immediate: true });
    return true;
  };

  setChartAnnotationDraft = (symbol, nextDraft) => {
    const key = getChartAnnotationStateKey(symbol);
    if (nextDraft) {
      chartAnnotationDrafts[key] = nextDraft;
      return;
    }

    delete chartAnnotationDrafts[key];
  };

  updateChartAnnotation = (symbol, annotationId, updater) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol || !annotationId || typeof updater !== 'function') {
      return false;
    }

    const annotations = getChartAnnotations(normalizedSymbol);
    if (!Array.isArray(annotations) || annotations.length === 0) {
      return false;
    }

    let changed = false;
    const nextAnnotations = annotations.map((annotation) => {
      if (!annotation || annotation.id !== annotationId) {
        return annotation;
      }
      const nextAnnotation = updater(annotation);
      if (!nextAnnotation || nextAnnotation === annotation) {
        return annotation;
      }
      changed = true;
      return {
        ...annotation,
        ...nextAnnotation,
        id: annotation.id,
        type: annotation.type,
      };
    });

    if (!changed) {
      return false;
    }

    setChartAnnotations(normalizedSymbol, nextAnnotations);
    return true;
  };

  scheduleAnnotationOnlyChartUpdate = (symbol, options = {}) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) {
      return;
    }

    const immediate = options.immediate === true;
    const existingTimerId = chartAnnotationUpdateFrames.get(normalizedSymbol);
    if (existingTimerId) {
      window.clearTimeout(existingTimerId);
      chartAnnotationUpdateFrames.delete(normalizedSymbol);
    }

    const run = () => {
      chartAnnotationUpdateFrames.delete(normalizedSymbol);
      if (chartInstances[normalizedSymbol] && candlesData[normalizedSymbol]?.length) {
        ctx.updateChart(normalizedSymbol, { annotationOnly: true });
      } else {
        ctx.scheduleChartViewportAxisRefresh(normalizedSymbol, { immediate: true });
      }
    };

    if (immediate) {
      run();
      return;
    }

    const timerId = window.setTimeout(run, CHART_ANNOTATION_UPDATE_FRAME_MS);
    chartAnnotationUpdateFrames.set(normalizedSymbol, timerId);
  };

  exportChartAnnotationsForPersistence = () => {
    const exported = {};

    Object.entries(chartAnnotations).forEach(([key, annotations]) => {
      if (!Array.isArray(annotations) || annotations.length === 0) {
        return;
      }

      exported[key] = annotations
        .map((annotation) => {
          if (!annotation || typeof annotation !== 'object') {
            return null;
          }

          const normalizedType = typeof annotation.type === 'string' ? annotation.type.trim() : '';
          if (!['trendline', 'horizontal', 'rectangle', 'ruler'].includes(normalizedType)) {
            return null;
          }

          const base = {
            id: typeof annotation.id === 'string' && annotation.id.trim()
              ? annotation.id.trim()
              : createChartAnnotationId(),
            type: normalizedType,
            meta: annotation.meta && typeof annotation.meta === 'object'
              ? { ...annotation.meta }
              : {},
          };

          if (normalizedType === 'horizontal') {
            const price = toFiniteNumber(annotation.price, Number.NaN);
            return Number.isFinite(price)
              ? { ...base, price }
              : null;
          }

          const startTs = toFiniteNumber(annotation.startTs, Number.NaN);
          const endTs = toFiniteNumber(annotation.endTs, Number.NaN);
          const startPrice = toFiniteNumber(annotation.startPrice, Number.NaN);
          const endPrice = toFiniteNumber(annotation.endPrice, Number.NaN);
          if (
            !Number.isFinite(startTs)
            || !Number.isFinite(endTs)
            || !Number.isFinite(startPrice)
            || !Number.isFinite(endPrice)
          ) {
            return null;
          }

          return {
            ...base,
            startTs,
            endTs,
            startPrice,
            endPrice,
          };
        })
        .filter(Boolean);
    });

    return exported;
  };

  hydrateChartAnnotationsFromPersistence = (payload) => {
    Object.keys(chartAnnotations).forEach((key) => {
      delete chartAnnotations[key];
    });
    Object.keys(chartSelectedAnnotationIds).forEach((key) => {
      delete chartSelectedAnnotationIds[key];
    });
    Object.keys(chartAnnotationDrafts).forEach((key) => {
      delete chartAnnotationDrafts[key];
    });

    if (!payload || typeof payload !== 'object') {
      return;
    }

    Object.entries(payload).forEach(([key, annotations]) => {
      if (!Array.isArray(annotations) || annotations.length === 0) {
        return;
      }

      const normalizedAnnotations = annotations
        .map((annotation) => {
          if (!annotation || typeof annotation !== 'object') {
            return null;
          }

          const normalizedType = typeof annotation.type === 'string' ? annotation.type.trim() : '';
          if (!['trendline', 'horizontal', 'rectangle', 'ruler'].includes(normalizedType)) {
            return null;
          }

          const id = typeof annotation.id === 'string' && annotation.id.trim()
            ? annotation.id.trim()
            : createChartAnnotationId();

          if (normalizedType === 'horizontal') {
            const price = toFiniteNumber(annotation.price, Number.NaN);
            return Number.isFinite(price)
              ? {
                  id,
                  type: normalizedType,
                  price,
                  meta: annotation.meta && typeof annotation.meta === 'object'
                    ? { ...annotation.meta }
                    : {},
                }
              : null;
          }

          const startTs = toFiniteNumber(annotation.startTs, Number.NaN);
          const endTs = toFiniteNumber(annotation.endTs, Number.NaN);
          const startPrice = toFiniteNumber(annotation.startPrice, Number.NaN);
          const endPrice = toFiniteNumber(annotation.endPrice, Number.NaN);
          if (
            !Number.isFinite(startTs)
            || !Number.isFinite(endTs)
            || !Number.isFinite(startPrice)
            || !Number.isFinite(endPrice)
          ) {
            return null;
          }

          return {
            id,
            type: normalizedType,
            startTs,
            endTs,
            startPrice,
            endPrice,
            meta: annotation.meta && typeof annotation.meta === 'object'
              ? { ...annotation.meta }
              : {},
          };
        })
        .filter(Boolean);

      if (normalizedAnnotations.length > 0) {
        chartAnnotations[key] = normalizedAnnotations;
      }
    });
  };

  scheduleChartAnnotationRefresh = (symbol) => {
    if (!symbol || chartAnnotationRefreshTimers.has(symbol)) {
      return;
    }

    const timerId = window.setTimeout(() => {
      chartAnnotationRefreshTimers.delete(symbol);
      ctx.renderChartDraftPreview(symbol);
    }, CHART_ANNOTATION_REFRESH_DELAY);
    chartAnnotationRefreshTimers.set(symbol, timerId);
  };

  clearChartAnnotationFrame = (symbol) => {
    const timerId = chartAnnotationRefreshTimers.get(symbol);
    if (timerId) {
      window.clearTimeout(timerId);
      chartAnnotationRefreshTimers.delete(symbol);
    }
  };

  clearChartAnnotationUpdateFrame = (symbol) => {
    const timerId = chartAnnotationUpdateFrames.get(symbol);
    if (!timerId) {
      return;
    }
    window.clearTimeout(timerId);
    chartAnnotationUpdateFrames.delete(symbol);
  };

  clearChartViewportAxisRefresh = (symbol) => {
    const timerId = chartViewportAxisRefreshTimers.get(symbol);
    if (timerId) {
      window.clearTimeout(timerId);
      chartViewportAxisRefreshTimers.delete(symbol);
    }
  };

  clearChartViewportActionFrame = (symbol) => {
    const frameState = chartViewportActionFrames.get(symbol);
    if (frameState?.type === 'raf' && typeof window.cancelAnimationFrame === 'function') {
      window.cancelAnimationFrame(frameState.id);
    } else if (frameState?.type === 'timeout') {
      window.clearTimeout(frameState.id);
    }
    chartViewportActionFrames.delete(symbol);
    chartPendingViewportActions.delete(symbol);
  };

  clearChartDraftPreview = (symbol) => {
    chartDraftPreviewSignatures.delete(symbol);
    const chart = chartInstances[symbol];
    if (!chart) {
      return;
    }

    ctx.renderChartDraftPreview(symbol);
  };

  clearChartGraphicOverlays = (symbol) => {
    chartDraftPreviewSignatures.delete(symbol);
    const chart = chartInstances[symbol];
    if (!chart) {
      return;
    }

    ctx.applyChartSetOption(symbol, chart, {
      graphic: [],
    }, {
      lazyUpdate: true,
      silent: true,
      replaceMerge: ['graphic'],
    }, 'graphic');
  };

  clearChartAnnotations = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) return;

    setChartAnnotations(normalizedSymbol, []);
    setChartAnnotationDraft(normalizedSymbol, null);
    setSelectedChartAnnotationId(normalizedSymbol, '');
    clearChartAnnotationFrame(normalizedSymbol);
    clearChartAnnotationUpdateFrame(normalizedSymbol);
    clearChartDraftPreview(normalizedSymbol);
    // 同步清理 LWC AnnotationManager
    const lwcManager = ctx.lwcManagers?.get(normalizedSymbol);
    if (lwcManager?.annotations) {
      lwcManager.annotations.clear();
    }
    if (chartInstances[normalizedSymbol]) {
      ctx.updateChart(normalizedSymbol, { annotationOnly: true });
    }
  };

  clearChartAnnotationsBySource = (symbol, source = AI_ANNOTATION_SOURCES) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) {
      return 0;
    }
    const annotations = getChartAnnotations(normalizedSymbol);
    if (!Array.isArray(annotations) || annotations.length === 0) {
      return 0;
    }
    const nextAnnotations = annotations.filter(annotation => !matchesAnnotationSource(annotation, source));
    const removedCount = annotations.length - nextAnnotations.length;
    if (removedCount <= 0) {
      return 0;
    }
    setChartAnnotations(normalizedSymbol, nextAnnotations);
    // 同步清理 LWC AnnotationManager 中对应 source 的标注
    const lwcManager = ctx.lwcManagers?.get(normalizedSymbol);
    if (lwcManager?.annotations) {
      const sources = Array.isArray(source) ? source : [source];
      lwcManager.annotations.clearBySource(sources);
    }
    clearChartAnnotationFrame(normalizedSymbol);
    clearChartAnnotationUpdateFrame(normalizedSymbol);
    clearChartDraftPreview(normalizedSymbol);
    if (chartInstances[normalizedSymbol] && candlesData[normalizedSymbol]?.length) {
      ctx.updateChart(normalizedSymbol, { annotationOnly: true });
    } else {
      ctx.scheduleChartViewportAxisRefresh(normalizedSymbol, { immediate: true });
    }
    return removedCount;
  };

  removeLastChartAnnotation = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) return false;

    const annotations = getChartAnnotations(normalizedSymbol);
    if (!Array.isArray(annotations) || annotations.length === 0) {
      return false;
    }

    const removedAnnotation = annotations[annotations.length - 1];
    setChartAnnotations(normalizedSymbol, annotations.slice(0, -1));
    clearChartAnnotationFrame(normalizedSymbol);
    clearChartAnnotationUpdateFrame(normalizedSymbol);
    clearChartDraftPreview(normalizedSymbol);
    if (removedAnnotation?.id && getSelectedChartAnnotationId(normalizedSymbol) === removedAnnotation.id) {
      setSelectedChartAnnotationId(normalizedSymbol, '');
    }
    // LWC 桥接
    if (removedAnnotation?.id) {
      const lwcManager = ctx.lwcManagers?.get(normalizedSymbol);
      lwcManager?.annotations?.remove(removedAnnotation.id);
    }
    if (chartInstances[normalizedSymbol] && candlesData[normalizedSymbol]?.length) {
      ctx.updateChart(normalizedSymbol, { annotationOnly: true });
    }
    return true;
  };

  removeSelectedChartAnnotation = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) {
      return false;
    }

    const selectedId = getSelectedChartAnnotationId(normalizedSymbol);
    if (!selectedId) {
      return false;
    }

    const annotations = getChartAnnotations(normalizedSymbol);
    if (!Array.isArray(annotations) || annotations.length === 0) {
      setSelectedChartAnnotationId(normalizedSymbol, '');
      return false;
    }

    const nextAnnotations = annotations.filter(annotation => annotation?.id !== selectedId);
    if (nextAnnotations.length === annotations.length) {
      setSelectedChartAnnotationId(normalizedSymbol, '');
      return false;
    }

    setChartAnnotations(normalizedSymbol, nextAnnotations);
    setSelectedChartAnnotationId(normalizedSymbol, '');
    clearChartAnnotationFrame(normalizedSymbol);
    clearChartAnnotationUpdateFrame(normalizedSymbol);
    clearChartDraftPreview(normalizedSymbol);
    // LWC 桥接
    const lwcManager = ctx.lwcManagers?.get(normalizedSymbol);
    lwcManager?.annotations?.remove(selectedId);
    if (chartInstances[normalizedSymbol] && candlesData[normalizedSymbol]?.length) {
      ctx.updateChart(normalizedSymbol, { annotationOnly: true });
    } else {
      ctx.scheduleChartViewportAxisRefresh(normalizedSymbol, { immediate: true });
    }
    return true;
  };

  cancelChartAnnotationDraft = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) return;

    if (!getChartAnnotationDraft(normalizedSymbol)) {
      return;
    }

    setChartAnnotationDraft(normalizedSymbol, null);
    clearChartAnnotationFrame(normalizedSymbol);
    clearChartDraftPreview(normalizedSymbol);
  };


  return {
    getChartAnnotationStateKey,
    getChartAnnotations,
    getSelectedChartAnnotationId,
    getSelectedChartAnnotation,
    getChartAnnotationDraft,
    getChartAnnotationCount,
    getChartAnnotationCountBySource,
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
    clearChartDraftPreview,
    clearChartGraphicOverlays,
    clearChartAnnotations,
    clearChartAnnotationsBySource,
    removeLastChartAnnotation,
    removeSelectedChartAnnotation,
    cancelChartAnnotationDraft,
  };
}
