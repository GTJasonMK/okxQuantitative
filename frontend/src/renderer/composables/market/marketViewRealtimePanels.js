import { computed, nextTick, ref } from 'vue';

import {
  formatChange,
  formatPercentValue,
  formatPrice,
  formatTradeSize,
  getLatestCandle,
  getPriceFlashClass,
  getRecentTradeKey,
  getTickerClass,
  normalizeTickerData,
  toFiniteNumber,
} from './marketViewRealtimeUtils';

export function createMarketViewRealtimePanels(options) {
  const {
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
    getSyncRealtimeTickerSubscriptions,
  } = options;

  let recentTradesTimer = null;
  let orderBookTimer = null;
  let recentTradesAutoScrollOffset = 0;

  const showMarketTypeDropdown = ref(false);
  const showTimeframeDropdown = ref(false);
  const showIndicatorDropdown = ref(false);
  const marketTypeDropdown = ref(null);
  const timeframeDropdown = ref(null);
  const indicatorDropdown = ref(null);

  const getWatchlistSymbolRank = (symbol) => {
    if (symbol === activeSymbol.value) return 0;
    if (selectedSymbols.value.includes(symbol)) return 1;
    if (isHoldingSymbol(symbol)) return 2;
    return 3;
  };

  const watchlistSymbols = computed(() => (
    [...availableSymbols.value].sort((left, right) => {
      const rankDiff = getWatchlistSymbolRank(left) - getWatchlistSymbolRank(right);
      if (rankDiff !== 0) return rankDiff;
      return left.localeCompare(right);
    })
  ));

  const currentMarketTypeLabel = computed(() => {
    const type = marketTypeOptions.find(item => item.value === marketInstType.value);
    return type ? type.label : marketInstType.value;
  });

  const activeBaseCurrency = computed(() => (
    activeSymbol.value ? getSymbolBaseCurrency(activeSymbol.value) : ''
  ));

  const currentTimeframeLabel = computed(() => {
    const timeframe = timeframes.find(item => item.value === currentTimeframe.value);
    return timeframe ? timeframe.label : currentTimeframe.value;
  });

  const toggleMarketTypeDropdown = () => {
    showMarketTypeDropdown.value = !showMarketTypeDropdown.value;
    showTimeframeDropdown.value = false;
    showIndicatorDropdown.value = false;
  };

  const toggleTimeframeDropdown = () => {
    showTimeframeDropdown.value = !showTimeframeDropdown.value;
    showMarketTypeDropdown.value = false;
    showIndicatorDropdown.value = false;
  };

  const toggleIndicatorDropdown = () => {
    showIndicatorDropdown.value = !showIndicatorDropdown.value;
    showMarketTypeDropdown.value = false;
    showTimeframeDropdown.value = false;
  };

  const selectedIndicatorsCount = computed(() => (
    Object.values(indicators).filter(Boolean).length
  ));

  const toggleIndicator = (key) => {
    indicators[key] = !indicators[key];
    updateAllCharts();
  };

  const clearAllIndicators = () => {
    Object.keys(indicators).forEach(key => {
      indicators[key] = false;
    });
    updateAllCharts();
  };

  const selectTimeframe = (timeframe) => {
    currentTimeframe.value = timeframe;
    showTimeframeDropdown.value = false;
    clearAllRealtimeChartUpdates();
    clearAllRealtimeTickerEvents();
    const syncRealtimeTickerSubscriptions = typeof getSyncRealtimeTickerSubscriptions === 'function'
      ? getSyncRealtimeTickerSubscriptions()
      : null;
    if (typeof syncRealtimeTickerSubscriptions === 'function') {
      void syncRealtimeTickerSubscriptions();
    }
    void refreshActiveChart();
  };

  const selectMarketType = (instType) => {
    if (marketInstType.value === instType) {
      showMarketTypeDropdown.value = false;
      return;
    }

    marketInstType.value = instType;
    showMarketTypeDropdown.value = false;
  };

  const cleanupSymbolState = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) return;
    const spotInstId = resolveMarketInstId(normalizedSymbol, 'SPOT');
    const swapInstId = resolveMarketInstId(normalizedSymbol, 'SWAP');

    clearRealtimeChartUpdate(normalizedSymbol);
    clearRealtimePriceMove(normalizedSymbol);
    clearRealtimeTickerEvent(normalizedSymbol);
    realtimeWsTickerArrivalTimestamps.delete(normalizedSymbol);
    bufferedTickers.delete(normalizedSymbol);
    clearChartViewportState(normalizedSymbol);
    disposeChartInstance(normalizedSymbol);
    delete chartRefs[normalizedSymbol];
    delete tickers[normalizedSymbol];
    delete displayTickers[normalizedSymbol];
    delete candlesData[normalizedSymbol];
    delete candleVersions[normalizedSymbol];
    delete realtimePriceMoves[normalizedSymbol];
    delete displayPriceMoves[normalizedSymbol];
    pendingDisplayTickerSymbols?.delete?.(normalizedSymbol);
    delete recentTradesData[normalizedSymbol];
    delete recentTradesLoading[normalizedSymbol];
    delete orderBookData[normalizedSymbol];
    delete orderBookLoading[normalizedSymbol];
    delete orderBookError[normalizedSymbol];
    delete chartLoading[normalizedSymbol];
    delete chartErrors[normalizedSymbol];
    delete fillsData[normalizedSymbol];
    delete pendingOrdersData[spotInstId];
    delete pendingOrdersData[swapInstId];
    delete contractPositionsData[swapInstId];
  };

  const openSymbolTab = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) return;
    if (!availableSymbols.value.includes(normalizedSymbol)) return;

    if (!selectedSymbols.value.includes(normalizedSymbol)) {
      selectedSymbols.value.push(normalizedSymbol);
    }
    activeSymbol.value = normalizedSymbol;

    nextTick(() => {
      initChart(normalizedSymbol);
      if (candlesData[normalizedSymbol]?.length > 0) {
        updateChart(normalizedSymbol);
      } else {
        loadChartData(normalizedSymbol);
      }
    });
  };

  const closeSymbolTab = (symbol) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    const index = selectedSymbols.value.indexOf(normalizedSymbol);
    if (index === -1) return;

    const fallbackSymbol = selectedSymbols.value[index + 1] || selectedSymbols.value[index - 1] || '';
    cleanupSymbolState(normalizedSymbol);
    selectedSymbols.value.splice(index, 1);
    ensureActiveSymbol(fallbackSymbol);
  };

  const isHoldingSymbol = (symbol) => (
    holdingSymbols.value.includes(normalizeMonitorSymbol(symbol))
  );

  const handleClickOutside = (event) => {
    if (marketTypeDropdown.value && !marketTypeDropdown.value.contains(event.target)) {
      showMarketTypeDropdown.value = false;
    }
    if (timeframeDropdown.value && !timeframeDropdown.value.contains(event.target)) {
      showTimeframeDropdown.value = false;
    }
    if (indicatorDropdown.value && !indicatorDropdown.value.contains(event.target)) {
      showIndicatorDropdown.value = false;
    }
  };

  const setChartRef = (symbol, element) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) return;

    if (element) {
      chartRefs[normalizedSymbol] = element;
    } else {
      delete chartRefs[normalizedSymbol];
    }
  };

  const getRealtimeDisplayTicker = (symbol) => {
    if (!symbol) {
      return null;
    }

    const baseTicker = tickers[symbol] || displayTickers[symbol] || null;
    if (symbol !== activeSymbol.value) {
      return baseTicker;
    }

    void candleVersions[symbol];
    const liveCandle = getLatestCandle(candlesData, symbol);
    if (!liveCandle) {
      return baseTicker;
    }

    const liveClose = toFiniteNumber(liveCandle.close, Number.NaN);
    if (!Number.isFinite(liveClose) || liveClose <= 0) {
      return baseTicker;
    }

    const lastTickerArrivalAt = Number(realtimeWsTickerArrivalTimestamps.get(symbol) || 0);
    const tickerIsFresh = lastTickerArrivalAt > 0
      && Date.now() - lastTickerArrivalAt < ACTIVE_TICKER_FALLBACK_STALE_MS;

    if (tickerIsFresh && baseTicker) {
      return baseTicker;
    }

    if (!baseTicker) {
      return {
        inst_id: resolveMarketInstId(symbol),
        last: liveClose,
        last_sz: 0,
        ask_px: 0,
        bid_px: 0,
        open_24h: 0,
        high_24h: liveClose,
        low_24h: liveClose,
        vol_24h: 0,
        change_24h: 0,
        timestamp: toFiniteNumber(liveCandle.timestamp, Date.now()),
      };
    }

    const open24h = toFiniteNumber(baseTicker.open_24h, Number.NaN);
    const derivedChange24h = Number.isFinite(open24h) && open24h > 0
      ? ((liveClose - open24h) / open24h) * 100
      : baseTicker.change_24h;

    return {
      ...baseTicker,
      last: liveClose,
      high_24h: Math.max(toFiniteNumber(baseTicker.high_24h, liveClose), liveClose),
      low_24h: Math.min(toFiniteNumber(baseTicker.low_24h, liveClose), liveClose),
      change_24h: derivedChange24h,
      timestamp: Math.max(
        toFiniteNumber(baseTicker.timestamp, 0),
        toFiniteNumber(liveCandle.timestamp, 0),
      ),
    };
  };

  const getTicker = (symbol) => {
    if (!symbol) {
      return null;
    }
    return getRealtimeDisplayTicker(symbol);
  };

  const handleTickerUpdate = (ticker) => {
    const normalized = normalizeTickerData(ticker);
    if (!normalized) return;
    const monitorSymbol = normalizeMonitorSymbol(normalized.inst_id);
    if (!monitorSymbol) return;
    realtimeWsTickerArrivalTimestamps.set(monitorSymbol, Date.now());
    if (monitorSymbol === activeSymbol.value) {
      flushBufferedTickerForSymbol(monitorSymbol);
      applyIncomingTicker(monitorSymbol, normalized);
      return;
    }

    bufferedTickers.set(monitorSymbol, normalized);
    scheduleBufferedTickerFlush();
  };

  const handleCandleUpdate = (candle) => {
    const normalized = normalizeRealtimeCandleData(candle);
    if (!normalized) return;

    const monitorSymbol = normalizeMonitorSymbol(normalized.inst_id);
    if (!monitorSymbol || normalized.timeframe !== currentTimeframe.value) {
      return;
    }

    applyIncomingRealtimeCandle(monitorSymbol, normalized);
  };

  const activeTicker = computed(() => (
    activeSymbol.value ? getTicker(activeSymbol.value) : null
  ));

  const activeRecentTrades = computed(() => (
    activeSymbol.value ? recentTradesData[activeSymbol.value] || [] : []
  ));

  const activeOrderBook = computed(() => (
    activeSymbol.value ? orderBookData[activeSymbol.value] || null : null
  ));

  const getRecentTradesLoopHeight = () => {
    const primaryList = recentTradesPrimaryListRef.value;
    const track = recentTradesTrackRef.value;

    if (!primaryList) {
      return 0;
    }

    const trackStyles = track ? window.getComputedStyle(track) : null;
    const gap = trackStyles
      ? parseFloat(trackStyles.rowGap || trackStyles.gap || '0')
      : 0;

    return primaryList.offsetHeight + gap;
  };

  const getRecentTradesCurrentOffset = (loopHeight = 0) => {
    if (!Number.isFinite(loopHeight) || loopHeight <= 0) {
      return 0;
    }

    const track = recentTradesTrackRef.value;
    if (!track) {
      return recentTradesAutoScrollOffset % loopHeight;
    }

    const transform = window.getComputedStyle(track).transform;
    if (!transform || transform === 'none') {
      return recentTradesAutoScrollOffset % loopHeight;
    }

    let translateY = 0;
    try {
      translateY = new DOMMatrixReadOnly(transform).m42;
    } catch (error) {
      const values = transform.match(/matrix(3d)?\((.+)\)/)?.[2]
        ?.split(',')
        .map(value => parseFloat(value.trim()))
        .filter(value => Number.isFinite(value)) || [];
      if (values.length === 6) {
        translateY = values[5];
      } else if (values.length === 16) {
        translateY = values[13];
      }
    }

    const normalizedOffset = ((-translateY) % loopHeight + loopHeight) % loopHeight;
    return Number.isFinite(normalizedOffset) ? normalizedOffset : 0;
  };

  const applyRecentTradesLoopAnimation = (loopHeight, offset = 0) => {
    const track = recentTradesTrackRef.value;
    if (!track || !Number.isFinite(loopHeight) || loopHeight <= 0) {
      return;
    }

    const normalizedOffset = ((offset % loopHeight) + loopHeight) % loopHeight;
    const durationSeconds = Math.max(loopHeight / RECENT_TRADES_AUTO_SCROLL_SPEED, 6);
    recentTradesAutoScrollOffset = normalizedOffset;
    track.style.setProperty('--recent-trades-loop-height', `${loopHeight}px`);
    track.style.setProperty('--recent-trades-loop-duration', `${durationSeconds.toFixed(3)}s`);
    track.style.setProperty('--recent-trades-loop-delay', `${-(normalizedOffset / RECENT_TRADES_AUTO_SCROLL_SPEED)}s`);
    track.style.animation = 'none';
    track.style.transform = `translate3d(0, ${-normalizedOffset}px, 0)`;
    void track.offsetHeight;
    track.style.removeProperty('animation');
    track.style.animationPlayState = recentTradesAutoScrollPaused.value ? 'paused' : 'running';
  };

  const loadRecentTrades = async (symbol, options = {}) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) return;

    const instId = resolveMarketInstId(normalizedSymbol);
    if (!instId) return;

    if (!options.silent) {
      recentTradesLoading[normalizedSymbol] = true;
    }

    try {
      const response = await api.getRecentTrades(instId, {
        limit: RECENT_MARKET_TRADES_LIMIT,
        instType: marketInstType.value,
      });
      if (response.code === 0 && Array.isArray(response.data)) {
        recentTradesData[normalizedSymbol] = response.data
          .map(item => ({
            inst_id: item.inst_id || instId,
            trade_id: item.trade_id || '',
            price: toFiniteNumber(item.price),
            size: toFiniteNumber(item.size),
            side: item.side || '',
            timestamp: toFiniteNumber(item.timestamp),
          }))
          .filter(item => item.timestamp > 0)
          .sort((left, right) => right.timestamp - left.timestamp)
          .slice(0, RECENT_MARKET_TRADES_LIMIT);
      }
    } catch (error) {
      if (!options.silent) {
        console.warn(`获取 ${normalizedSymbol} 最新成交失败:`, error.message);
      }
    } finally {
      recentTradesLoading[normalizedSymbol] = false;
    }
  };

  const loadOrderBook = async (symbol, options = {}) => {
    const normalizedSymbol = normalizeMonitorSymbol(symbol);
    if (!normalizedSymbol) return;

    const instId = resolveMarketInstId(normalizedSymbol);
    if (!instId) return;

    if (!options.silent) {
      orderBookLoading[normalizedSymbol] = true;
    }

    try {
      const response = await api.getOrderBook(instId, {
        size: getOrderBookDepthLimit(),
        instType: marketInstType.value,
      });

      if (response.code === 0 && response.data && typeof response.data === 'object') {
        const normalizeLevels = (levels) => (
          Array.isArray(levels)
            ? levels.map(item => ({
              price: toFiniteNumber(item?.price),
              size: toFiniteNumber(item?.size),
              total: toFiniteNumber(item?.total),
              order_count: Math.max(0, Math.round(toFiniteNumber(item?.order_count))),
            })).filter(item => item.price > 0)
            : []
        );

        orderBookData[normalizedSymbol] = {
          inst_id: response.data.inst_id || instId,
          asks: normalizeLevels(response.data.asks),
          bids: normalizeLevels(response.data.bids),
          best_ask: toFiniteNumber(response.data.best_ask),
          best_bid: toFiniteNumber(response.data.best_bid),
          mid_price: toFiniteNumber(response.data.mid_price),
          spread: toFiniteNumber(response.data.spread),
          spread_rate: toFiniteNumber(response.data.spread_rate),
          ask_depth_total: toFiniteNumber(response.data.ask_depth_total),
          bid_depth_total: toFiniteNumber(response.data.bid_depth_total),
          timestamp: toFiniteNumber(response.data.timestamp),
        };
        orderBookError[normalizedSymbol] = '';
      }
    } catch (error) {
      if (!options.silent || !orderBookData[normalizedSymbol]) {
        orderBookError[normalizedSymbol] = getRequestErrorMessage(error, '盘口深度加载失败');
      }
      if (!options.silent) {
        console.warn(`获取 ${normalizedSymbol} 盘口深度失败:`, error.message);
      }
    } finally {
      orderBookLoading[normalizedSymbol] = false;
    }
  };

  const stopRecentTradesPolling = () => {
    if (recentTradesTimer) {
      clearInterval(recentTradesTimer);
      recentTradesTimer = null;
    }
  };

  const stopOrderBookPolling = () => {
    if (orderBookTimer) {
      clearInterval(orderBookTimer);
      orderBookTimer = null;
    }
  };

  const stopRecentTradesAutoScroll = (options = {}) => {
    const track = recentTradesTrackRef.value;
    if (options.resetPause) {
      recentTradesAutoScrollPaused.value = false;
    }
    if (options.resetPosition) {
      recentTradesAutoScrollOffset = 0;
    }
    if (track) {
      track.style.animation = 'none';
      track.style.animationPlayState = 'paused';
      track.style.removeProperty('--recent-trades-loop-delay');
      track.style.removeProperty('--recent-trades-loop-duration');
      track.style.removeProperty('--recent-trades-loop-height');
      if (options.resetPosition) {
        track.style.transform = 'translate3d(0, 0, 0)';
      }
    }
  };

  const syncRecentTradesAutoScroll = async (options = {}) => {
    const preservePosition = options.preservePosition !== false;

    if (
      !marketViewActive.value
      || !activeSymbol.value
      || !recentTradesPanelActive.value
      || recentTradesAutoScrollPaused.value
    ) {
      stopRecentTradesAutoScroll({ resetPause: false, resetPosition: false });
      return;
    }

    await nextTick();

    const container = recentTradesScrollRef.value;
    const primaryList = recentTradesPrimaryListRef.value;

    if (!container || !primaryList || activeRecentTrades.value.length <= 1) {
      recentTradesLooping.value = false;
      stopRecentTradesAutoScroll({ resetPause: false, resetPosition: true });
      return;
    }

    const shouldLoop = primaryList.offsetHeight > container.clientHeight + 4;
    if (recentTradesLooping.value !== shouldLoop) {
      recentTradesLooping.value = shouldLoop;
      await nextTick();
    }

    if (!shouldLoop) {
      stopRecentTradesAutoScroll({ resetPause: false, resetPosition: true });
      return;
    }

    const loopHeight = getRecentTradesLoopHeight();
    if (loopHeight <= 4) {
      recentTradesLooping.value = false;
      stopRecentTradesAutoScroll({ resetPause: false, resetPosition: true });
      return;
    }

    const nextOffset = preservePosition
      ? getRecentTradesCurrentOffset(loopHeight)
      : 0;
    applyRecentTradesLoopAnimation(loopHeight, nextOffset);
  };

  const startRecentTradesPolling = async () => {
    stopRecentTradesPolling();
    if (!marketViewActive.value || !activeSymbol.value || !recentTradesPanelActive.value) {
      stopRecentTradesAutoScroll({ resetPause: false, resetPosition: true });
      return;
    }

    await loadRecentTrades(activeSymbol.value);

    recentTradesTimer = setInterval(() => {
      if (!marketViewActive.value || !activeSymbol.value) return;
      if (getChartInteractionDelay(activeSymbol.value) > 0) return;
      loadRecentTrades(activeSymbol.value, { silent: true });
    }, RECENT_MARKET_TRADES_POLL_INTERVAL);
  };

  const startOrderBookPolling = async () => {
    stopOrderBookPolling();
    if (!marketViewActive.value || !activeSymbol.value || !orderBookPanelActive.value) {
      return;
    }

    await loadOrderBook(activeSymbol.value);

    orderBookTimer = setInterval(() => {
      if (!marketViewActive.value || !activeSymbol.value || !orderBookPanelActive.value) return;
      if (getChartInteractionDelay(activeSymbol.value) > 0) return;
      loadOrderBook(activeSymbol.value, { silent: true });
    }, ORDERBOOK_POLL_INTERVAL);
  };

  return {
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
    getTicker,
    handleTickerUpdate,
    handleCandleUpdate,
    activeTicker,
    activeRecentTrades,
    activeOrderBook,
    getRecentTradeKey,
    loadRecentTrades,
    stopRecentTradesPolling,
    stopRecentTradesAutoScroll,
    syncRecentTradesAutoScroll,
    loadOrderBook,
    stopOrderBookPolling,
    startRecentTradesPolling,
    startOrderBookPolling,
    getTickerClass: (symbol) => getTickerClass(getTicker, symbol),
    getPriceFlashClass: (symbol) => getPriceFlashClass(displayPriceMoves, symbol),
    formatPrice,
    formatChange,
    formatPercentValue,
    formatTradeSize,
  };
}
