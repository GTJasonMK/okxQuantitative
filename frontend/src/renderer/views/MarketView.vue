<template>
  <div class="market-view">
    <div v-if="connectionError" class="market-banner market-banner-danger">
      <div class="market-banner-content">
        <span class="error-badge">!</span>
        <span>{{ connectionError }}</span>
      </div>
      <button class="btn-link" @click="checkConnection">重新连接</button>
    </div>
    <MarketWorkspaceShell />
  </div>
</template>
<script setup>
import { ref, reactive, shallowReactive, shallowRef, computed, nextTick, watch, onUnmounted, provide } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { api, waitForBackend } from '../services/api';
import marketWS from '../services/websocket';
import { useAppStore } from '../stores/app';
import MarketWorkspaceShell from '../components/market/MarketWorkspaceShell.vue';
import { MARKET_VIEW_CONTEXT } from '../components/market/marketViewContext';
import { useMarketViewRealtime } from '../composables/market/useMarketViewRealtime';
import { useMarketViewCharting } from '../composables/market/useMarketViewCharting';
import { useMarketViewOrderBook } from '../composables/market/useMarketViewOrderBook';
import { useMarketViewAssistant } from '../composables/market/useMarketViewAssistant';
import { useMarketViewSync } from '../composables/market/useMarketViewSync';
import { useSymbolDataHealth } from '../composables/useSymbolDataHealth';
import { throttle, binarySearchCandleIndex } from '../utils/async';
import { normalizeMonitorSymbol, normalizeSymbolList } from '../utils/formatting';
// 定义组件名称，用于 keep-alive 缓存
defineOptions({
  name: 'MarketView'
})
const route = useRoute();
const router = useRouter();
const appStore = useAppStore();
// ========== 持久化存储（通过后端 API） ==========
const PREFERENCES_KEY = 'market_settings';
const ORDERBOOK_DEPTH_MIN = 1;
const ORDERBOOK_DEPTH_MAX = 500;
const marketTypeOptions = [
  { value: 'SPOT', label: '现货' },
  { value: 'SWAP', label: '永续合约' },
];
const syncModeOptions = [
  { value: 'incremental', label: '增量更新', hint: '只补本地最新缺口' },
  { value: 'window', label: '最近窗口', hint: '补最近 N 天历史' },
  { value: 'full', label: '全量回补', hint: '一直回补到最早可获取历史' },
];
// 保存设置到后端
const saveSettings = async () => {
  try {
    const settings = {
      selectedSymbols: selectedSymbols.value,
      activeSymbol: activeSymbol.value,
      marketInstType: marketInstType.value,
      displayRangeDays: displayRangeDays.value,
      autoRefresh: autoRefresh.value,
      refreshInterval: refreshInterval.value,
      syncMode: syncMode.value,
      syncDays: syncDays.value,
      inspectorFocusMode: inspectorFocusMode.value,
      orderBookDepthLimit: orderBookDepthLimit.value,
      indicators: { ...indicators },
      chartAnnotations: exportChartAnnotationsForPersistence(),
    };
    await api.updatePreferences({ [PREFERENCES_KEY]: settings });
  } catch (e) {
    console.warn('保存行情监控设置失败:', e);
  }
};
// 防抖保存（避免频繁调用 API）
let saveTimer = null;
const debouncedSave = () => {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    saveSettings();
  }, 500);
};
const availableSymbols = ref([]);   // 仅来自关注币种列表
const selectedSymbols = ref([]);    // 当前打开的 tab
const activeSymbol = ref('');       // 当前激活的 tab
const holdingSymbols = ref([]);     // 持仓币种（只做标记，不自动加入监控）
const holdingsBase = ref([]);       // 轻量持仓明细（用于右侧终端面板）
const marketInstType = ref('SPOT'); // 当前显示价格类型
const autoRefresh = ref(true);
const refreshInterval = ref(5);
const pendingOrdersData = shallowReactive({});
const contractPositionsData = shallowReactive({});
const resolveMarketInstId = (symbol, instType = marketInstType.value) => {
  const normalized = normalizeMonitorSymbol(symbol);
  if (!normalized) return '';
  if (instType === 'SWAP') {
    return `${normalized}-SWAP`;
  }
  return normalized;
};
// 技术指标设置
const indicators = reactive({
  ma5: true,
  ma10: true,
  ma20: false,
  ma60: false,
  ema12: false,
  ema26: false,
  boll: false,
  vma5: true,
  vma10: true,
  vma20: false,
  sar: false,
});
// 买卖标记设置
const showTradeMarkers = ref(true);
const fillsData = shallowReactive({});  // { 'BTC-USDT': [...fills] } - 使用 shallowReactive 减少开销
// 行情监控页：持仓与成交记录统一使用“实盘”，避免模拟盘虚拟资产干扰
const tradingMode = ref('live');
// 设置是否已加载
const settingsLoaded = ref(false);
// 从后端加载设置
const loadSettings = async () => {
  try {
    const res = await api.getPreferences();
    if (res.success && res.data && res.data[PREFERENCES_KEY]) {
      const saved = res.data[PREFERENCES_KEY];
      if (saved.selectedSymbols) selectedSymbols.value = normalizeSymbolList(saved.selectedSymbols);
      if (saved.activeSymbol) activeSymbol.value = normalizeMonitorSymbol(saved.activeSymbol);
      if (saved.marketInstType && marketTypeOptions.some(type => type.value === saved.marketInstType)) {
        marketInstType.value = saved.marketInstType;
      }
      if (saved.displayRangeDays !== undefined) {
        displayRangeDays.value = clampDisplayRangeDays(saved.displayRangeDays);
      }
      if (saved.autoRefresh !== undefined) autoRefresh.value = saved.autoRefresh;
      if (saved.refreshInterval !== undefined) refreshInterval.value = saved.refreshInterval;
      if (saved.syncMode && syncModeOptions.some(option => option.value === saved.syncMode)) {
        syncMode.value = saved.syncMode;
      }
      if (saved.syncDays !== undefined) {
        const nextDays = Number(saved.syncDays);
        if (Number.isFinite(nextDays)) {
          syncDays.value = Math.min(Math.max(Math.round(nextDays), 1), SYNC_DAYS_HARD_MAX);
        }
      }
      if (saved.inspectorFocusMode !== undefined) {
        inspectorFocusMode.value = Boolean(saved.inspectorFocusMode);
      }
      if (saved.orderBookDepthLimit !== undefined) {
        orderBookDepthLimit.value = clampOrderBookDepthLimit(saved.orderBookDepthLimit);
      }
      clampSyncDays();
      if (saved.indicators) {
        Object.assign(indicators, saved.indicators);
      }
      hydrateChartAnnotationsFromPersistence(saved.chartAnnotations || {});
    }
  } catch (e) {
    // 加载失败时使用默认值
  } finally {
    settingsLoaded.value = true;
  }
};
const ensureActiveSymbol = (preferredSymbol = '') => {
  const normalizedPreferred = normalizeMonitorSymbol(preferredSymbol);
  if (normalizedPreferred && selectedSymbols.value.includes(normalizedPreferred)) {
    activeSymbol.value = normalizedPreferred;
    return;
  }
  if (activeSymbol.value && selectedSymbols.value.includes(activeSymbol.value)) {
    return;
  }
  activeSymbol.value = selectedSymbols.value[0] || '';
};
const getSymbolBaseCurrency = (symbol) => {
  const normalized = normalizeMonitorSymbol(symbol);
  if (!normalized) return '';
  return normalized.split('-')[0] || normalized;
};
// 加载账户持仓币种
const loadHoldingSymbols = async () => {
  try {
    const res = await api.getHoldingsBase(tradingMode.value);
    const nextHoldings = Array.isArray(res?.holdings) ? res.holdings : [];
    holdingsBase.value = nextHoldings;
    if (nextHoldings.length > 0) {
      // 轻量持仓基础接口返回字段: ccy, total, available, frozen, avg_cost, is_stablecoin
      const symbols = nextHoldings
        .filter(h => !h.is_stablecoin && parseFloat(h.total || '0') > 0)
        .map(h => `${h.ccy}-USDT`);
      // 更新持仓币种引用（用于锁定保护）
      holdingSymbols.value = normalizeSymbolList(symbols);
      return holdingSymbols.value;
    }
  } catch (e) {
    // 加载持仓失败时返回空数组
  }
  holdingsBase.value = [];
  holdingSymbols.value = [];
  return [];
};
// 是否已同步过成交记录
let fillsSynced = false;
// 从交易所同步成交记录到本地
const syncFillsFromExchange = async () => {
  if (marketInstType.value !== 'SPOT') return;
  if (fillsSynced) return;
  try {
    await api.syncFillsToLocal(tradingMode.value);
    fillsSynced = true;
  } catch (e) {
    // 同步失败不影响主流程
  }
};
// 加载单个币种的成交记录
const loadFillsForSymbol = async (symbol) => {
  if (marketInstType.value !== 'SPOT') {
    fillsData[symbol] = [];
    return;
  }
  const instId = resolveMarketInstId(symbol);
  try {
    let res = await api.getLocalFills(tradingMode.value, '', instId, 500);
    // 本地无记录时，先同步再重新加载
    if ((!res.fills || res.fills.length === 0) && !fillsSynced) {
      await syncFillsFromExchange();
      res = await api.getLocalFills(tradingMode.value, '', instId, 500);
    }
    if (res.fills) {
      fillsData[symbol] = res.fills;
    }
  } catch (e) {
    fillsData[symbol] = [];
  }
};
// 辅助面板已收敛为盘口视图，执行数据不再在此页拉取，减少额外请求开销。
const loadExecutionPanelData = async () => {};
// 时间周期对应的毫秒数
const TIMEFRAME_MS = {
  '1m': 60 * 1000,
  '3m': 3 * 60 * 1000,
  '5m': 5 * 60 * 1000,
  '15m': 15 * 60 * 1000,
  '30m': 30 * 60 * 1000,
  '1H': 60 * 60 * 1000,
  '2H': 2 * 60 * 60 * 1000,
  '4H': 4 * 60 * 60 * 1000,
  '6H': 6 * 60 * 60 * 1000,
  '12H': 12 * 60 * 60 * 1000,
  '1D': 24 * 60 * 60 * 1000,
  '1W': 7 * 24 * 60 * 60 * 1000,
  '1M': 30 * 24 * 60 * 60 * 1000,
};
const DAY_MS = 24 * 60 * 60 * 1000;
const SYNC_DAYS_HARD_MAX = 365;
const SYNC_SOFT_MAX_CANDLES_PER_SYMBOL = 12000;
const SYNC_DAY_PRESET_VALUES = [1, 3, 7, 14, 30, 60, 90, 180, 365];
const DISPLAY_RANGE_OPTION_VALUES = [1, 3, 7, 14, 30, 90, 180];
const DISPLAY_RANGE_MAX_VISIBLE_CANDLES = 4500;
const DISPLAY_RANGE_WARMUP_CANDLES = 180;
// 时间周期
const currentTimeframe = computed({
  get: () => appStore.currentTimeframe,
  set: (val) => appStore.setCurrentTimeframe(val)
});
const timeframes = [
  { value: '1m', label: '1分' },
  { value: '5m', label: '5分' },
  { value: '15m', label: '15分' },
  { value: '1H', label: '1时' },
  { value: '4H', label: '4时' },
  { value: '1D', label: '1天' },
];
const getTimeframeLabel = (timeframe) => (
  timeframes.find(item => item.value === timeframe)?.label || timeframe || '--'
);
const displayRangeDays = ref(7);
const estimateDisplayRangeCandles = (days, timeframe = currentTimeframe.value) => {
  const normalizedDays = Math.max(1, Math.round(Number(days) || 1));
  const timeframeMs = TIMEFRAME_MS[timeframe] || DAY_MS;
  return Math.max(1, Math.ceil((normalizedDays * DAY_MS) / timeframeMs));
};
const estimateSyncCandles = (days, timeframe = currentTimeframe.value) => {
  const normalizedDays = Math.max(1, Math.round(Number(days) || 1));
  const timeframeMs = TIMEFRAME_MS[timeframe] || DAY_MS;
  return Math.max(100, Math.ceil((normalizedDays * DAY_MS) / timeframeMs));
};
const resolveSyncDaysMax = (timeframe = currentTimeframe.value, mode = syncMode.value) => {
  if (mode === 'full') {
    return SYNC_DAYS_HARD_MAX;
  }

  const matched = SYNC_DAY_PRESET_VALUES.filter(days => (
    days <= SYNC_DAYS_HARD_MAX
    && estimateSyncCandles(days, timeframe) <= SYNC_SOFT_MAX_CANDLES_PER_SYMBOL
  ));
  return matched.length > 0 ? matched[matched.length - 1] : 1;
};
const displayRangeOptions = computed(() => {
  const options = DISPLAY_RANGE_OPTION_VALUES
    .filter(days => estimateDisplayRangeCandles(days) <= DISPLAY_RANGE_MAX_VISIBLE_CANDLES)
    .map(days => ({
      value: days,
      label: `${days}天`,
    }));

  return options.length > 0 ? options : [{ value: 1, label: '1天' }];
});
const clampDisplayRangeDays = (days) => {
  const options = displayRangeOptions.value.map(option => option.value);
  if (options.length === 0) {
    return 1;
  }

  const normalized = Math.max(1, Math.round(Number(days) || options[0]));
  const matched = [...options].reverse().find(option => option <= normalized);
  return matched || options[0];
};
const currentDisplayRangeLabel = computed(() => `近${displayRangeDays.value}天`);
const maxTrackedCandles = computed(() => {
  const visibleCandles = estimateDisplayRangeCandles(displayRangeDays.value);
  return Math.min(
    visibleCandles + DISPLAY_RANGE_WARMUP_CANDLES,
    DISPLAY_RANGE_MAX_VISIBLE_CANDLES + DISPLAY_RANGE_WARMUP_CANDLES
  );
});
const recentTradesScrollRef = ref(null);
const recentTradesTrackRef = ref(null);
const recentTradesPrimaryListRef = ref(null);
const recentTradesAutoScrollPaused = ref(false);
const recentTradesLooping = ref(false);
const inspectorAnchorRef = ref(null);
const chartInspectorPanelRef = ref(null);
const depthInspectorScrollRef = ref(null);
const depthChartCanvasRef = ref(null);
const inspectorFloatingStyle = shallowRef({});
const syncJobsList = computed(() => (
  Object.values(syncJobs).sort((left, right) => (
    (right.created_at || '').localeCompare(left.created_at || '')
  ))
));
const activeSyncJobs = computed(() => (
  syncJobsList.value.filter(job => ['queued', 'running'].includes(job.status))
));
const syncDaysMax = computed(() => resolveSyncDaysMax(currentTimeframe.value, syncMode.value));
const clampSyncDays = () => {
  const normalized = Number(syncDays.value);
  if (!Number.isFinite(normalized)) {
    syncDays.value = Math.min(30, syncDaysMax.value);
    return;
  }
  syncDays.value = Math.min(Math.max(Math.round(normalized), 1), syncDaysMax.value);
};
const getRequestErrorMessage = (error, fallback = '请求失败') => (
  error?.response?.data?.detail
  || error?.message
  || fallback
);
// 加载状态
const loading = ref(false);
const syncMode = ref('incremental');
const syncDays = ref(30);
const syncJobs = shallowReactive({});
const chartLoading = reactive({});
const chartErrors = reactive({});
// 连接状态
const connectionError = ref(null);
const wsConnected = ref(false);
const analysisToolOptions = [
  { key: 'none', label: '浏览' },
  { key: 'trendline', label: '趋势线' },
  { key: 'horizontal', label: '水平位' },
  { key: 'rectangle', label: '区间框' },
  { key: 'ruler', label: '测距尺' },
];
const activeAnalysisTool = ref('none');
const marketViewActive = ref(false);
// 均线指标定义
const maIndicators = [
  { key: 'ma5', label: 'MA5', period: 5, color: 'var(--gold-color)' },
  { key: 'ma10', label: 'MA10', period: 10, color: '#2DD4BF' },
  { key: 'ma20', label: 'MA20', period: 20, color: 'var(--color-info)' },
  { key: 'ma60', label: 'MA60', period: 60, color: '#8B5CF6' },
];
const volumeMaIndicators = [
  { key: 'vma5', label: 'VMA5', period: 5, color: 'var(--accent-color)' },
  { key: 'vma10', label: 'VMA10', period: 10, color: 'var(--color-info)' },
  { key: 'vma20', label: 'VMA20', period: 20, color: '#A855F7' },
];
// EMA指标定义
const emaIndicators = [
  { key: 'ema12', label: 'EMA12', period: 12, color: 'var(--color-danger)' },
  { key: 'ema26', label: 'EMA26', period: 26, color: '#14B8A6' },
];
// 各币种数据 - 使用 shallowReactive 减少深层响应式追踪开销
const tickers = {};
const candlesData = shallowReactive({});
const realtimePriceMoves = {};
const recentTradesData = shallowReactive({});
const orderBookData = shallowReactive({});
const inspectorExpanded = ref(false);
const inspectorFocusMode = ref(false);
const orderBookViewMode = ref('depth');
const orderBookGrouping = ref(1);
const orderBookDepthLimit = ref(50);
const orderBookDepthInput = ref('50');
const clampOrderBookDepthLimit = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 50;
  }
  return Math.min(
    ORDERBOOK_DEPTH_MAX,
    Math.max(ORDERBOOK_DEPTH_MIN, Math.round(numeric))
  );
};
const inspectorLayoutPreset = computed(() => {
  if (inspectorFocusMode.value) {
    return {
      width: 1040,
      minWidth: 860,
      preferredHeight: 640,
      minHeight: 520,
      maxHeight: 760,
    };
  }

  if (orderBookViewMode.value === 'depth') {
    return {
      width: 760,
      minWidth: 640,
      preferredHeight: 540,
      minHeight: 440,
      maxHeight: 640,
    };
  }

  return {
    width: 720,
    minWidth: 600,
    preferredHeight: 500,
    minHeight: 420,
    maxHeight: 600,
  };
});
const recentTradesPanelActive = computed(() => false);
const orderBookPanelActive = computed(() => (
  inspectorExpanded.value
));
const DEFAULT_VISIBLE_CANDLES = 120;
const REALTIME_CHART_UPDATE_DELAY = 100;
const RECENT_MARKET_TRADES_LIMIT = 12;
const RECENT_MARKET_TRADES_POLL_INTERVAL = 3000;
const RECENT_TRADES_AUTO_SCROLL_SPEED = 26;
const ORDERBOOK_DEPTH_LIMIT = orderBookDepthLimit;
const ORDERBOOK_POLL_INTERVAL = 2000;
const CHART_TOUCHPAD_PAN_RATIO = 0.12;
const CHART_DRAG_PAN_RATIO = 1;
const MIN_DATA_ZOOM_SPAN_PERCENT = 6;
const headerCollapsed = ref(true);
const chartToolboxExpanded = ref(false);
// 图表实例 - 使用 shallowReactive，图表实例不需要深层响应
const chartRefs = shallowReactive({});
const chartInstances = shallowReactive({});
const candleVersions = shallowReactive({});
const recentTradesLoading = reactive({});
const orderBookLoading = reactive({});
const orderBookError = reactive({});
let chartViewportInteractionStateResolver = () => false;
let chartViewportInteractionRemainingResolver = () => 0;
const {
  getCandleTimestamp,
  clearRealtimeChartUpdate,
  clearAllRealtimeChartUpdates,
  clearRealtimePriceMove,
  clearAllRealtimePriceMoves,
  clearRealtimeTickerEvent,
  clearAllRealtimeTickerEvents,
  clearDisplayPriceMoveState,
  applyRealtimeTickerToCandles,
  applyIncomingTicker,
  showMarketTypeDropdown,
  showTimeframeDropdown,
  showIndicatorDropdown,
  marketTypeDropdown,
  timeframeDropdown,
  indicatorDropdown,
  watchlistSymbols,
  currentMarketTypeLabel,
  activeBaseCurrency,
  currentTimeframeLabel,
  toggleMarketTypeDropdown,
  toggleTimeframeDropdown,
  toggleIndicatorDropdown,
  selectedIndicatorsCount,
  toggleIndicator,
  clearAllIndicators,
  selectTimeframe,
  selectMarketType,
  cleanupSymbolState,
  openSymbolTab,
  closeSymbolTab,
  handleClickOutside,
  setChartRef,
  toFiniteNumber,
  normalizeTickerData,
  clamp,
  activeTicker,
  activeOrderBook,
  stopRecentTradesPolling,
  stopRecentTradesAutoScroll,
  syncRecentTradesAutoScroll,
  startActiveTickerWatchdog,
  stopActiveTickerWatchdog,
  startRecentTradesPolling,
  loadOrderBook,
  stopOrderBookPolling,
  startOrderBookPolling,
  handleWsConnectionChange,
  clearRealtimeTickerSubscriptions,
  syncRealtimeTickerSubscriptions,
  getTickerClass,
  getPriceFlashClass,
  formatPrice,
  formatChange,
  formatPercentValue,
  formatTradeSize,
  flushBufferedTickerForSymbol,
} = useMarketViewRealtime({ api, marketWS, activeSymbol, availableSymbols, selectedSymbols, holdingSymbols, marketInstType, marketTypeOptions, pendingOrdersData, contractPositionsData, timeframes, indicators, fillsData, recentTradesData, recentTradesLoading, orderBookData, orderBookLoading, orderBookError, recentTradesScrollRef, recentTradesTrackRef, recentTradesPrimaryListRef, recentTradesAutoScrollPaused, recentTradesLooping, recentTradesPanelActive, orderBookPanelActive, chartRefs, chartInstances, chartLoading, chartErrors, candlesData, candleVersions, tickers, realtimePriceMoves, TIMEFRAME_MS, currentTimeframe, MAX_VISIBLE_CANDLES: maxTrackedCandles, REALTIME_CHART_UPDATE_DELAY, RECENT_MARKET_TRADES_LIMIT, RECENT_MARKET_TRADES_POLL_INTERVAL, RECENT_TRADES_AUTO_SCROLL_SPEED, ORDERBOOK_DEPTH_LIMIT, ORDERBOOK_POLL_INTERVAL, wsConnected, resolveMarketInstId, normalizeMonitorSymbol, getSymbolBaseCurrency, ensureActiveSymbol, marketViewActive, getRequestErrorMessage, getUpdateChart: () => updateChart, getRefreshAllCharts: () => refreshAllCharts, getRefreshActiveChart: () => refreshActiveChart, getUpdateAllCharts: () => updateAllCharts, getInitChart: () => initChart, getLoadChartData: () => loadChartData, getClearChartViewportState: () => clearChartViewportState, getDisposeChartInstance: () => disposeChartInstance, getStartAutoRefresh: () => startAutoRefresh, getIsChartViewportInteracting: () => chartViewportInteractionStateResolver, getChartViewportInteractionRemainingMs: () => chartViewportInteractionRemainingResolver });
const commandContextLabel = computed(() => (
  `${currentMarketTypeLabel.value} / ${currentTimeframeLabel.value} / ${currentDisplayRangeLabel.value}`
));
const { clearChartViewportState, getChartViewportInteractionRemainingMs: getChartViewportInteractionRemainingMsForSymbol, isChartViewportInteracting: isChartViewportInteractingForSymbol, disposeChartInstance, initChart, getSelectedChartAnnotation, getChartAnnotationDraft, getChartAnnotationCount, getChartAnnotationCountBySource, appendChartAnnotation, clearChartAnnotations, clearChartAnnotationsBySource, removeLastChartAnnotation, removeSelectedChartAnnotation, cancelChartAnnotationDraft, clearSelectedChartAnnotation, hydrateChartAnnotationsFromPersistence, exportChartAnnotationsForPersistence, chartAnnotations, updateChart, loadChartData, updateAllCharts, refreshChart, refreshActiveChart, refreshAllCharts, refreshAllTickers } = useMarketViewCharting({ api, loading, activeSymbol, activeAnalysisTool, selectedSymbols, marketInstType, currentTimeframe, displayRangeDays, maxTrackedCandles, chartRefs, chartInstances, chartLoading, chartErrors, candlesData, tickers, indicators, showTradeMarkers, fillsData, TIMEFRAME_MS, DEFAULT_VISIBLE_CANDLES, MIN_DATA_ZOOM_SPAN_PERCENT, CHART_TOUCHPAD_PAN_RATIO, CHART_DRAG_PAN_RATIO, normalizeMonitorSymbol, resolveMarketInstId, toFiniteNumber, binarySearchCandleIndex, getCandleTimestamp, formatPrice, formatTradeSize, loadFillsForSymbol, loadExecutionPanelData, normalizeTickerData, applyIncomingTicker, applyRealtimeTickerToCandles, clamp, nextTick });
chartViewportInteractionStateResolver = isChartViewportInteractingForSymbol;
chartViewportInteractionRemainingResolver = getChartViewportInteractionRemainingMsForSymbol;
const clearSaveTimer = () => { if (saveTimer) clearTimeout(saveTimer); };
const { startSyncJobsPolling, startAutoRefresh, toggleAutoRefresh, restartAutoRefresh, checkConnection, loadAvailableSymbols } = useMarketViewSync({ api, waitForBackend, marketWS, marketViewActive, activeSyncJobs, settingsLoaded, selectedSymbols, activeSymbol, holdingSymbols, availableSymbols, marketInstType, currentTimeframe, syncMode, syncDays, syncJobs, syncJobsList, chartErrors, chartLoading, loading, autoRefresh, refreshInterval, indicators, wsConnected, connectionError, chartInstances, chartRefs, candlesData, candleVersions, tickers, realtimePriceMoves, recentTradesData, recentTradesLoading, recentTradesPanelActive, orderBookData, orderBookLoading, orderBookError, orderBookPanelActive, fillsData, recentTradesLooping, loadSettings, loadHoldingSymbols, ensureActiveSymbol, loadExecutionPanelData, resolveMarketInstId, normalizeMonitorSymbol, normalizeSymbolList, clampSyncDays, throttle, debouncedSave, clearSaveTimer, loadChartData, refreshActiveChart, refreshAllCharts, refreshAllTickers, initChart, updateChart, cleanupSymbolState, disposeChartInstance, clearChartViewportState, clearRealtimeChartUpdate, clearAllRealtimeChartUpdates, clearRealtimePriceMove, clearAllRealtimePriceMoves, clearRealtimeTickerEvent, clearAllRealtimeTickerEvents, clearDisplayPriceMoveState, applyRealtimeTickerToCandles, startRecentTradesPolling, stopRecentTradesPolling, stopRecentTradesAutoScroll, syncRecentTradesAutoScroll, startActiveTickerWatchdog, stopActiveTickerWatchdog, startOrderBookPolling, stopOrderBookPolling, clearRealtimeTickerSubscriptions, syncRealtimeTickerSubscriptions, handleWsConnectionChange, handleClickOutside, flushBufferedTickerForSymbol });
const toggleHeaderCollapsed = () => {
  headerCollapsed.value = !headerCollapsed.value;
};
const selectDisplayRangeDays = async (days) => {
  const nextRange = clampDisplayRangeDays(days);
  if (nextRange === displayRangeDays.value) {
    return;
  }

  displayRangeDays.value = nextRange;
  if (settingsLoaded.value) {
    debouncedSave();
  }

  clearAllRealtimeChartUpdates();
  clearAllRealtimeTickerEvents();

  selectedSymbols.value.forEach((symbol) => {
    clearChartViewportState(symbol);
    if (symbol !== activeSymbol.value) {
      delete candlesData[symbol];
      delete candleVersions[symbol];
    }
  });

  if (!activeSymbol.value) {
    return;
  }

  await refreshActiveChart();
};
let chartToolboxCloseTimer = null;
let inspectorCloseTimer = null;
let inspectorPositionRaf = 0;
let inspectorViewportListenersBound = false;
const clearChartToolboxCloseTimer = () => {
  if (chartToolboxCloseTimer) {
    clearTimeout(chartToolboxCloseTimer);
    chartToolboxCloseTimer = null;
  }
};
const clearInspectorCloseTimer = () => {
  if (inspectorCloseTimer) {
    clearTimeout(inspectorCloseTimer);
    inspectorCloseTimer = null;
  }
};
const cancelInspectorPositionFrame = () => {
  if (inspectorPositionRaf) {
    cancelAnimationFrame(inspectorPositionRaf);
    inspectorPositionRaf = 0;
  }
};
const updateInspectorFloatingPosition = () => {
  if (typeof window === 'undefined') {
    return;
  }

  const anchor = inspectorAnchorRef.value;
  if (!(anchor instanceof HTMLElement)) {
    return;
  }

  const anchorRect = anchor.getBoundingClientRect();
  const panel = chartInspectorPanelRef.value;
  const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
  const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
  const layoutPreset = inspectorLayoutPreset.value;
  const margin = 12;
  const gap = 8;
  const availableWidth = Math.max(280, viewportWidth - margin * 2);
  const width = Math.max(
    Math.min(layoutPreset.minWidth, availableWidth),
    Math.min(layoutPreset.width, availableWidth),
  );
  const measuredHeight = panel instanceof HTMLElement ? panel.scrollHeight : 0;
  const bottomSpace = viewportHeight - anchorRect.bottom - gap - margin;
  const topSpace = anchorRect.top - gap - margin;
  const preferredHeight = layoutPreset.preferredHeight;
  const preferAbove = bottomSpace < preferredHeight && topSpace > bottomSpace;
  const availableHeight = Math.max(260, preferAbove ? topSpace : bottomSpace);
  const maxHeight = Math.min(layoutPreset.maxHeight, availableHeight);
  const resolvedHeight = measuredHeight > 0
    ? Math.min(measuredHeight, maxHeight)
    : Math.min(preferredHeight, maxHeight);
  const centeredLeft = Math.round((viewportWidth - width) / 2);
  const anchorAlignedLeft = Math.round(anchorRect.left);
  const left = Math.max(
    margin,
    Math.min(
      viewportWidth - width - margin,
      Math.max(anchorAlignedLeft, centeredLeft),
    ),
  );
  const top = preferAbove
    ? Math.max(margin, anchorRect.top - gap - resolvedHeight)
    : Math.max(margin, anchorRect.bottom + gap);

  inspectorFloatingStyle.value = {
    position: 'fixed',
    top: `${Math.round(top)}px`,
    left: `${Math.round(left)}px`,
    right: 'auto',
    width: `${Math.round(width)}px`,
    maxWidth: `${Math.round(availableWidth)}px`,
    maxHeight: `${Math.round(maxHeight)}px`,
    zIndex: 2000,
  };
};
const scheduleInspectorFloatingPosition = () => {
  if (typeof window === 'undefined') {
    return;
  }
  cancelInspectorPositionFrame();
  inspectorPositionRaf = requestAnimationFrame(() => {
    inspectorPositionRaf = 0;
    updateInspectorFloatingPosition();
  });
};
const handleInspectorViewportChange = () => {
  if (!inspectorExpanded.value) {
    return;
  }
  scheduleInspectorFloatingPosition();
};
const bindInspectorViewportListeners = () => {
  if (typeof window === 'undefined' || inspectorViewportListenersBound) {
    return;
  }
  inspectorViewportListenersBound = true;
  window.addEventListener('resize', handleInspectorViewportChange);
  window.addEventListener('scroll', handleInspectorViewportChange, true);
};
const unbindInspectorViewportListeners = () => {
  if (typeof window === 'undefined' || !inspectorViewportListenersBound) {
    return;
  }
  inspectorViewportListenersBound = false;
  window.removeEventListener('resize', handleInspectorViewportChange);
  window.removeEventListener('scroll', handleInspectorViewportChange, true);
};
const toggleChartToolboxExpanded = () => {
  clearChartToolboxCloseTimer();
  setChartToolboxExpanded(!chartToolboxExpanded.value);
};
const setChartToolboxExpanded = (nextExpanded) => {
  const normalizedNextExpanded = Boolean(nextExpanded);
  if (chartToolboxExpanded.value === normalizedNextExpanded) {
    return;
  }
  chartToolboxExpanded.value = normalizedNextExpanded;
};
const handleChartToolboxPointerEnter = () => {
  clearChartToolboxCloseTimer();
  setChartToolboxExpanded(true);
};
const handleChartToolboxPointerLeave = () => {
  clearChartToolboxCloseTimer();
  chartToolboxCloseTimer = setTimeout(() => {
    chartToolboxCloseTimer = null;
    setChartToolboxExpanded(false);
  }, 220);
};
const setInspectorExpanded = (nextExpanded) => {
  const normalizedNextExpanded = Boolean(nextExpanded);
  if (inspectorExpanded.value === normalizedNextExpanded) {
    return;
  }
  inspectorExpanded.value = normalizedNextExpanded;
  if (!normalizedNextExpanded) {
    unbindInspectorViewportListeners();
    cancelInspectorPositionFrame();
    return;
  }
  bindInspectorViewportListeners();
  nextTick(() => {
    updateInspectorFloatingPosition();
    scheduleInspectorFloatingPosition();
  });
};
const toggleInspectorExpanded = () => {
  clearInspectorCloseTimer();
  setInspectorExpanded(!inspectorExpanded.value);
};
const toggleInspectorFocusMode = () => {
  inspectorFocusMode.value = !inspectorFocusMode.value;
  if (settingsLoaded.value) {
    debouncedSave();
  }
  if (inspectorExpanded.value) {
    nextTick(() => {
      updateInspectorFloatingPosition();
      scheduleInspectorFloatingPosition();
    });
  }
};
const handleInspectorPointerEnter = () => {
  clearInspectorCloseTimer();
  if (inspectorExpanded.value) {
    scheduleInspectorFloatingPosition();
  }
  setInspectorExpanded(true);
};
const handleInspectorPointerLeave = () => {
  clearInspectorCloseTimer();
  inspectorCloseTimer = setTimeout(() => {
    inspectorCloseTimer = null;
    setInspectorExpanded(false);
  }, 220);
};
const watchlistSelectPlaceholder = computed(() => (
  watchlistSymbols.value.length > 0 ? '选择关注币种' : '暂无关注币种'
));
const selectWatchlistSymbol = (symbol) => {
  const normalizedSymbol = normalizeMonitorSymbol(symbol);
  if (!normalizedSymbol) {
    return;
  }
  openSymbolTab(normalizedSymbol);
};
const getWatchlistOptionLabel = (symbol) => {
  const normalizedSymbol = normalizeMonitorSymbol(symbol);
  if (!normalizedSymbol) {
    return symbol || '--';
  }
  if (activeSymbol.value === normalizedSymbol) {
    return `${normalizedSymbol} · 当前`;
  }
  if (selectedSymbols.value.includes(normalizedSymbol)) {
    return `${normalizedSymbol} · 已打开`;
  }
  return normalizedSymbol;
};
const currentAnalysisToolLabel = computed(() => (
  analysisToolOptions.find(tool => tool.key === activeAnalysisTool.value)?.label || '浏览'
));
const activeChartLoading = computed(() => (
  activeSymbol.value ? Boolean(chartLoading[activeSymbol.value]) : false
));
const activeChartError = computed(() => (
  activeSymbol.value ? chartErrors[activeSymbol.value] || '' : ''
));
const activeAnnotationCount = computed(() => (
  activeSymbol.value ? getChartAnnotationCount(activeSymbol.value) : 0
));
const activeAssistantAnnotationCount = computed(() => (
  activeSymbol.value ? getChartAnnotationCountBySource(activeSymbol.value, ['assistant', 'assistant_patrol']) : 0
));
const activeAnnotationDraft = computed(() => (
  activeSymbol.value ? getChartAnnotationDraft(activeSymbol.value) : null
));
const activeSelectedAnnotation = computed(() => (
  activeSymbol.value ? getSelectedChartAnnotation(activeSymbol.value) : null
));
const activeSelectedAnnotationLabel = computed(() => {
  const selectedAnnotation = activeSelectedAnnotation.value;
  if (!selectedAnnotation) {
    return '';
  }

  const typeLabels = {
    trendline: '趋势线',
    horizontal: '水平位',
    rectangle: '区间框',
    ruler: '测距尺',
  };
  return typeLabels[selectedAnnotation.type] || '标注';
});
const chartToolboxHint = computed(() => {
  if (activeAnnotationDraft.value) {
    return '等待第二个落点，Esc 退出，右键撤销最后一次操作。';
  }
  if (activeSelectedAnnotation.value) {
    return `已选中${activeSelectedAnnotationLabel.value}，可直接拖拽控制点，Delete 删除，Esc 取消选中。`;
  }
  if (activeAnalysisTool.value !== 'none') {
    return '已进入绘图模式，Delete 可撤销最后一条标注。';
  }
  return '选择工具后直接在图表上落点绘制，避免额外按钮堆叠。';
});
const selectAnalysisTool = (toolKey) => {
  if (activeAnalysisTool.value === toolKey) {
    activeAnalysisTool.value = 'none';
    cancelChartAnnotationDraft(activeSymbol.value);
    return;
  }

  activeAnalysisTool.value = toolKey;
  cancelChartAnnotationDraft(activeSymbol.value);
  clearSelectedChartAnnotation(activeSymbol.value);
};
const {
  depthChartHover,
  orderBookViewTabs,
  orderBookGroupingOptions,
  orderBookDepthOptions,
  applyOrderBookDepthLimit,
  commitCustomOrderBookDepthLimit,
  customOrderBookDepthActive,
  activeOrderBookAssetLabel,
  activeOrderBookPrecisionLabel,
  activeOrderBookGroupingLabel,
  activeOrderBookSpreadLabel,
  activeOrderBookSpreadPercentLabel,
  activeOrderBookLevelCount,
  activeOrderBookLadderRows,
  activeOrderBookDepthChart,
  activePrimaryBidWall,
  activePrimaryAskWall,
  getOrderBookLevelSizeRatio,
  isOrderBookWall,
  handleDepthPanelWheel,
  handleDepthChartPointerMove,
  hideDepthChartHover,
  currentInspectorTabLabel,
  currentInspectorTriggerMeta,
} = useMarketViewOrderBook({
  ORDERBOOK_DEPTH_MIN,
  ORDERBOOK_DEPTH_MAX,
  activeSymbol,
  activeOrderBook,
  activeBaseCurrency,
  activeTicker,
  orderBookGrouping,
  orderBookDepthLimit,
  orderBookDepthInput,
  orderBookViewMode,
  orderBookPanelActive,
  settingsLoaded,
  debouncedSave,
  loadOrderBook,
  startOrderBookPolling,
  formatPrice,
  formatTradeSize,
  formatPercentValue,
  normalizeMonitorSymbol,
  depthInspectorScrollRef,
  chartInspectorPanelRef,
  depthChartCanvasRef,
  clampOrderBookDepthLimit,
});
const currentInspectorTriggerMetaDisplay = computed(() => (
  inspectorFocusMode.value
    ? `专注 / ${activeOrderBookLevelCount.value} 档`
    : currentInspectorTriggerMeta.value
));
const {
  healthRow: activeSymbolHealthRow,
  healthLoading: activeSymbolHealthLoading,
  healthError: activeSymbolHealthError,
  healthStatus: activeSymbolHealthStatus,
  healthStatusLabel: activeSymbolHealthStatusLabel,
  healthScore: activeSymbolHealthScore,
  healthBadgeText: activeSymbolHealthBadgeText,
  healthSummaryText: activeSymbolHealthSummaryText,
  selectedMarketHealth: activeSymbolMarketHealth,
  selectedMissingTimeframes: activeSymbolMissingTimeframes,
  loadHealth: loadActiveSymbolHealth,
} = useSymbolDataHealth({
  symbolRef: activeSymbol,
  instTypeRef: marketInstType,
});
const {
  assistantAnchorRef,
  assistantPanelRef,
  assistantMessagesRef,
  assistantInputRef,
  assistantFloatingStyle,
  assistantExpanded,
  assistantProgressVisible,
  assistantBusy,
  assistantInput,
  assistantError,
  assistantStatus,
  assistantStatusLoaded,
  assistantPatrolStatusLoaded,
  assistantPatrolBusy,
  assistantPatrolConfig,
  assistantPatrolStatus,
  assistantPatrolSummary,
  assistantPatrolMeta,
  assistantPatrolEvents,
  assistantPatrolRuns,
  assistantPatrolRunsLoaded,
  assistantPatrolRunsLoading,
  assistantPanelTab,
  assistantPanelTabs,
  activeAssistantMessages,
  activeAssistantTimelineEntries,
  activeAssistantSteps,
  assistantProgressSteps,
  quickPromptOptions,
  assistantTriggerMeta,
  assistantContextSummary,
  assistantInputPlaceholder,
  assistantCanSend,
  assistantVisibleSessions,
  assistantVisibleLevelSnapshots,
  assistantVisibleOrderDrafts,
  assistantLevelSnapshotsLoaded,
  assistantLevelSnapshotsLoading,
  assistantOrderDraftsLoaded,
  assistantOrderDraftsLoading,
  assistantSnapshotBusy,
  assistantToolCatalog,
  assistantToolCount,
  assistantCurrentSessionTitle,
  assistantSessionStatusText,
  assistantLatestStepTitle,
  assistantSessionListLoading,
  assistantDetailLoading,
  syncAssistantInputHeight,
  applyAssistantStepChartAnnotations,
  applyAssistantPatrolCandidate,
  syncAssistantPatrolCandidateTimeframe,
  applyAssistantLevelSnapshot,
  applyAssistantOrderDraft,
  loadAssistantPatrolRuns,
  loadAssistantLevelSnapshots,
  loadAssistantOrderDrafts,
  saveAssistantLevelSnapshot,
  toggleAssistantExpanded,
  setAssistantPanelTab,
  setAssistantPatrolEnabled,
  activateAssistantSession,
  clearAssistantConversation,
  stopAssistantResponse,
  runAssistantPatrolNow,
  submitAssistantMessage,
  formatAssistantTimestamp,
} = useMarketViewAssistant({
  marketWS,
  activeSymbol,
  marketInstType,
  currentTimeframe,
  displayRangeDays,
  indicators,
  activeTicker,
  activeOrderBook,
  activeSyncJobs,
  candlesData,
  activeSymbolHealthRow,
  activeSymbolMarketHealth,
  activeSymbolHealthStatus,
  activeSymbolHealthSummaryText,
  appendChartAnnotation,
  updateChart,
  openSymbolTab,
  normalizeMonitorSymbol,
  formatPrice,
  formatChange,
});
const commandControlsMemoKey = computed(() => (
  [
    marketInstType.value,
    currentTimeframe.value,
    displayRangeDays.value,
    wsConnected.value ? '1' : '0',
    showMarketTypeDropdown.value ? '1' : '0',
    showTimeframeDropdown.value ? '1' : '0',
    showIndicatorDropdown.value ? '1' : '0',
    selectedIndicatorsCount.value,
    autoRefresh.value ? '1' : '0',
    refreshInterval.value,
  ].join('|')
));
// 向拆分后的子组件提供行情工作区上下文，避免继续把模板和逻辑堆回单文件。
provide(MARKET_VIEW_CONTEXT, {
  ORDERBOOK_DEPTH_MIN,
  ORDERBOOK_DEPTH_MAX,
  activeAssistantMessages,
  activeAssistantTimelineEntries,
  activeSymbol,
  activeSymbolHealthBadgeText,
  activeSymbolHealthError,
  activeSymbolHealthLoading,
  activeSymbolHealthRow,
  activeSymbolHealthScore,
  activeSymbolHealthStatus,
  activeSymbolHealthStatusLabel,
  activeSymbolHealthSummaryText,
  activeSymbolMarketHealth,
  activeSymbolMissingTimeframes,
  activeTicker,
  activeChartLoading,
  activeChartError,
  activeAnalysisTool,
  activeAnnotationCount,
  activeAssistantAnnotationCount,
  activeAnnotationDraft,
  activeOrderBookAssetLabel,
  activeOrderBookDepthChart,
  activeOrderBookGroupingLabel,
  activeOrderBookLadderRows,
  activeOrderBookLevelCount,
  activeOrderBookPrecisionLabel,
  activeOrderBookSpreadLabel,
  activeOrderBookSpreadPercentLabel,
  activePrimaryAskWall,
  activePrimaryBidWall,
  activeSelectedAnnotation,
  analysisToolOptions,
  applyOrderBookDepthLimit,
  applyAssistantOrderDraft,
  applyAssistantLevelSnapshot,
  applyAssistantPatrolCandidate,
  syncAssistantPatrolCandidateTimeframe,
  applyAssistantStepChartAnnotations,
  assistantAnchorRef,
  assistantBusy,
  assistantCanSend,
  assistantContextSummary,
  assistantCurrentSessionTitle,
  assistantDetailLoading,
  assistantError,
  assistantExpanded,
  assistantPatrolBusy,
  assistantPatrolConfig,
  assistantPatrolEvents,
  assistantPatrolMeta,
  assistantPatrolRuns,
  assistantPatrolRunsLoaded,
  assistantPatrolRunsLoading,
  assistantPatrolStatus,
  assistantPatrolStatusLoaded,
  assistantPatrolSummary,
  assistantProgressVisible,
  assistantFloatingStyle,
  assistantInput,
  assistantInputRef,
  assistantInputPlaceholder,
  assistantLevelSnapshotsLoaded,
  assistantLevelSnapshotsLoading,
  assistantOrderDraftsLoaded,
  assistantOrderDraftsLoading,
  assistantLatestStepTitle,
  assistantMessagesRef,
  assistantPanelRef,
  assistantPanelTab,
  assistantPanelTabs,
  assistantSnapshotBusy,
  assistantSessionListLoading,
  assistantSessionStatusText,
  assistantStatus,
  assistantStatusLoaded,
  assistantTriggerMeta,
  assistantToolCatalog,
  assistantToolCount,
  assistantVisibleLevelSnapshots,
  assistantVisibleOrderDrafts,
  assistantVisibleSessions,
  activeAssistantSteps,
  assistantProgressSteps,
  activateAssistantSession,
  autoRefresh,
  formatAssistantTimestamp,
  cancelChartAnnotationDraft,
  chartInspectorPanelRef,
  chartToolboxExpanded,
  chartToolboxHint,
  clearAllIndicators,
  clearAssistantConversation,
  clearChartAnnotations,
  clearChartAnnotationsBySource,
  clearSelectedChartAnnotation,
  closeSymbolTab,
  commandContextLabel,
  commandControlsMemoKey,
  commitCustomOrderBookDepthLimit,
  currentAnalysisToolLabel,
  currentInspectorTabLabel,
  currentInspectorTriggerMeta: currentInspectorTriggerMetaDisplay,
  currentMarketTypeLabel,
  currentTimeframe,
  currentTimeframeLabel,
  customOrderBookDepthActive,
  depthChartCanvasRef,
  depthChartHover,
  depthInspectorScrollRef,
  displayRangeDays,
  displayRangeOptions,
  emaIndicators,
  formatChange,
  formatPercentValue,
  formatPrice,
  formatTradeSize,
  getOrderBookLevelSizeRatio,
  getPriceFlashClass,
  getTickerClass,
  getWatchlistOptionLabel,
  handleChartToolboxPointerEnter,
  handleChartToolboxPointerLeave,
  handleDepthChartPointerMove,
  handleDepthPanelWheel,
  handleInspectorPointerEnter,
  handleInspectorPointerLeave,
  headerCollapsed,
  hideDepthChartHover,
  indicators,
  indicatorDropdown,
  inspectorAnchorRef,
  inspectorExpanded,
  inspectorFocusMode,
  inspectorFloatingStyle,
  isOrderBookWall,
  maIndicators,
  marketInstType,
  marketTypeDropdown,
  marketTypeOptions,
  orderBookDepthInput,
  orderBookDepthLimit,
  orderBookDepthOptions,
  orderBookError,
  orderBookGrouping,
  orderBookGroupingOptions,
  orderBookLoading,
  orderBookViewMode,
  orderBookViewTabs,
  loadAssistantLevelSnapshots,
  loadAssistantOrderDrafts,
  loadAssistantPatrolRuns,
  loadActiveSymbolHealth,
  quickPromptOptions,
  runAssistantPatrolNow,
  saveAssistantLevelSnapshot,
  refreshChart,
  refreshInterval,
  removeLastChartAnnotation,
  removeSelectedChartAnnotation,
  restartAutoRefresh,
  selectAnalysisTool,
  selectDisplayRangeDays,
  selectedIndicatorsCount,
  selectMarketType,
  selectTimeframe,
  selectWatchlistSymbol,
  setAssistantPatrolEnabled,
  setChartRef,
  setAssistantPanelTab,
  showIndicatorDropdown,
  showMarketTypeDropdown,
  showTimeframeDropdown,
  syncAssistantInputHeight,
  stopAssistantResponse,
  submitAssistantMessage,
  timeframes,
  timeframeDropdown,
  toggleAutoRefresh,
  toggleAssistantExpanded,
  toggleChartToolboxExpanded,
  toggleHeaderCollapsed,
  toggleIndicator,
  toggleIndicatorDropdown,
  toggleInspectorFocusMode,
  toggleInspectorExpanded,
  toggleMarketTypeDropdown,
  toggleTimeframeDropdown,
  volumeMaIndicators,
  watchlistSelectPlaceholder,
  watchlistSymbols,
  wsConnected,
});
const consumeRouteRequestedSymbol = async () => {
  const requestedSymbol = normalizeMonitorSymbol(route.query.symbol);
  if (!requestedSymbol || !availableSymbols.value.includes(requestedSymbol)) {
    return;
  }

  openSymbolTab(requestedSymbol);

  if (route.query.symbol) {
    const nextQuery = { ...route.query };
    delete nextQuery.symbol;
    try {
      await router.replace({ query: nextQuery });
    } catch (error) {
      console.warn('清理行情路由参数失败:', error);
    }
  }
};
watch(currentTimeframe, () => {
  const nextRange = clampDisplayRangeDays(displayRangeDays.value);
  if (nextRange !== displayRangeDays.value) {
    displayRangeDays.value = nextRange;
    if (settingsLoaded.value) {
      debouncedSave();
    }
    if (activeSymbol.value) {
      clearChartViewportState(activeSymbol.value);
      void refreshActiveChart();
    }
  }
});
watch(chartAnnotations, () => {
  if (settingsLoaded.value) {
    debouncedSave();
  }
}, { deep: true });
watch(
  [inspectorExpanded, orderBookViewMode, activeSymbol, headerCollapsed, inspectorFocusMode],
  ([expanded]) => {
    if (!expanded) {
      return;
    }
    nextTick(() => {
      updateInspectorFloatingPosition();
      scheduleInspectorFloatingPosition();
    });
  },
  { flush: 'post' },
);
watch(activeSymbol, (symbol, previousSymbol) => {
  hideDepthChartHover();
  if (previousSymbol && previousSymbol !== symbol) {
    cancelChartAnnotationDraft(previousSymbol);
  }
});
watch(
  [() => route.query.symbol, availableSymbols],
  () => {
    if (!route.query.symbol) {
      return;
    }
    void consumeRouteRequestedSymbol();
  },
  { immediate: true },
);
onUnmounted(() => {
  clearChartToolboxCloseTimer();
  clearInspectorCloseTimer();
  unbindInspectorViewportListeners();
  cancelInspectorPositionFrame();
});
</script>
<style scoped src="../assets/styles/views/market-view-layout.css"></style>
