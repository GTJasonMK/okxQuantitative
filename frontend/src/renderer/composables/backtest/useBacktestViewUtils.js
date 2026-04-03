import { computed } from 'vue';
import * as echarts from 'echarts';
import { formatPrice } from '@/utils/formatting';

export function useBacktestViewUtils(deps) {
  const {
    config,
    result,
    availableSymbolRows,
    strategies,
    strategyParams,
    scanConfig,
    scanResult,
    indicatorMap,
    candles,
    trades,
    activeOverlayIndicators,
    activeSecondaryIndicator,
    INDICATOR_LABELS,
    INDICATOR_COLORS,
    PRIMARY_OVERLAY_ORDER,
    SECONDARY_PANEL_ORDER,
    PRICE_UP_COLOR,
    PRICE_DOWN_COLOR,
  } = deps;

  function safeNum(value, fallback = 0) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
  }

  function parseMaybeJSON(value, fallback = {}) {
    if (value && typeof value === 'object') {
      return value;
    }
    if (typeof value !== 'string' || !value.trim()) {
      return fallback;
    }
    try {
      return JSON.parse(value);
    } catch (_error) {
      return fallback;
    }
  }

  function normalizeCandle(item) {
    const timestamp = safeNum(item?.timestamp);
    if (!timestamp) return null;
    return {
      timestamp,
      open: safeNum(item?.open),
      high: safeNum(item?.high),
      low: safeNum(item?.low),
      close: safeNum(item?.close),
      volume: safeNum(item?.volume),
    };
  }

  function normalizeCandles(list = []) {
    return (Array.isArray(list) ? list : [])
      .map(normalizeCandle)
      .filter(Boolean)
      .sort((left, right) => left.timestamp - right.timestamp);
  }

  function normalizeEquityCurve(list = []) {
    return (Array.isArray(list) ? list : [])
      .map((item) => ({
        timestamp: safeNum(item?.timestamp),
        equity: safeNum(item?.equity),
        cash: safeNum(item?.cash),
        positionValue: safeNum(item?.position_value ?? item?.positionValue),
      }))
      .filter((item) => item.timestamp > 0)
      .sort((left, right) => left.timestamp - right.timestamp);
  }

  function normalizeTrades(list = []) {
    return (Array.isArray(list) ? list : [])
      .map((item) => ({
        timestamp: safeNum(item?.timestamp),
        datetime: item?.datetime || '',
        side: String(item?.side || '').toLowerCase(),
        price: safeNum(item?.price),
        quantity: safeNum(item?.quantity),
        value: safeNum(item?.value),
        commission: safeNum(item?.commission),
        pnl: item?.pnl === null || item?.pnl === undefined ? null : safeNum(item?.pnl),
        reason: String(item?.reason || ''),
        metadata: parseMaybeJSON(item?.metadata, {}),
      }))
      .filter((item) => item.timestamp > 0 && item.price > 0)
      .sort((left, right) => left.timestamp - right.timestamp);
  }

  function normalizeIndicatorMap(rawIndicators = {}) {
    const normalized = {};
    Object.entries(rawIndicators || {}).forEach(([key, values]) => {
      if (!Array.isArray(values)) return;
      normalized[key] = values.map((value) => {
        if (value === null || value === undefined || value === '') {
          return null;
        }
        const numeric = Number(value);
        return Number.isFinite(numeric) ? numeric : null;
      });
    });
    return normalized;
  }

  function normalizeBacktestPayload(payload = {}) {
    const params = parseMaybeJSON(payload.params, parseMaybeJSON(payload.params_json, {}));
    return {
      id: payload.id ?? null,
      strategyId: payload.strategy_id || payload.strategyId || '',
      strategyName: payload.strategy_name || payload.strategyName || '',
      symbol: payload.symbol || '',
      instType: payload.inst_type || payload.instType || 'SPOT',
      timeframe: payload.timeframe || '',
      startTime: payload.start_time || payload.startTime || '',
      endTime: payload.end_time || payload.endTime || '',
      durationDays: safeNum(payload.duration_days ?? payload.durationDays ?? payload.days),
      days: safeNum(payload.days ?? payload.duration_days ?? payload.durationDays),
      initialCapital: safeNum(payload.initial_capital ?? payload.initialCapital),
      finalCapital: safeNum(payload.final_capital ?? payload.finalCapital),
      totalReturn: safeNum(payload.total_return ?? payload.totalReturn),
      annualReturn: safeNum(payload.annual_return ?? payload.annualReturn),
      maxDrawdown: safeNum(payload.max_drawdown ?? payload.maxDrawdown),
      sharpeRatio: safeNum(payload.sharpe_ratio ?? payload.sharpeRatio),
      sortinoRatio: safeNum(payload.sortino_ratio ?? payload.sortinoRatio),
      calmarRatio: safeNum(payload.calmar_ratio ?? payload.calmarRatio),
      winRate: safeNum(payload.win_rate ?? payload.winRate),
      profitFactor: safeNum(payload.profit_factor ?? payload.profitFactor),
      totalTrades: safeNum(payload.total_trades ?? payload.totalTrades),
      winningTrades: safeNum(payload.winning_trades ?? payload.winningTrades),
      losingTrades: safeNum(payload.losing_trades ?? payload.losingTrades),
      avgProfit: safeNum(payload.avg_profit ?? payload.avgProfit),
      avgLoss: safeNum(payload.avg_loss ?? payload.avgLoss),
      largestProfit: safeNum(payload.largest_profit ?? payload.largestProfit),
      largestLoss: safeNum(payload.largest_loss ?? payload.largestLoss),
      totalCommission: safeNum(payload.total_commission ?? payload.totalCommission),
      params,
      sampleStep: safeNum(payload.sample_step ?? payload.sampleStep, 1) || 1,
      createdAt: payload.created_at || payload.createdAt || '',
      candles: normalizeCandles(payload.candles || []),
      equityCurve: normalizeEquityCurve(payload.equity_curve || payload.equityCurve || []),
      trades: normalizeTrades(payload.trades || []),
      indicators: normalizeIndicatorMap(payload.indicators || {}),
    };
  }

  function formatIndicatorLabel(key) {
    if (INDICATOR_LABELS[key]) {
      return INDICATOR_LABELS[key];
    }
    return String(key || '')
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function getIndicatorColor(key, index = 0) {
    if (INDICATOR_COLORS[key]) {
      return INDICATOR_COLORS[key];
    }
    const fallbackPalette = ['#F7931A', '#f6c85d', '#ab47bc', '#26a69a', '#ff8a65', '#5c6bc0'];
    return fallbackPalette[index % fallbackPalette.length];
  }

  function isPrimaryOverlayIndicator(key) {
    if (!key) return false;
    if (['dif', 'dea', 'histogram', 'rsi', 'k', 'd', 'j', 'bandwidth', 'volume', 'volume_ma', 'close'].includes(key)) {
      return false;
    }
    if (PRIMARY_OVERLAY_ORDER.includes(key)) {
      return true;
    }
    if (/^ma\d+$/.test(key) || /^ema\d+$/.test(key)) {
      return true;
    }
    return key.startsWith('bb_') || key === 'sar';
  }

  function buildOverlayOptions() {
    const keys = Object.keys(indicatorMap).filter((key) => Array.isArray(indicatorMap[key]) && isPrimaryOverlayIndicator(key));
    return keys
      .sort((left, right) => {
        const leftIndex = PRIMARY_OVERLAY_ORDER.indexOf(left);
        const rightIndex = PRIMARY_OVERLAY_ORDER.indexOf(right);
        if (leftIndex === -1 && rightIndex === -1) return left.localeCompare(right);
        if (leftIndex === -1) return 1;
        if (rightIndex === -1) return -1;
        return leftIndex - rightIndex;
      })
      .map((key, index) => ({
        key,
        label: formatIndicatorLabel(key),
        color: getIndicatorColor(key, index),
      }));
  }

  function buildSecondaryOptions() {
    const keys = Object.keys(indicatorMap).filter((key) => Array.isArray(indicatorMap[key]));
    const options = [];
    const leftovers = new Set(keys.filter((key) => !isPrimaryOverlayIndicator(key) && !['volume', 'volume_ma', 'close'].includes(key)));

    if (leftovers.has('dif') || leftovers.has('dea') || leftovers.has('histogram')) {
      options.push({
        key: 'macd',
        label: 'MACD',
        seriesKeys: ['dif', 'dea', 'histogram'].filter((name) => leftovers.has(name)),
      });
      ['dif', 'dea', 'histogram'].forEach((name) => leftovers.delete(name));
    }

    if (leftovers.has('rsi')) {
      options.push({
        key: 'rsi',
        label: 'RSI',
        seriesKeys: ['rsi'],
      });
      leftovers.delete('rsi');
    }

    if (leftovers.has('k') || leftovers.has('d') || leftovers.has('j')) {
      options.push({
        key: 'kdj',
        label: 'KDJ',
        seriesKeys: ['k', 'd', 'j'].filter((name) => leftovers.has(name)),
      });
      ['k', 'd', 'j'].forEach((name) => leftovers.delete(name));
    }

    if (leftovers.has('bandwidth')) {
      options.push({
        key: 'bandwidth',
        label: '带宽',
        seriesKeys: ['bandwidth'],
      });
      leftovers.delete('bandwidth');
    }

    Array.from(leftovers)
      .sort((left, right) => left.localeCompare(right))
      .forEach((key) => {
        options.push({
          key: `series:${key}`,
          label: formatIndicatorLabel(key),
          seriesKeys: [key],
        });
      });

    return options.sort((left, right) => {
      const leftIndex = SECONDARY_PANEL_ORDER.indexOf(left.key);
      const rightIndex = SECONDARY_PANEL_ORDER.indexOf(right.key);
      if (leftIndex === -1 && rightIndex === -1) return left.label.localeCompare(right.label);
      if (leftIndex === -1) return 1;
      if (rightIndex === -1) return -1;
      return leftIndex - rightIndex;
    });
  }

  const symbols = computed(() => {
    const rows = availableSymbolRows.value.filter((item) => (item.inst_type || 'SPOT') === config.instType);
    return rows.map((item) => item.inst_id);
  });

  const currentStrategy = computed(() => (
    strategies.value.find((item) => item.id === config.strategy) || null
  ));

  const currentStrategyParams = computed(() => (
    (currentStrategy.value?.params || []).slice()
  ));

  const numericStrategyParams = computed(() => (
    currentStrategyParams.value.filter((item) => ['int', 'float'].includes(item.type))
  ));

  const secondaryScanParams = computed(() => (
    numericStrategyParams.value.filter((item) => item.name !== scanConfig.xParam)
  ));

  const overlayIndicatorOptions = computed(() => buildOverlayOptions());
  const secondaryIndicatorOptions = computed(() => buildSecondaryOptions());
  const showSnapshotEmpty = computed(() => Boolean(result.strategyName) && candles.value.length === 0);

  const recentTrades = computed(() => trades.value.slice(-8).reverse());

  function ensureSelectedSymbol() {
    if (symbols.value.length === 0) {
      if (!config.symbol) {
        config.symbol = 'BTC-USDT';
      }
      return;
    }
    if (!symbols.value.includes(config.symbol)) {
      config.symbol = symbols.value[0];
    }
  }

  function getDefaultParamValue(param) {
    if (param.default !== undefined) {
      return param.default;
    }
    if (param.type === 'bool') {
      return false;
    }
    if (param.type === 'int' || param.type === 'float') {
      if (param.min !== undefined) return param.min;
      return 0;
    }
    if (param.options?.length) {
      return param.options[0];
    }
    return '';
  }

  function initializeStrategyParams(incomingParams = {}) {
    Object.keys(strategyParams).forEach((key) => {
      delete strategyParams[key];
    });

    currentStrategyParams.value.forEach((param) => {
      if (incomingParams[param.name] !== undefined) {
        strategyParams[param.name] = incomingParams[param.name];
        return;
      }
      strategyParams[param.name] = getDefaultParamValue(param);
    });

    initScanParams();
  }

  function deriveScanRange(param) {
    const currentValue = safeNum(strategyParams[param.name], safeNum(param.default, 0));
    const min = param.min !== undefined ? safeNum(param.min) : Math.max(1, currentValue * 0.5);
    const max = param.max !== undefined ? safeNum(param.max) : Math.max(min + 1, currentValue * 1.5);
    const normalizedMin = Math.min(min, max);
    const normalizedMax = Math.max(min, max);
    const span = normalizedMax - normalizedMin;
    let step = param.type === 'float' ? 0.1 : 1;
    if (span > 0) {
      step = param.type === 'float'
        ? Math.max(Number((span / 6).toFixed(2)), 0.01)
        : Math.max(Math.round(span / 6), 1);
    }
    return {
      start: normalizedMin,
      end: normalizedMax,
      step,
    };
  }

  function initScanParams() {
    if (numericStrategyParams.value.length === 0) {
      scanConfig.xParam = '';
      scanConfig.yParam = '';
      return;
    }

    const xParam = numericStrategyParams.value.find((item) => item.name === scanConfig.xParam) || numericStrategyParams.value[0];
    scanConfig.xParam = xParam.name;
    const xRange = deriveScanRange(xParam);
    scanConfig.xStart = xRange.start;
    scanConfig.xEnd = xRange.end;
    scanConfig.xStep = xRange.step;

    const nextYCandidate = secondaryScanParams.value.find((item) => item.name === scanConfig.yParam) || secondaryScanParams.value[0];
    if (!nextYCandidate) {
      scanConfig.yParam = '';
      return;
    }

    scanConfig.yParam = nextYCandidate.name;
    const yRange = deriveScanRange(nextYCandidate);
    scanConfig.yStart = yRange.start;
    scanConfig.yEnd = yRange.end;
    scanConfig.yStep = yRange.step;
  }

  function buildScanValues(start, end, step, type = 'int') {
    const values = [];
    const normalizedStart = safeNum(start);
    const normalizedEnd = safeNum(end);
    const normalizedStep = Math.abs(safeNum(step));

    if (!Number.isFinite(normalizedStart) || !Number.isFinite(normalizedEnd) || !Number.isFinite(normalizedStep) || normalizedStep <= 0) {
      return values;
    }

    if (normalizedStart > normalizedEnd) {
      return values;
    }

    const maxIterations = 60;
    let current = normalizedStart;
    let iterations = 0;

    while (current <= normalizedEnd + normalizedStep / 2 && iterations < maxIterations) {
      const value = type === 'float' ? Number(current.toFixed(4)) : Math.round(current);
      values.push(value);
      current += normalizedStep;
      iterations += 1;
    }

    const deduped = [];
    const seen = new Set();
    values.forEach((value) => {
      const marker = String(value);
      if (seen.has(marker)) return;
      seen.add(marker);
      deduped.push(value);
    });
    return deduped;
  }

  function syncIndicatorSelections(preserveExisting = true) {
    const overlayKeys = overlayIndicatorOptions.value.map((item) => item.key);
    if (preserveExisting) {
      activeOverlayIndicators.value = activeOverlayIndicators.value.filter((key) => overlayKeys.includes(key));
    }
    if (activeOverlayIndicators.value.length === 0) {
      activeOverlayIndicators.value = [...overlayKeys];
    }

    const secondaryKeys = secondaryIndicatorOptions.value.map((item) => item.key);
    if (!secondaryKeys.includes(activeSecondaryIndicator.value)) {
      activeSecondaryIndicator.value = secondaryKeys[0] || '';
    }
  }

  function toggleOverlayIndicator(key) {
    if (activeOverlayIndicators.value.includes(key)) {
      activeOverlayIndicators.value = activeOverlayIndicators.value.filter((item) => item !== key);
      return;
    }
    activeOverlayIndicators.value = [...activeOverlayIndicators.value, key];
  }

  function getActiveSecondaryMeta() {
    return secondaryIndicatorOptions.value.find((item) => item.key === activeSecondaryIndicator.value) || null;
  }

  function formatMoney(value) {
    const numeric = safeNum(value);
    return new Intl.NumberFormat('zh-CN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(numeric);
  }

  function formatPercent(value) {
    return `${safeNum(value).toFixed(2)}%`;
  }

  function formatRatio(value) {
    const numeric = safeNum(value, NaN);
    if (!Number.isFinite(numeric)) return '-';
    return numeric.toFixed(2);
  }

  function formatDateTime(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString('zh-CN', {
      hour12: false,
    });
  }

  function formatTime(value) {
    const date = new Date(safeNum(value) || value);
    if (Number.isNaN(date.getTime())) return '-';
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  }

  function formatAxisTime(timestamp) {
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) return '';
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hour = String(date.getHours()).padStart(2, '0');
    const minute = String(date.getMinutes()).padStart(2, '0');
    if (config.timeframe === '1D') {
      return `${month}-${day}`;
    }
    return `${month}-${day} ${hour}:${minute}`;
  }

  function formatParams(params = {}) {
    const entries = Object.entries(params || {});
    if (entries.length === 0) return '-';
    return entries.map(([key, value]) => `${formatIndicatorLabel(key)}=${value}`).join(' · ');
  }

  function formatScanMetric(value) {
    if (scanResult.metric === 'max_drawdown' || scanResult.metric === 'total_return' || scanResult.metric === 'annual_return' || scanResult.metric === 'win_rate') {
      return formatPercent(value);
    }
    if (scanResult.metric === 'total_trades') {
      return `${safeNum(value).toFixed(0)} 笔`;
    }
    return formatRatio(value);
  }

  function formatMetadataValue(value) {
    if (value === null || value === undefined || value === '') {
      return '-';
    }
    if (typeof value === 'boolean') {
      return value ? '是' : '否';
    }
    if (typeof value === 'number') {
      if (!Number.isFinite(value)) {
        return '-';
      }
      const absolute = Math.abs(value);
      if (absolute >= 1000) return value.toFixed(2);
      if (absolute >= 1) return value.toFixed(4);
      return value.toFixed(6);
    }
    if (Array.isArray(value)) {
      return value.slice(0, 4).map((item) => formatMetadataValue(item)).join(', ');
    }
    if (typeof value === 'object') {
      try {
        return JSON.stringify(value);
      } catch (_error) {
        return '[Object]';
      }
    }
    return String(value);
  }

  function getTradeMetadataEntries(trade) {
    const rawEntries = Object.entries(trade?.metadata || {})
      .filter(([, value]) => value !== null && value !== undefined && value !== '');
    return {
      entries: rawEntries.slice(0, 6),
      truncated: rawEntries.length > 6,
    };
  }

  function buildTradeTooltipHtml(trade) {
    if (!trade) {
      return '';
    }

    const lines = [
      `<div style="font-weight:600;margin-bottom:4px">${trade.side === 'buy' ? '买入' : '卖出'}</div>`,
      `时间: ${formatTime(trade.timestamp)}`,
      `价格: ${formatPrice(trade.price)}`,
      `数量: ${safeNum(trade.quantity).toFixed(6)}`,
      `金额: ${formatMoney(trade.value)}`,
      `手续费: ${formatMoney(trade.commission)}`,
      `盈亏: ${trade.pnl === null ? '-' : formatMoney(trade.pnl)}`,
    ];

    if (trade.reason) {
      lines.push(`原因: ${trade.reason}`);
    }

    const { entries, truncated } = getTradeMetadataEntries(trade);
    entries.forEach(([key, value]) => {
      lines.push(`${formatIndicatorLabel(key)}: ${formatMetadataValue(value)}`);
    });
    if (truncated) {
      lines.push('更多指标已省略...');
    }

    return lines.join('<br/>');
  }

  function getTradeIndexByTimestamp(timestamp) {
    if (candles.value.length === 0) return -1;
    let closestIndex = 0;
    let closestDelta = Math.abs(candles.value[0].timestamp - timestamp);
    for (let index = 1; index < candles.value.length; index += 1) {
      const delta = Math.abs(candles.value[index].timestamp - timestamp);
      if (delta < closestDelta) {
        closestDelta = delta;
        closestIndex = index;
      }
    }
    return closestIndex;
  }

  function ensureChartInstance(refEl, instance) {
    if (!refEl?.value) {
      return instance;
    }
    if (instance) {
      return instance;
    }
    return echarts.init(refEl.value, 'dark', {
      renderer: 'canvas',
      useDirtyRect: true,
    });
  }

  function buildTradeScatterSeries(side) {
    const sideTrades = trades.value.filter((trade) => trade.side === side);
    if (sideTrades.length === 0) return null;
    return {
      name: side === 'buy' ? '买入信号' : '卖出信号',
      type: 'scatter',
      xAxisIndex: 0,
      yAxisIndex: 0,
      symbol: 'triangle',
      symbolSize: 13,
      symbolRotate: side === 'buy' ? 0 : 180,
      z: 9,
      tooltip: {
        trigger: 'item',
        formatter: (params) => {
          const trade = params.data?.trade;
          if (!trade) return params.seriesName;
          return buildTradeTooltipHtml(trade);
        },
      },
      itemStyle: {
        color: side === 'buy' ? PRICE_UP_COLOR : PRICE_DOWN_COLOR,
      },
      data: sideTrades
        .map((trade) => {
          const index = getTradeIndexByTimestamp(trade.timestamp);
          if (index < 0) return null;
          return {
            value: [index, trade.price],
            trade,
          };
        })
        .filter(Boolean),
    };
  }

  function buildSecondarySeries(meta) {
    if (!meta) {
      return [];
    }

    if (meta.key === 'macd') {
      const dif = indicatorMap.dif || [];
      const dea = indicatorMap.dea || [];
      const histogram = indicatorMap.histogram || [];
      return [
        {
          name: 'MACD 柱',
          type: 'bar',
          xAxisIndex: 2,
          yAxisIndex: 2,
          data: histogram.map((value) => ({
            value,
            itemStyle: {
              color: safeNum(value) >= 0 ? PRICE_UP_COLOR : PRICE_DOWN_COLOR,
            },
          })),
        },
        {
          name: 'DIF',
          type: 'line',
          xAxisIndex: 2,
          yAxisIndex: 2,
          data: dif,
          showSymbol: false,
          connectNulls: true,
          lineStyle: { width: 1.4, color: getIndicatorColor('dif') },
        },
        {
          name: 'DEA',
          type: 'line',
          xAxisIndex: 2,
          yAxisIndex: 2,
          data: dea,
          showSymbol: false,
          connectNulls: true,
          lineStyle: { width: 1.4, color: getIndicatorColor('dea') },
        },
      ];
    }

    return meta.seriesKeys.map((seriesKey, index) => ({
      name: formatIndicatorLabel(seriesKey),
      type: 'line',
      xAxisIndex: 2,
      yAxisIndex: 2,
      data: indicatorMap[seriesKey] || [],
      showSymbol: false,
      connectNulls: true,
      lineStyle: {
        width: 1.6,
        color: getIndicatorColor(seriesKey, index),
      },
      markLine: meta.key === 'rsi'
        ? {
            symbol: 'none',
            lineStyle: {
              type: 'dashed',
              color: 'rgba(201, 209, 217, 0.28)',
            },
            label: { show: false },
            data: [{ yAxis: 30 }, { yAxis: 70 }],
          }
        : meta.key === 'kdj'
          ? {
              symbol: 'none',
              lineStyle: {
                type: 'dashed',
                color: 'rgba(201, 209, 217, 0.22)',
              },
              label: { show: false },
              data: [{ yAxis: 20 }, { yAxis: 80 }],
            }
          : undefined,
    }));
  }

  return {
    symbols,
    currentStrategy,
    currentStrategyParams,
    numericStrategyParams,
    secondaryScanParams,
    overlayIndicatorOptions,
    secondaryIndicatorOptions,
    showSnapshotEmpty,
    recentTrades,
    safeNum,
    parseMaybeJSON,
    normalizeCandle,
    normalizeCandles,
    normalizeEquityCurve,
    normalizeTrades,
    normalizeIndicatorMap,
    normalizeBacktestPayload,
    formatIndicatorLabel,
    getIndicatorColor,
    isPrimaryOverlayIndicator,
    buildOverlayOptions,
    buildSecondaryOptions,
    ensureSelectedSymbol,
    getDefaultParamValue,
    initializeStrategyParams,
    deriveScanRange,
    initScanParams,
    buildScanValues,
    syncIndicatorSelections,
    toggleOverlayIndicator,
    getActiveSecondaryMeta,
    formatPrice,
    formatMoney,
    formatPercent,
    formatRatio,
    formatDateTime,
    formatTime,
    formatAxisTime,
    formatParams,
    formatScanMetric,
    formatMetadataValue,
    getTradeMetadataEntries,
    buildTradeTooltipHtml,
    getTradeIndexByTimestamp,
    ensureChartInstance,
    buildTradeScatterSeries,
    buildSecondarySeries,
  };
}
