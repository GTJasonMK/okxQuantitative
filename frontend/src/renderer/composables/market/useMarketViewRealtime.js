import { shallowReactive } from 'vue';

import { createMarketViewRealtimePanels } from './marketViewRealtimePanels';
import {
  clamp,
  getLatestCandle as resolveLatestCandle,
  getTickerMetrics as resolveTickerMetrics,
  normalizeTickerData,
  toFiniteNumber,
} from './marketViewRealtimeUtils';

export function useMarketViewRealtime(deps) {
  const {
    api,
    marketWS,
    activeSymbol,
    availableSymbols,
    selectedSymbols,
    holdingSymbols,
    marketInstType,
    marketTypeOptions,
    pendingOrdersData,
    contractPositionsData,
    timeframes,
    indicators,
    fillsData,
    recentTradesData,
    recentTradesLoading,
    orderBookData,
    orderBookLoading,
    orderBookError,
    recentTradesScrollRef,
    recentTradesTrackRef,
    recentTradesPrimaryListRef,
    recentTradesAutoScrollPaused,
    recentTradesLooping,
    recentTradesPanelActive,
    orderBookPanelActive,
    chartRefs,
    chartInstances,
    chartLoading,
    chartErrors,
    candlesData,
    candleVersions,
    tickers,
    realtimePriceMoves,
    TIMEFRAME_MS,
    currentTimeframe,
    MAX_VISIBLE_CANDLES,
    REALTIME_CHART_UPDATE_DELAY,
    RECENT_MARKET_TRADES_LIMIT,
    RECENT_MARKET_TRADES_POLL_INTERVAL,
    RECENT_TRADES_AUTO_SCROLL_SPEED,
    ORDERBOOK_DEPTH_LIMIT,
    ORDERBOOK_POLL_INTERVAL,
    wsConnected,
    resolveMarketInstId,
    normalizeMonitorSymbol,
    getSymbolBaseCurrency,
    ensureActiveSymbol,
    marketViewActive,
  } = deps;
  const getRequestErrorMessage = typeof deps.getRequestErrorMessage === 'function'
    ? deps.getRequestErrorMessage
    : ((error, fallback = '请求失败') => (
        error?.response?.data?.detail
        || error?.message
        || fallback
      ));
  let recentTradesTimer = null;
  let orderBookTimer = null;
  let recentTradesAutoScrollOffset = 0;
  let bufferedTickerFlushTimer = null;
  let displayTickerFlushTimer = null;
  let displayTickerFlushDueAt = 0;
  let activeTickerWatchdogTimer = null;
  let activeTickerFallbackPendingSymbol = '';
  const wsSubscribedSymbols = new Set();
  const wsSubscribedCandleKeys = new Set();
  const bufferedTickers = new Map();
  const pendingRealtimeCandleTickers = new Map();
  const pendingRealtimeWsCandles = new Map();
  const pendingDisplayTickerSymbols = new Set();
  const realtimeChartUpdateTimers = new Map();
  const realtimeChartUpdateTimestamps = new Map();
  const realtimePriceMoveTimers = new Map();
  const realtimeTickerEventKeys = new Map();
  const realtimeWsTickerArrivalTimestamps = new Map();
  const INACTIVE_TICKER_BATCH_DELAY = 180;
  const DISPLAY_TICKER_BATCH_DELAY = 120;
  const ACTIVE_TICKER_FALLBACK_POLL_MS = 1000;
  const ACTIVE_TICKER_FALLBACK_STALE_MS = 1500;
  const displayTickers = shallowReactive({});
  const displayPriceMoves = shallowReactive({});
  const updateChart = (...args) => deps.getUpdateChart()?.(...args);
  const refreshActiveChart = (...args) => deps.getRefreshActiveChart?.()?.(...args);
  const updateAllCharts = (...args) => deps.getUpdateAllCharts()?.(...args);
  const initChart = (...args) => deps.getInitChart()?.(...args);
  const loadChartData = (...args) => deps.getLoadChartData()?.(...args);
  const clearChartViewportState = (...args) => deps.getClearChartViewportState()?.(...args);
  const disposeChartInstance = (...args) => deps.getDisposeChartInstance()?.(...args);
  const startAutoRefresh = (...args) => deps.getStartAutoRefresh()?.(...args);
  const isChartViewportInteracting = (symbol) => {
    const resolver = deps.getIsChartViewportInteracting?.();
    return typeof resolver === 'function' ? resolver(symbol) === true : false;
  };
  const getChartViewportInteractionRemainingMs = (symbol) => {
    const resolver = deps.getChartViewportInteractionRemainingMs?.();
    if (typeof resolver !== 'function') {
      return 0;
    }

    const remaining = Number(resolver(symbol));
    return Number.isFinite(remaining) && remaining > 0 ? remaining : 0;
  };
  const CHART_INTERACTION_RETRY_DELAY = 48;
  const ACTIVE_SYMBOL_REALTIME_CHART_DELAY = 48;
  const getChartInteractionDelay = (symbol) => {
    const interactionWaitMs = getChartViewportInteractionRemainingMs(symbol);
    if (interactionWaitMs > 0 || isChartViewportInteracting(symbol)) {
      return Math.max(interactionWaitMs, CHART_INTERACTION_RETRY_DELAY);
    }
    return 0;
  };
  const getMaxVisibleCandles = () => {
    const numeric = Number(
      typeof MAX_VISIBLE_CANDLES === 'object' && MAX_VISIBLE_CANDLES !== null
        ? MAX_VISIBLE_CANDLES.value
        : MAX_VISIBLE_CANDLES
    );
    if (!Number.isFinite(numeric) || numeric <= 0) {
      return 300;
    }
    return Math.max(120, Math.round(numeric));
  };
  const getOrderBookDepthLimit = () => {
    const numeric = Number(
      typeof ORDERBOOK_DEPTH_LIMIT === 'object' && ORDERBOOK_DEPTH_LIMIT !== null
        ? ORDERBOOK_DEPTH_LIMIT.value
        : ORDERBOOK_DEPTH_LIMIT
    );
    if (!Number.isFinite(numeric) || numeric <= 0) {
      return 50;
    }
    return Math.max(1, Math.min(500, Math.round(numeric)));
  };
  const normalizeCandleTimeframe = (timeframe) => {
    if (typeof timeframe !== 'string') {
      return '';
    }

    const normalized = timeframe.trim();
    if (!normalized) {
      return '';
    }

    return normalized.startsWith('candle') ? normalized.slice(6) : normalized;
  };
  const buildRealtimeCandleSubscriptionKey = (instId, timeframe) => {
    const normalizedTimeframe = normalizeCandleTimeframe(timeframe);
    return instId && normalizedTimeframe ? `${instId}:${normalizedTimeframe}` : '';
  };
  const hasRealtimeCandleSubscription = (symbol) => {
    const instId = resolveMarketInstId(symbol);
    if (!instId || !marketWS.isConnected) {
      return false;
    }

    const candleKey = buildRealtimeCandleSubscriptionKey(instId, currentTimeframe.value);
    return candleKey ? wsSubscribedCandleKeys.has(candleKey) : false;
  };
  const bumpCandleVersion = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) {
      return;
    }
    candleVersions[normalizedSymbol] = Number(candleVersions[normalizedSymbol] || 0) + 1;
  };

  const getCandleTimestamp = (candle) => {
    const timestamp = Number(candle?.timestamp);
    if (Number.isFinite(timestamp) && timestamp > 0) {
      return timestamp;
    }

    const parsed = Date.parse(candle?.datetime || '');
    return Number.isFinite(parsed) ? parsed : 0;
  };

  const clearScheduledDisplayTickerFlush = () => {
    if (displayTickerFlushTimer) {
      clearTimeout(displayTickerFlushTimer);
      displayTickerFlushTimer = null;
    }
    displayTickerFlushDueAt = 0;
  };

  const getDisplayTickerInteractionDelay = () => 0;

  const syncDisplayTickerState = (symbol) => {
    if (!symbol) {
      return;
    }

    if (tickers[symbol]) {
      if (!hasSameDisplayTicker(displayTickers[symbol], tickers[symbol])) {
        displayTickers[symbol] = tickers[symbol];
      }
    } else {
      delete displayTickers[symbol];
    }

    if (realtimePriceMoves[symbol]) {
      if (!hasSameDisplayPriceMove(displayPriceMoves[symbol], realtimePriceMoves[symbol])) {
        displayPriceMoves[symbol] = realtimePriceMoves[symbol];
      }
    } else {
      delete displayPriceMoves[symbol];
    }
  };

  const clearRealtimeChartUpdate = (symbol) => {
    const timer = realtimeChartUpdateTimers.get(symbol);
    if (timer) {
      clearTimeout(timer);
    }
    realtimeChartUpdateTimers.delete(symbol);
    realtimeChartUpdateTimestamps.delete(symbol);
    pendingRealtimeCandleTickers.delete(symbol);
    pendingRealtimeWsCandles.delete(symbol);
  };

  const clearAllRealtimeChartUpdates = () => {
    [...realtimeChartUpdateTimers.keys()].forEach(clearRealtimeChartUpdate);
  };

  const clearRealtimePriceMove = (symbol) => {
    const timer = realtimePriceMoveTimers.get(symbol);
    if (timer) {
      clearTimeout(timer);
    }
    realtimePriceMoveTimers.delete(symbol);
  };

  const clearAllRealtimePriceMoves = () => {
    [...realtimePriceMoveTimers.keys()].forEach(clearRealtimePriceMove);
  };

  const clearRealtimeTickerEvent = (symbol) => {
    realtimeTickerEventKeys.delete(symbol);
  };

  const clearAllRealtimeTickerEvents = () => {
    realtimeTickerEventKeys.clear();
  };

  const clearDisplayPriceMoveState = (symbol) => {
    if (!symbol) {
      return;
    }
    clearRealtimePriceMove(symbol);
    delete realtimePriceMoves[symbol];
    delete displayPriceMoves[symbol];
  };

  const hasSameDisplayTicker = (currentTicker, nextTicker) => (
    currentTicker === nextTicker || (
      currentTicker
      && nextTicker
      && currentTicker.last === nextTicker.last
      && currentTicker.change_24h === nextTicker.change_24h
      && currentTicker.bid_px === nextTicker.bid_px
      && currentTicker.ask_px === nextTicker.ask_px
      && currentTicker.open_24h === nextTicker.open_24h
      && currentTicker.high_24h === nextTicker.high_24h
      && currentTicker.low_24h === nextTicker.low_24h
      && currentTicker.vol_24h === nextTicker.vol_24h
    )
  );

  const hasSameDisplayPriceMove = (currentMove, nextMove) => (
    currentMove === nextMove || (
      currentMove
      && nextMove
      && currentMove.delta === nextMove.delta
      && currentMove.direction === nextMove.direction
      && currentMove.flashing === nextMove.flashing
    )
  );

  const flushDisplayTickerState = () => {
    clearScheduledDisplayTickerFlush();

    if (pendingDisplayTickerSymbols.size === 0) {
      return;
    }

    let deferredDelay = 0;

    [...pendingDisplayTickerSymbols].forEach(symbol => {
      const interactionDelay = getDisplayTickerInteractionDelay(symbol);
      if (interactionDelay > 0) {
        deferredDelay = Math.max(deferredDelay, interactionDelay);
        return;
      }

      pendingDisplayTickerSymbols.delete(symbol);
      syncDisplayTickerState(symbol);
    });

    if (pendingDisplayTickerSymbols.size > 0) {
      scheduleDisplayTickerFlush(Math.max(deferredDelay, DISPLAY_TICKER_BATCH_DELAY));
    }
  };

  const scheduleDisplayTickerFlush = (delayMs = DISPLAY_TICKER_BATCH_DELAY) => {
    const numericDelay = Number(delayMs);
    const normalizedDelay = Math.max(
      Math.round(Number.isFinite(numericDelay) ? numericDelay : DISPLAY_TICKER_BATCH_DELAY),
      0
    );
    const nextDueAt = Date.now() + normalizedDelay;

    if (displayTickerFlushTimer) {
      if (displayTickerFlushDueAt > 0 && displayTickerFlushDueAt <= nextDueAt + 8) {
        return;
      }
      clearScheduledDisplayTickerFlush();
    }

    displayTickerFlushDueAt = nextDueAt;
    displayTickerFlushTimer = setTimeout(() => {
      displayTickerFlushTimer = null;
      displayTickerFlushDueAt = 0;
      flushDisplayTickerState();
    }, normalizedDelay);
  };

  const queueDisplayTickerState = (symbol, options = {}) => {
    if (!symbol) {
      return;
    }
    pendingDisplayTickerSymbols.add(symbol);
    if (options.immediate) {
      const interactionDelay = getDisplayTickerInteractionDelay(symbol);
      if (interactionDelay > 0) {
        scheduleDisplayTickerFlush(interactionDelay);
        return;
      }
      flushDisplayTickerState();
      return;
    }
    scheduleDisplayTickerFlush();
  };

  const stopBufferedTickerFlush = () => {
    if (bufferedTickerFlushTimer) {
      clearTimeout(bufferedTickerFlushTimer);
      bufferedTickerFlushTimer = null;
    }
  };

  const stopActiveTickerWatchdog = () => {
    if (activeTickerWatchdogTimer) {
      clearInterval(activeTickerWatchdogTimer);
      activeTickerWatchdogTimer = null;
    }
    activeTickerFallbackPendingSymbol = '';
  };

  const refreshActiveTickerFallback = async () => {
    const symbol = activeSymbol.value;
    if (!marketViewActive.value || !symbol) {
      return;
    }

    const instId = resolveMarketInstId(symbol);
    if (!instId) {
      return;
    }

    const lastArrivalAt = Number(realtimeWsTickerArrivalTimestamps.get(symbol) || 0);
    const idleMs = lastArrivalAt > 0 ? Date.now() - lastArrivalAt : Number.POSITIVE_INFINITY;
    if (marketWS.isConnected && idleMs < ACTIVE_TICKER_FALLBACK_STALE_MS) {
      return;
    }

    if (activeTickerFallbackPendingSymbol === symbol) {
      return;
    }

    activeTickerFallbackPendingSymbol = symbol;
    try {
      const response = await api.getTicker(instId, {
        instType: marketInstType.value,
        fresh: true,
      });
      if (response?.code === 0) {
        const normalized = normalizeTickerData(response.data);
        if (normalized) {
          applyIncomingTicker(symbol, normalized);
        }
      }
    } catch (error) {
      // 当前激活币种的兜底补偿失败时静默处理，避免界面持续报错。
    } finally {
      if (activeTickerFallbackPendingSymbol === symbol) {
        activeTickerFallbackPendingSymbol = '';
      }
    }
  };

  const startActiveTickerWatchdog = () => {
    stopActiveTickerWatchdog();
    if (!marketViewActive.value || !activeSymbol.value) {
      return;
    }

    void refreshActiveTickerFallback();
    activeTickerWatchdogTimer = setInterval(() => {
      void refreshActiveTickerFallback();
    }, ACTIVE_TICKER_FALLBACK_POLL_MS);
  };

  const applyIncomingTicker = (symbol, ticker) => {
    const previousTicker = tickers[symbol];
    tickers[symbol] = ticker;
    updateRealtimePriceMove(symbol, previousTicker, ticker);
    if (symbol === activeSymbol.value) {
      pendingDisplayTickerSymbols.delete(symbol);
      syncDisplayTickerState(symbol);
    } else {
      queueDisplayTickerState(symbol);
    }

    if (chartLoading[symbol]) {
      return;
    }

    if (symbol !== activeSymbol.value) {
      return;
    }

    if (!chartInstances[symbol] || !candlesData[symbol]?.length) {
      return;
    }

    pendingRealtimeCandleTickers.set(symbol, ticker);
    scheduleRealtimeChartUpdate(symbol);
  };

  const normalizeRealtimeCandleData = (candle) => {
    const instId = candle?.inst_id || candle?.instId;
    const timeframe = normalizeCandleTimeframe(candle?.timeframe);
    const timestamp = toFiniteNumber(candle?.timestamp ?? candle?.ts, 0);

    if (!instId || !timeframe || timestamp <= 0) {
      return null;
    }

    return {
      inst_id: instId,
      timeframe,
      timestamp,
      datetime: new Date(timestamp).toISOString(),
      open: toFiniteNumber(candle?.open),
      high: toFiniteNumber(candle?.high),
      low: toFiniteNumber(candle?.low),
      close: toFiniteNumber(candle?.close),
      volume: toFiniteNumber(candle?.volume ?? candle?.vol),
      volume_ccy: toFiniteNumber(candle?.volume_ccy ?? candle?.volumeCcy ?? candle?.volCcy),
      volume_quote: toFiniteNumber(candle?.volume_quote ?? candle?.volumeQuote ?? candle?.volCcyQuote),
      confirm: toFiniteNumber(candle?.confirm, 0),
    };
  };

  const applyIncomingRealtimeCandle = (symbol, candle) => {
    if (chartLoading[symbol]) {
      return;
    }

    if (!candlesData[symbol]?.length) {
      return;
    }

    if (symbol !== activeSymbol.value || !chartInstances[symbol]) {
      applyRealtimeCandleToCandles(symbol, candle);
      return;
    }

    pendingRealtimeWsCandles.set(symbol, candle);
    scheduleRealtimeChartUpdate(symbol);
  };

  const flushBufferedTickers = () => {
    stopBufferedTickerFlush();
    if (bufferedTickers.size === 0) {
      return;
    }

    const queuedUpdates = [...bufferedTickers.entries()];
    bufferedTickers.clear();
    queuedUpdates.forEach(([symbol, ticker]) => {
      applyIncomingTicker(symbol, ticker);
    });
  };

  const scheduleBufferedTickerFlush = () => {
    if (bufferedTickerFlushTimer || bufferedTickers.size === 0) {
      return;
    }

    bufferedTickerFlushTimer = setTimeout(() => {
      flushBufferedTickers();
    }, INACTIVE_TICKER_BATCH_DELAY);
  };

  const flushBufferedTickerForSymbol = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol || !bufferedTickers.has(normalizedSymbol)) {
      return false;
    }

    const bufferedTicker = bufferedTickers.get(normalizedSymbol);
    bufferedTickers.delete(normalizedSymbol);
    if (bufferedTickers.size === 0) {
      stopBufferedTickerFlush();
    }
    applyIncomingTicker(normalizedSymbol, bufferedTicker);
    return true;
  };

  const updateRealtimePriceMove = (symbol, previousTicker, nextTicker) => {
    if (symbol !== activeSymbol.value) {
      clearDisplayPriceMoveState(symbol);
      return;
    }

    const previousLast = toFiniteNumber(previousTicker?.last, Number.NaN);
    const nextLast = toFiniteNumber(nextTicker?.last, Number.NaN);

    if (!Number.isFinite(nextLast) || nextLast <= 0) {
      return;
    }

    if (!Number.isFinite(previousLast) || previousLast === nextLast) {
      if (realtimePriceMoves[symbol]) {
        clearDisplayPriceMoveState(symbol);
        syncDisplayTickerState(symbol);
      }
      return;
    }

    const delta = nextLast - previousLast;
    const direction = delta > 0 ? 'up' : 'down';

    realtimePriceMoves[symbol] = {
      delta,
      direction,
      flashing: true,
    };
    syncDisplayTickerState(symbol);

    clearRealtimePriceMove(symbol);
    realtimePriceMoveTimers.set(symbol, setTimeout(() => {
      const currentMove = realtimePriceMoves[symbol];
      if (!currentMove) return;
      realtimePriceMoves[symbol] = {
        ...currentMove,
        flashing: false,
      };
      syncDisplayTickerState(symbol);
      realtimePriceMoveTimers.delete(symbol);
    }, 700));
  };

  const scheduleRealtimeChartUpdate = (symbol) => {
    if (!symbol || activeSymbol.value !== symbol) return;
    if (!chartInstances[symbol] || !candlesData[symbol]?.length) return;

    const runUpdate = () => {
      realtimeChartUpdateTimers.delete(symbol);

      if (!chartInstances[symbol] || !candlesData[symbol]?.length || activeSymbol.value !== symbol) {
        return;
      }

      realtimeChartUpdateTimestamps.set(symbol, Date.now());

      if (activeSymbol.value === symbol && chartInstances[symbol] && candlesData[symbol]?.length) {
        let changed = false;
        let needsChartRefresh = false;

        const pendingCandle = pendingRealtimeWsCandles.get(symbol);
        if (pendingCandle) {
          pendingRealtimeWsCandles.delete(symbol);
          changed = applyRealtimeCandleToCandles(symbol, pendingCandle) || changed;
          needsChartRefresh = changed || needsChartRefresh;
        }

        const pendingTicker = pendingRealtimeCandleTickers.get(symbol);
        if (pendingTicker) {
          pendingRealtimeCandleTickers.delete(symbol);
          if (hasRealtimeCandleSubscription(symbol)) {
            changed = applyRealtimeTickerToCandles(symbol, pendingTicker, {
              volumeMode: 'none',
            }) || changed;
            needsChartRefresh = true;
          } else {
            changed = applyRealtimeTickerToCandles(symbol, pendingTicker) || changed;
            needsChartRefresh = changed || needsChartRefresh;
          }
        }

        if (!changed && !needsChartRefresh) {
          return;
        }
        updateChart(symbol, { realtime: true });
      }
    };

    const now = Date.now();
    const lastRunAt = realtimeChartUpdateTimestamps.get(symbol) || 0;
    const elapsed = now - lastRunAt;
    const minDelay = Math.min(
      Math.max(Number(REALTIME_CHART_UPDATE_DELAY) || 0, 0),
      ACTIVE_SYMBOL_REALTIME_CHART_DELAY
    );
    const waitMs = Math.max(minDelay - elapsed, 0);

    if (
      waitMs <= 0
      && !realtimeChartUpdateTimers.has(symbol)
    ) {
      runUpdate();
      return;
    }

    if (realtimeChartUpdateTimers.has(symbol)) {
      return;
    }

    const timer = setTimeout(runUpdate, Math.max(waitMs, CHART_INTERACTION_RETRY_DELAY));
    realtimeChartUpdateTimers.set(symbol, timer);
  };

  // 用实时 ticker 增量维护最后一根 K 线，跨周期时自动补出新 K 线。
  const applyRealtimeTickerToCandles = (symbol, ticker, options = {}) => {
    const candles = candlesData[symbol];
    const timeframeMs = TIMEFRAME_MS[currentTimeframe.value];

    if (!Array.isArray(candles) || candles.length === 0 || !timeframeMs) {
      return false;
    }

    const lastPrice = toFiniteNumber(ticker?.last, Number.NaN);
    if (!Number.isFinite(lastPrice) || lastPrice <= 0) {
      return false;
    }

    const tickTimestamp = Math.max(toFiniteNumber(ticker?.timestamp, 0), 0) || Date.now();
    const bucketTimestamp = Math.floor(tickTimestamp / timeframeMs) * timeframeMs;
    const lastTradeSize = Math.max(toFiniteNumber(ticker?.last_sz, 0), 0);
    const appendVolume = options.volumeMode !== 'none';
    const eventKey = `${tickTimestamp}:${lastPrice}:${lastTradeSize}`;
    const isNewTickerEvent = realtimeTickerEventKeys.get(symbol) !== eventKey;
    if (isNewTickerEvent) {
      realtimeTickerEventKeys.set(symbol, eventKey);
    }
    const lastIndex = candles.length - 1;
    const lastCandle = candles[lastIndex];
    const lastCandleTimestamp = getCandleTimestamp(lastCandle);

    if (!lastCandleTimestamp) {
      return false;
    }

    const normalizedLastCandle = {
      ...lastCandle,
      timestamp: lastCandleTimestamp,
      datetime: lastCandle?.datetime || new Date(lastCandleTimestamp).toISOString(),
      open: toFiniteNumber(lastCandle?.open, lastPrice),
      high: toFiniteNumber(lastCandle?.high, lastPrice),
      low: toFiniteNumber(lastCandle?.low, lastPrice),
      close: toFiniteNumber(lastCandle?.close, lastPrice),
      volume: toFiniteNumber(lastCandle?.volume, 0),
    };

    if (bucketTimestamp < lastCandleTimestamp) {
      return false;
    }

    if (bucketTimestamp === lastCandleTimestamp) {
      const nextHigh = Math.max(normalizedLastCandle.high, lastPrice);
      const nextLow = Math.min(normalizedLastCandle.low, lastPrice);
      const nextVolume = appendVolume
        ? normalizedLastCandle.volume + (isNewTickerEvent ? lastTradeSize : 0)
        : normalizedLastCandle.volume;
      const changed =
        normalizedLastCandle.close !== lastPrice ||
        normalizedLastCandle.high !== nextHigh ||
        normalizedLastCandle.low !== nextLow ||
        normalizedLastCandle.volume !== nextVolume;

      if (!changed) {
        return false;
      }

      candles[lastIndex] = {
        ...normalizedLastCandle,
        high: nextHigh,
        low: nextLow,
        close: lastPrice,
        volume: nextVolume,
      };
      bumpCandleVersion(symbol);
      return true;
    }

    let previousClose = normalizedLastCandle.close;
    let nextBucketTimestamp = lastCandleTimestamp + timeframeMs;

    while (nextBucketTimestamp <= bucketTimestamp) {
      const nextClose = nextBucketTimestamp === bucketTimestamp ? lastPrice : previousClose;
      candles.push({
        timestamp: nextBucketTimestamp,
        datetime: new Date(nextBucketTimestamp).toISOString(),
        open: previousClose,
        high: Math.max(previousClose, nextClose),
        low: Math.min(previousClose, nextClose),
        close: nextClose,
        volume: appendVolume && nextBucketTimestamp === bucketTimestamp && isNewTickerEvent ? lastTradeSize : 0,
      });
      previousClose = nextClose;
      nextBucketTimestamp += timeframeMs;
    }

    while (candles.length > getMaxVisibleCandles()) {
      candles.shift();
    }
    bumpCandleVersion(symbol);
    return true;
  };

  // 优先使用交易所原生 candle 流更新最后一根 K 线，避免本地按 ticker 补线造成偏差。
  const applyRealtimeCandleToCandles = (symbol, candle) => {
    const normalizedCandle = normalizeRealtimeCandleData(candle);
    const candles = candlesData[symbol];
    if (!normalizedCandle || !Array.isArray(candles) || candles.length === 0) {
      return false;
    }

    if (normalizedCandle.timeframe !== currentTimeframe.value) {
      return false;
    }

    const normalizedSymbol = normalizeMonitorSymbol(normalizedCandle.inst_id);
    if (normalizedSymbol !== symbol) {
      return false;
    }

    const candleTimestamp = normalizedCandle.timestamp;
    const lastIndex = candles.length - 1;
    const lastCandleTimestamp = getCandleTimestamp(candles[lastIndex]);
    if (!lastCandleTimestamp) {
      return false;
    }

    if (candleTimestamp < lastCandleTimestamp) {
      return false;
    }

    if (candleTimestamp === lastCandleTimestamp) {
      const previous = candles[lastIndex];
      const changed =
        toFiniteNumber(previous?.open, Number.NaN) !== normalizedCandle.open ||
        toFiniteNumber(previous?.high, Number.NaN) !== normalizedCandle.high ||
        toFiniteNumber(previous?.low, Number.NaN) !== normalizedCandle.low ||
        toFiniteNumber(previous?.close, Number.NaN) !== normalizedCandle.close ||
        toFiniteNumber(previous?.volume, Number.NaN) !== normalizedCandle.volume;

      if (!changed) {
        return false;
      }

      candles[lastIndex] = {
        ...previous,
        ...normalizedCandle,
      };
      bumpCandleVersion(symbol);
      return true;
    }

    candles.push(normalizedCandle);
    while (candles.length > getMaxVisibleCandles()) {
      candles.shift();
    }
    bumpCandleVersion(symbol);
    return true;
  };

  let syncRealtimeTickerSubscriptions = async () => {};
  const panelState = createMarketViewRealtimePanels({
    api,
    activeSymbol,
    availableSymbols,
    selectedSymbols,
    holdingSymbols,
    marketInstType,
    marketTypeOptions,
    pendingOrdersData,
    contractPositionsData,
    timeframes,
    indicators,
    fillsData,
    recentTradesData,
    recentTradesLoading,
    orderBookData,
    orderBookLoading,
    orderBookError,
    recentTradesScrollRef,
    recentTradesTrackRef,
    recentTradesPrimaryListRef,
    recentTradesAutoScrollPaused,
    recentTradesLooping,
    recentTradesPanelActive,
    orderBookPanelActive,
    chartRefs,
    chartInstances,
    chartLoading,
    chartErrors,
    candlesData,
    candleVersions,
    tickers,
    realtimePriceMoves,
    displayTickers,
    displayPriceMoves,
    currentTimeframe,
    RECENT_MARKET_TRADES_LIMIT,
    RECENT_MARKET_TRADES_POLL_INTERVAL,
    RECENT_TRADES_AUTO_SCROLL_SPEED,
    ORDERBOOK_POLL_INTERVAL,
    wsConnected,
    resolveMarketInstId,
    normalizeMonitorSymbol,
    getSymbolBaseCurrency,
    ensureActiveSymbol,
    marketViewActive,
    getRequestErrorMessage,
    clearRealtimeChartUpdate,
    clearRealtimePriceMove,
    clearRealtimeTickerEvent,
    clearChartViewportState,
    disposeChartInstance,
    clearAllRealtimeChartUpdates,
    clearAllRealtimeTickerEvents,
    initChart,
    updateChart,
    loadChartData,
    updateAllCharts,
    refreshActiveChart,
    getChartInteractionDelay,
    getOrderBookDepthLimit,
    bufferedTickers,
    pendingDisplayTickerSymbols,
    scheduleBufferedTickerFlush,
    flushBufferedTickerForSymbol,
    realtimeWsTickerArrivalTimestamps,
    ACTIVE_TICKER_FALLBACK_STALE_MS,
    normalizeRealtimeCandleData,
    applyIncomingTicker,
    applyIncomingRealtimeCandle,
    getSyncRealtimeTickerSubscriptions: () => syncRealtimeTickerSubscriptions,
  });

  const {
    handleTickerUpdate,
    handleCandleUpdate,
  } = panelState;

  const handleWsConnectionChange = ({ connected }) => {
    wsConnected.value = connected;
    if (!marketViewActive.value) return;
    startAutoRefresh();
  };

  const clearRealtimeTickerSubscriptions = () => {
    stopBufferedTickerFlush();
    clearScheduledDisplayTickerFlush();
    stopActiveTickerWatchdog();
    bufferedTickers.clear();
    pendingDisplayTickerSymbols.clear();
    for (const instId of wsSubscribedSymbols) {
      marketWS.unsubscribe(instId, handleTickerUpdate);
    }
    wsSubscribedSymbols.clear();
    for (const candleKey of wsSubscribedCandleKeys) {
      const separatorIndex = candleKey.lastIndexOf(':');
      if (separatorIndex <= 0) {
        continue;
      }
      const instId = candleKey.slice(0, separatorIndex);
      const timeframe = candleKey.slice(separatorIndex + 1);
      marketWS.unsubscribeCandle(instId, timeframe, handleCandleUpdate);
    }
    wsSubscribedCandleKeys.clear();
    pendingRealtimeWsCandles.clear();
  };

  syncRealtimeTickerSubscriptions = async () => {
    if (!marketViewActive.value) return;

    const nextSymbols = new Set(
      selectedSymbols.value
        .map(symbol => resolveMarketInstId(symbol))
        .filter(Boolean)
    );
    const activeInstId = activeSymbol.value ? resolveMarketInstId(activeSymbol.value) : '';
    const activeCandleKey = buildRealtimeCandleSubscriptionKey(activeInstId, currentTimeframe.value);
    const nextCandleSubscriptions = new Set(activeCandleKey ? [activeCandleKey] : []);

    for (const symbol of [...wsSubscribedSymbols]) {
      if (!nextSymbols.has(symbol)) {
        marketWS.unsubscribe(symbol, handleTickerUpdate);
        wsSubscribedSymbols.delete(symbol);
      }
    }

    for (const candleKey of [...wsSubscribedCandleKeys]) {
      if (nextCandleSubscriptions.has(candleKey)) {
        continue;
      }

      const separatorIndex = candleKey.lastIndexOf(':');
      if (separatorIndex <= 0) {
        wsSubscribedCandleKeys.delete(candleKey);
        continue;
      }

      const instId = candleKey.slice(0, separatorIndex);
      const timeframe = candleKey.slice(separatorIndex + 1);
      marketWS.unsubscribeCandle(instId, timeframe, handleCandleUpdate);
      wsSubscribedCandleKeys.delete(candleKey);
    }

    const newSymbols = [...nextSymbols].filter(instId => !wsSubscribedSymbols.has(instId));
    if (newSymbols.length > 0) {
      marketWS.subscribeMany(newSymbols, handleTickerUpdate);
      newSymbols.forEach(instId => wsSubscribedSymbols.add(instId));
    }

    const newCandleSubscriptions = activeInstId
      ? [{
          instId: activeInstId,
          timeframe: currentTimeframe.value,
          candleKey: activeCandleKey,
        }].filter(item => item.candleKey && !wsSubscribedCandleKeys.has(item.candleKey))
      : [];
    if (newCandleSubscriptions.length > 0) {
      marketWS.subscribeManyCandles(newCandleSubscriptions, handleCandleUpdate);
      newCandleSubscriptions.forEach(item => wsSubscribedCandleKeys.add(item.candleKey));
    }

    if (nextSymbols.size > 0 && !marketWS.isConnected) {
      try {
        await marketWS.connect();
      } catch (error) {
        console.warn('实时行情 WebSocket 连接失败，回退到 HTTP 轮询:', error);
      }
    }

    wsConnected.value = marketWS.isConnected;
    startAutoRefresh();
  };

  return {
    getCandleTimestamp,
    clearRealtimeChartUpdate,
    clearAllRealtimeChartUpdates,
    clearRealtimePriceMove,
    clearAllRealtimePriceMoves,
    clearRealtimeTickerEvent,
    clearAllRealtimeTickerEvents,
    clearDisplayPriceMoveState,
    updateRealtimePriceMove,
    scheduleRealtimeChartUpdate,
    applyRealtimeTickerToCandles,
    applyIncomingTicker,
    flushBufferedTickerForSymbol,
    toFiniteNumber,
    normalizeTickerData,
    clamp,
    startActiveTickerWatchdog,
    stopActiveTickerWatchdog,
    handleWsConnectionChange,
    clearRealtimeTickerSubscriptions,
    syncRealtimeTickerSubscriptions,
    getTickerMetrics: (symbol) => resolveTickerMetrics(panelState.getTicker, symbol),
    getLatestCandle: (symbol) => resolveLatestCandle(candlesData, symbol),
    ...panelState,
  };
}
