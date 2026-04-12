// 统一 ECharts 图表工厂
// 集中管理 init/dispose/resize，消除各使用处的重复代码和不一致行为

import { echarts } from './echarts';

// ===== Dark Theme 颜色常量 =====
// ECharts 不解析 CSS 变量，所有图表选项中必须使用这些常量
export const CHART_COLORS = {
  // 文字
  text: '#FFFFFF',
  textSecondary: '#94A3B8',
  textMuted: '#64748B',
  // 背景/边框
  bg: 'transparent',
  border: '#1E293B',
  borderSoft: 'rgba(255, 255, 255, 0.08)',
  splitLine: '#21262d',
  // 功能色
  up: '#26a69a',
  down: '#ef5350',
  success: '#22C55E',
  danger: '#EF4444',
  // 主题色
  accent: '#F7931A',
  accentDark: '#EA580C',
  gold: '#FFD600',
  // 图表通用
  tooltip: {
    bg: 'rgba(22, 27, 34, 0.9)',
    border: '#30363d',
    text: '#e6edf3',
  },
  axisLine: '#30363d',
  // 渐变工厂方法（每次调用返回新实例，ECharts 内部会修改对象，不可复用）
  areaUp: (opacity = 0.24) => new echarts.graphic.LinearGradient(0, 0, 0, 1, [
    { offset: 0, color: `rgba(34, 197, 94, ${opacity})` },
    { offset: 1, color: 'rgba(0, 0, 0, 0)' },
  ]),
  areaDown: (opacity = 0.24) => new echarts.graphic.LinearGradient(0, 0, 0, 1, [
    { offset: 0, color: `rgba(239, 68, 68, ${opacity})` },
    { offset: 1, color: 'rgba(0, 0, 0, 0)' },
  ]),
  areaAccent: (opacity = 0.28) => new echarts.graphic.LinearGradient(0, 0, 0, 1, [
    { offset: 0, color: `rgba(247, 147, 26, ${opacity})` },
    { offset: 1, color: 'rgba(0, 0, 0, 0)' },
  ]),
};

// ===== 全局 ResizeObserver 单例 =====
const resizeTargets = new Map(); // el → chart (WeakRef)
let resizeObserver = null;
let resizeFlushTimer = null;
const RESIZE_THROTTLE_MS = 100;

const flushResizes = () => {
  resizeFlushTimer = null;
  // 清理已回收的条目 + 批量 resize 存活图表
  const deadKeys = [];
  for (const [el, weakRef] of resizeTargets.entries()) {
    const chart = weakRef.deref();
    if (!chart || chart.isDisposed()) {
      deadKeys.push(el);
      continue;
    }
    // 只 resize 有实际尺寸的容器（display:none 时跳过）
    if (el.offsetWidth > 0 || el.offsetHeight > 0) {
      chart.resize();
    }
  }
  for (const key of deadKeys) {
    resizeTargets.delete(key);
    try { getResizeObserver().unobserve(key); } catch (_) { /* 元素可能已移除 */ }
  }
};

const scheduleResizeFlush = () => {
  if (resizeFlushTimer) return;
  resizeFlushTimer = setTimeout(flushResizes, RESIZE_THROTTLE_MS);
};

const getResizeObserver = () => {
  if (!resizeObserver) {
    resizeObserver = new ResizeObserver(scheduleResizeFlush);
  }
  return resizeObserver;
};

// ===== 图表工厂 =====

/**
 * 创建 ECharts 实例（统一配置 + 自动 resize 管理）
 *
 * @param {HTMLElement} el 容器 DOM 元素
 * @param {object} [options] 覆盖选项（传给 echarts.init 的第三个参数）
 * @param {object} [options.theme] 传 null 跳过内置 dark 主题
 * @returns {echarts.ECharts} 实例
 */
export const createChart = (el, options = {}) => {
  if (!el) throw new Error('createChart: 容器元素不能为空');

  // 如果该 el 上已有实例且未 disposed，直接复用
  const existingChart = echarts.getInstanceByDom(el);
  if (existingChart && !existingChart.isDisposed()) {
    return existingChart;
  }

  const { theme, ...initOptions } = options;
  const chart = echarts.init(el, theme !== undefined ? theme : 'dark', {
    renderer: 'canvas',
    useDirtyRect: false,
    devicePixelRatio: initOptions.devicePixelRatio ?? Math.min(window.devicePixelRatio || 1, 2),
    ...initOptions,
  });

  // 用 WeakRef 存储，避免阻止垃圾回收
  resizeTargets.set(el, new WeakRef(chart));
  getResizeObserver().observe(el);

  return chart;
};

/**
 * 安全销毁 ECharts 实例 + 清理 resize 监听
 * @param {echarts.ECharts} chart
 */
export const disposeChart = (chart) => {
  if (!chart) return;

  const el = chart.getDom?.();
  if (el) {
    resizeTargets.delete(el);
    try { getResizeObserver().unobserve(el); } catch (_) { /* 忽略 */ }
  }

  if (!chart.isDisposed()) {
    chart.dispose();
  }
};

/**
 * 确保图表在容器可见后正确渲染尺寸。
 * 用于 v-show/tab 切换后首次显示时调用。
 * @param {echarts.ECharts} chart
 */
export const ensureChartResize = (chart) => {
  if (!chart || chart.isDisposed()) return;
  const el = chart.getDom?.();
  if (el && (el.offsetWidth > 0 || el.offsetHeight > 0)) {
    chart.resize();
  }
};

/**
 * 通用 tooltip 配置
 */
export const defaultTooltip = (overrides = {}) => ({
  trigger: 'axis',
  backgroundColor: CHART_COLORS.tooltip.bg,
  borderColor: CHART_COLORS.tooltip.border,
  textStyle: { color: CHART_COLORS.tooltip.text, fontSize: 11 },
  confine: true,
  ...overrides,
});

/**
 * 通用网格配置
 */
export const defaultGrid = (overrides = {}) => ({
  top: 16,
  left: 56,
  right: 16,
  bottom: 28,
  containLabel: false,
  ...overrides,
});

/**
 * 通用 X 轴配置
 */
export const defaultCategoryXAxis = (data, overrides = {}) => ({
  type: 'category',
  data,
  axisLabel: { color: CHART_COLORS.textMuted, fontSize: 10 },
  axisLine: { lineStyle: { color: CHART_COLORS.axisLine } },
  splitLine: { show: false },
  ...overrides,
});

/**
 * 通用值 Y 轴配置
 */
export const defaultValueYAxis = (overrides = {}) => ({
  type: 'value',
  axisLabel: { color: CHART_COLORS.textMuted, fontSize: 10 },
  splitLine: { lineStyle: { color: CHART_COLORS.borderSoft } },
  ...overrides,
});

// 导出 echarts 本身以便少数需要直接使用的场景
export { echarts };
