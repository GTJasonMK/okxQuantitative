// Lightweight Charts (TradingView) 统一封装层
// 替代 ECharts 用于 K 线图 + 成交量 + 技术指标的渲染

import {
  createChart as lwcCreateChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  CrosshairMode,
  createSeriesMarkers,
} from 'lightweight-charts';
import { createSeriesMarkerAdapter } from './lwcMarkers.mjs';

// ===== Bitcoin DeFi 主题配置 =====
export const LWC_THEME = {
  layout: {
    background: { color: '#030304' },
    textColor: '#94A3B8',
    fontSize: 11,
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
    attributionLogo: false,
  },
  grid: {
    vertLines: { color: 'rgba(255, 255, 255, 0.04)' },
    horzLines: { color: 'rgba(255, 255, 255, 0.04)' },
  },
  crosshair: {
    mode: CrosshairMode.Normal,
    vertLine: {
      color: 'rgba(247, 147, 26, 0.4)',
      width: 1,
      style: 3,
      labelBackgroundColor: '#F7931A',
    },
    horzLine: {
      color: 'rgba(247, 147, 26, 0.4)',
      width: 1,
      style: 3,
      labelBackgroundColor: '#F7931A',
    },
  },
  rightPriceScale: {
    borderColor: 'rgba(255, 255, 255, 0.06)',
    scaleMargins: { top: 0.08, bottom: 0.22 },
  },
  timeScale: {
    borderColor: 'rgba(255, 255, 255, 0.06)',
    timeVisible: true,
    secondsVisible: false,
    // rightOffset 决定最新 K 线右边允许多少根空白位置
    // 设为可见区域的一半（约 50 根），这样最新 K 线可以停在画布中部
    rightOffset: 50,
    barSpacing: 8,
    minBarSpacing: 2,
    fixLeftEdge: true,
    fixRightEdge: false, // 不限制右边界，让用户自由拖拽到右侧空白
    shiftVisibleRangeOnNewBar: true,
  },
};

const mergeChartOptions = (el, overrides = {}) => {
  const {
    layout,
    grid,
    crosshair,
    rightPriceScale,
    timeScale,
    ...restOverrides
  } = overrides;

  return {
    width: el.clientWidth,
    height: el.clientHeight,
    ...restOverrides,
    layout: {
      ...LWC_THEME.layout,
      ...(layout || {}),
      background: {
        ...LWC_THEME.layout.background,
        ...(layout?.background || {}),
      },
    },
    grid: {
      ...LWC_THEME.grid,
      ...(grid || {}),
      vertLines: {
        ...LWC_THEME.grid.vertLines,
        ...(grid?.vertLines || {}),
      },
      horzLines: {
        ...LWC_THEME.grid.horzLines,
        ...(grid?.horzLines || {}),
      },
    },
    crosshair: {
      ...LWC_THEME.crosshair,
      ...(crosshair || {}),
      vertLine: {
        ...LWC_THEME.crosshair.vertLine,
        ...(crosshair?.vertLine || {}),
      },
      horzLine: {
        ...LWC_THEME.crosshair.horzLine,
        ...(crosshair?.horzLine || {}),
      },
    },
    rightPriceScale: {
      ...LWC_THEME.rightPriceScale,
      ...(rightPriceScale || {}),
      scaleMargins: {
        ...LWC_THEME.rightPriceScale.scaleMargins,
        ...(rightPriceScale?.scaleMargins || {}),
      },
    },
    timeScale: {
      ...LWC_THEME.timeScale,
      ...(timeScale || {}),
    },
  };
};

// ===== 颜色常量 =====
export const LWC_COLORS = {
  up: '#26a69a',
  down: '#ef5350',
  volume: {
    up: 'rgba(38, 166, 154, 0.35)',
    down: 'rgba(239, 83, 80, 0.35)',
  },
  accent: '#F7931A',
  accentDark: '#EA580C',
  gold: '#FFD600',
  // 指标颜色
  ma5: '#f6c85d',
  ma10: '#6be6c1',
  ma20: '#3fb1e3',
  ma60: '#a38bf8',
  ema12: '#ff6b6b',
  ema26: '#4ecdc4',
  bollUpper: '#ff9800',
  bollMiddle: '#ffab40',
  bollLower: '#ff9800',
};

// ===== 全局 ResizeObserver =====
const resizeTargets = new Map();
let resizeObserver = null;
let resizeFlushTimer = null;

const flushResizes = () => {
  resizeFlushTimer = null;
  for (const [el, chartRef] of resizeTargets.entries()) {
    const chart = chartRef.deref?.();
    if (!chart) {
      resizeTargets.delete(el);
      try { getResizeObserver().unobserve(el); } catch (_) {}
      continue;
    }
    if (el.offsetWidth > 0 || el.offsetHeight > 0) {
      chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
    }
  }
};

const getResizeObserver = () => {
  if (!resizeObserver) {
    resizeObserver = new ResizeObserver(() => {
      if (resizeFlushTimer) return;
      resizeFlushTimer = setTimeout(flushResizes, 80);
    });
  }
  return resizeObserver;
};

// ===== 工厂函数 =====

/**
 * 创建 LWC 图表实例
 * @param {HTMLElement} el 容器
 * @param {object} [overrides] 覆盖主题选项
 * @returns {{ chart, bindResize, dispose }}
 */
export const createLwcChart = (el, overrides = {}) => {
  if (!el) throw new Error('createLwcChart: 容器不能为空');

  const chart = lwcCreateChart(el, mergeChartOptions(el, overrides));

  // 自动 resize
  const weakChart = new WeakRef(chart);
  resizeTargets.set(el, weakChart);
  getResizeObserver().observe(el);

  return chart;
};

/**
 * 安全销毁 LWC 图表
 */
export const disposeLwcChart = (chart) => {
  if (!chart) return;
  // 查找并移除 resize 监听
  for (const [el, ref] of resizeTargets.entries()) {
    if (ref.deref?.() === chart) {
      resizeTargets.delete(el);
      try { getResizeObserver().unobserve(el); } catch (_) {}
      break;
    }
  }
  chart.remove();
};

// ===== Series 工厂 =====

/**
 * 添加 K 线 series
 */
export const addCandlestickSeries = (chart, overrides = {}) => (
  chart.addSeries(CandlestickSeries, {
    upColor: LWC_COLORS.up,
    downColor: LWC_COLORS.down,
    borderUpColor: LWC_COLORS.up,
    borderDownColor: LWC_COLORS.down,
    wickUpColor: LWC_COLORS.up,
    wickDownColor: LWC_COLORS.down,
    ...overrides,
  })
);

/**
 * 添加成交量 series（叠加在主图底部）
 */
export const addVolumeSeries = (chart, overrides = {}) => {
  const series = chart.addSeries(HistogramSeries, {
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume',
    ...overrides,
  });
  series.priceScale().applyOptions({
    scaleMargins: { top: 0.8, bottom: 0 },
  });
  return series;
};

/**
 * 添加指标线 series
 */
export const addLineSeries = (chart, color, overrides = {}) => (
  chart.addSeries(LineSeries, {
    color,
    lineWidth: 1,
    crosshairMarkerVisible: false,
    priceLineVisible: false,
    lastValueVisible: false,
    ...overrides,
  })
);

export const addSeriesMarkers = (series, markers = [], options) => (
  createSeriesMarkerAdapter({
    series,
    createSeriesMarkersImpl: createSeriesMarkers,
    initialMarkers: markers,
    options,
  })
);

// ===== 数据格式转换 =====

/**
 * 将后端 Candle 对象转为 LWC 格式
 * @param {object} candle { timestamp, open, high, low, close, volume }
 * @returns {{ time: number, open, high, low, close }}
 */
export const toLwcCandle = (candle) => ({
  time: Math.floor(candle.timestamp / 1000),
  open: candle.open,
  high: candle.high,
  low: candle.low,
  close: candle.close,
});

/**
 * 将后端 Candle 对象转为 LWC 成交量格式
 */
export const toLwcVolume = (candle) => ({
  time: Math.floor(candle.timestamp / 1000),
  value: candle.volume || 0,
  color: candle.close >= candle.open ? LWC_COLORS.volume.up : LWC_COLORS.volume.down,
});

/**
 * 将指标数组转为 LWC 线数据格式
 * @param {Array} candles 原始 K 线数组
 * @param {Array} values 指标值数组（与 candles 等长，null 表示无值）
 */
export const toLwcLineSeries = (candles, values) => {
  const result = [];
  for (let i = 0; i < candles.length; i++) {
    if (values[i] !== null && values[i] !== undefined && Number.isFinite(values[i])) {
      result.push({
        time: Math.floor(candles[i].timestamp / 1000),
        value: values[i],
      });
    }
  }
  return result;
};

// 导出 LWC 原生类型供直接使用
export { CandlestickSeries, HistogramSeries, LineSeries, CrosshairMode };
