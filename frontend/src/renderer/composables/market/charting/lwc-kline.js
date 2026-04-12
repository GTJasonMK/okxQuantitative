// MarketView K 线图 — Lightweight Charts 实现
// K 线/成交量/指标渲染 + 标注系统（趋势线/水平线/矩形/测距尺）

import {
  createLwcChart,
  disposeLwcChart,
  addCandlestickSeries,
  addVolumeSeries,
  addLineSeries,
  addSeriesMarkers,
  toLwcCandle,
  toLwcVolume,
  toLwcLineSeries,
  LWC_COLORS,
} from '@/utils/lwc';
import { toTradeMarkers } from '@/utils/lwcMarkers.mjs';
import { AnnotationManager } from './lwc-annotations';
import { resolveKlineChartModeConfig } from './lwcKlineMode.mjs';

/**
 * 创建 K 线图管理器。
 * 每个 symbol 对应一个管理器实例，管理 chart + series + annotations 生命周期。
 */
export function createKlineChartManager(options = {}) {
  let chart = null;
  let candleSeries = null;
  let markerSeries = null;
  let volumeSeries = null;
  const indicatorSeries = new Map();
  const annotations = new AnnotationManager();
  const modeConfig = resolveKlineChartModeConfig(options.mode);

  let currentCandles = [];
  let currentSymbol = '';

  /**
   * 初始化图表到指定 DOM 容器
   */
  const init = (el) => {
    if (chart) dispose();
    chart = createLwcChart(el, modeConfig.chartOverrides);
    candleSeries = addCandlestickSeries(chart);
    markerSeries = addSeriesMarkers(candleSeries, []);
    volumeSeries = addVolumeSeries(chart);
    annotations.bind(candleSeries);

    if (!modeConfig.constrainVisibleRange) {
      return chart;
    }

    // 视口约束：
    // 1. 最新 K 线至少停在画布 40% 偏右（不能被拖到最左边）
    // 2. 右侧空白不能超过可见范围的 60%（不能无限往右拖）
    let constraintPending = false;
    chart.timeScale().subscribeVisibleLogicalRangeChange((logicalRange) => {
      if (!logicalRange || currentCandles.length === 0 || constraintPending) return;
      const dataLength = currentCandles.length;
      const visibleBars = logicalRange.to - logicalRange.from;
      if (visibleBars <= 0) return;

      let needFix = false;
      let fixFrom = logicalRange.from;
      let fixTo = logicalRange.to;

      // 约束1：最新 K 线（index = dataLength-1）至少在可见范围的 40% 位置
      // 即 logicalRange.to 至少 = dataLength - 1 + visibleBars * 0.1
      //（最新 K 线在右侧 10% 留白处，不能再往右拖）
      // 但更关键的是不能往左拖太多：logicalRange.to 不能小于 visibleBars * 0.4
      const minTo = Math.max(visibleBars * 0.4, 1);
      if (logicalRange.to < minTo) {
        fixTo = minTo;
        fixFrom = fixTo - visibleBars;
        needFix = true;
      }

      // 约束2：右侧空白不能超过可见范围的 60%
      const maxRightOffset = visibleBars * 0.6;
      const currentRightOffset = logicalRange.to - (dataLength - 1);
      if (currentRightOffset > maxRightOffset) {
        fixTo = (dataLength - 1) + maxRightOffset;
        fixFrom = fixTo - visibleBars;
        needFix = true;
      }

      if (needFix) {
        constraintPending = true;
        chart.timeScale().setVisibleLogicalRange({ from: fixFrom, to: fixTo });
        // 防止约束回调递归
        requestAnimationFrame(() => { constraintPending = false; });
      }
    });

    return chart;
  };

  /**
   * 设置完整 K 线数据（切换 symbol/timeframe 时调用）
   */
  const setData = (candles, options = {}) => {
    if (!chart || !candleSeries) return;

    currentCandles = candles;
    currentSymbol = options.symbol || '';

    // K 线
    candleSeries.setData(candles.map(toLwcCandle));

    // 成交量
    volumeSeries.setData(candles.map(toLwcVolume));

    // 指标
    updateIndicators(candles, options.indicators || {});

    // 自动适配视口
    if (options.fitContent !== false) {
      chart.timeScale().fitContent();
    }
  };

  /**
   * 增量更新最后一根 K 线（实时 ticker 推送时调用）
   */
  const updateLastBar = (candle) => {
    if (!candleSeries) return;
    candleSeries.update(toLwcCandle(candle));
    volumeSeries.update(toLwcVolume(candle));
  };

  /**
   * 追加新 K 线（跨周期时调用）
   */
  const appendBar = (candle) => {
    if (!candleSeries) return;
    candleSeries.update(toLwcCandle(candle));
    volumeSeries.update(toLwcVolume(candle));
    currentCandles.push(candle);
  };

  /**
   * 更新技术指标
   */
  const updateIndicators = (candles, indicators = {}) => {
    if (!chart) return;

    const closeData = candles.map(c => c.close);
    const volumeData = candles.map(c => c.volume || 0);

    const indicatorConfigs = [
      { key: 'ma5', enabled: indicators.ma5, calc: () => calcMA(closeData, 5), color: LWC_COLORS.ma5 },
      { key: 'ma10', enabled: indicators.ma10, calc: () => calcMA(closeData, 10), color: LWC_COLORS.ma10 },
      { key: 'ma20', enabled: indicators.ma20, calc: () => calcMA(closeData, 20), color: LWC_COLORS.ma20 },
      { key: 'ma60', enabled: indicators.ma60, calc: () => calcMA(closeData, 60), color: LWC_COLORS.ma60 },
      { key: 'ema12', enabled: indicators.ema12, calc: () => calcEMA(closeData, 12), color: LWC_COLORS.ema12 },
      { key: 'ema26', enabled: indicators.ema26, calc: () => calcEMA(closeData, 26), color: LWC_COLORS.ema26 },
      { key: 'bollUpper', enabled: indicators.boll, calc: () => calcBOLL(closeData).upper, color: LWC_COLORS.bollUpper, style: 2 },
      { key: 'bollMiddle', enabled: indicators.boll, calc: () => calcBOLL(closeData).middle, color: LWC_COLORS.bollMiddle },
      { key: 'bollLower', enabled: indicators.boll, calc: () => calcBOLL(closeData).lower, color: LWC_COLORS.bollLower, style: 2 },
    ];

    // 移除不再需要的指标
    for (const [key, series] of indicatorSeries.entries()) {
      const config = indicatorConfigs.find(c => c.key === key);
      if (!config || !config.enabled) {
        chart.removeSeries(series);
        indicatorSeries.delete(key);
      }
    }

    // 添加/更新指标
    for (const config of indicatorConfigs) {
      if (!config.enabled) continue;

      let series = indicatorSeries.get(config.key);
      if (!series) {
        series = addLineSeries(chart, config.color, {
          lineStyle: config.style || 0,
        });
        indicatorSeries.set(config.key, series);
      }

      const values = config.calc();
      series.setData(toLwcLineSeries(candles, values));
    }
  };

  /**
   * 添加买卖标记（回测/成交记录）
   */
  const setMarkers = (markers) => {
    if (!markerSeries) return;
    markerSeries.setMarkers(toTradeMarkers(markers, LWC_COLORS));
  };

  /**
   * 获取 chart 实例（供外部订阅 crosshair 等事件）
   */
  const getChart = () => chart;
  const getCandleSeries = () => candleSeries;

  /**
   * resize（通常由全局 ResizeObserver 自动管理）
   */
  const resize = () => {
    if (!chart) return;
    const el = chart.chartElement?.();
    if (el && el.parentElement) {
      chart.applyOptions({
        width: el.parentElement.clientWidth,
        height: el.parentElement.clientHeight,
      });
    }
  };

  /**
   * 销毁
   */
  const dispose = () => {
    annotations.unbind();
    markerSeries?.detach();
    indicatorSeries.clear();
    candleSeries = null;
    markerSeries = null;
    volumeSeries = null;
    currentCandles = [];
    currentSymbol = '';
    if (chart) {
      disposeLwcChart(chart);
      chart = null;
    }
  };

  return {
    init,
    setData,
    updateLastBar,
    appendBar,
    updateIndicators,
    setMarkers,
    getChart,
    getCandleSeries,
    annotations,
    resize,
    dispose,
  };
}


// ===== 指标计算（滑动窗口 O(n)，从 indicators.js 提取） =====

function calcMA(data, period) {
  const result = new Array(data.length).fill(null);
  let windowSum = 0;
  for (let i = 0; i < data.length; i++) {
    windowSum += data[i];
    if (i >= period) windowSum -= data[i - period];
    if (i >= period - 1) result[i] = windowSum / period;
  }
  return result;
}

function calcEMA(data, period) {
  const result = new Array(data.length).fill(null);
  const multiplier = 2 / (period + 1);
  let ema = null;
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) continue;
    if (i === period - 1) {
      let sum = 0;
      for (let j = 0; j < period; j++) sum += data[i - j];
      ema = sum / period;
    } else {
      ema = (data[i] - ema) * multiplier + ema;
    }
    result[i] = ema;
  }
  return result;
}

let _bollCache = null;
function calcBOLL(data, period = 20, mult = 2) {
  const upper = new Array(data.length).fill(null);
  const middle = new Array(data.length).fill(null);
  const lower = new Array(data.length).fill(null);
  let wSum = 0, wSqSum = 0;
  for (let i = 0; i < data.length; i++) {
    wSum += data[i];
    wSqSum += data[i] * data[i];
    if (i >= period) {
      const d = data[i - period];
      wSum -= d;
      wSqSum -= d * d;
    }
    if (i >= period - 1) {
      const mean = wSum / period;
      const variance = Math.max(wSqSum / period - mean * mean, 0);
      const std = Math.sqrt(variance);
      middle[i] = mean;
      upper[i] = mean + mult * std;
      lower[i] = mean - mult * std;
    }
  }
  return { upper, middle, lower };
}
