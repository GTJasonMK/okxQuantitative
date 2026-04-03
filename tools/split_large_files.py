from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8').replace('\r\n', '\n')


def write_text(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8')


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise ValueError(f'找不到待替换片段: {old[:80]!r}')
    return text.replace(old, new, 1)


def extract_block(text: str, start_marker: str, end_marker: str) -> tuple[str, str]:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end], text[:start] + text[end:]


def top_level_names(block: str) -> list[str]:
    names: list[str] = []
    patterns = [
        re.compile(r'^(?:const|let|var)\s+([A-Za-z_]\w*)\s*=', re.MULTILINE),
        re.compile(r'^(?:async\s+)?function\s+([A-Za-z_]\w*)\s*\(', re.MULTILINE),
    ]
    for pattern in patterns:
        for match in pattern.finditer(block):
            name = match.group(1)
            if name not in names:
                names.append(name)
    return names


def build_return_block(names: list[str], indent: str = '  ') -> str:
    if not names:
        return f'{indent}return {{}};\n'
    joined = ',\n'.join(f'{indent}  {name},' for name in names)
    return f'{indent}return {{\n{joined}\n{indent}}};\n'


def indent_block(text: str, prefix: str) -> str:
    return ''.join(prefix + line if line.strip() else line for line in text.splitlines(keepends=True))


def extract_style(text: str) -> tuple[str, str]:
    match = re.search(r'<style scoped>\s*\n(?P<body>.*)\n</style>\s*$', text, re.DOTALL)
    if not match:
        raise ValueError('找不到 scoped style 块')
    body = match.group('body').strip('\n') + '\n'
    remaining = text[:match.start()].rstrip() + '\n'
    return body, remaining


def build_market_style_tags() -> str:
    return (
        '<style scoped src="../assets/styles/views/market-view-layout.css"></style>\n'
        '<style scoped src="../assets/styles/views/market-view-controls.css"></style>\n'
        '<style scoped src="../assets/styles/views/market-view-panels.css"></style>\n'
    )


def split_market_styles(style_body: str) -> dict[str, str]:
    lines = style_body.splitlines()
    layout = '\n'.join(lines[:644]).rstrip() + '\n'
    controls = '\n'.join(lines[644:1268]).rstrip() + '\n'
    panels = '\n'.join(lines[1268:]).rstrip() + '\n'
    return {
        'frontend/src/renderer/assets/styles/views/market-view-layout.css': layout,
        'frontend/src/renderer/assets/styles/views/market-view-controls.css': controls,
        'frontend/src/renderer/assets/styles/views/market-view-panels.css': panels,
    }


def transform_strategy_view() -> None:
    path = 'frontend/src/renderer/views/StrategyView.vue'
    text = read_text(path)
    if 'strategy-view.css' in text:
        return
    style_body, remaining = extract_style(text)
    write_text('frontend/src/renderer/assets/styles/views/strategy-view.css', style_body)
    remaining += '<style scoped src="../assets/styles/views/strategy-view.css"></style>\n'
    write_text(path, remaining)


def transform_backtest_view() -> None:
    path = 'frontend/src/renderer/views/BacktestView.vue'
    text = read_text(path)
    if 'useBacktestViewUtils' in text and 'backtest-view.css' in text:
        return
    style_body, remaining = extract_style(text)
    write_text('frontend/src/renderer/assets/styles/views/backtest-view.css', style_body)

    remaining = replace_once(remaining, "import * as echarts from 'echarts';\n\n", '')
    remaining = replace_once(
        remaining,
        "import { api } from '../services/api';\n",
        (
            "import { api } from '../services/api';\n"
            "import { useBacktestViewUtils } from '../composables/backtest/useBacktestViewUtils';\n"
            "import { useBacktestViewCharts } from '../composables/backtest/useBacktestViewCharts';\n"
        ),
    )

    utils_block, remaining = extract_block(
        remaining,
        'function safeNum(value, fallback = 0) {\n',
        'function renderKlineChart() {\n',
    )
    charts_block, remaining = extract_block(
        remaining,
        'function renderKlineChart() {\n',
        'async function loadSymbols() {\n',
    )

    utils_names = top_level_names(utils_block)
    charts_names = top_level_names(charts_block)

    utils_module = (
        "export function useBacktestViewUtils(deps) {\n"
        "  const {\n"
        "    config,\n"
        "    scanResult,\n"
        "    indicatorMap,\n"
        "    candles,\n"
        "    trades,\n"
        "    activeOverlayIndicators,\n"
        "    activeSecondaryIndicator,\n"
        "    INDICATOR_LABELS,\n"
        "    INDICATOR_COLORS,\n"
        "    PRIMARY_OVERLAY_ORDER,\n"
        "    SECONDARY_PANEL_ORDER,\n"
        "  } = deps;\n\n"
        f"{indent_block(utils_block.rstrip() + chr(10), '  ')}\n"
        f"{build_return_block(utils_names)}"
        "}\n"
    )
    write_text('frontend/src/renderer/composables/backtest/useBacktestViewUtils.js', utils_module)

    charts_module = (
        "import * as echarts from 'echarts';\n\n"
        "export function useBacktestViewCharts(deps) {\n"
        "  const {\n"
        "    klineChartRef,\n"
        "    equityChartRef,\n"
        "    scanHeatmapRef,\n"
        "    compareChartRef,\n"
        "    candles,\n"
        "    config,\n"
        "    activeOverlayIndicators,\n"
        "    overlayIndicatorOptions,\n"
        "    activeSecondaryIndicator,\n"
        "    secondaryIndicatorOptions,\n"
        "    trades,\n"
        "    indicatorMap,\n"
        "    scanResult,\n"
        "    compareResults,\n"
        "    compareScaleMode,\n"
        "    result,\n"
        "    equityCurve,\n"
        "    bottomTab,\n"
        "    formatAxisTime,\n"
        "    formatDateTime,\n"
        "    formatPrice,\n"
        "    formatMoney,\n"
        "    safeNum,\n"
        "    getIndicatorColor,\n"
        "    buildTradeTooltipHtml,\n"
        "    getTradeIndexByTimestamp,\n"
        "    getActiveSecondaryMeta,\n"
        "    buildSecondarySeries,\n"
        "    PRICE_UP_COLOR,\n"
        "    PRICE_DOWN_COLOR,\n"
        "    DEFAULT_TEXT,\n"
        "    MUTED_TEXT,\n"
        "    GRID_COLOR,\n"
        "    SURFACE_BG,\n"
        "    VOLUME_UP,\n"
        "    VOLUME_DOWN,\n"
        "  } = deps;\n\n"
        f"{indent_block(charts_block.rstrip() + chr(10), '  ')}\n"
        f"{build_return_block(charts_names)}"
        "}\n"
    )
    write_text('frontend/src/renderer/composables/backtest/useBacktestViewCharts.js', charts_module)

    utils_init = (
        "const { safeNum, parseMaybeJSON, normalizeCandle, normalizeCandles, normalizeEquityCurve, normalizeTrades, "
        "normalizeIndicatorMap, normalizeBacktestPayload, formatIndicatorLabel, getIndicatorColor, isPrimaryOverlayIndicator, "
        "buildOverlayOptions, buildSecondaryOptions, formatPrice, formatMoney, formatPercent, formatRatio, formatDateTime, "
        "formatTime, formatAxisTime, formatParams, formatScanMetric, formatMetadataValue, getTradeMetadataEntries, "
        "buildTradeTooltipHtml, getTradeIndexByTimestamp, buildTradeScatterSeries, buildSecondarySeries, getActiveSecondaryMeta } = "
        "useBacktestViewUtils({ config, scanResult, indicatorMap, candles, trades, activeOverlayIndicators, activeSecondaryIndicator, "
        "INDICATOR_LABELS, INDICATOR_COLORS, PRIMARY_OVERLAY_ORDER, SECONDARY_PANEL_ORDER });\n"
    )
    charts_init = (
        "const { renderKlineChart, renderEquityChart, renderScanHeatmap, renderCompareChart, renderAllCharts, resizeCharts } = "
        "useBacktestViewCharts({ klineChartRef, equityChartRef, scanHeatmapRef, compareChartRef, candles, config, activeOverlayIndicators, "
        "overlayIndicatorOptions, activeSecondaryIndicator, secondaryIndicatorOptions, trades, indicatorMap, scanResult, compareResults, "
        "compareScaleMode, result, equityCurve, bottomTab, formatAxisTime, formatDateTime, formatPrice, formatMoney, safeNum, "
        "getIndicatorColor, buildTradeTooltipHtml, getTradeIndexByTimestamp, getActiveSecondaryMeta, buildSecondarySeries, PRICE_UP_COLOR, "
        "PRICE_DOWN_COLOR, DEFAULT_TEXT, MUTED_TEXT, GRID_COLOR, SURFACE_BG, VOLUME_UP, VOLUME_DOWN });\n"
    )

    remaining = replace_once(
        remaining,
        'const historyDetailCache = new Map();\n',
        f'const historyDetailCache = new Map();\n{utils_init}{charts_init}',
    )
    remaining += '<style scoped src="../assets/styles/views/backtest-view.css"></style>\n'
    write_text(path, remaining)


def transform_trading_view() -> None:
    path = 'frontend/src/renderer/views/TradingView.vue'
    text = read_text(path)
    if 'useTradingViewRuntime' in text and 'trading-view.css' in text:
        return
    style_body, remaining = extract_style(text)
    write_text('frontend/src/renderer/assets/styles/views/trading-view.css', style_body)

    remaining = replace_once(
        remaining,
        "import { useAppStore } from '../stores/app'\n",
        (
            "import { useAppStore } from '../stores/app'\n"
            "import { useTradingViewRuntime } from '../composables/useTradingViewRuntime'\n"
        ),
    )

    runtime_block, remaining = extract_block(
        remaining,
        '// ========== 方法 ==========\n\n',
        '</script>',
    )
    runtime_block = '// ========== 方法 ==========\n\n' + runtime_block
    runtime_names = top_level_names(runtime_block)
    runtime_module = (
        "import { onActivated, onDeactivated, onMounted, onUnmounted, watch } from 'vue';\n\n"
        "export function useTradingViewRuntime(deps) {\n"
        "  const {\n"
        "    api,\n"
        "    marketWS,\n"
        "    props,\n"
        "    appStore,\n"
        "    selectedSymbol,\n"
        "    availableSymbols,\n"
        "    settingsLoaded,\n"
        "    symbolDropdownOpen,\n"
        "    symbolSearch,\n"
        "    newSymbolInput,\n"
        "    holdingSymbols,\n"
        "    loading,\n"
        "    orderLoading,\n"
        "    cancelingOrderId,\n"
        "    currentPrice,\n"
        "    priceLoading,\n"
        "    wsConnected,\n"
        "    maxTradeSize,\n"
        "    showConfirmDialog,\n"
        "    pendingOrder,\n"
        "    showContractConfirmDialog,\n"
        "    pendingContractOrder,\n"
        "    currentSide,\n"
        "    tradeType,\n"
        "    contractSide,\n"
        "    contractSettings,\n"
        "    contractPosMode,\n"
        "    contractPositions,\n"
        "    tradingStatus,\n"
        "    accountBalance,\n"
        "    spotHoldings,\n"
        "    totalValueUsdt,\n"
        "    totalValueWithCost,\n"
        "    totalCostUsdt,\n"
        "    totalFeeUsdt,\n"
        "    totalPnlUsdt,\n"
        "    totalPnlPercent,\n"
        "    holdingsBase,\n"
        "    holdingPrices,\n"
        "    syncingFills,\n"
        "    showEditCostDialog,\n"
        "    editingCcy,\n"
        "    editCostValue,\n"
        "    savingCost,\n"
        "    pendingOrders,\n"
        "    fills,\n"
        "    orderResult,\n"
        "    orderForm,\n"
        "    defaultModeText,\n"
        "    isModeLocked,\n"
        "    buildModeLockMessage,\n"
        "    getErrorDetail,\n"
        "    recalcHoldings,\n"
        "    isHoldingSymbol,\n"
        "    estimatedAmount,\n"
        "    priceChange24h,\n"
        "    contractInstId,\n"
        "    baseCurrency,\n"
        "    contractSideClass,\n"
        "    contractSideText,\n"
        "  } = deps;\n\n"
        f"{indent_block(runtime_block.rstrip() + chr(10), '  ')}\n"
        f"{build_return_block(runtime_names)}"
        "}\n"
    )
    write_text('frontend/src/renderer/composables/useTradingViewRuntime.js', runtime_module)

    runtime_init = (
        "const { formatNumber, formatPrice, formatPercent, formatTime, getPlClass, getChangeClass, formatChange, "
        "getOrderStateText, toggleSymbolDropdown, selectSymbol, addCustomSymbol, removeSymbol, fetchCurrentPrice, fetchMaxSize, "
        "setQuickAmount, refreshAll, fetchTradingStatus, fetchAccountBalance, onHoldingPriceUpdate, subscribeHoldingPrices, "
        "unsubscribeHoldingPrices, fetchSpotHoldings, fetchPendingOrders, fetchFills, placeOrder, cancelOrder, confirmOrder, "
        "executeOrder, cancelConfirm, switchTradeType, fetchContractAccountConfig, getDesiredContractPosSide, setLeverage, "
        "fetchContractLeverage, fetchContractPositions, confirmContractOrder, cancelContractConfirm, executeContractOrder, quickSell, "
        "syncFills, openEditCostDialog, closeEditCostDialog, saveCostBasis, getPnlClass, formatPnl, handleClickOutside, onPriceUpdate, "
        "onAccountUpdate, mapInstTypeToTradeType, onOrderUpdate, onFillUpdate, initWebSocket, cleanupWebSocket, refreshTimer, "
        "priceRefreshTimer, isInitialized } = useTradingViewRuntime({ api, marketWS, props, appStore, selectedSymbol, availableSymbols, "
        "settingsLoaded, symbolDropdownOpen, symbolSearch, newSymbolInput, holdingSymbols, loading, orderLoading, cancelingOrderId, "
        "currentPrice, priceLoading, wsConnected, maxTradeSize, showConfirmDialog, pendingOrder, showContractConfirmDialog, "
        "pendingContractOrder, currentSide, tradeType, contractSide, contractSettings, contractPosMode, contractPositions, "
        "tradingStatus, accountBalance, spotHoldings, totalValueUsdt, totalValueWithCost, totalCostUsdt, totalFeeUsdt, totalPnlUsdt, "
        "totalPnlPercent, holdingsBase, holdingPrices, syncingFills, showEditCostDialog, editingCcy, editCostValue, savingCost, "
        "pendingOrders, fills, orderResult, orderForm, defaultModeText, isModeLocked, buildModeLockMessage, getErrorDetail, "
        "recalcHoldings, isHoldingSymbol, estimatedAmount, priceChange24h, contractInstId, baseCurrency, contractSideClass, "
        "contractSideText });\n"
    )
    remaining = replace_once(
        remaining,
        '</script>',
        f'{runtime_init}\n</script>',
    )
    remaining += '<style scoped src="../assets/styles/views/trading-view.css"></style>\n'
    write_text(path, remaining)


def transform_market_view() -> None:
    path = 'frontend/src/renderer/views/MarketView.vue'
    text = read_text(path)
    if 'useMarketViewRealtime' in text and 'market-view-layout.css' in text:
        return
    style_body, remaining = extract_style(text)
    for style_path, style_content in split_market_styles(style_body).items():
        write_text(style_path, style_content)

    remaining = replace_once(
        remaining,
        "import { ref, reactive, shallowReactive, markRaw, computed, onMounted, onUnmounted, onActivated, onDeactivated, watch, nextTick } from 'vue';\n",
        (
            "import { ref, reactive, shallowReactive, computed, nextTick } from 'vue';\n"
        ),
    )
    remaining = replace_once(remaining, "import * as echarts from 'echarts';\n", '')
    remaining = replace_once(
        remaining,
        "import { useAppStore } from '../stores/app';\n",
        (
            "import { useAppStore } from '../stores/app';\n"
            "import { useMarketViewRealtime } from '../composables/market/useMarketViewRealtime';\n"
            "import { useMarketViewCharting } from '../composables/market/useMarketViewCharting';\n"
            "import { useMarketViewSync } from '../composables/market/useMarketViewSync';\n"
        ),
    )
    remaining = replace_once(remaining, 'let marketViewActive = false;\n', 'const marketViewActive = ref(false);\n')

    block_a, remaining = extract_block(
        remaining,
        'const getCandleTimestamp = (candle) => {\n',
        'const chartViewportStates = reactive({});\n',
    )
    block_b, remaining = extract_block(
        remaining,
        'const chartViewportStates = reactive({});\n',
        'const pruneSyncJobs = () => {\n',
    )
    block_b = replace_once(block_b, 'const chartViewportStates = reactive({});\n\n', '')
    block_c, remaining = extract_block(
        remaining,
        'const pruneSyncJobs = () => {\n',
        '</script>',
    )

    block_a = re.sub(r'\bmarketViewActive\b', 'marketViewActive.value', block_a)
    block_c = re.sub(r'\bmarketViewActive\b', 'marketViewActive.value', block_c)
    block_c = block_c.replace('if (saveTimer) clearTimeout(saveTimer);', 'clearSaveTimer();')

    names_a = top_level_names(block_a)
    names_b = top_level_names(block_b)
    names_c = top_level_names(block_c)

    module_a = (
        "import { computed, nextTick, ref } from 'vue';\n\n"
        "export function useMarketViewRealtime(deps) {\n"
        "  const {\n"
        "    api,\n"
        "    marketWS,\n"
        "    activeSymbol,\n"
        "    availableSymbols,\n"
        "    selectedSymbols,\n"
        "    holdingSymbols,\n"
        "    marketInstType,\n"
        "    marketTypeOptions,\n"
        "    holdingsBase,\n"
        "    pendingOrdersData,\n"
        "    contractPositionsData,\n"
        "    timeframes,\n"
        "    showSyncJobsPanel,\n"
        "    indicators,\n"
        "    fillsData,\n"
        "    recentTradesData,\n"
        "    recentTradesLoading,\n"
        "    recentTradesScrollRef,\n"
        "    recentTradesTrackRef,\n"
        "    recentTradesPrimaryListRef,\n"
        "    recentTradesAutoScrollPaused,\n"
        "    recentTradesLooping,\n"
        "    chartRefs,\n"
        "    chartInstances,\n"
        "    chartLoading,\n"
        "    chartErrors,\n"
        "    candlesData,\n"
        "    tickers,\n"
        "    realtimePriceMoves,\n"
        "    TIMEFRAME_MS,\n"
        "    currentTimeframe,\n"
        "    MAX_VISIBLE_CANDLES,\n"
        "    REALTIME_CHART_UPDATE_DELAY,\n"
        "    RECENT_MARKET_TRADES_LIMIT,\n"
        "    RECENT_MARKET_TRADES_POLL_INTERVAL,\n"
        "    RECENT_TRADES_AUTO_SCROLL_SPEED,\n"
        "    syncJobsToggleRef,\n"
        "    syncJobsPanelRef,\n"
        "    marketTypeDropdown,\n"
        "    timeframeDropdown,\n"
        "    indicatorDropdown,\n"
        "    wsConnected,\n"
        "    resolveMarketInstId,\n"
        "    normalizeMonitorSymbol,\n"
        "    getSymbolBaseCurrency,\n"
        "    ensureActiveSymbol,\n"
        "    marketViewActive,\n"
        "  } = deps;\n"
        "  let recentTradesTimer = null;\n"
        "  let recentTradesAutoScrollTimer = null;\n"
        "  let recentTradesAutoScrollOffset = 0;\n"
        "  let recentTradesAutoScrollLastFrameTime = 0;\n"
        "  const wsSubscribedSymbols = new Set();\n"
        "  const realtimeChartUpdateTimers = new Map();\n"
        "  const realtimeChartUpdateTimestamps = new Map();\n"
        "  const realtimePriceMoveTimers = new Map();\n"
        "  const realtimeTickerEventKeys = new Map();\n"
        "  const updateChart = (...args) => deps.getUpdateChart()?.(...args);\n"
        "  const refreshAllCharts = (...args) => deps.getRefreshAllCharts()?.(...args);\n"
        "  const updateAllCharts = (...args) => deps.getUpdateAllCharts()?.(...args);\n"
        "  const initChart = (...args) => deps.getInitChart()?.(...args);\n"
        "  const loadChartData = (...args) => deps.getLoadChartData()?.(...args);\n"
        "  const clearChartViewportState = (...args) => deps.getClearChartViewportState()?.(...args);\n"
        "  const disposeChartInstance = (...args) => deps.getDisposeChartInstance()?.(...args);\n"
        "  const startAutoRefresh = (...args) => deps.getStartAutoRefresh()?.(...args);\n\n"
        f"{indent_block(block_a.rstrip() + chr(10), '  ')}\n"
        f"{build_return_block(names_a)}"
        "}\n"
    )
    write_text('frontend/src/renderer/composables/market/useMarketViewRealtime.js', module_a)

    module_b = (
        "import * as echarts from 'echarts';\n\n"
        "export function useMarketViewCharting(deps) {\n"
        "  const {\n"
        "    api,\n"
        "    loading,\n"
        "    activeSymbol,\n"
        "    selectedSymbols,\n"
        "    marketInstType,\n"
        "    currentTimeframe,\n"
        "    chartRefs,\n"
        "    chartInstances,\n"
        "    chartLoading,\n"
        "    chartErrors,\n"
        "    candlesData,\n"
        "    tickers,\n"
        "    indicators,\n"
        "    showTradeMarkers,\n"
        "    fillsData,\n"
        "    TIMEFRAME_MS,\n"
        "    DEFAULT_VISIBLE_CANDLES,\n"
        "    MIN_DATA_ZOOM_SPAN_PERCENT,\n"
        "    CHART_TOUCHPAD_PAN_RATIO,\n"
        "    CHART_DRAG_PAN_RATIO,\n"
        "    normalizeMonitorSymbol,\n"
        "    resolveMarketInstId,\n"
        "    toFiniteNumber,\n"
        "    binarySearchCandleIndex,\n"
        "    formatPrice,\n"
        "    formatTradeSize,\n"
        "    loadFillsForSymbol,\n"
        "    loadExecutionPanelData,\n"
        "    normalizeTickerData,\n"
        "    applyIncomingTicker,\n"
        "    applyRealtimeTickerToCandles,\n"
        "    clamp,\n"
        "    nextTick,\n"
        "  } = deps;\n"
        "  const chartViewportStates = {};\n"
        "  const chartWheelInteractionHandlers = new Map();\n"
        "  const chartDragInteractionHandlers = new Map();\n\n"
        f"{indent_block(block_b.rstrip() + chr(10), '  ')}\n"
        f"{build_return_block(names_b)}"
        "}\n"
    )
    write_text('frontend/src/renderer/composables/market/useMarketViewCharting.js', module_b)

    module_c = (
        "import { nextTick, onActivated, onDeactivated, onMounted, onUnmounted, watch } from 'vue';\n\n"
        "export function useMarketViewSync(deps) {\n"
        "  const {\n"
        "    api,\n"
        "    waitForBackend,\n"
        "    marketWS,\n"
        "    marketViewActive,\n"
        "    activeSyncJobs,\n"
        "    visibleSyncJobs,\n"
        "    settingsLoaded,\n"
        "    selectedSymbols,\n"
        "    activeSymbol,\n"
        "    holdingSymbols,\n"
        "    availableSymbols,\n"
        "    marketInstType,\n"
        "    currentTimeframe,\n"
        "    syncMode,\n"
        "    syncDays,\n"
        "    syncing,\n"
        "    syncCurrentLoading,\n"
        "    syncJobs,\n"
        "    showSyncJobsPanel,\n"
        "    chartErrors,\n"
        "    loading,\n"
        "    autoRefresh,\n"
        "    refreshInterval,\n"
        "    indicators,\n"
        "    wsConnected,\n"
        "    connectionError,\n"
        "    chartInstances,\n"
        "    chartRefs,\n"
        "    candlesData,\n"
        "    tickers,\n"
        "    realtimePriceMoves,\n"
        "    recentTradesData,\n"
        "    recentTradesLoading,\n"
        "    fillsData,\n"
        "    recentTradesLooping,\n"
        "    loadSettings,\n"
        "    loadHoldingSymbols,\n"
        "    ensureActiveSymbol,\n"
        "    loadExecutionPanelData,\n"
        "    resolveMarketInstId,\n"
        "    normalizeMonitorSymbol,\n"
        "    normalizeSymbolList,\n"
        "    clampSyncDays,\n"
        "    getRequestErrorMessage,\n"
        "    throttle,\n"
        "    clearSaveTimer,\n"
        "    loadChartData,\n"
        "    refreshAllCharts,\n"
        "    refreshAllTickers,\n"
        "    initChart,\n"
        "    updateChart,\n"
        "    disposeChartInstance,\n"
        "    clearChartViewportState,\n"
        "    clearRealtimeChartUpdate,\n"
        "    clearAllRealtimeChartUpdates,\n"
        "    clearRealtimePriceMove,\n"
        "    clearAllRealtimePriceMoves,\n"
        "    clearRealtimeTickerEvent,\n"
        "    clearAllRealtimeTickerEvents,\n"
        "    startRecentTradesPolling,\n"
        "    stopRecentTradesPolling,\n"
        "    stopRecentTradesAutoScroll,\n"
        "    syncRecentTradesAutoScroll,\n"
        "    clearRealtimeTickerSubscriptions,\n"
        "    syncRealtimeTickerSubscriptions,\n"
        "    handleWsConnectionChange,\n"
        "    handleClickOutside,\n"
        "  } = deps;\n"
        "  let refreshTimer = null;\n"
        "  let syncJobsTimer = null;\n"
        "  const handledFinishedSyncJobs = new Set();\n\n"
        f"{indent_block(block_c.rstrip() + chr(10), '  ')}\n"
        f"{build_return_block(names_c)}"
        "}\n"
    )
    write_text('frontend/src/renderer/composables/market/useMarketViewSync.js', module_c)

    init_a = (
        "const { getCandleTimestamp, clearRealtimeChartUpdate, clearAllRealtimeChartUpdates, clearRealtimePriceMove, clearAllRealtimePriceMoves, "
        "clearRealtimeTickerEvent, clearAllRealtimeTickerEvents, updateRealtimePriceMove, scheduleRealtimeChartUpdate, applyRealtimeTickerToCandles, "
        "applyIncomingTicker, showMarketTypeDropdown, showTimeframeDropdown, showIndicatorDropdown, symbolSearch, marketTypeDropdown, timeframeDropdown, "
        "indicatorDropdown, syncJobsToggleRef, syncJobsPanelRef, filteredSymbols, getWatchlistSymbolRank, watchlistSymbols, currentMarketTypeLabel, "
        "activeDisplayInstId, activeBaseCurrency, activeSpotHolding, activePendingOrders, activePrimaryPendingOrder, activeContractPositions, "
        "activePrimaryContractPosition, currentTimeframeLabel, toggleMarketTypeDropdown, toggleTimeframeDropdown, toggleIndicatorDropdown, "
        "toggleSyncJobsPanel, selectedIndicatorsCount, toggleIndicator, clearAllIndicators, selectTimeframe, selectMarketType, cleanupSymbolState, "
        "activateSymbolTab, openSymbolTab, closeSymbolTab, closeAllTabs, clearAllSymbols, isHoldingSymbol, removeSymbol, addCustomSymbol, "
        "handleClickOutside, setChartRef, getTicker, toFiniteNumber, normalizeTickerData, handleTickerUpdate, getTickerMetrics, clamp, getLatestCandle, "
        "activeTicker, activeTickerMetrics, activePriceMove, activeLiveCandle, activeSpotHoldingValue, activeSpotHoldingPnl, activeSpotHoldingPnlPercent, "
        "activeFills, activeFillCount, activeLatestFill, activeLiveCandleChange, activeLiveCandleRange, activeRecentTrades, activeLiveCandleVolume, "
        "activeCandleCount, formatTradeTime, getRecentTradeKey, getRecentTradesLoopHeight, loadRecentTrades, stopRecentTradesPolling, "
        "stopRecentTradesAutoScroll, pauseRecentTradesAutoScroll, resumeRecentTradesAutoScroll, syncRecentTradesAutoScroll, startRecentTradesPolling, "
        "handleWsConnectionChange, clearRealtimeTickerSubscriptions, syncRealtimeTickerSubscriptions, getTickerClass, getPriceMoveClass, "
        "getPriceFlashClass, getActiveLiveCandleClass, formatPrice, formatPriceDelta, formatChange, formatPercentValue, formatTickerTime, formatVolume, "
        "formatTradeSize, formatMetricValue } = useMarketViewRealtime({ api, marketWS, activeSymbol, availableSymbols, selectedSymbols, holdingSymbols, "
        "marketInstType, marketTypeOptions, holdingsBase, pendingOrdersData, contractPositionsData, timeframes, showSyncJobsPanel, indicators, fillsData, "
        "recentTradesData, recentTradesLoading, recentTradesScrollRef, recentTradesTrackRef, recentTradesPrimaryListRef, recentTradesAutoScrollPaused, "
        "recentTradesLooping, chartRefs, chartInstances, chartLoading, chartErrors, candlesData, tickers, realtimePriceMoves, TIMEFRAME_MS, "
        "currentTimeframe, MAX_VISIBLE_CANDLES, REALTIME_CHART_UPDATE_DELAY, RECENT_MARKET_TRADES_LIMIT, RECENT_MARKET_TRADES_POLL_INTERVAL, "
        "RECENT_TRADES_AUTO_SCROLL_SPEED, syncJobsToggleRef, syncJobsPanelRef, marketTypeDropdown, timeframeDropdown, indicatorDropdown, wsConnected, "
        "resolveMarketInstId, normalizeMonitorSymbol, getSymbolBaseCurrency, ensureActiveSymbol, marketViewActive, getUpdateChart: () => updateChart, "
        "getRefreshAllCharts: () => refreshAllCharts, getUpdateAllCharts: () => updateAllCharts, getInitChart: () => initChart, getLoadChartData: () => loadChartData, "
        "getClearChartViewportState: () => clearChartViewportState, getDisposeChartInstance: () => disposeChartInstance, getStartAutoRefresh: () => startAutoRefresh });\n"
    )
    init_b = (
        "const { chartViewportStates, getChartViewportStateKey, buildDefaultChartViewportState, getChartViewportState, setChartViewportState, "
        "clearChartViewportState, getChartDataZoomWindow, removeChartWheelInteraction, removeChartDragInteraction, disposeChartInstance, "
        "panChartViewportByWheel, zoomChartViewportByWheel, bindChartWheelInteraction, bindChartDragInteraction, initChart, calculateMA, calculateEMA, "
        "calculateBOLL, calculateSAR, updateChart, loadChartData, updateAllCharts, refreshChart, refreshAllCharts, refreshAllTickers } = "
        "useMarketViewCharting({ api, loading, activeSymbol, selectedSymbols, marketInstType, currentTimeframe, chartRefs, chartInstances, chartLoading, "
        "chartErrors, candlesData, tickers, indicators, showTradeMarkers, fillsData, TIMEFRAME_MS, DEFAULT_VISIBLE_CANDLES, MIN_DATA_ZOOM_SPAN_PERCENT, "
        "CHART_TOUCHPAD_PAN_RATIO, CHART_DRAG_PAN_RATIO, normalizeMonitorSymbol, resolveMarketInstId, toFiniteNumber, binarySearchCandleIndex, "
        "formatPrice, formatTradeSize, loadFillsForSymbol, loadExecutionPanelData, normalizeTickerData, applyIncomingTicker, applyRealtimeTickerToCandles, "
        "clamp, nextTick });\n"
    )
    init_c = (
        "const clearSaveTimer = () => { if (saveTimer) clearTimeout(saveTimer); };\n"
        "const { pruneSyncJobs, stopSyncJobsPolling, handleSyncJobFinished, applySyncJobUpdate, pollSyncJobs, startSyncJobsPolling, recoverActiveSyncJobs, "
        "dismissFinishedSyncJobs, syncCurrentSymbolData, syncAllData, onSymbolsChange, initAllCharts, resetMarketDisplayState, startAutoRefresh, "
        "stopAutoRefresh, toggleAutoRefresh, restartAutoRefresh, doResize, handleResize, checkConnection, loadAvailableSymbols } = useMarketViewSync({ "
        "api, waitForBackend, marketWS, marketViewActive, activeSyncJobs, visibleSyncJobs, settingsLoaded, selectedSymbols, activeSymbol, holdingSymbols, "
        "availableSymbols, marketInstType, currentTimeframe, syncMode, syncDays, syncing, syncCurrentLoading, syncJobs, showSyncJobsPanel, chartErrors, "
        "loading, autoRefresh, refreshInterval, indicators, wsConnected, connectionError, chartInstances, chartRefs, candlesData, tickers, realtimePriceMoves, "
        "recentTradesData, recentTradesLoading, fillsData, recentTradesLooping, loadSettings, loadHoldingSymbols, ensureActiveSymbol, loadExecutionPanelData, "
        "resolveMarketInstId, normalizeMonitorSymbol, normalizeSymbolList, clampSyncDays, getRequestErrorMessage, throttle, clearSaveTimer, loadChartData, "
        "refreshAllCharts, refreshAllTickers, initChart, updateChart, disposeChartInstance, clearChartViewportState, clearRealtimeChartUpdate, "
        "clearAllRealtimeChartUpdates, clearRealtimePriceMove, clearAllRealtimePriceMoves, clearRealtimeTickerEvent, clearAllRealtimeTickerEvents, "
        "startRecentTradesPolling, stopRecentTradesPolling, stopRecentTradesAutoScroll, syncRecentTradesAutoScroll, clearRealtimeTickerSubscriptions, "
        "syncRealtimeTickerSubscriptions, handleWsConnectionChange, handleClickOutside });\n"
    )

    remaining = replace_once(
        remaining,
        'const recentTradesLoading = reactive({});\n',
        f'const recentTradesLoading = reactive({{}});\n{init_a}{init_b}{init_c}',
    )
    remaining += build_market_style_tags()
    write_text(path, remaining)


def transform_data_storage() -> None:
    path = 'backend/app/core/data_storage.py'
    text = read_text(path)
    if 'from .storage_backtest import StorageBacktestMixin' in text:
        return

    core_block, tail = extract_block(text, 'class DataStorage:\n', '    # ==================== 成交记录和成本基础方法 ====================\n')
    fills_block, tail = extract_block(tail, '    def save_fill(\n', '    # ==================== 回测结果持久化方法 ====================\n')
    backtest_block, tail = extract_block(tail, '    def save_backtest_result(self, result_dict: Dict[str, Any], strategy_id: str = "", params: Dict[str, Any] = None) -> int:\n', '    # ==================== 实时交易订单记录方法 ====================\n')
    live_block, tail = extract_block(tail, '    def save_live_order(\n', '\n\nclass DataManager:\n')
    data_manager_block = tail[tail.index('class DataManager:\n'):]

    core_class_body = core_block.split('class DataStorage:\n', 1)[1]
    storage_base = (
        "import sqlite3\n"
        "import threading\n"
        "from contextlib import contextmanager\n"
        "from datetime import datetime\n"
        "from pathlib import Path\n"
        "from typing import Any, Dict, List, Optional, Tuple\n\n"
        "from .data_fetcher import Candle\n\n\n"
        "class StorageCoreMixin:\n"
        f"{core_class_body}"
    )
    write_text('backend/app/core/storage_base.py', storage_base)

    storage_fills = (
        "from collections import defaultdict\n"
        "from datetime import datetime\n"
        "from decimal import Decimal\n"
        "from typing import Any, Dict, List\n\n\n"
        "class StorageFillMixin:\n"
        f"{fills_block}"
    )
    write_text('backend/app/core/storage_fills.py', storage_fills)

    storage_backtest = (
        "from typing import Any, Dict, List, Optional\n\n\n"
        "class StorageBacktestMixin:\n"
        f"{backtest_block}"
    )
    write_text('backend/app/core/storage_backtest.py', storage_backtest)

    storage_live = (
        "from typing import Any, Dict, List\n\n\n"
        "class StorageLiveOrderMixin:\n"
        f"{live_block}"
    )
    write_text('backend/app/core/storage_live_orders.py', storage_live)

    data_manager = (
        "import time\n"
        "from datetime import datetime\n"
        "from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING\n\n"
        "from .data_fetcher import Candle\n"
        "from ..utils.timeframes import estimate_days_for_candle_count, timeframe_to_ms\n\n"
        "if TYPE_CHECKING:\n"
        "    from .data_storage import DataStorage\n\n\n"
        + data_manager_block.replace('storage: DataStorage', 'storage: "DataStorage"')
    )
    write_text('backend/app/core/data_manager.py', data_manager)

    entry = (
        "from .data_manager import DataManager\n"
        "from .storage_backtest import StorageBacktestMixin\n"
        "from .storage_base import StorageCoreMixin\n"
        "from .storage_fills import StorageFillMixin\n"
        "from .storage_live_orders import StorageLiveOrderMixin\n\n\n"
        "class DataStorage(StorageCoreMixin, StorageFillMixin, StorageBacktestMixin, StorageLiveOrderMixin):\n"
        "    \"\"\"组合后的数据存储入口。\"\"\"\n\n"
        "    pass\n"
    )
    write_text(path, entry)


def main() -> None:
    transform_strategy_view()
    transform_backtest_view()
    transform_trading_view()
    transform_market_view()
    transform_data_storage()


if __name__ == '__main__':
    main()
