import { shallowReactive } from 'vue';
import * as echarts from 'echarts';

import { createMarketViewChartViewport } from './charting/viewport';
import { createMarketViewChartAnnotationState } from './charting/annotations-state';
import { createMarketViewChartAnnotationGeometry } from './charting/annotations-geometry';
import { createMarketViewChartRuntime } from './charting/runtime';
import { createMarketViewChartIndicators } from './charting/indicators';
import { createMarketViewChartAnnotationRender } from './charting/annotations-render';
import { createMarketViewChartRenderingSupport } from './charting/rendering-support';
import { createMarketViewChartRendering } from './charting/rendering';

export function useMarketViewCharting(deps) {
  const chartViewportStates = {};
  const chartWheelInteractionHandlers = new Map();
  const chartDragInteractionHandlers = new Map();
  const chartAnnotationInteractionHandlers = new Map();
  const chartAnnotationRefreshTimers = new Map();
  const chartViewportAxisRefreshTimers = new Map();
  const chartViewportActionFrames = new Map();
  const chartPendingViewportActions = new Map();
  const chartViewportInteractionTimers = new Map();
  const chartViewportInteractionUntil = new Map();
  const chartViewportInteractionFlags = shallowReactive({});
  const chartViewportInteractionLightweightSymbols = new Set();
  const chartDeferredSetOptionFrames = new Map();
  const chartDeferredSetOptionPayloads = new Map();
  const chartDeferredResizeFrames = new Map();
  const chartDeferredResizePayloads = new Map();
  const chartDeferredHideTipFrames = new Map();
  const chartResizeObservers = new Map();
  const chartResizeObserverSizes = new Map();
  const chartRawResizeFns = new WeakMap();
  const chartDraftPreviewSignatures = new Map();
  const chartAnnotations = shallowReactive({});
  const chartSelectedAnnotationIds = shallowReactive({});
  const chartAnnotationDrafts = shallowReactive({});
  const chartAnnotationUpdateFrames = new Map();
  const chartAnnotationEditSessions = new Map();
  const chartAnnotationSuppressClickUntil = new Map();
  const chartRenderCaches = {};
  const CHART_ANNOTATION_REFRESH_DELAY = 72;
  const CHART_ANNOTATION_UPDATE_FRAME_MS = 16;
  const CHART_REALTIME_ANIMATION_DURATION = 180;
  const CHART_REALTIME_AXIS_ANIMATION_DURATION = 140;
  const CHART_REALTIME_ANIMATION_EASING = 'cubicOut';
  const CHART_VIEWPORT_ACTION_FRAME_MS = 16;
  const CHART_VIEWPORT_AXIS_REFRESH_DELAY = 48;
  const CHART_VIEWPORT_AXIS_INTERACTION_REFRESH_DELAY = 88;
  const CHART_VIEWPORT_INTERACTION_IDLE_MS = 120;
  const CHART_LATEST_CANDLE_VIEW_RATIO = 0.5;
  const ENABLE_CHART_VIEWPORT_LIGHTWEIGHT_MODE = true;
  const DAY_MS = 24 * 60 * 60 * 1000;
  const RANGE_FETCH_BATCH_LIMIT = 1000;
  const RANGE_FETCH_WARMUP_CANDLES = 180;
  const RANGE_FETCH_MIN_CANDLES = 120;

  const ctx = {
    ...deps,
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
  };

  Object.assign(ctx, createMarketViewChartViewport(ctx));
  Object.assign(ctx, createMarketViewChartAnnotationState(ctx));
  Object.assign(ctx, createMarketViewChartAnnotationGeometry(ctx));
  Object.assign(ctx, createMarketViewChartRuntime(ctx));
  Object.assign(ctx, createMarketViewChartIndicators(ctx));
  Object.assign(ctx, createMarketViewChartAnnotationRender(ctx));
  Object.assign(ctx, createMarketViewChartRenderingSupport(ctx));
  Object.assign(ctx, createMarketViewChartRendering(ctx));

  return {
    chartViewportStates: ctx.chartViewportStates,
    getChartViewportStateKey: ctx.getChartViewportStateKey,
    buildDefaultChartViewportState: ctx.buildDefaultChartViewportState,
    getChartViewportState: ctx.getChartViewportState,
    setChartViewportState: ctx.setChartViewportState,
    clearChartViewportState: ctx.clearChartViewportState,
    getChartViewportInteractionRemainingMs: ctx.getChartViewportInteractionRemainingMs,
    isChartViewportInteracting: ctx.isChartViewportInteracting,
    getChartAnnotationStateKey: ctx.getChartAnnotationStateKey,
    getChartAnnotations: ctx.getChartAnnotations,
    getSelectedChartAnnotation: ctx.getSelectedChartAnnotation,
    getChartAnnotationDraft: ctx.getChartAnnotationDraft,
    getChartAnnotationCount: ctx.getChartAnnotationCount,
    getChartAnnotationCountBySource: ctx.getChartAnnotationCountBySource,
    appendChartAnnotation: ctx.appendChartAnnotation,
    clearChartAnnotations: ctx.clearChartAnnotations,
    clearChartAnnotationsBySource: ctx.clearChartAnnotationsBySource,
    removeLastChartAnnotation: ctx.removeLastChartAnnotation,
    removeSelectedChartAnnotation: ctx.removeSelectedChartAnnotation,
    cancelChartAnnotationDraft: ctx.cancelChartAnnotationDraft,
    clearSelectedChartAnnotation: ctx.clearSelectedChartAnnotation,
    hydrateChartAnnotationsFromPersistence: ctx.hydrateChartAnnotationsFromPersistence,
    exportChartAnnotationsForPersistence: ctx.exportChartAnnotationsForPersistence,
    getChartDataZoomWindow: ctx.getChartDataZoomWindow,
    removeChartWheelInteraction: ctx.removeChartWheelInteraction,
    removeChartDragInteraction: ctx.removeChartDragInteraction,
    removeChartAnnotationInteraction: ctx.removeChartAnnotationInteraction,
    disposeChartInstance: ctx.disposeChartInstance,
    panChartViewportByWheel: ctx.panChartViewportByWheel,
    zoomChartViewportByWheel: ctx.zoomChartViewportByWheel,
    bindChartWheelInteraction: ctx.bindChartWheelInteraction,
    bindChartDragInteraction: ctx.bindChartDragInteraction,
    bindChartAnnotationInteraction: ctx.bindChartAnnotationInteraction,
    initChart: ctx.initChart,
    calculateSAR: ctx.calculateSAR,
    chartAnnotations: ctx.chartAnnotations,
    chartSelectedAnnotationIds: ctx.chartSelectedAnnotationIds,
    updateChart: ctx.updateChart,
    loadChartData: ctx.loadChartData,
    updateAllCharts: ctx.updateAllCharts,
    refreshChart: ctx.refreshChart,
    refreshActiveChart: ctx.refreshActiveChart,
    refreshAllCharts: ctx.refreshAllCharts,
    refreshAllTickers: ctx.refreshAllTickers,
  };
}
