import { AreaSeries, LineSeries } from 'lightweight-charts';

import { createLwcChart, disposeLwcChart } from './lwc';

const DEFAULT_TEXT_COLOR = '#94A3B8';
const DEFAULT_BORDER_COLOR = 'rgba(255, 255, 255, 0.06)';
const DEFAULT_TOOLTIP_BG = 'rgba(15, 23, 42, 0.94)';
const DEFAULT_TOOLTIP_BORDER = 'rgba(148, 163, 184, 0.25)';
const DEFAULT_TOOLTIP_TEXT = '#E2E8F0';
const DEFAULT_TIME_GAP_PX = 14;
const DEFAULT_LINE_WIDTH = 2;

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

export const toLwcTime = (value) => {
  if (typeof value === 'string') {
    return value;
  }

  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return null;
  }

  return numeric > 1e11 ? Math.floor(numeric / 1000) : Math.floor(numeric);
};

const toTooltipTimeLabel = (time, formatter) => {
  if (typeof formatter === 'function') {
    return formatter(time);
  }
  if (typeof time === 'string') {
    return time;
  }
  if (typeof time === 'number') {
    return new Date(time * 1000).toLocaleString();
  }
  if (time && typeof time === 'object') {
    const { year, month, day } = time;
    if (year && month && day) {
      return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    }
  }
  return '--';
};

const extractSeriesValue = (point) => {
  if (typeof point === 'number') {
    return point;
  }
  if (point && typeof point === 'object') {
    if (Number.isFinite(point.value)) {
      return Number(point.value);
    }
    if (Number.isFinite(point.close)) {
      return Number(point.close);
    }
  }
  return Number.NaN;
};

export const buildTimeSeriesPoints = (rows, resolver) => {
  const list = [];
  for (const row of Array.isArray(rows) ? rows : []) {
    const entry = resolver(row);
    if (!entry) {
      continue;
    }
    const time = toLwcTime(entry.time);
    const value = Number(entry.value);
    if (time === null || !Number.isFinite(value)) {
      continue;
    }
    list.push({ time, value });
  }
  return list;
};

const buildLineOptions = (config) => ({
  color: config.color,
  lineWidth: config.lineWidth || DEFAULT_LINE_WIDTH,
  lineType: config.lineType,
  lineStyle: config.lineStyle,
  priceScaleId: config.priceScaleId,
  lastValueVisible: false,
  priceLineVisible: false,
  crosshairMarkerVisible: true,
  crosshairMarkerRadius: 3,
});

const buildAreaOptions = (config) => ({
  lineColor: config.color,
  lineWidth: config.lineWidth || DEFAULT_LINE_WIDTH,
  topColor: config.topColor || `${config.color}66`,
  bottomColor: config.bottomColor || `${config.color}08`,
  priceScaleId: config.priceScaleId,
  lastValueVisible: false,
  priceLineVisible: false,
  crosshairMarkerVisible: true,
  crosshairMarkerRadius: 3,
});

export const createTimeSeriesChartManager = () => {
  let host = null;
  let chart = null;
  let tooltipEl = null;
  let crosshairHandler = null;
  let seriesEntries = [];

  const ensureTooltip = () => {
    if (!host) {
      return null;
    }
    if (!tooltipEl) {
      tooltipEl = document.createElement('div');
      tooltipEl.className = 'lwc-time-series-tooltip';
      Object.assign(tooltipEl.style, {
        position: 'absolute',
        display: 'none',
        pointerEvents: 'none',
        zIndex: '20',
        minWidth: '160px',
        maxWidth: '280px',
        padding: '10px 12px',
        borderRadius: '10px',
        border: `1px solid ${DEFAULT_TOOLTIP_BORDER}`,
        background: DEFAULT_TOOLTIP_BG,
        color: DEFAULT_TOOLTIP_TEXT,
        boxShadow: '0 12px 32px rgba(15, 23, 42, 0.28)',
        fontSize: '11px',
        lineHeight: '1.5',
        backdropFilter: 'blur(14px)',
      });
      host.appendChild(tooltipEl);
    }
    return tooltipEl;
  };

  const hideTooltip = () => {
    if (tooltipEl) {
      tooltipEl.style.display = 'none';
    }
  };

  const clearSeries = () => {
    if (!chart) {
      return;
    }
    seriesEntries.forEach(({ api }) => {
      chart.removeSeries(api);
    });
    seriesEntries = [];
    hideTooltip();
  };

  const bindTooltip = (options = {}) => {
    if (!chart) {
      return;
    }
    if (crosshairHandler) {
      chart.unsubscribeCrosshairMove(crosshairHandler);
    }

    crosshairHandler = (param) => {
      const hoverTime = param?.time ?? null;
      if (typeof options.onHoverTimeChange === 'function') {
        options.onHoverTimeChange(hoverTime);
      }

      const tooltip = ensureTooltip();
      if (!tooltip || !host || !param?.point || !param?.time) {
        hideTooltip();
        return;
      }

      const width = host.clientWidth || 0;
      const height = host.clientHeight || 0;
      const { x, y } = param.point;
      if (x < 0 || y < 0 || x > width || y > height) {
        hideTooltip();
        return;
      }

      const rows = seriesEntries
        .map(({ api, config }) => {
          const point = param.seriesData?.get(api);
          const value = extractSeriesValue(point);
          if (!Number.isFinite(value)) {
            return null;
          }
          const formatted = typeof config.tooltipValueFormatter === 'function'
            ? config.tooltipValueFormatter(value, param.time, point)
            : typeof config.valueFormatter === 'function'
              ? config.valueFormatter(value)
              : value.toFixed(2);
          return `<div style="display:flex;align-items:center;gap:8px;"><span style="width:8px;height:8px;border-radius:999px;background:${config.color};display:inline-block;"></span><span style="flex:1;min-width:0;">${config.label}</span><strong style="font-weight:600;">${formatted}</strong></div>`;
        })
        .filter(Boolean);

      if (rows.length === 0) {
        hideTooltip();
        return;
      }

      const extraRows = typeof options.extraTooltipRows === 'function'
        ? (options.extraTooltipRows(param.time) || []).filter(Boolean)
        : [];

      tooltip.innerHTML = [
        `<div style="margin-bottom:6px;font-weight:600;">${toTooltipTimeLabel(param.time, options.timeFormatter)}</div>`,
        ...rows,
        ...extraRows.map((row) => `<div style="color:#CBD5E1;">${row}</div>`),
      ].join('');
      tooltip.style.display = 'block';

      const tooltipWidth = tooltip.offsetWidth || 180;
      const tooltipHeight = tooltip.offsetHeight || 72;
      const left = x > width - tooltipWidth - DEFAULT_TIME_GAP_PX
        ? x - tooltipWidth - DEFAULT_TIME_GAP_PX
        : x + DEFAULT_TIME_GAP_PX;
      const top = clamp(y - tooltipHeight - DEFAULT_TIME_GAP_PX, 8, Math.max(height - tooltipHeight - 8, 8));

      tooltip.style.left = `${clamp(left, 8, Math.max(width - tooltipWidth - 8, 8))}px`;
      tooltip.style.top = `${top}px`;
    };

    chart.subscribeCrosshairMove(crosshairHandler);
  };

  const init = (el, options = {}) => {
    if (chart && host === el) {
      return chart;
    }

    host = el;
    if (!host) {
      return null;
    }

    if (getComputedStyle(host).position === 'static') {
      host.style.position = 'relative';
    }

    chart = createLwcChart(host, {
      layout: {
        background: { color: 'transparent' },
        textColor: DEFAULT_TEXT_COLOR,
        fontSize: 11,
        fontFamily: "'Inter', 'Segoe UI', sans-serif",
      },
      leftPriceScale: {
        visible: Boolean(options.leftPriceScale?.visible),
        borderColor: DEFAULT_BORDER_COLOR,
        scaleMargins: options.scaleMargins || { top: 0.08, bottom: 0.12 },
      },
      rightPriceScale: {
        visible: options.rightPriceScale?.visible !== false,
        borderColor: DEFAULT_BORDER_COLOR,
        scaleMargins: options.scaleMargins || { top: 0.08, bottom: 0.12 },
      },
      timeScale: {
        borderColor: DEFAULT_BORDER_COLOR,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 6,
        barSpacing: 12,
        minBarSpacing: 6,
        fixLeftEdge: false,
        fixRightEdge: false,
      },
    });

    ensureTooltip();
    return chart;
  };

  const setSeries = (configs = [], options = {}) => {
    if (!chart) {
      return;
    }

    clearSeries();
    chart.applyOptions({
      localization: {
        priceFormatter: options.priceFormatter,
        timeFormatter: options.timeFormatter,
      },
    });

    seriesEntries = configs
      .filter((config) => Array.isArray(config.data) && config.data.length > 0)
      .map((config) => {
        const api = chart.addSeries(
          config.type === 'area' ? AreaSeries : LineSeries,
          config.type === 'area' ? buildAreaOptions(config) : buildLineOptions(config),
        );
        api.setData(config.data);
        return { api, config };
      });

    bindTooltip(options);
    if (options.fitContent !== false) {
      chart.timeScale().fitContent();
    }
  };

  const resize = () => {
    if (!chart || !host) {
      return;
    }
    chart.applyOptions({ width: host.clientWidth, height: host.clientHeight });
  };

  const clear = () => {
    clearSeries();
  };

  const getTimeCoordinate = (time) => {
    if (!chart || time == null) {
      return null;
    }
    return chart.timeScale().timeToCoordinate(time);
  };

  const dispose = () => {
    if (chart && crosshairHandler) {
      chart.unsubscribeCrosshairMove(crosshairHandler);
    }
    crosshairHandler = null;
    clearSeries();
    if (tooltipEl?.parentNode) {
      tooltipEl.parentNode.removeChild(tooltipEl);
    }
    tooltipEl = null;
    if (chart) {
      disposeLwcChart(chart);
    }
    chart = null;
    host = null;
  };

  return {
    init,
    setSeries,
    clear,
    resize,
    getTimeCoordinate,
    dispose,
  };
};
