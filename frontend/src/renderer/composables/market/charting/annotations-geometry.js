import { HorizontalLinePrimitive, TrendLinePrimitive, RectanglePrimitive, RulerPrimitive } from './lwc-annotations';

export function createMarketViewChartAnnotationGeometry(ctx) {
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

  createChartAnnotationId = () => (
    `annotation-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  );

  ANNOTATION_HANDLE_HIT_RADIUS = 12;
  ANNOTATION_BODY_HIT_RADIUS = 8;
  ANNOTATION_SELECTED_STROKE = '#f2f6fb';
  ANNOTATION_SELECTED_FILL = 'rgba(242, 246, 251, 0.12)';

  findClosestCandleIndexByTimestamp = (candles, targetTimestamp) => {
    if (!Array.isArray(candles) || candles.length === 0 || !Number.isFinite(targetTimestamp)) {
      return -1;
    }

    const firstTimestamp = getCandleTimestamp(candles[0]);
    const lastTimestamp = getCandleTimestamp(candles[candles.length - 1]);
    if (
      !Number.isFinite(firstTimestamp)
      || !Number.isFinite(lastTimestamp)
      || targetTimestamp < firstTimestamp
      || targetTimestamp > lastTimestamp
    ) {
      return -1;
    }

    let closestIndex = 0;
    let closestDelta = Math.abs(firstTimestamp - targetTimestamp);

    for (let index = 1; index < candles.length; index += 1) {
      const timestamp = getCandleTimestamp(candles[index]);
      const delta = Math.abs(timestamp - targetTimestamp);
      if (delta < closestDelta) {
        closestDelta = delta;
        closestIndex = index;
      }
    }

    return closestIndex;
  };

  getChartPrimaryGridRect = (chart) => (
    chart?.getModel?.()?.getComponent?.('grid', 0)?.coordinateSystem?.getRect?.() || null
  );

  convertChartCoordToPixel = (chart, xValue, yValue) => {
    const pixel = chart?.convertToPixel?.({ xAxisIndex: 0, yAxisIndex: 0 }, [xValue, yValue]);
    if (!Array.isArray(pixel) || pixel.length < 2) {
      return null;
    }

    const [x, y] = pixel;
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return null;
    }

    return { x, y };
  };

  getChartRenderLengthForSymbol = (symbol, candles) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    const cache = normalizedSymbol ? chartRenderCaches[normalizedSymbol] : null;
    return Math.max(
      Number.isFinite(cache?.renderLength) ? cache.renderLength : 0,
      Array.isArray(cache?.dates) ? cache.dates.length : 0,
      getChartRenderLength(Array.isArray(candles) ? candles.length : 0),
      Array.isArray(candles) ? candles.length : 0,
      1
    );
  };

  getDistanceToSegment = (point, start, end) => {
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    if (Math.abs(dx) <= Number.EPSILON && Math.abs(dy) <= Number.EPSILON) {
      return Math.hypot(point.x - start.x, point.y - start.y);
    }

    const projection = (
      ((point.x - start.x) * dx + (point.y - start.y) * dy)
      / (dx * dx + dy * dy)
    );
    const clamped = clamp(projection, 0, 1);
    const closestX = start.x + dx * clamped;
    const closestY = start.y + dy * clamped;
    return Math.hypot(point.x - closestX, point.y - closestY);
  };

  isPointInsideRect = (point, rect, padding = 0) => (
    point.x >= rect.x - padding
    && point.x <= rect.x + rect.width + padding
    && point.y >= rect.y - padding
    && point.y <= rect.y + rect.height + padding
  );

  buildAnnotationPixelGeometry = (symbol, chart, annotation) => {
    const candles = candlesData[symbol];
    if (!chart || !Array.isArray(candles) || candles.length === 0 || !annotation) {
      return null;
    }

    if (annotation.type === 'horizontal') {
      const renderLength = getChartRenderLengthForSymbol(symbol, candles);
      const start = convertChartCoordToPixel(chart, 0, annotation.price);
      const end = convertChartCoordToPixel(chart, renderLength - 1, annotation.price);
      if (!start || !end) {
        return null;
      }

      return {
        type: 'horizontal',
        handles: [
          { part: 'line', x: end.x, y: end.y },
        ],
        line: {
          x1: start.x,
          y1: start.y,
          x2: end.x,
          y2: end.y,
        },
      };
    }

    const startIndex = findClosestCandleIndexByTimestamp(candles, annotation.startTs);
    const endIndex = findClosestCandleIndexByTimestamp(candles, annotation.endTs);
    if (startIndex < 0 || endIndex < 0) {
      return null;
    }

    const start = convertChartCoordToPixel(chart, startIndex, annotation.startPrice);
    const end = convertChartCoordToPixel(chart, endIndex, annotation.endPrice);
    if (!start || !end) {
      return null;
    }

    const rect = {
      x: Math.min(start.x, end.x),
      y: Math.min(start.y, end.y),
      width: Math.max(Math.abs(end.x - start.x), 1),
      height: Math.max(Math.abs(end.y - start.y), 1),
    };

    return {
      type: annotation.type,
      start,
      end,
      rect,
      handles: [
        { part: 'start', x: start.x, y: start.y },
        { part: 'end', x: end.x, y: end.y },
      ],
      line: {
        x1: start.x,
        y1: start.y,
        x2: end.x,
        y2: end.y,
      },
    };
  };

  resolveChartAnnotationHit = (symbol, chart, event, options = {}) => {
    const annotations = options.selectedOnly
      ? [getSelectedChartAnnotation(symbol)].filter(Boolean)
      : getChartAnnotations(symbol);
    if (!Array.isArray(annotations) || annotations.length === 0) {
      return null;
    }

    const nativeEvent = event?.event?.event || event?.event || event;
    const dom = chart?.getDom?.();
    const rect = dom?.getBoundingClientRect?.();
    const x = Number(
      event?.zrX
      ?? event?.offsetX
      ?? event?.event?.zrX
      ?? event?.event?.offsetX
      ?? (
        Number.isFinite(nativeEvent?.clientX) && rect
          ? nativeEvent.clientX - rect.left
          : Number.NaN
      )
    );
    const y = Number(
      event?.zrY
      ?? event?.offsetY
      ?? event?.event?.zrY
      ?? event?.event?.offsetY
      ?? (
        Number.isFinite(nativeEvent?.clientY) && rect
          ? nativeEvent.clientY - rect.top
          : Number.NaN
      )
    );

    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      return null;
    }

    const pointer = { x, y };
    let bestHit = null;

    annotations.forEach((annotation) => {
      const geometry = buildAnnotationPixelGeometry(symbol, chart, annotation);
      if (!geometry) {
        return;
      }

      geometry.handles.forEach((handle) => {
        const distance = Math.hypot(pointer.x - handle.x, pointer.y - handle.y);
        if (distance > ANNOTATION_HANDLE_HIT_RADIUS) {
          return;
        }

        if (!bestHit || distance < bestHit.distance || bestHit.hitKind !== 'handle') {
          bestHit = {
            annotationId: annotation.id,
            annotation,
            part: handle.part,
            hitKind: 'handle',
            distance,
          };
        }
      });

      if (geometry.type === 'horizontal') {
        const line = geometry.line;
        const withinX = pointer.x >= Math.min(line.x1, line.x2) - ANNOTATION_BODY_HIT_RADIUS
          && pointer.x <= Math.max(line.x1, line.x2) + ANNOTATION_BODY_HIT_RADIUS;
        const distance = withinX ? Math.abs(pointer.y - line.y1) : Number.POSITIVE_INFINITY;
        if (distance <= ANNOTATION_BODY_HIT_RADIUS && (!bestHit || distance < bestHit.distance)) {
          bestHit = {
            annotationId: annotation.id,
            annotation,
            part: 'line',
            hitKind: 'body',
            distance,
          };
        }
        return;
      }

      if (geometry.type === 'trendline') {
        const distance = getDistanceToSegment(pointer, geometry.start, geometry.end);
        if (distance <= ANNOTATION_BODY_HIT_RADIUS && (!bestHit || distance < bestHit.distance)) {
          bestHit = {
            annotationId: annotation.id,
            annotation,
            part: 'line',
            hitKind: 'body',
            distance,
          };
        }
        return;
      }

      if (geometry.type === 'rectangle' || geometry.type === 'ruler') {
        const inside = isPointInsideRect(pointer, geometry.rect, ANNOTATION_BODY_HIT_RADIUS);
        if (inside && (!bestHit || bestHit.hitKind !== 'handle')) {
          bestHit = {
            annotationId: annotation.id,
            annotation,
            part: 'body',
            hitKind: 'body',
            distance: 0,
          };
          return;
        }

        const edges = [
          [{ x: geometry.rect.x, y: geometry.rect.y }, { x: geometry.rect.x + geometry.rect.width, y: geometry.rect.y }],
          [{ x: geometry.rect.x + geometry.rect.width, y: geometry.rect.y }, { x: geometry.rect.x + geometry.rect.width, y: geometry.rect.y + geometry.rect.height }],
          [{ x: geometry.rect.x + geometry.rect.width, y: geometry.rect.y + geometry.rect.height }, { x: geometry.rect.x, y: geometry.rect.y + geometry.rect.height }],
          [{ x: geometry.rect.x, y: geometry.rect.y + geometry.rect.height }, { x: geometry.rect.x, y: geometry.rect.y }],
        ];
        const edgeDistance = Math.min(...edges.map(([start, end]) => getDistanceToSegment(pointer, start, end)));
        if (edgeDistance <= ANNOTATION_BODY_HIT_RADIUS && (!bestHit || edgeDistance < bestHit.distance)) {
          bestHit = {
            annotationId: annotation.id,
            annotation,
            part: 'body',
            hitKind: 'body',
            distance: edgeDistance,
          };
        }
      }
    });

    return bestHit;
  };

  updateChartAnnotationFromPoint = (symbol, annotationId, editPart, point) => (
    updateChartAnnotation(symbol, annotationId, (annotation) => {
      if (annotation.type === 'horizontal') {
        if (editPart !== 'line') {
          return annotation;
        }
        return {
          price: point.price,
        };
      }

      if (editPart === 'start') {
        return {
          startTs: point.candleTimestamp,
          startPrice: point.price,
        };
      }

      if (editPart === 'end') {
        return {
          endTs: point.candleTimestamp,
          endPrice: point.price,
        };
      }

      return annotation;
    })
  );

  clearChartAnnotationEditSession = (symbol) => {
    chartAnnotationEditSessions.delete(symbol);
  };

  beginSelectedChartAnnotationEdit = (symbol, chart, event) => {
    const selectedAnnotation = getSelectedChartAnnotation(symbol);
    if (!selectedAnnotation) {
      return false;
    }

    const hit = resolveChartAnnotationHit(symbol, chart, event, { selectedOnly: true });
    if (!hit || hit.annotationId !== selectedAnnotation.id) {
      return false;
    }

    let editPart = hit.part;
    if (selectedAnnotation.type === 'horizontal') {
      editPart = 'line';
    } else if (!['start', 'end'].includes(editPart)) {
      return false;
    }

    chartAnnotationEditSessions.set(symbol, {
      annotationId: selectedAnnotation.id,
      editPart,
    });
    chartAnnotationSuppressClickUntil.set(symbol, Date.now() + 180);
    return true;
  };

  updateSelectedChartAnnotationEdit = (symbol, chart, event) => {
    const editSession = chartAnnotationEditSessions.get(symbol);
    if (!editSession) {
      return false;
    }

    const point = getChartValueFromPointerEvent(symbol, chart, event);
    if (!point) {
      return true;
    }

    const changed = updateChartAnnotationFromPoint(
      symbol,
      editSession.annotationId,
      editSession.editPart,
      point
    );
    if (changed) {
      scheduleAnnotationOnlyChartUpdate(symbol);
    }
    return true;
  };

  finishSelectedChartAnnotationEdit = (symbol) => {
    if (!chartAnnotationEditSessions.has(symbol)) {
      return false;
    }

    clearChartAnnotationEditSession(symbol);
    chartAnnotationSuppressClickUntil.set(symbol, Date.now() + 180);
    scheduleAnnotationOnlyChartUpdate(symbol, { immediate: true });
    return true;
  };

  getChartValueFromPointerEvent = (symbol, chart, event) => {
    // LWC 实例没有 convertFromPixel/containPixel，标注交互由 lwc-annotations 管理
    if (!chart || typeof chart.convertFromPixel !== 'function') {
      return null;
    }
    const candles = candlesData[symbol];
    if (!chart || !Array.isArray(candles) || candles.length === 0) {
      return null;
    }

    const nativeEvent = event?.event?.event || event?.event || event;
    const dom = chart?.getDom?.();
    const rect = dom?.getBoundingClientRect?.();
    const offsetX = Number(
      event?.zrX
      ?? event?.offsetX
      ?? event?.event?.zrX
      ?? event?.event?.offsetX
      ?? (
        Number.isFinite(nativeEvent?.clientX) && rect
          ? nativeEvent.clientX - rect.left
          : Number.NaN
      )
    );
    const offsetY = Number(
      event?.zrY
      ?? event?.offsetY
      ?? event?.event?.zrY
      ?? event?.event?.offsetY
      ?? (
        Number.isFinite(nativeEvent?.clientY) && rect
          ? nativeEvent.clientY - rect.top
          : Number.NaN
      )
    );
    if (!Number.isFinite(offsetX) || !Number.isFinite(offsetY)) {
      return null;
    }

    const point = [offsetX, offsetY];
    if (!chart.containPixel({ gridIndex: 0 }, point)) {
      return null;
    }

    const coord = chart.convertFromPixel({ xAxisIndex: 0, yAxisIndex: 0 }, point);
    if (!Array.isArray(coord) || coord.length < 2) {
      return null;
    }

    const candleIndex = clamp(Math.round(Number(coord[0])), 0, candles.length - 1);
    const candle = candles[candleIndex];
    const candleTimestamp = getCandleTimestamp(candle);
    const price = toFiniteNumber(coord[1], Number.NaN);

    if (!Number.isFinite(candleTimestamp) || !Number.isFinite(price)) {
      return null;
    }

    return {
      candleIndex,
      candleTimestamp,
      price,
    };
  };

  appendChartAnnotation = (symbol, annotation) => {
    if (!annotation) return;
    setChartAnnotations(symbol, [
      ...getChartAnnotations(symbol),
      annotation,
    ]);
    // 桥接到 LWC AnnotationManager
    const { lwcManagers } = ctx;
    const manager = lwcManagers?.get(symbol);
    if (manager?.annotations) {
      const type = annotation.type;
      const color = annotation.meta?.color || '#F7931A';
      const source = annotation.meta?.source || 'assistant';
      let primitive = null;
      if (type === 'horizontal') {
        primitive = new HorizontalLinePrimitive({
          id: annotation.id, price: annotation.price, color, source,
          label: annotation.meta?.label || '',
        });
      } else if (type === 'trendline') {
        primitive = new TrendLinePrimitive({
          id: annotation.id, color, source,
          p1: { time: Math.floor(annotation.startTs / 1000), price: annotation.startPrice },
          p2: { time: Math.floor(annotation.endTs / 1000), price: annotation.endPrice },
        });
      } else if (type === 'rectangle') {
        primitive = new RectanglePrimitive({
          id: annotation.id, color, source,
          p1: { time: Math.floor(annotation.startTs / 1000), price: annotation.startPrice },
          p2: { time: Math.floor(annotation.endTs / 1000), price: annotation.endPrice },
        });
      } else if (type === 'ruler') {
        primitive = new RulerPrimitive({
          id: annotation.id, color, source,
          p1: { time: Math.floor(annotation.startTs / 1000), price: annotation.startPrice },
          p2: { time: Math.floor(annotation.endTs / 1000), price: annotation.endPrice },
        });
      }
      if (primitive) {
        manager.annotations.add(primitive);
      }
    }
  };

  bindChartAnnotationInteraction = (symbol, chart) => {
    if (typeof ctx.removeChartAnnotationInteraction === 'function') {
      ctx.removeChartAnnotationInteraction(symbol);
    }

    const zr = chart?.getZr?.();
    if (!zr) return;

    const finalizeDrawing = (point) => {
      const draft = getChartAnnotationDraft(symbol);
      if (!draft || !point) return;

      appendChartAnnotation(symbol, {
        id: draft.id,
        type: draft.type,
        startTs: draft.startTs,
        endTs: point.candleTimestamp,
        startPrice: draft.startPrice,
        endPrice: point.price,
      });
      setChartAnnotationDraft(symbol, null);
      setSelectedChartAnnotationId(symbol, draft.id);
      clearChartAnnotationFrame(symbol);
      clearChartDraftPreview(symbol);
      ctx.updateChart(symbol, { annotationOnly: true });
    };

    const handleClick = (event) => {
      const tool = activeAnalysisTool?.value || 'none';
      const suppressUntil = Number(chartAnnotationSuppressClickUntil.get(symbol) || 0);
      if (suppressUntil > Date.now()) {
        return;
      }

      if (tool === 'none') {
        const hit = resolveChartAnnotationHit(symbol, chart, event);
        if (hit?.annotationId) {
          setSelectedChartAnnotationId(symbol, hit.annotationId);
        } else {
          setSelectedChartAnnotationId(symbol, '');
        }
        ctx.scheduleChartViewportAxisRefresh(symbol, { immediate: true });
        return;
      }

      const point = getChartValueFromPointerEvent(symbol, chart, event);
      if (!point) return;

      const nativeEvent = event?.event;
      nativeEvent?.preventDefault?.();
      nativeEvent?.stopPropagation?.();
      setSelectedChartAnnotationId(symbol, '');

      if (tool === 'horizontal') {
        clearChartAnnotationFrame(symbol);
        clearChartDraftPreview(symbol);
        const nextAnnotationId = createChartAnnotationId();
        appendChartAnnotation(symbol, {
          id: nextAnnotationId,
          type: 'horizontal',
          price: point.price,
        });
        setSelectedChartAnnotationId(symbol, nextAnnotationId);
        ctx.updateChart(symbol, { annotationOnly: true });
        return;
      }

      const currentDraft = getChartAnnotationDraft(symbol);
      if (!currentDraft || currentDraft.type !== tool) {
        setChartAnnotationDraft(symbol, {
          id: createChartAnnotationId(),
          type: tool,
          startTs: point.candleTimestamp,
          endTs: point.candleTimestamp,
          startPrice: point.price,
          endPrice: point.price,
        });
        ctx.renderChartDraftPreview(symbol);
        return;
      }

      finalizeDrawing(point);
    };

    const handleMouseMove = (event) => {
      const draft = getChartAnnotationDraft(symbol);
      if (!draft || !['trendline', 'rectangle', 'ruler'].includes(draft.type)) {
        return;
      }

      const point = getChartValueFromPointerEvent(symbol, chart, event);
      if (!point) return;

      const priceTolerance = Math.max(Math.abs(toFiniteNumber(draft.endPrice, point.price)) * 0.00008, 1e-6);
      if (
        draft.endTs === point.candleTimestamp
        && Math.abs(toFiniteNumber(draft.endPrice, point.price) - point.price) <= priceTolerance
      ) {
        return;
      }

      setChartAnnotationDraft(symbol, {
        ...draft,
        endTs: point.candleTimestamp,
        endPrice: point.price,
      });
      scheduleChartAnnotationRefresh(symbol);
    };

    const handleContextMenu = (event) => {
      event?.event?.preventDefault?.();
      event?.event?.stopPropagation?.();
      if (getChartAnnotationDraft(symbol)) {
        cancelChartAnnotationDraft(symbol);
        return;
      }

      if (removeSelectedChartAnnotation(symbol)) {
        return;
      }

      removeLastChartAnnotation(symbol);
    };

    const handleKeyDown = (event) => {
      if (activeSymbol?.value !== symbol) {
        return;
      }

      const activeTagName = document.activeElement?.tagName?.toLowerCase?.() || '';
      if (['input', 'textarea', 'select'].includes(activeTagName)) {
        return;
      }

      if (event.key === 'Escape') {
        if (getChartAnnotationDraft(symbol)) {
          event.preventDefault();
          cancelChartAnnotationDraft(symbol);
          return;
        }

        if (clearSelectedChartAnnotation(symbol)) {
          event.preventDefault();
          return;
        }

        if (activeAnalysisTool?.value && activeAnalysisTool.value !== 'none') {
          event.preventDefault();
          activeAnalysisTool.value = 'none';
        }
        return;
      }

      if (event.key === 'Backspace' || event.key === 'Delete') {
        event.preventDefault();
        if (removeSelectedChartAnnotation(symbol)) {
          return;
        }
        if (getChartAnnotations(symbol).length > 0) {
          removeLastChartAnnotation(symbol);
        }
      }
    };

    zr.on('click', handleClick);
    zr.on('mousemove', handleMouseMove);
    zr.on('contextmenu', handleContextMenu);
    document.addEventListener('keydown', handleKeyDown);

    chartAnnotationInteractionHandlers.set(symbol, {
      cleanup: () => {
        zr.off('click', handleClick);
        zr.off('mousemove', handleMouseMove);
        zr.off('contextmenu', handleContextMenu);
        document.removeEventListener('keydown', handleKeyDown);
        clearChartAnnotationEditSession(symbol);
      },
    });
  };

  return {
    createChartAnnotationId,
    ANNOTATION_HANDLE_HIT_RADIUS,
    ANNOTATION_BODY_HIT_RADIUS,
    ANNOTATION_SELECTED_STROKE,
    ANNOTATION_SELECTED_FILL,
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
  };
}
